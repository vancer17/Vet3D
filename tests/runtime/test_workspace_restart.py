# 文件信息：L1-01 独立 Python 进程退出后的真实存储对账验证。
# 作用：在三个已提交边界强制退出子进程，再经公开 Bootstrap 入口续做原身份。
# 证据边界：证明当前本地文件系统的进程中断恢复，不证明断电、磁盘损坏或执行隔离。
"""使用真实 SQLite 和目录验证重启，不把替身调用顺序作为恢复证据。"""

import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Literal, NoReturn, cast
from uuid import uuid4

from vet3d.adapters import ManagedWorkspaceRoot, SqliteWorkspaceRepository
from vet3d.bootstrap import open_workspaces
from vet3d.identity import WorkspaceId
from vet3d.workspaces import WorkspaceCreationError


type CrashWindow = Literal["intent", "directory", "registered"]
_DISPLAY_NAME = "原始动物工作区"
_INTERRUPTED_EXIT_CODE = 73


def _interrupt_at_window(root_path: Path, workspace_id: WorkspaceId, window: CrashWindow) -> NoReturn:
    """在子进程真实提交后直接退出，不运行析构或正常关闭流程。

    :param root_path: 本例独立的受管根路径。
    :param workspace_id: 父进程预先保存的原工作区身份。
    :param window: 意图提交、目录同步或注册提交后的中断位置。
    """
    root = ManagedWorkspaceRoot.initialize(root_path)
    repository = SqliteWorkspaceRepository.initialize(root.database_path)
    repository.record_intent(workspace_id, _DISPLAY_NAME)
    if window == "intent":
        print("pending", flush=True)
        os._exit(_INTERRUPTED_EXIT_CODE)
    root.directories.prepare(workspace_id)
    if window == "directory":
        print("pending", flush=True)
        os._exit(_INTERRUPTED_EXIT_CODE)
    registered = repository.confirm_registration(workspace_id)
    assert registered.registered_at is not None
    print(registered.registered_at.isoformat(), flush=True)
    os._exit(_INTERRUPTED_EXIT_CODE)


