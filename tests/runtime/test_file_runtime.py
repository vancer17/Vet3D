# 文件信息：L1-02 公开文件宿主和私有暂存输入的真实生命周期验证。
# 作用：验证固定作用域、有界文件并行、控制操作独立及取消关闭时的资源归属。
# 证据边界：真实本地文件配合可控阻塞点；不证明执行沙箱、来源登记或断电持久性。
"""以公开装配调用核对文件字节与运行生命周期的交接。"""

import asyncio
from collections.abc import Callable
import hashlib
import os
from pathlib import Path
import tempfile
import threading
from typing import BinaryIO
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalArtifactFileStore, LocalWorkspaceDirectories, open_staged_input
from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileMissing, FilePresent, FileReference
from vet3d.bootstrap import (
    WorkspaceBusyError, WorkspaceClosedError, WorkspaceTimeoutError,
    initialize_workspaces, open_workspaces,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
from vet3d.workspaces import WorkspaceContractError, WorkspaceCreationError


async def _wait_event(event: threading.Event) -> None:
    """有界等待工作线程经过测试点，同时让宿主事件循环继续推进。

    :param event: 实际工作线程设置的到达通知。
    """
    async with asyncio.timeout(5):
        while not event.is_set():
            await asyncio.sleep(0.001)


def _held_store(
    entered: threading.Event, release: threading.Event, sources: list[BinaryIO], *, fail: bool = False,
) -> Callable[[LocalArtifactFileStore, ArtifactIdentity, FileReference, BinaryIO], FilePresent]:
    """在源已经打开后暂停真实保存，检验句柄归属而不替换字节处理。

    :param entered: 工作线程到达暂停点的通知。
    :param release: 允许实际操作继续的通知。
    :param sources: 保留借用对象供断言开关状态。
    :param fail: 是否在恢复后注入晚期故障。
    :returns: 与文件端口签名一致的可控保存函数。
    """
    original = LocalArtifactFileStore.store_new

    def store(
        adapter: LocalArtifactFileStore, artifact: ArtifactIdentity, reference: FileReference, source: BinaryIO,
    ) -> FilePresent:
        """持有打开的源直到测试放行，再执行实际保存或故障。

        :param adapter: 真实固定工作区适配器。
        :param artifact: 原产物归属。
        :param reference: 原预期字节引用。
        :param source: 实际线程拥有的源句柄。
        :returns: 实际保存观察。
        """
        sources.append(source)
        entered.set()
        if not release.wait(5):
            raise TimeoutError("测试未放行文件操作")
        if fail:
            raise OSError("受控晚期文件故障")
        return original(adapter, artifact, reference, source)

    return store


class FileRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """验证服务端文件调用的装配、准入和实际 I/O 生命周期。"""

    async def asyncSetUp(self) -> None:
        """创建独立真实根及已登记工作区，源目录由可信宿主预先准备。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "managed"
        self.inputs = self.base / "inputs"
        self.inputs.mkdir(mode=0o700)
        self.runtime = await initialize_workspaces(self.root)
        self.addAsyncCleanup(self.runtime.aclose)
        self.workspace_id = WorkspaceId(uuid4())
        await self.runtime.create(workspace_id=self.workspace_id, display_name="动物")
        self.files = await self.runtime.files(self.workspace_id, input_root=self.inputs, max_file_bytes=1024)
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        self.data = b"animal source\x00\xff"
        self.reference = FileReference(
            self.artifact.id, ContentFingerprint(hashlib.sha256(self.data).hexdigest(), len(self.data)),
        )
        self.source = self.inputs / "source.rgb"
        self.source.write_bytes(self.data)
        self.source.chmod(0o600)

    async def test_public_store_observe_and_reopen_do_not_register_artifact(self) -> None:
        """实际字节保存后能沿原引用重观察，同身份同内容仍拒绝重复保存。"""
        location = self.files.location_for(self.artifact)
        self.assertIsInstance(await self.files.observe(self.artifact, location), FileMissing)
        result = await self.files.store_new(self.artifact, self.reference, self.source.name)
        self.assertEqual(result.location, location)
        self.assertEqual(result.observed, self.reference.content)
        self.assertEqual(self.source.read_bytes(), self.data)
        await self.runtime.aclose()
        async with await open_workspaces(self.root) as reopened:
            files = await reopened.files(self.workspace_id, input_root=self.inputs, max_file_bytes=1024)
            self.assertEqual(await files.observe(self.artifact, location), result)
            with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(FileExistsError):
                await files.store_new(self.artifact, self.reference, self.source.name)
        with self.assertRaises(WorkspaceClosedError):
            await self.files.observe(self.artifact, location)

    async def test_binding_requires_committed_workspace(self) -> None:
        """未登记身份和只有持久意图的身份均不能绑定文件操作。"""
        pending = WorkspaceId(uuid4())
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(WorkspaceContractError):
            await self.runtime.files(pending, input_root=self.inputs, max_file_bytes=1024)
        with patch.object(LocalWorkspaceDirectories, "prepare", side_effect=OSError("准备失败")):
            with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(WorkspaceCreationError):
                await self.runtime.create(workspace_id=pending, display_name="未完成")
        record = await self.runtime.read(pending)
        assert record is not None
        self.assertIsNone(record.registered_at)
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(WorkspaceContractError):
            await self.runtime.files(pending, input_root=self.inputs, max_file_bytes=1024)

    async def test_same_input_names_keep_distinct_artifacts_and_workspaces(self) -> None:
        """同名输入在同区新产物和另一工作区均保持独立，不按名称合并或覆盖。"""
        saved = await self.files.store_new(self.artifact, self.reference, self.source.name)
        other_id = WorkspaceId(uuid4())
        await self.runtime.create(workspace_id=other_id, display_name="动物")
        other_inputs = self.base / "other-inputs"
        other_inputs.mkdir(mode=0o700)
        data = b"different original"
        other_source = other_inputs / self.source.name
        other_source.write_bytes(data)
        other_source.chmod(0o600)
        other_files = await self.runtime.files(other_id, input_root=other_inputs, max_file_bytes=1024)
        other_artifact = ArtifactIdentity(ArtifactId(uuid4()), other_id)
        other_reference = FileReference(
            other_artifact.id, ContentFingerprint(hashlib.sha256(data).hexdigest(), len(data)),
        )
        other_saved = await other_files.store_new(other_artifact, other_reference, other_source.name)
        next_artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        next_reference = FileReference(next_artifact.id, self.reference.content)
        next_saved = await self.files.store_new(next_artifact, next_reference, self.source.name)
        self.assertNotEqual(saved.location, next_saved.location)
        self.assertEqual(await self.files.observe(self.artifact, saved.location), saved)
        self.assertEqual(await other_files.observe(other_artifact, other_saved.location), other_saved)
        self.assertEqual(other_source.read_bytes(), data)
        with self.assertRaises(ArtifactContractError):
            await other_files.observe(self.artifact, saved.location)

    async def test_configuration_and_scope_rejections_have_no_file_side_effect(self) -> None:
        """重叠根、非法预算和跨区身份在接收字节前拒绝，不新增 files 目录。"""
        for root in (self.root, self.root / "inputs", self.base, self.inputs / ".." / "elsewhere"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                await self.runtime.files(self.workspace_id, input_root=root, max_file_bytes=1024)
        for budget in (0, -1, True):
            with self.subTest(budget=budget), self.assertRaises((TypeError, ValueError)):
                await self.runtime.files(self.workspace_id, input_root=self.inputs, max_file_bytes=budget)
        foreign = ArtifactIdentity(self.artifact.id, WorkspaceId(uuid4()))
        with self.assertRaises(ArtifactContractError):
            await self.files.store_new(foreign, self.reference, self.source.name)
        self.assertFalse((self.root / "workspaces" / str(self.workspace_id.value) / "files").exists())

    async def test_input_path_in_request_cannot_select_service_files(self) -> None:
        """公开命令只接受暂存根下的单文件名，不能读取父目录或绝对位置。"""
        for name in ("", ".", "..", "../managed/control.sqlite3", str(self.source), "sub/source", "sub\\source", "bad\x00"):
            with self.subTest(name=name), self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ValueError):
                await self.files.store_new(self.artifact, self.reference, name)
        self.assertIsInstance(await self.files.observe(self.artifact, self.files.location_for(self.artifact)), FileMissing)

    async def test_relative_root_is_frozen_before_working_directory_changes(self) -> None:
        """构造时固定相对根，后续 cwd 变化不能让输入根重叠检查指向另一位置。"""
        previous = Path.cwd()
        moved = self.base / "moved"
        moved.mkdir()
        try:
            os.chdir(self.base)
            async with await initialize_workspaces(Path("relative-managed")) as runtime:
                await runtime.create(workspace_id=self.workspace_id, display_name="固定根")
                os.chdir(moved)
                with self.assertRaises(ValueError):
                    await runtime.files(
                        self.workspace_id, input_root=self.base / "relative-managed" / ".control",
                        max_file_bytes=1024,
                    )
                files = await runtime.files(self.workspace_id, input_root=self.inputs, max_file_bytes=1024)
                self.assertEqual(
                    (await files.store_new(self.artifact, self.reference, self.source.name)).observed,
                    self.reference.content,
                )
        finally:
            os.chdir(previous)

    async def test_cancelled_wait_keeps_source_and_root_until_actual_completion(self) -> None:
        """取消等待后保留源及原文件名额，另一名额可用且关闭仍等待实际保存。"""
        entered, release = threading.Event(), threading.Event()
        sources: list[BinaryIO] = []
        with patch.object(LocalArtifactFileStore, "store_new", _held_store(entered, release, sources)):
            operation = asyncio.create_task(self.files.store_new(self.artifact, self.reference, self.source.name))
            try:
                await _wait_event(entered)
                operation.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await operation
                self.assertFalse(sources[0].closed)
                self.assertIsInstance(
                    await self.files.observe(self.artifact, self.files.location_for(self.artifact)), FileMissing,
                )
                closing = asyncio.create_task(self.runtime.aclose())
                await asyncio.sleep(0)
                self.assertFalse(closing.done())
                with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                    await open_workspaces(self.root)
            finally:
                release.set()
            await self.runtime.aclose()
            await closing
        self.assertTrue(sources[0].closed)
        async with await open_workspaces(self.root) as reopened:
            files = await reopened.files(self.workspace_id, input_root=self.inputs, max_file_bytes=1024)
            observed = await files.observe(self.artifact, files.location_for(self.artifact))
            self.assertEqual(observed, FilePresent(files.location_for(self.artifact), self.reference.content))

    async def test_timeout_retains_late_failure_once_and_closes_source(self) -> None:
        """超时不丢失晚期故障，原句柄在真实终结关闭且只有一次堆栈诊断。"""
        entered, release = threading.Event(), threading.Event()
        sources: list[BinaryIO] = []
        with self.assertLogs("vet3d", level="INFO") as captured:
            with patch.object(LocalArtifactFileStore, "store_new", _held_store(entered, release, sources, fail=True)):
                operation = asyncio.create_task(self.files.store_new(
                    self.artifact, self.reference, self.source.name, timeout_seconds=0.05,
                ))
                try:
                    await _wait_event(entered)
                    with self.assertRaises(WorkspaceTimeoutError):
                        await operation
                    self.assertFalse(sources[0].closed)
                    record = await self.runtime.read(self.workspace_id)
                    self.assertIsNotNone(record)
                finally:
                    release.set()
                await self.runtime.aclose()
        self.assertTrue(sources[0].closed)
        failures = [record for record in captured.records if record.levelname == "ERROR"]
        self.assertEqual(len(failures), 1)
        self.assertIsNotNone(failures[0].exc_info)
        self.assertIn(str(self.artifact.id.value), failures[0].getMessage())
        self.assertIn(str(self.workspace_id.value), failures[0].getMessage())

    async def test_long_copy_allows_another_workspace_and_metadata_to_progress(self) -> None:
        """实际读源期间另一工作区能保存及观察文件，短注册查询不被复制占用。"""
        other_id = WorkspaceId(uuid4())
        await self.runtime.create(workspace_id=other_id, display_name="并行动物")
        other_artifact = ArtifactIdentity(ArtifactId(uuid4()), other_id)
        other_reference = FileReference(other_artifact.id, self.reference.content)
        other_source = self.inputs / "other.rgb"
        other_source.write_bytes(self.data)
        other_source.chmod(0o600)
        entered, release = threading.Event(), threading.Event()
        original_read = os.pread
        source_identity = self.source.stat().st_dev, self.source.stat().st_ino

        def read_with_pause(descriptor: int, size: int, offset: int) -> bytes:
            """真实读出指定源的首块后暂停，让其余文件和控制调用竞争运行资源。

            :param descriptor: 当前真实文件描述符。
            :param size: 有界读取请求的长度。
            :param offset: 不改变流游标的读取位置。
            :returns: 该描述符的实际字节。
            """
            data = original_read(descriptor, size, offset)
            info = os.fstat(descriptor)
            if offset == 0 and (info.st_dev, info.st_ino) == source_identity:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("测试未放行实际复制")
            return data

        with patch("vet3d.adapters.artifact_files.os.pread", new=read_with_pause):
            operation = asyncio.create_task(self.files.store_new(self.artifact, self.reference, self.source.name))
            try:
                await _wait_event(entered)
                record = await self.runtime.read(self.workspace_id)
                self.assertIsNotNone(record)
                other_files = await self.runtime.files(other_id, input_root=self.inputs, max_file_bytes=1024)
                saved = await other_files.store_new(other_artifact, other_reference, other_source.name)
                self.assertEqual(await other_files.observe(other_artifact, saved.location), saved)
                self.assertFalse(operation.done())
            finally:
                release.set()
            saved_original = await operation
        self.assertEqual(await self.files.observe(self.artifact, saved_original.location), saved_original)

    async def test_saturation_retains_cancelled_slot_and_close_drains_all_files(self) -> None:
        """两个实际调用占满文件名额时拒绝排队，取消不腾位且关闭逐一排空。"""
        first_entered, second_entered = threading.Event(), threading.Event()
        first_release, second_release = threading.Event(), threading.Event()
        first_sources: list[BinaryIO] = []
        second_sources: list[BinaryIO] = []
        first_store = _held_store(first_entered, first_release, first_sources)
        second_store = _held_store(second_entered, second_release, second_sources)
        second_artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        second_reference = FileReference(second_artifact.id, self.reference.content)

        def hold_each_store(
            adapter: LocalArtifactFileStore, artifact: ArtifactIdentity, reference: FileReference, source: BinaryIO,
        ) -> FilePresent:
            """按原产物身份分别控制两份真实文件操作，不更改实际存储规则。

            :param adapter: 本次固定工作区文件适配器。
            :param artifact: 两次保存各自的原产物身份。
            :param reference: 对应的预期原件引用。
            :param source: 宿主已打开且尚需保留的源句柄。
            :returns: 放行后的实际保存观察。
            """
            operation = first_store if artifact == self.artifact else second_store
            return operation(adapter, artifact, reference, source)

        with patch.object(LocalArtifactFileStore, "store_new", new=hold_each_store):
            first = asyncio.create_task(self.files.store_new(self.artifact, self.reference, self.source.name))
            second = asyncio.create_task(self.files.store_new(second_artifact, second_reference, self.source.name))
            closing: asyncio.Task[None] | None = None
            try:
                await _wait_event(first_entered)
                await _wait_event(second_entered)
                second.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await second
                with self.assertRaises(WorkspaceBusyError):
                    await self.files.observe(self.artifact, self.files.location_for(self.artifact))
                self.assertIsNotNone(await self.runtime.read(self.workspace_id))
                closing = asyncio.create_task(self.runtime.aclose())
                await asyncio.sleep(0)
                first_release.set()
                await first
                self.assertTrue(first_sources[0].closed)
                self.assertFalse(second_sources[0].closed)
                self.assertFalse(closing.done())
                with self.assertRaises(WorkspaceClosedError):
                    await self.files.observe(self.artifact, self.files.location_for(self.artifact))
                with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                    await open_workspaces(self.root)
            finally:
                first_release.set()
                second_release.set()
            assert closing is not None
            await closing
        self.assertTrue(second_sources[0].closed)
        async with await open_workspaces(self.root) as reopened:
            files = await reopened.files(self.workspace_id, input_root=self.inputs, max_file_bytes=1024)
            for artifact in (self.artifact, second_artifact):
                location = files.location_for(artifact)
                self.assertEqual(await files.observe(artifact, location), FilePresent(location, self.reference.content))


class StagedInputTests(unittest.TestCase):
    """真实输入路径检查只支持已完成上传的私有普通文件。"""

    def setUp(self) -> None:
        """建立真实私有暂存根和普通文件。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "inputs"
        self.root.mkdir(mode=0o700)
        self.source = self.root / "source"
        self.source.write_bytes(b"original")
        self.source.chmod(0o600)

    def test_private_readonly_source_is_opened_without_modification(self) -> None:
        """支持只读完成文件，返回句柄读取原字节并由调用方关闭。"""
        self.source.chmod(0o400)
        with open_staged_input(self.root, "source") as source:
            self.assertEqual(source.read(), b"original")
            self.assertFalse(source.writable())
        self.assertTrue(source.closed)
        self.assertEqual(self.source.stat().st_mode & 0o7777, 0o400)

    def test_symlinks_hardlinks_and_fifo_are_rejected(self) -> None:
        """源链接、目录链接和管道不能成为暂存文件，不会阻塞等待管道数据。"""
        (self.root / "symlink").symlink_to(self.source)
        os.link(self.source, self.root / "hardlink")
        os.mkfifo(self.root / "fifo", mode=0o600)
        for name in ("symlink", "hardlink", "fifo"):
            with self.subTest(name=name), self.assertRaises(OSError):
                open_staged_input(self.root, name)
        (self.base / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            open_staged_input(self.base / "alias", "source")
        (self.base / "parent-alias").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(OSError):
            open_staged_input(self.base / "parent-alias" / "inputs", "source")

    def test_nonprivate_permissions_are_rejected(self) -> None:
        """根或文件权限超出本期私有暂存模型时拒绝，不自动改权修复。"""
        self.source.chmod(0o644)
        with self.assertRaises(PermissionError):
            open_staged_input(self.root, "source")
        self.source.chmod(0o600)
        self.root.chmod(0o755)
        with self.assertRaises(PermissionError):
            open_staged_input(self.root, "source")
