# 文件信息：L1-02 真实文件保存与独立 Python 进程中断的边界验证。
# 作用：凭调用方保留的身份、内容和位置重观察文件，并核对不覆盖与未知暂存保留。
# 证据边界：不建立导入账本；重开观察不是导入登记恢复，不证明断电持久性或执行隔离。
"""以实际文件和强制进程退出核对保存回执不明时的可观察事实。"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalArtifactFileStore, ManagedWorkspaceRoot, SqliteWorkspaceRepository
from vet3d.artifacts import ContentFingerprint, FileMissing, FilePresent, FileReference
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
from vet3d.workspaces import WorkspaceService


type ProcessWindow = Literal["complete", "partial", "after-rename", "observe"]
_PAYLOAD = bytes(range(256)) * 8192
_PARTIAL_EXIT = 73
_RENAMED_EXIT = 74


@contextmanager
def _opened_store(root_path: Path, workspace_id: WorkspaceId) -> Iterator[LocalArtifactFileStore]:
    """重开真实注册根并核对工作区后装配文件适配器，不扫描素材登记。

    :param root_path: 已初始化的受管根。
    :param workspace_id: 调用方保留的原工作区身份。
    :yields: 只在当前线程使用的真实文件适配器。
    """
    root = ManagedWorkspaceRoot.open(root_path)
    try:
        repository = SqliteWorkspaceRepository.open(root.database_path)
        try:
            record = repository.get(workspace_id)
            if record is None or record.registered_at is None:
                raise AssertionError("测试工作区尚未真实注册")
            yield LocalArtifactFileStore(root, workspace_id, max_file_bytes=4 * 1024 * 1024)
        finally:
            repository.close()
    finally:
        root.close()


def _run_child(
    root_path: Path, artifact: ArtifactIdentity, reference: FileReference,
    source_path: Path, window: ProcessWindow,
) -> None:
    """在独立解释器中保存或重观察，按指定真实落盘窗口直接退出。

    :param root_path: 父进程已经注册的受管根。
    :param artifact: 父进程预先保存的完整身份与归属。
    :param reference: 父进程保存的预期内容声明。
    :param source_path: 受信测试宿主提供的真实普通源文件。
    :param window: 正常保存、部分复制、重命名后同步前或只观察。
    """
    original_pread = os.pread
    original_fsync = os.fsync
    with _opened_store(root_path, artifact.workspace_id) as store:
        location = store.location_for(artifact)
        destination = root_path / "workspaces" / str(artifact.workspace_id.value) / location.relative_path.value

        def interrupt_during_copy(descriptor: int, byte_count: int, offset: int) -> bytes:
            """在首段真实复制后停止进程，保留尚未取得完整回执的暂存文件。

            :param descriptor: 适配器已经核对的源文件描述符。
            :param byte_count: 本次读取上限。
            :param offset: 从源文件起点计算的读取位置。
            :returns: 退出窗口之前的实际源字节。
            """
            if offset >= 1024 * 1024:
                os._exit(_PARTIAL_EXIT)
            return original_pread(descriptor, byte_count, offset)

        def interrupt_before_directory_sync(descriptor: int) -> None:
            """最终名字已经出现时在同步回执之前退出，不伪造保存完成。

            :param descriptor: 文件适配器当前需要同步的实际描述符。
            """
            if destination.exists():
                os._exit(_RENAMED_EXIT)
            original_fsync(descriptor)

        if window == "observe":
            observed = store.observe(artifact, location)
            if isinstance(observed, FilePresent):
                print(observed.observed.sha256, flush=True)
            elif isinstance(observed, FileMissing):
                print("missing", flush=True)
            else:
                raise AssertionError(f"新进程无法观察测试文件：{observed}")
            return
        with source_path.open("rb") as source:
            if window == "partial":
                with patch("os.pread", side_effect=interrupt_during_copy):
                    store.store_new(artifact, reference, source)
                raise AssertionError("部分复制中断窗口没有发生")
            if window == "after-rename":
                with patch("os.fsync", side_effect=interrupt_before_directory_sync):
                    store.store_new(artifact, reference, source)
                raise AssertionError("目标出现后的同步中断窗口没有发生")
            saved = store.store_new(artifact, reference, source)
            print(saved.observed.sha256, flush=True)


class ArtifactFileRestartTests(unittest.TestCase):
    """区分文件可重观察、保存回执和尚未实现的持久导入登记。"""

    def setUp(self) -> None:
        """建立真实注册根，预先保留文件关联并准备独立普通源文件。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self._parent = Path(temporary.name)
        self._root_path = self._parent / "managed"
        self._workspace_id = WorkspaceId(uuid4())
        self._artifact = ArtifactIdentity(ArtifactId(uuid4()), self._workspace_id)
        self._reference = FileReference(
            self._artifact.id, ContentFingerprint(hashlib.sha256(_PAYLOAD).hexdigest(), len(_PAYLOAD))
        )
        self._source = self._parent / "source.bin"
        self._source.write_bytes(_PAYLOAD)
        self._source.chmod(0o600)
        root = ManagedWorkspaceRoot.initialize(self._root_path)
        try:
            repository = SqliteWorkspaceRepository.initialize(root.database_path)
            try:
                service = WorkspaceService(repository=repository, directories=root.directories)
                service.create(workspace_id=self._workspace_id, display_name="原件观察测试")
                self._database = root.database_path
            finally:
                repository.close()
        finally:
            root.close()
        with _opened_store(self._root_path, self._workspace_id) as store:
            self._location = store.location_for(self._artifact)
        self._destination = (
            self._root_path / "workspaces" / str(self._workspace_id.value) / self._location.relative_path.value
        )
        self._database_before = self._database.read_bytes()

    def _child(self, window: ProcessWindow, expected_exit: int = 0) -> str:
        """运行独立解释器并核对退出窗口，返回实际输出的观察内容。

        :param window: 本次子进程行为。
        :param expected_exit: 预期的正常或强制退出码。
        :returns: 子进程标准输出原文去掉尾部换行。
        """
        result = subprocess.run(
            [
                sys.executable, str(Path(__file__).absolute()), "--child", str(self._root_path),
                str(self._workspace_id.value), str(self._artifact.id.value), self._reference.content.sha256,
                str(self._reference.content.byte_size), str(self._source), window,
            ],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, expected_exit, result.stderr)
        return result.stdout.rstrip("\n")

    def test_completed_file_is_observed_by_another_process_using_retained_reference(self) -> None:
        """保存和观察分处独立解释器，仍需调用方保留原身份及内容声明。"""
        self.assertEqual(self._child("complete"), self._reference.content.sha256)
        self.assertEqual(self._child("observe"), self._reference.content.sha256)
        with _opened_store(self._root_path, self._workspace_id) as store:
            observed = store.observe(self._artifact, self._location)
        self.assertEqual(observed, FilePresent(self._location, self._reference.content))
        self.assertEqual(self._destination.read_bytes(), _PAYLOAD)
        self.assertEqual(self._source.read_bytes(), _PAYLOAD)
        self.assertEqual(self._database.read_bytes(), self._database_before)

    def test_partial_process_exit_preserves_temporary_file_without_automatic_resume(self) -> None:
        """复制中途退出只留下暂存；重开观察不续写、不清理、不登记。"""
        self._child("partial", _PARTIAL_EXIT)
        self.assertFalse(self._destination.exists())
        temporary_files = tuple(self._destination.parent.iterdir())
        self.assertEqual(len(temporary_files), 1)
        partial = temporary_files[0]
        before = partial.read_bytes()
        self.assertGreater(len(before), 0)
        self.assertLess(len(before), len(_PAYLOAD))
        self.assertEqual(self._child("observe"), "missing")
        self.assertEqual(partial.read_bytes(), before)
        self.assertFalse(self._destination.exists())
        self.assertEqual(self._database.read_bytes(), self._database_before)

    def test_exit_after_rename_allows_observation_but_never_overwrite_or_adoption(self) -> None:
        """完整目标出现而同步回执未返回时，只能重观察，原路径再次保存明确拒绝。"""
        self._child("after-rename", _RENAMED_EXIT)
        self.assertEqual(self._destination.read_bytes(), _PAYLOAD)
        self.assertEqual(self._child("observe"), self._reference.content.sha256)
        with _opened_store(self._root_path, self._workspace_id) as store:
            with self._source.open("rb") as source:
                with self.assertRaises(FileExistsError):
                    store.store_new(self._artifact, self._reference, source)
        self.assertEqual(self._destination.read_bytes(), _PAYLOAD)
        self.assertEqual(self._database.read_bytes(), self._database_before)

    def test_unknown_temporary_content_survives_reopen_and_explicit_observation(self) -> None:
        """没有导入账本时不凭暂存命名认领文件，也不在打开工作区时扫描清理。"""
        self._destination.parent.mkdir(mode=0o700)
        unknown = self._destination.parent / ".incoming-0123456789abcdef0123456789abcdef.tmp"
        with unknown.open("xb") as stream:
            stream.write(b"unknown owner and content")
        unknown.chmod(0o600)
        self.assertEqual(self._child("observe"), "missing")
        self.assertEqual(unknown.read_bytes(), b"unknown owner and content")
        self.assertFalse(self._destination.exists())
        self.assertEqual(self._database.read_bytes(), self._database_before)


if __name__ == "__main__":
    if len(sys.argv) == 9 and sys.argv[1] == "--child":
        if sys.argv[8] not in ("complete", "partial", "after-rename", "observe"):
            raise ValueError("未知文件中断窗口")
        identity = ArtifactIdentity(ArtifactId.parse(sys.argv[4]), WorkspaceId.parse(sys.argv[3]))
        expected = FileReference(identity.id, ContentFingerprint(sys.argv[5], int(sys.argv[6])))
        _run_child(Path(sys.argv[2]), identity, expected, Path(sys.argv[7]), cast(ProcessWindow, sys.argv[8]))
    else:
        unittest.main()