class WorkspaceRestartTests(unittest.IsolatedAsyncioTestCase):
    """通过原身份、真实退出与重新装配验证有限恢复和保留故障现场。"""

    def setUp(self) -> None:
        """准备本例独立路径，子进程负责实际初始化存储。"""
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self._parent = Path(self._temporary.name)

    def _run_interrupted_process(self, root: Path, workspace_id: WorkspaceId, window: CrashWindow) -> str:
        """启动独立解释器并确认其在指定已提交窗口直接退出。

        :param root: 子进程初始化的受管根。
        :param workspace_id: 同时由父进程持有的原身份。
        :param window: 指定的中断窗口。
        :returns: 子进程在退出前刷新的原时间或 pending 标记。
        """
        result = subprocess.run(
            [sys.executable, str(Path(__file__).absolute()), "--interrupt", str(root), str(workspace_id.value), window],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, _INTERRUPTED_EXIT_CODE, result.stderr)
        return result.stdout.strip()

    async def test_all_committed_windows_resume_original_identity_after_process_exit(self) -> None:
        """三种中断均经新宿主对账；首次提交时间在再次重开后保持原值。"""
        windows: tuple[CrashWindow, ...] = ("intent", "directory", "registered")
        for window in windows:
            with self.subTest(window=window):
                root = self._parent / window
                workspace_id = WorkspaceId(uuid4())
                previous = await asyncio.to_thread(self._run_interrupted_process, root, workspace_id, window)
                workspace_path = root / "workspaces" / str(workspace_id.value)
                self.assertEqual(workspace_path.exists(), window != "intent")
                async with await open_workspaces(root) as runtime:
                    before = await runtime.read(workspace_id)
                    assert before is not None
                    self.assertEqual(before.id, workspace_id)
                    self.assertEqual(before.display_name, _DISPLAY_NAME)
                    if window == "registered":
                        self.assertEqual(before.registered_at, datetime.fromisoformat(previous))
                    else:
                        self.assertIsNone(before.registered_at)
                    restored = await runtime.create(workspace_id=workspace_id, display_name=_DISPLAY_NAME)
                    self.assertIsNotNone(restored.registered_at)
                    self.assertTrue(workspace_path.is_dir())
                    self.assertEqual(await runtime.read(workspace_id), restored)
                    if window == "registered":
                        self.assertEqual(restored, before)
                async with await open_workspaces(root) as reopened:
                    self.assertEqual(await reopened.read(workspace_id), restored)
                    self.assertEqual(
                        await reopened.create(workspace_id=workspace_id, display_name=_DISPLAY_NAME), restored
                    )

    async def test_registered_directory_missing_after_restart_is_not_recreated(self) -> None:
        """已提交目录丢失时保留原登记并报告访问失败，不创建空替代目录。"""
        root = self._parent / "missing-directory"
        workspace_id = WorkspaceId(uuid4())
        previous = await asyncio.to_thread(self._run_interrupted_process, root, workspace_id, "registered")
        workspace_path = root / "workspaces" / str(workspace_id.value)
        workspace_path.rmdir()
        async with await open_workspaces(root) as runtime:
            before = await runtime.read(workspace_id)
            assert before is not None
            self.assertEqual(before.registered_at, datetime.fromisoformat(previous))
            with self.assertLogs("vet3d", level="ERROR"):
                with self.assertRaises(WorkspaceCreationError) as failure:
                    await runtime.create(workspace_id=workspace_id, display_name=_DISPLAY_NAME)
            self.assertIsInstance(failure.exception.cause, FileNotFoundError)
            self.assertFalse(workspace_path.exists())
            self.assertEqual(await runtime.read(workspace_id), before)

    async def test_missing_registry_after_restart_is_not_initialized(self) -> None:
        """已有工作区目录而注册库缺失时重开失败，不建立空库猜测归属。"""
        root = self._parent / "missing-registry"
        workspace_id = WorkspaceId(uuid4())
        await asyncio.to_thread(self._run_interrupted_process, root, workspace_id, "registered")
        database_path = root / ".control" / "registry.sqlite3"
        database_path.unlink()
        with self.assertLogs("vet3d", level="ERROR"):
            with self.assertRaises(FileNotFoundError):
                await open_workspaces(root)
        self.assertFalse(database_path.exists())
        self.assertTrue((root / "workspaces" / str(workspace_id.value)).is_dir())

    async def test_pending_directory_with_unknown_content_is_not_adopted(self) -> None:
        """未提交目录中出现未知内容时拒绝接管，原意图和未知文件均保留。"""
        root = self._parent / "unknown-content"
        workspace_id = WorkspaceId(uuid4())
        await asyncio.to_thread(self._run_interrupted_process, root, workspace_id, "directory")
        unknown_file = root / "workspaces" / str(workspace_id.value) / "unrelated.blend"
        unknown_file.write_bytes(b"untrusted fixture")
        async with await open_workspaces(root) as runtime:
            before = await runtime.read(workspace_id)
            assert before is not None
            self.assertIsNone(before.registered_at)
            with self.assertLogs("vet3d", level="ERROR"):
                with self.assertRaises(WorkspaceCreationError) as failure:
                    await runtime.create(workspace_id=workspace_id, display_name=_DISPLAY_NAME)
            self.assertIsInstance(failure.exception.cause, FileExistsError)
            self.assertEqual(await runtime.read(workspace_id), before)
            self.assertEqual(unknown_file.read_bytes(), b"untrusted fixture")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--interrupt":
        if sys.argv[4] not in ("intent", "directory", "registered"):
            raise ValueError("未知中断窗口")
        _interrupt_at_window(Path(sys.argv[2]), WorkspaceId.parse(sys.argv[3]), cast(CrashWindow, sys.argv[4]))
    unittest.main()
