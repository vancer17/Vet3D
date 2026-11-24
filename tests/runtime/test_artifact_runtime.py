# 文件信息：L1-04 持久资产目录与真实 ArtifactAccess 的公开装配验证。
# 作用：验证单件登记、重开对账、独立文件观察及取消后的真实 I/O 生命周期。
# 证据边界：真实本地文件和 SQLite 配合故障注入，不证明断电持久性、执行隔离或动物质量。
"""沿公开宿主入口核对登记事实与实际文件状态的独立交接。"""

import asyncio
from collections.abc import Callable
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalArtifactFileStore, SqliteArtifactRepository
from vet3d.artifacts import (
    ArtifactContractError, ArtifactRegistrationConflict, ContentFingerprint,
    FileMissing, FileObservation, FilePresent, FileReference, ImportOrigin,
    LocatedArtifact, WorkspaceFileLocation, WorkspaceRelativePath, require_matching_file,
)
from vet3d.bootstrap import (
    WorkspaceBusyError, WorkspaceClosedError, WorkspaceTimeoutError,
    initialize_workspaces, open_workspaces,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId


async def _wait_event(event: threading.Event) -> None:
    """有界等待工作线程到达测试点，不阻塞服务端事件循环。

    :param event: 实际线程产生的到达通知。
    """
    async with asyncio.timeout(5):
        while not event.is_set():
            await asyncio.sleep(0.001)


def _held_observe(
    artifact_id: ArtifactId, entered: threading.Event, release: threading.Event,
    completed: threading.Event,
) -> Callable[[LocalArtifactFileStore, ArtifactIdentity, WorkspaceFileLocation], FileObservation]:
    """仅暂停指定产物的实际观察，检验取消是否错误推进后续提交。

    :param artifact_id: 需要阻塞的确切产物身份。
    :param entered: 文件线程开始执行的通知。
    :param release: 允许真实观察继续执行的通知。
    :param completed: 真实观察已经终结的通知。
    :returns: 与现有文件端口签名一致的受控观察函数。
    """
    original = LocalArtifactFileStore.observe

    def observe(
        adapter: LocalArtifactFileStore, artifact: ArtifactIdentity, location: WorkspaceFileLocation,
    ) -> FileObservation:
        """保留实际文件实现，只在指定观察开始后等待测试放行。

        :param adapter: 固定工作区的真实文件适配器。
        :param artifact: 实际操作的产物归属。
        :param location: 真实文件的规范位置。
        :returns: 放行后取得的真实文件观察。
        """
        if artifact.id != artifact_id:
            return original(adapter, artifact, location)
        entered.set()
        try:
            if not release.wait(5):
                raise TimeoutError("测试未放行资产观察")
            return original(adapter, artifact, location)
        finally:
            completed.set()

    return observe


class ArtifactRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """验证单资产持久化的消费路径及其恢复边界。"""

    async def asyncSetUp(self) -> None:
        """创建真实受管根、工作区和可信暂存文件，不预先登记资产。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "managed"
        self.inputs = self.base / "inputs"
        self.inputs.mkdir(mode=0o700)
        self.runtime = await initialize_workspaces(self.root, max_file_operations=2)
        self.addAsyncCleanup(self.runtime.aclose)
        self.workspace_id = WorkspaceId(uuid4())
        await self.runtime.create(workspace_id=self.workspace_id, display_name="动物")
        self.files = await self.runtime.files(self.workspace_id, input_root=self.inputs, max_file_bytes=4096)
        self.catalog = await self.runtime.artifacts(self.workspace_id, max_file_bytes=4096)
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        self.data = b"animal RGB source\x00\xff"
        self.reference = FileReference(
            self.artifact.id, ContentFingerprint(hashlib.sha256(self.data).hexdigest(), len(self.data)),
        )
        self.origin = ImportOrigin(self.artifact.id, "BFF 提交的原始照片")
        self.source = self.inputs / "source.rgb"
        self.source.write_bytes(self.data)
        self.source.chmod(0o600)

    async def _save(self) -> FilePresent:
        """实际接收当前输入字节，保持资产登记仍为空。

        :returns: L1-02 文件保存取得的真实观察。
        """
        return await self.files.store_new(self.artifact, self.reference, self.source.name)

    async def _reopen(self) -> None:
        """关闭旧线程和数据库，再从相同磁盘根建立全新的消费者实例。"""
        await self.runtime.aclose()
        self.runtime = await open_workspaces(self.root, max_file_operations=2)
        self.addAsyncCleanup(self.runtime.aclose)
        self.files = await self.runtime.files(self.workspace_id, input_root=self.inputs, max_file_bytes=4096)
        self.catalog = await self.runtime.artifacts(self.workspace_id, max_file_bytes=4096)

    def _installed_path(self, location: WorkspaceFileLocation) -> Path:
        """定位测试已知布局中的实际文件，专用于外部损坏故障注入。

        :param location: 由真实保存返回的规范位置。
        :returns: 当前测试根内对应的实际文件。
        """
        return self.root / "workspaces" / str(self.workspace_id.value) / location.relative_path.value

    async def test_saved_file_requires_explicit_registration_and_reopens_with_origin(self) -> None:
        """字节写出不创建登记，显式登记后内容关联与出处可独立重开读回。"""
        saved = await self._save()
        self.assertIsNone(await self.catalog.resolve(self.artifact.id))
        self.assertIsNone(await self.catalog.get_origin(self.artifact.id))
        with self.assertRaises(ArtifactContractError):
            await self.catalog.observe(saved.location)
        registered = await self.catalog.register(self.artifact, self.reference, origin=self.origin)
        self.assertEqual(registered, LocatedArtifact(self.artifact, self.reference, saved.location))
        self.assertEqual(await self.catalog.observe(registered.location), saved)
        await self._reopen()
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)
        self.assertEqual(await self.catalog.get_origin(self.artifact.id), self.origin)
        self.assertEqual(await self.catalog.observe(registered.location), saved)
        self.assertEqual(
            await self.catalog.register(self.artifact, self.reference, origin=self.origin), registered,
        )
        self.assertEqual(self.source.read_bytes(), self.data)

    async def test_registration_requires_matching_existing_file(self) -> None:
        """文件缺失或实际字节不符均不能建立持久目录行。"""
        with self.assertRaises(ArtifactContractError):
            await self.catalog.register(self.artifact, self.reference)
        await self._save()
        wrong = FileReference(self.artifact.id, ContentFingerprint("0" * 64, len(self.data)))
        with self.assertRaises(ArtifactContractError):
            await self.catalog.register(self.artifact, wrong)
        self.assertIsNone(await self.catalog.resolve(self.artifact.id))
        registered = await self.catalog.register(self.artifact, self.reference)
        self.assertIsNone(await self.catalog.get_origin(self.artifact.id))
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)

    async def test_existing_identity_rejects_changed_content_or_origin(self) -> None:
        """原身份不允许更改内容或出处，冲突不会覆盖原登记字段。"""
        await self._save()
        registered = await self.catalog.register(self.artifact, self.reference, origin=self.origin)
        wrong = FileReference(self.artifact.id, ContentFingerprint("0" * 64, len(self.data)))
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ArtifactRegistrationConflict):
            await self.catalog.register(self.artifact, wrong, origin=self.origin)
        for origin in (None, ImportOrigin(self.artifact.id, "另一个来源")):
            with self.subTest(origin=origin):
                with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ArtifactRegistrationConflict):
                    await self.catalog.register(self.artifact, self.reference, origin=origin)
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)
        self.assertEqual(await self.catalog.get_origin(self.artifact.id), self.origin)

    async def test_scope_and_location_do_not_authorize_other_assets(self) -> None:
        """知道其他工作区产物身份或伪造相对位置不能取得其资产记录或字节。"""
        saved = await self._save()
        registered = await self.catalog.register(self.artifact, self.reference)
        other_id = WorkspaceId(uuid4())
        await self.runtime.create(workspace_id=other_id, display_name="另一动物")
        other = await self.runtime.artifacts(other_id, max_file_bytes=4096)
        with self.assertRaises(ArtifactContractError):
            await other.register(self.artifact, self.reference)
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ArtifactContractError):
            await other.resolve(self.artifact.id)
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ArtifactContractError):
            await other.get_origin(self.artifact.id)
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ArtifactContractError):
            await other.observe(saved.location)
        wrong = WorkspaceFileLocation(self.artifact.id, WorkspaceRelativePath("files/not-the-registered-file"))
        with self.assertRaises(ArtifactContractError):
            await self.catalog.observe(wrong)
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)

    async def test_file_changes_and_missing_bytes_do_not_rewrite_registration(self) -> None:
        """真实观察揭示篡改或缺失，原登记及同参重放仍只表达历史提交事实。"""
        saved = await self._save()
        registered = await self.catalog.register(self.artifact, self.reference, origin=self.origin)
        installed = self._installed_path(saved.location)
        installed.chmod(0o600)
        installed.write_bytes(b"x" * len(self.data))
        installed.chmod(0o400)
        changed = await self.catalog.observe(saved.location)
        self.assertIsInstance(changed, FilePresent)
        with self.assertRaises(ArtifactContractError):
            require_matching_file(changed, reference=self.reference, artifact=self.artifact)
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)
        installed.unlink()
        self.assertEqual(await self.catalog.observe(saved.location), FileMissing(saved.location))
        self.assertEqual(
            await self.catalog.register(self.artifact, self.reference, origin=self.origin), registered,
        )
        await self._reopen()
        self.assertEqual(await self.catalog.resolve(self.artifact.id), registered)
        self.assertEqual(await self.catalog.get_origin(self.artifact.id), self.origin)

    async def test_unregistered_file_is_not_discovered_or_registered_on_reopen(self) -> None:
        """保存后中断只留下字节，重开不扫描认领，原身份可显式继续单件登记。"""
        saved = await self._save()
        await self._reopen()
        self.assertIsNone(await self.catalog.resolve(self.artifact.id))
        with self.assertRaises(ArtifactContractError):
            await self.catalog.observe(saved.location)
        registered = await self.catalog.register(self.artifact, self.reference, origin=self.origin)
        self.assertEqual(registered.location, saved.location)
        self.assertEqual(await self.catalog.observe(saved.location), saved)

    async def _stop_first_registration(self, *, timeout: bool) -> None:
        """中断首次登记的观察等待，确认真实 I/O 终结后没有后台登记阶段。

        :param timeout: 使用有界等待超时，否则主动取消调用方任务。
        """
        await self._save()
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        held = _held_observe(self.artifact.id, entered, release, completed)
        with patch.object(LocalArtifactFileStore, "observe", new=held):
            pending = asyncio.create_task(self.catalog.register(
                self.artifact, self.reference, origin=self.origin,
                timeout_seconds=0.2 if timeout else None,
            ))
            try:
                await _wait_event(entered)
                if timeout:
                    with self.assertRaises(WorkspaceTimeoutError):
                        await pending
                else:
                    pending.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await pending
                self.assertFalse(completed.is_set())
                self.assertIsNone(await self.catalog.resolve(self.artifact.id))
            finally:
                release.set()
                await _wait_event(completed)
                await self.runtime.aclose()
        await self._reopen()
        self.assertIsNone(await self.catalog.resolve(self.artifact.id))
        self.assertEqual(
            (await self.catalog.register(self.artifact, self.reference, origin=self.origin)).reference,
            self.reference,
        )

    async def test_cancelled_observation_cannot_automatically_register_afterward(self) -> None:
        """取消只结束调用方等待，仍运行的观察完成后不能自行登记。"""
        await self._stop_first_registration(timeout=False)

    async def test_timed_out_observation_cannot_automatically_register_afterward(self) -> None:
        """超时后通过原身份查询保持未登记，显式重试才执行后续提交。"""
        await self._stop_first_registration(timeout=True)

    async def test_committed_registration_can_be_reconciled_after_response_failure(self) -> None:
        """数据库已提交但响应报错时，重开后按原身份对账取得唯一原记录。"""
        saved = await self._save()
        original = SqliteArtifactRepository.register

        def commit_then_fail(
            repository: SqliteArtifactRepository, record: LocatedArtifact, *, origin: ImportOrigin | None = None,
        ) -> LocatedArtifact:
            """先执行真实短事务，再在返回边界注入一次可见故障。

            :param repository: 真实数据库生命周期内的固定工作区仓储。
            :param record: 已观察核对的唯一产物声明。
            :param origin: 当前登记的出处说明。
            :returns: 故障注入始终抛错，无伪造成功值。
            """
            original(repository, record, origin=origin)
            raise OSError("登记已提交但响应未交付")

        with patch.object(SqliteArtifactRepository, "register", new=commit_then_fail):
            with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(OSError):
                await self.catalog.register(self.artifact, self.reference, origin=self.origin)
        await self._reopen()
        expected = LocatedArtifact(self.artifact, self.reference, saved.location)
        self.assertEqual(await self.catalog.resolve(self.artifact.id), expected)
        self.assertEqual(await self.catalog.get_origin(self.artifact.id), self.origin)
        self.assertEqual(
            await self.catalog.register(self.artifact, self.reference, origin=self.origin), expected,
        )

    async def test_interrupted_final_registration_retains_control_and_root_until_commit(self) -> None:
        """最终登记已开始后取消或超时仍排空真实事务，关闭后重开取得唯一原记录。"""
        original = SqliteArtifactRepository.register
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
                reference = FileReference(artifact.id, self.reference.content)
                origin = ImportOrigin(artifact.id, "最终登记阶段的原始出处")
                saved = await self.files.store_new(artifact, reference, self.source.name)
                entered, release, completed = threading.Event(), threading.Event(), threading.Event()

                def held_register(
                    repository: SqliteArtifactRepository, record: LocatedArtifact, *,
                    origin: ImportOrigin | None = None,
                ) -> LocatedArtifact:
                    """在实际登记调用开始后暂停，放行后执行原 SQLite 事务。

                    :param repository: 控制线程内的真实资产仓储。
                    :param record: 已通过实际文件观察的原登记声明。
                    :param origin: 需要原样持久保存的出处。
                    :returns: 原 SQLite 提交成功后的登记，不返回合成结果。
                    """
                    entered.set()
                    try:
                        if not release.wait(5):
                            raise TimeoutError("测试未放行最终资产登记")
                        return original(repository, record, origin=origin)
                    finally:
                        completed.set()

                with patch.object(SqliteArtifactRepository, "register", new=held_register):
                    pending = asyncio.create_task(self.catalog.register(
                        artifact, reference, origin=origin, timeout_seconds=0.2 if timeout else None,
                    ))
                    closing: asyncio.Task[None] | None = None
                    try:
                        await _wait_event(entered)
                        if timeout:
                            with self.assertRaises(WorkspaceTimeoutError):
                                await pending
                        else:
                            pending.cancel()
                            with self.assertRaises(asyncio.CancelledError):
                                await pending
                        self.assertFalse(completed.is_set())
                        with self.assertRaises(WorkspaceBusyError):
                            await self.catalog.resolve(artifact.id)
                        closing = asyncio.create_task(self.runtime.aclose())
                        await asyncio.sleep(0)
                        self.assertFalse(closing.done())
                        with self.assertRaises(WorkspaceClosedError):
                            await self.catalog.resolve(artifact.id)
                        with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                            await open_workspaces(self.root)
                        self.assertFalse(completed.is_set())
                    finally:
                        release.set()
                        await self.runtime.aclose()
                        if closing is not None:
                            await closing
                        await asyncio.gather(pending, return_exceptions=True)
                self.assertTrue(completed.is_set())
                await self._reopen()
                expected = LocatedArtifact(artifact, reference, saved.location)
                self.assertEqual(await self.catalog.resolve(artifact.id), expected)
                self.assertEqual(await self.catalog.get_origin(artifact.id), origin)
                self.assertEqual(await self.catalog.register(artifact, reference, origin=origin), expected)
