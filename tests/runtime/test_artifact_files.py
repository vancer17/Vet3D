# 文件信息：L1-02 受管文件适配器的真实文件系统验证。
# 作用：核对作用域、字节复制、无覆盖提交、并行文件 I/O 与失败副作用。
# 证据边界：本机本地文件系统和有限故障注入，不证明恶意同 UID 隔离或断电恢复。
"""通过公开适配器与真实源句柄验证文件行为，不建立资产登记替身。"""

import errno
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from threading import Barrier
from typing import BinaryIO
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalArtifactFileStore, ManagedWorkspaceRoot, SqliteWorkspaceRepository
from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileMissing, FilePresent, FileReference,
    FileUnavailable, WorkspaceFileLocation, WorkspaceRelativePath,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
from vet3d.workspaces import WorkspaceService


class ArtifactFileTests(unittest.TestCase):
    """在已注册工作区与真实普通文件上验证本期存储边界。"""

    def setUp(self) -> None:
        """装配真实根与注册服务，临时数据在资源关闭后清理。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.path = self.base / "managed"
        self.root = ManagedWorkspaceRoot.initialize(self.path)
        self.addCleanup(self.root.close)
        repository = SqliteWorkspaceRepository.initialize(self.root.database_path)
        self.addCleanup(repository.close)
        self.workspaces = WorkspaceService(repository=repository, directories=self.root.directories)
        self.workspace_id = WorkspaceId(uuid4())
        self.workspaces.create(workspace_id=self.workspace_id, display_name="动物")
        self.store = LocalArtifactFileStore(self.root, self.workspace_id, max_file_bytes=4 * 1024 * 1024)
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)

    def _source(self, data: bytes) -> BinaryIO:
        """创建私有真实源文件，借用给适配器并保留测试侧所有权。

        :param data: 本例原件的精确字节。
        :returns: 可读写测试句柄，适配器不得关闭或修改其游标。
        """
        descriptor = os.open(self.base / ("source-" + uuid4().hex), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        source = os.fdopen(descriptor, "w+b")
        self.addCleanup(source.close)
        source.write(data)
        source.flush()
        source.seek(0)
        return source

    def _reference(self, data: bytes, artifact: ArtifactIdentity | None = None) -> FileReference:
        """从测试字节生成调用方保留的预期引用。

        :param data: 原始预期字节。
        :param artifact: 可选的其他产物归属。
        :returns: 现有唯一 FileReference 类型。
        """
        selected = self.artifact if artifact is None else artifact
        return FileReference(selected.id, ContentFingerprint(hashlib.sha256(data).hexdigest(), len(data)))

    def _files(self) -> Path:
        """仅供测试观察当前工作区的集合位置。

        :returns: 实例固定工作区的 files 目录。
        """
        return self.path / "workspaces" / str(self.workspace_id.value) / "files"

    def _target(self) -> Path:
        """仅供测试断言当前产物的实际目标。

        :returns: 固定身份目标位置。
        """
        return self._files() / str(self.artifact.id.value)

    def test_store_preserves_source_cursor_and_exact_bytes(self) -> None:
        """复制完整源而不依赖调用方游标，原件独立且最终文件只读单链接。"""
        data = b"original animal\x00RGB\xff"
        source = self._source(data)
        source.seek(5)
        result = self.store.store_new(self.artifact, self._reference(data), source)
        self.assertEqual(source.tell(), 5)
        self.assertFalse(source.closed)
        self.assertEqual(os.pread(source.fileno(), len(data), 0), data)
        self.assertEqual(self._target().read_bytes(), data)
        self.assertNotEqual(self._target().stat().st_ino, os.fstat(source.fileno()).st_ino)
        self.assertEqual(self._target().stat().st_mode & 0o7777, 0o400)
        self.assertEqual(self._target().stat().st_nlink, 1)
        self.assertEqual(result.observed, self._reference(data).content)
        self.assertEqual(self.store.observe(self.artifact, result.location), result)

    def test_zero_bytes_are_a_valid_storage_fact(self) -> None:
        """零长度字节可被保存观察，不提前冒充图片或业务质量校验。"""
        result = self.store.store_new(self.artifact, self._reference(b""), self._source(b""))
        self.assertEqual(result.observed.byte_size, 0)
        self.assertEqual(self.store.observe(self.artifact, result.location), result)

    def test_independent_workspaces_copy_in_parallel_without_sharing_cursor(self) -> None:
        """两个文件 worker 同时处理不同工作区，源游标与控制线程保持独立。"""
        other_workspace = WorkspaceId(uuid4())
        self.workspaces.create(workspace_id=other_workspace, display_name="另一动物")
        other_store = LocalArtifactFileStore(self.root, other_workspace, max_file_bytes=1024)
        other_artifact = ArtifactIdentity(ArtifactId(uuid4()), other_workspace)
        data = b"parallel original animal"
        source = self._source(data)
        source.seek(7)
        entered = Barrier(2)
        original = LocalArtifactFileStore._fingerprint

        def concurrent_fingerprint(
            store: LocalArtifactFileStore, descriptor: int, *, target: int | None = None,
            expected_bytes: int | None = None,
        ) -> ContentFingerprint:
            """要求两个实际文件调用都进入复制，再继续各自的独立描述符操作。

            :param store: 本次文件调用绑定的固定工作区适配器。
            :param descriptor: 实际源文件描述符。
            :param target: 本次独占暂存文件。
            :param expected_bytes: 调用方预期原件长度。
            :returns: 实际读取复制后取得的摘要与长度。
            """
            entered.wait(timeout=5)
            return original(store, descriptor, target=target, expected_bytes=expected_bytes)

        with ThreadPoolExecutor(max_workers=2) as executor:
            with patch.object(LocalArtifactFileStore, "_fingerprint", new=concurrent_fingerprint):
                first = executor.submit(self.store.store_new, self.artifact, self._reference(data), source)
                second = executor.submit(other_store.store_new, other_artifact, self._reference(data, other_artifact), source)
                first_result, second_result = first.result(timeout=10), second.result(timeout=10)
            self.assertEqual(executor.submit(self.store.observe, self.artifact, first_result.location).result(timeout=5), first_result)
            self.assertEqual(executor.submit(other_store.observe, other_artifact, second_result.location).result(timeout=5), second_result)
        self.assertEqual(source.tell(), 7)
        self.assertEqual(self._target().read_bytes(), data)
        self.root.validate()

    def test_parallel_same_target_has_exactly_one_no_replace_commit(self) -> None:
        """同一目标并发复制只允许一个提交成功，失败者不覆盖或移除已提交字节。"""
        entered = Barrier(2)
        original = LocalArtifactFileStore._fingerprint

        def concurrent_fingerprint(
            store: LocalArtifactFileStore, descriptor: int, *, target: int | None = None,
            expected_bytes: int | None = None,
        ) -> ContentFingerprint:
            """将两次复制停在目标存在检查之后，真实竞争无覆盖文件提交。

            :param store: 固定工作区文件适配器。
            :param descriptor: 本次源描述符。
            :param target: 本次独占暂存描述符。
            :param expected_bytes: 当前请求保留的预期字节数。
            :returns: 真实复制所得内容观察。
            """
            entered.wait(timeout=5)
            return original(store, descriptor, target=target, expected_bytes=expected_bytes)

        successes: list[FilePresent] = []
        conflicts = 0
        with ThreadPoolExecutor(max_workers=2) as executor:
            with patch.object(LocalArtifactFileStore, "_fingerprint", new=concurrent_fingerprint):
                first = executor.submit(self.store.store_new, self.artifact, self._reference(b"first"), self._source(b"first"))
                second = executor.submit(self.store.store_new, self.artifact, self._reference(b"second"), self._source(b"second"))
                for future in (first, second):
                    try:
                        successes.append(future.result(timeout=10))
                    except FileExistsError:
                        conflicts += 1
        self.assertEqual(len(successes), 1)
        self.assertEqual(conflicts, 1)
        self.assertEqual(successes[0].observed, self._reference(self._target().read_bytes()).content)
        self.assertEqual(list(self._files().iterdir()), [self._target()])

    def test_file_workers_reject_closed_root(self) -> None:
        """原根关闭后即使保留文件作用域，worker 也不能继续读写或重取所有权。"""
        source = self._source(b"x")
        self.root.close()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(RuntimeError):
                executor.submit(self.store.store_new, self.artifact, self._reference(b"x"), source).result(timeout=5)
            with self.assertRaises(RuntimeError):
                executor.submit(self.store.observe, self.artifact, self.store.location_for(self.artifact)).result(timeout=5)
        self.assertFalse(self._files().exists())

    def test_frozen_file_scope_rejects_replaced_workspace_and_lock(self) -> None:
        """工作区和锁即使换成相同权限的新对象，文件 worker 仍拒绝原作用域失效。"""
        location = self.store.location_for(self.artifact)
        workspace = self.path / "workspaces" / str(self.workspace_id.value)
        lock = self.path / ".control" / "writer.lock"
        with ThreadPoolExecutor(max_workers=1) as executor:
            for path in (workspace, lock):
                with self.subTest(path=path.name):
                    previous = path.with_name(path.name + "-original")
                    path.rename(previous)
                    try:
                        if path == workspace:
                            path.mkdir(mode=0o700)
                        else:
                            path.touch(mode=0o600)
                        result = executor.submit(self.store.observe, self.artifact, location).result(timeout=5)
                        self.assertIsInstance(result, FileUnavailable)
                    finally:
                        if path.is_dir():
                            path.rmdir()
                        else:
                            path.unlink()
                        previous.rename(path)

    def test_file_scope_checks_root_again_after_reading(self) -> None:
        """读取期间根被替换时不得返回可信文件观察，已写出的原文件保留在原根。"""
        stored = self.store.store_new(self.artifact, self._reference(b"animal"), self._source(b"animal"))
        previous = self.path.with_name("original-managed")
        original = LocalArtifactFileStore._fingerprint

        def replace_root_after_read(
            store: LocalArtifactFileStore, descriptor: int, *, target: int | None = None,
            expected_bytes: int | None = None,
        ) -> ContentFingerprint:
            """在真实读取完成后替换根名称，检验结束边界的路径与身份复核。

            :param store: 固定工作区文件适配器。
            :param descriptor: 实际打开的目标文件。
            :param target: 当前观察没有写入目标。
            :param expected_bytes: 当前观察没有预期内容长度。
            :returns: 原文件实际字节观察。
            """
            observed = original(store, descriptor, target=target, expected_bytes=expected_bytes)
            self.path.rename(previous)
            self.path.mkdir(mode=0o700)
            return observed

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                with patch.object(LocalArtifactFileStore, "_fingerprint", new=replace_root_after_read):
                    observed = executor.submit(self.store.observe, self.artifact, stored.location).result(timeout=5)
            self.assertIsInstance(observed, FileUnavailable)
        finally:
            if previous.exists():
                self.path.rmdir()
                previous.rename(self.path)
        self.assertEqual(self._target().read_bytes(), b"animal")

    def test_scope_and_noncanonical_location_fail_before_io(self) -> None:
        """跨区、错引用和替代路径属于契约错误，不创建文件集合。"""
        foreign = ArtifactIdentity(ArtifactId(uuid4()), WorkspaceId(uuid4()))
        with self.assertRaises(ArtifactContractError):
            self.store.store_new(foreign, self._reference(b"x", foreign), self._source(b"x"))
        with self.assertRaises(ArtifactContractError):
            self.store.store_new(self.artifact, self._reference(b"x", foreign), self._source(b"x"))
        alternative = WorkspaceFileLocation(self.artifact.id, WorkspaceRelativePath("files/another-file"))
        with self.assertRaises(ArtifactContractError):
            self.store.observe(self.artifact, alternative)
        self.assertFalse(self._files().exists())

    def test_missing_file_is_distinct_from_missing_workspace(self) -> None:
        """首次读取不建立 files；已登记工作区消失时报告不可用。"""
        location = self.store.location_for(self.artifact)
        self.assertEqual(self.store.observe(self.artifact, location), FileMissing(location))
        self.assertFalse(self._files().exists())
        self._files().parent.rmdir()
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)

    def test_existing_target_is_never_reused_or_overwritten(self) -> None:
        """相同身份相同内容再次保存仍拒绝，字节存在不是登记幂等证明。"""
        data = b"retained"
        self.store.store_new(self.artifact, self._reference(data), self._source(data))
        inode = self._target().stat().st_ino
        with self.assertRaises(FileExistsError):
            self.store.store_new(self.artifact, self._reference(data), self._source(data))
        self.assertEqual(self._target().read_bytes(), data)
        self.assertEqual(self._target().stat().st_ino, inode)

    def test_actual_no_replace_commit_rejects_a_late_target(self) -> None:
        """预检后才出现的目标仍被真实 renameat2 拒绝，不能被竞态覆盖。"""
        original_sync = os.fsync

        def introduce_target(descriptor: int) -> None:
            """在临时文件同步后、实际提交前建立冲突目标。

            :param descriptor: 当前同步的真实文件或目录。
            """
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                self._target().write_bytes(b"foreign")
                self._target().chmod(0o400)
            original_sync(descriptor)

        with patch("vet3d.adapters.artifact_files.os.fsync", side_effect=introduce_target):
            with self.assertRaises(FileExistsError):
                self.store.store_new(self.artifact, self._reference(b"new"), self._source(b"new"))
        self.assertEqual(self._target().read_bytes(), b"foreign")
        self.assertEqual(list(self._files().glob(".incoming-*")), [])

    def test_actual_no_replace_commit_rejects_late_dangling_link(self) -> None:
        """最终项为悬空链接也属于已有目标，真实提交不能覆盖它。"""
        original_sync = os.fsync

        def introduce_link(descriptor: int) -> None:
            """在目标存在性预检之后插入悬空符号链接。

            :param descriptor: 当前同步的真实文件或目录。
            """
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                self._target().symlink_to("missing")
            original_sync(descriptor)

        with patch("vet3d.adapters.artifact_files.os.fsync", side_effect=introduce_link):
            with self.assertRaises(FileExistsError):
                self.store.store_new(self.artifact, self._reference(b"new"), self._source(b"new"))
        self.assertTrue(self._target().is_symlink())
        self.assertEqual(os.readlink(self._target()), "missing")

    def test_unavailable_primitive_has_no_covering_fallback(self) -> None:
        """底层无覆盖原语不可用时失败，不采用可能覆盖的替代路径。"""
        with patch("vet3d.adapters.file_commit.ctypes.CDLL", side_effect=OSError(errno.ENOSYS, "unavailable")):
            with self.assertRaises(OSError):
                self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))
        self.assertFalse(self._target().exists())
        self.assertEqual(list(self._files().glob(".incoming-*")), [])

    def test_wrong_digest_and_source_length_do_not_leave_a_final_file(self) -> None:
        """源长度和实际摘要都必须匹配；失败时仅清理本次暂存。"""
        with self.assertRaises(ArtifactContractError):
            self.store.store_new(self.artifact, self._reference(b"longer"), self._source(b"x"))
        self.assertFalse(self._files().exists())
        with self.assertRaises(ArtifactContractError):
            self.store.store_new(self.artifact, self._reference(b"expected"), self._source(b"different"[:8]))
        self.assertFalse(self._target().exists())
        self.assertEqual(list(self._files().glob(".incoming-*")), [])

    def test_source_growth_stops_after_one_extra_byte(self) -> None:
        """源增长超过预期时最多额外读取一字节，不持续复制到部署上限。"""
        source = self._source(b"x")
        original_read = os.pread
        requested: list[int] = []

        def grow_before_read(descriptor: int, size: int, offset: int) -> bytes:
            """在源长度预检之后增加内容，并记录实际读取请求。

            :param descriptor: 被借用的真实源描述符。
            :param size: 复制请求的最大读取长度。
            :param offset: 绝对源位置。
            :returns: 实际读取结果。
            """
            requested.append(size)
            if offset == 0:
                os.pwrite(source.fileno(), b"growth" * 1024, 1)
            return original_read(descriptor, size, offset)

        with patch("vet3d.adapters.artifact_files.os.pread", side_effect=grow_before_read):
            with self.assertRaises(ArtifactContractError):
                self.store.store_new(self.artifact, self._reference(b"x"), source)
        self.assertEqual(requested, [2])
        self.assertFalse(self._target().exists())

    def test_same_length_source_mutation_is_rejected(self) -> None:
        """即使复制摘要恰好匹配，读取期间源元数据变化仍拒绝提交。"""
        source = self._source(b"original")
        original_read = os.pread

        def mutate_after_read(descriptor: int, size: int, offset: int) -> bytes:
            """取得原字节后明确改变源时间，模拟同长度修改窗口。

            :param descriptor: 当前读取描述符。
            :param size: 最大读取长度。
            :param offset: 绝对文件位置。
            :returns: 改动前已取得的字节。
            """
            data = original_read(descriptor, size, offset)
            if offset == 0:
                info = os.fstat(source.fileno())
                os.pwrite(source.fileno(), b"modified", 0)
                os.utime(source.fileno(), ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000))
            return data

        with patch("vet3d.adapters.artifact_files.os.pread", side_effect=mutate_after_read):
            with self.assertRaises(OSError):
                self.store.store_new(self.artifact, self._reference(b"original"), source)
        self.assertFalse(self._target().exists())

    def test_byte_budget_is_enforced_for_source_and_observation(self) -> None:
        """源和观察都遵守实际字节上限，超限观察不是文件缺失。"""
        limited = LocalArtifactFileStore(self.root, self.workspace_id, max_file_bytes=1)
        with self.assertRaises(OSError):
            limited.store_new(self.artifact, self._reference(b"large"), self._source(b"large"))
        stored = self.store.store_new(self.artifact, self._reference(b"large"), self._source(b"large"))
        self.assertIsInstance(limited.observe(self.artifact, stored.location), FileUnavailable)

    def test_unsafe_source_permissions_hardlinks_and_special_files_are_rejected(self) -> None:
        """源句柄须为私有单链接普通文件，类型检查发生在实际读取之前。"""
        source = self._source(b"x")
        os.fchmod(source.fileno(), 0o644)
        with self.assertRaises(PermissionError):
            self.store.store_new(self.artifact, self._reference(b"x"), source)
        os.fchmod(source.fileno(), 0o600)
        os.link(f"/proc/self/fd/{source.fileno()}", self.base / "source-hardlink", follow_symlinks=True)
        with self.assertRaises(PermissionError):
            self.store.store_new(self.artifact, self._reference(b"x"), source)
        with open("/dev/null", "rb") as special:
            with self.assertRaises(PermissionError):
                self.store.store_new(self.artifact, self._reference(b""), special)
        self.assertFalse(self._files().exists())

    def test_links_fifo_and_wrong_permissions_are_unavailable(self) -> None:
        """最终位置的链接、FIFO 和可写文件不被当作安全存在或缺失。"""
        self._files().mkdir(mode=0o700)
        location = self.store.location_for(self.artifact)
        self._target().symlink_to("missing")
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)
        self._target().unlink()
        os.mkfifo(self._target(), mode=0o600)
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)
        self._target().unlink()
        self._target().write_bytes(b"x")
        self._target().chmod(0o600)
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)
        self._target().chmod(0o400)
        os.link(self._target(), self._files() / "alias")
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)

    def test_files_collection_symlink_is_not_followed(self) -> None:
        """集合目录被替换为外部链接时不读取或写入链接目标。"""
        outside = self.base / "outside"
        outside.mkdir(mode=0o700)
        self._files().symlink_to(outside, target_is_directory=True)
        location = self.store.location_for(self.artifact)
        self.assertIsInstance(self.store.observe(self.artifact, location), FileUnavailable)
        with self.assertRaises(OSError):
            self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))
        self.assertEqual(list(outside.iterdir()), [])

    def test_changed_content_is_reported_as_actual_present(self) -> None:
        """稳定但不同的最终字节仍产生实际观察，预期匹配由上层守卫判断。"""
        stored = self.store.store_new(self.artifact, self._reference(b"old"), self._source(b"old"))
        self._target().chmod(0o600)
        self._target().write_bytes(b"new bytes")
        self._target().chmod(0o400)
        observation = self.store.observe(self.artifact, stored.location)
        self.assertIsInstance(observation, FilePresent)
        assert isinstance(observation, FilePresent)
        self.assertEqual(observation.observed, self._reference(b"new bytes").content)
        self.assertNotEqual(observation.observed, stored.observed)

    def test_replaced_file_during_observation_is_unavailable(self) -> None:
        """实际读取句柄仍有效时，位置替换也必须被核对并拒绝报告存在。"""
        stored = self.store.store_new(self.artifact, self._reference(b"old"), self._source(b"old"))
        original_read = os.pread

        def replace_after_read(descriptor: int, size: int, offset: int) -> bytes:
            """在读取原 inode 后将同名位置指向另一个普通文件。

            :param descriptor: 原最终文件句柄。
            :param size: 最大读取长度。
            :param offset: 当前绝对位置。
            :returns: 从原句柄取得的字节。
            """
            data = original_read(descriptor, size, offset)
            if offset == 0:
                self._target().rename(self._files() / "retained-original")
                self._target().write_bytes(b"replacement")
                self._target().chmod(0o400)
            return data

        with patch("vet3d.adapters.artifact_files.os.pread", side_effect=replace_after_read):
            self.assertIsInstance(self.store.observe(self.artifact, stored.location), FileUnavailable)

    def test_ordinary_failure_cleans_only_own_temporary(self) -> None:
        """普通复制失败只清理本次暂存，不扫描或删除未知历史残留。"""
        self._files().mkdir(mode=0o700)
        unknown = self._files() / ".incoming-unknown.tmp"
        unknown.write_bytes(b"preserve")
        with patch("vet3d.adapters.artifact_files.os.pread", side_effect=OSError("read failed")):
            with self.assertRaises(OSError):
                self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))
        self.assertEqual(unknown.read_bytes(), b"preserve")
        self.assertEqual(set(self._files().iterdir()), {unknown})

    def test_post_commit_sync_failure_keeps_final_and_rejects_resubmit(self) -> None:
        """重命名后的目录同步失败不删除最终文件，重提也不覆盖可能已提交字节。"""
        original_sync = os.fsync

        def fail_after_commit(descriptor: int) -> None:
            """仅在最终目标已经出现后的目录同步阶段报错。

            :param descriptor: 本次同步描述符。
            :raises OSError: 已重命名且正在同步目录。
            """
            if self._target().exists() and stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("directory sync failed after rename")
            original_sync(descriptor)

        with patch("vet3d.adapters.artifact_files.os.fsync", side_effect=fail_after_commit):
            with self.assertRaises(OSError):
                self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))
        self.assertEqual(self._target().read_bytes(), b"x")
        self.assertIsInstance(self.store.observe(self.artifact, self.store.location_for(self.artifact)), FilePresent)
        with self.assertRaises(FileExistsError):
            self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))

    def test_cleanup_preserves_replaced_temporary_name(self) -> None:
        """失败清理发现暂存名称指向陌生 inode 时保留它并报告清理未确认。"""
        replaced: list[Path] = []

        def replace_temporary(descriptor: int, size: int, offset: int) -> bytes:
            """在复制失败前替换本次暂存名称，检查定点清理的所有权门槛。

            :param descriptor: 原源文件描述符。
            :param size: 本次拟读取长度。
            :param offset: 原源文件绝对位置。
            :raises OSError: 已完成受控替换后报告复制失败。
            """
            temporary = next(self._files().glob(".incoming-*"))
            temporary.rename(self._files() / "retained-owned-temporary")
            temporary.write_bytes(b"foreign replacement")
            replaced.append(temporary)
            raise OSError("read failed after temporary replacement")

        with patch("vet3d.adapters.artifact_files.os.pread", side_effect=replace_temporary):
            with self.assertRaises(OSError) as failure:
                self.store.store_new(self.artifact, self._reference(b"x"), self._source(b"x"))
        self.assertEqual(replaced[0].read_bytes(), b"foreign replacement")
        self.assertFalse(self._target().exists())
        self.assertTrue(any("暂存清理未确认" in note for note in failure.exception.__notes__))

    def test_short_writes_are_completed_before_commit(self) -> None:
        """系统短写不丢失块内剩余字节，最终指纹仍对应完整原件。"""
        original_write = os.write

        def short_write(descriptor: int, data: bytes) -> int:
            """限制每次实际写入长度以覆盖合法短写行为。

            :param descriptor: 本次暂存描述符。
            :param data: 尚待写入的块。
            :returns: 本次实际写入的字节数。
            """
            return original_write(descriptor, data[:3])

        data = b"a complete animal original"
        with patch("vet3d.adapters.artifact_files.os.write", side_effect=short_write):
            result = self.store.store_new(self.artifact, self._reference(data), self._source(data))
        self.assertEqual(self._target().read_bytes(), data)
        self.assertEqual(result.observed, self._reference(data).content)
