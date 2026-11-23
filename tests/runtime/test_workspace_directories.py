# 文件信息：L1-01 本地受管根与目录端口的真实文件系统测试。
# 作用：验证私有路径、独占 flock、创建残留和线程生命周期边界。
# 证据边界：本机临时目录与独立 Python 进程，不证明不可信代码隔离或掉电可靠性。
"""通过公共适配器入口验证目录与进程行为，异常注入只覆盖明确的恢复窗口。"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import ManagedWorkspaceRoot
from vet3d.identity import WorkspaceId


class WorkspaceDirectoryTests(unittest.TestCase):
    """验证独占管理前提下的根布局与 UUID 目录操作。"""

    def setUp(self) -> None:
        """为每个案例建立独立临时父目录，自动清理测试现场。"""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "managed"
        self.workspace_id = WorkspaceId(uuid4())

    def _initialize(self) -> ManagedWorkspaceRoot:
        """初始化并登记同线程关闭动作，避免断言失败泄漏写入锁。

        :returns: 本测试持有的受管根。
        """
        managed = ManagedWorkspaceRoot.initialize(self.root)
        self.addCleanup(managed.close)
        return managed

    def _database_placeholder(self, managed: ManagedWorkspaceRoot) -> None:
        """只为根重开测试创建私有普通文件，不冒充 SQLite 格式验证。

        :param managed: 已初始化且持有写入锁的根对象。
        """
        descriptor = os.open(managed.database_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)

    def _workspace_path(self) -> Path:
        """从测试身份推导预期目录，仅用于观察磁盘副作用。

        :returns: 当前案例的 UUID 目录位置。
        """
        return self.root / "workspaces" / str(self.workspace_id.value)

    def _child_open(self) -> subprocess.CompletedProcess[str]:
        """启动独立解释器探测写入锁，进程退出自然释放持有资源。

        :returns: 返回码 23 表示锁冲突，0 表示成功持有直到进程退出。
        """
        script = (
            "from pathlib import Path\n"
            "import sys\n"
            "from vet3d.adapters import ManagedWorkspaceRoot\n"
            "try:\n"
            "    root = ManagedWorkspaceRoot.open(Path(sys.argv[1]))\n"
            "except BlockingIOError:\n"
            "    sys.exit(23)\n"
        )
        return subprocess.run(
            [sys.executable, "-c", script, str(self.root)], capture_output=True, text=True, timeout=10, check=False
        )

    def test_initialize_creates_private_layout_without_database(self) -> None:
        """初始化只建立私有布局与固定锁，数据库由仓储单独初始化。"""
        managed = self._initialize()
        for path in (self.root, self.root / ".control", self.root / "workspaces"):
            self.assertEqual(path.stat().st_mode & 0o7777, 0o700)
        self.assertEqual((self.root / ".control" / "writer.lock").stat().st_mode & 0o7777, 0o600)
        self.assertFalse(managed.database_path.exists())
        managed.directories.check_absent(self.workspace_id)
        managed.directories.prepare(self.workspace_id)
        managed.directories.require_existing(self.workspace_id)
        self.assertEqual(self._workspace_path().stat().st_mode & 0o7777, 0o700)

    def test_initialize_accepts_empty_private_root(self) -> None:
        """已由运维建立的空白私有根可显式初始化。"""
        self.root.mkdir(mode=0o700)
        self._initialize().validate()

    def test_initialize_rejects_nonempty_or_public_root(self) -> None:
        """非空或可被其他用户访问的根不自动接管和改权。"""
        self.root.mkdir(mode=0o700)
        marker = self.root / "foreign"
        marker.write_text("original", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            ManagedWorkspaceRoot.initialize(self.root)
        self.assertEqual(marker.read_text(encoding="utf-8"), "original")
        marker.unlink()
        self.root.chmod(0o755)
        with self.assertRaises(PermissionError):
            ManagedWorkspaceRoot.initialize(self.root)
        self.assertFalse((self.root / ".control").exists())

    def test_initialize_rejects_root_and_parent_symlinks(self) -> None:
        """受管根及父路径均不能通过符号链接重定向。"""
        target = Path(self.temporary.name) / "target"
        target.mkdir(mode=0o700)
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):
            ManagedWorkspaceRoot.initialize(self.root)
        with self.assertRaises(OSError):
            ManagedWorkspaceRoot.initialize(self.root / "child")
        self.assertEqual(list(target.iterdir()), [])

    def test_open_does_not_repair_missing_layout_or_database(self) -> None:
        """重开拒绝不存在的根和缺库现场，不自动建库或补建子目录。"""
        with self.assertRaises(FileNotFoundError):
            ManagedWorkspaceRoot.open(self.root)
        self.assertFalse(self.root.exists())
        managed = self._initialize()
        managed.close()
        with self.assertRaises(FileNotFoundError):
            ManagedWorkspaceRoot.open(self.root)
        self.assertFalse((self.root / ".control" / "registry.sqlite3").exists())
        (self.root / "workspaces").rmdir()
        with self.assertRaises(FileNotFoundError):
            ManagedWorkspaceRoot.open(self.root)
        self.assertFalse((self.root / "workspaces").exists())

    def test_same_process_and_independent_process_are_excluded_until_close(self) -> None:
        """固定 flock 排除第二实例和独立进程，退出后原锁文件仍可重开。"""
        managed = self._initialize()
        self._database_placeholder(managed)
        lock = self.root / ".control" / "writer.lock"
        original_inode = lock.stat().st_ino
        with self.assertRaises(BlockingIOError):
            ManagedWorkspaceRoot.open(self.root)
        child = self._child_open()
        self.assertEqual(child.returncode, 23, child.stderr)
        managed.close()
        child = self._child_open()
        self.assertEqual(child.returncode, 0, child.stderr)
        reopened = ManagedWorkspaceRoot.open(self.root)
        self.addCleanup(reopened.close)
        reopened.validate()
        self.assertEqual(lock.stat().st_ino, original_inode)

    def test_new_identity_rejects_all_preexisting_objects(self) -> None:
        """新身份不能接管空目录、普通文件或悬空符号链接。"""
        managed = self._initialize()
        path = self._workspace_path()
        path.mkdir(mode=0o700)
        with self.assertRaises(FileExistsError):
            managed.directories.check_absent(self.workspace_id)
        path.rmdir()
        path.write_text("foreign", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            managed.directories.check_absent(self.workspace_id)
        path.unlink()
        path.symlink_to(path.parent / "missing")
        with self.assertRaises(FileExistsError):
            managed.directories.check_absent(self.workspace_id)

    def test_pending_empty_residue_can_be_prepared_but_unknown_content_is_rejected(self) -> None:
        """原待确认意图允许空残留；未知内容拒绝接管且保留现场。"""
        managed = self._initialize()
        path = self._workspace_path()
        path.mkdir(mode=0o700)
        managed.directories.prepare(self.workspace_id)
        marker = path / "unknown.blend"
        marker.write_bytes(b"unregistered")
        with self.assertRaises(FileExistsError):
            managed.directories.prepare(self.workspace_id)
        self.assertEqual(marker.read_bytes(), b"unregistered")

    def test_registered_workspace_accepts_assets_and_does_not_recreate_missing_directory(self) -> None:
        """已登记目录可含素材，缺失时明确失败而不返回伪造空工作区。"""
        managed = self._initialize()
        managed.directories.prepare(self.workspace_id)
        marker = self._workspace_path() / "animal.blend"
        marker.write_bytes(b"asset")
        managed.directories.require_existing(self.workspace_id)
        marker.unlink()
        self._workspace_path().rmdir()
        with self.assertRaises(FileNotFoundError):
            managed.directories.require_existing(self.workspace_id)
        self.assertFalse(self._workspace_path().exists())

    def test_workspace_links_files_and_unsafe_permissions_are_rejected(self) -> None:
        """目录端口拒绝链接、普通文件及已扩大访问权限的目录。"""
        managed = self._initialize()
        path = self._workspace_path()
        path.symlink_to(Path(self.temporary.name), target_is_directory=True)
        with self.assertRaises(OSError):
            managed.directories.prepare(self.workspace_id)
        with self.assertRaises(OSError):
            managed.directories.require_existing(self.workspace_id)
        path.unlink()
        path.write_bytes(b"not a directory")
        with self.assertRaises(OSError):
            managed.directories.prepare(self.workspace_id)
        path.unlink()
        path.mkdir(mode=0o755)
        with self.assertRaises(PermissionError):
            managed.directories.require_existing(self.workspace_id)

    def test_observed_workspace_replacement_is_rejected(self) -> None:
        """同实例已观察的身份目录被重命名替换后不接受新对象。"""
        managed = self._initialize()
        managed.directories.prepare(self.workspace_id)
        path = self._workspace_path()
        path.rename(path.with_name("retained-original"))
        path.mkdir(mode=0o700)
        with self.assertRaises(OSError):
            managed.directories.require_existing(self.workspace_id)

    def test_root_and_parent_replacement_is_rejected(self) -> None:
        """保留描述符不掩盖根或父路径已改变这一可观察事实。"""
        managed = self._initialize()
        moved = self.root.with_name("old-root")
        self.root.rename(moved)
        self.root.mkdir(mode=0o700)
        with self.assertRaises(OSError):
            managed.validate()
        self.root.rmdir()
        moved.rename(self.root)
        managed.validate()
        parent = self.root.parent
        moved_parent = parent.with_name(parent.name + "-moved")
        parent.rename(moved_parent)
        try:
            parent.mkdir(mode=0o700)
            with self.assertRaises(OSError):
                managed.validate()
        finally:
            parent.rmdir()
            moved_parent.rename(parent)

    def test_lock_replacement_is_rejected_instead_of_reacquired(self) -> None:
        """锁对象替换被检测后不在新 inode 上静默恢复写入资格。"""
        managed = self._initialize()
        lock = self.root / ".control" / "writer.lock"
        lock.rename(lock.with_name("original.lock"))
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with self.assertRaises(OSError):
            managed.validate()

    def test_thread_misuse_and_post_close_access_are_rejected(self) -> None:
        """跨线程操作或关闭被拒绝，原线程关闭后端口不继续写入。"""
        managed = self._initialize()
        directories = managed.directories
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(RuntimeError):
                executor.submit(managed.validate).result(timeout=5)
            with self.assertRaises(RuntimeError):
                executor.submit(managed.close).result(timeout=5)
        managed.validate()
        managed.close()
        managed.close()
        with self.assertRaises(RuntimeError):
            directories.prepare(self.workspace_id)

    def test_directory_sync_failure_preserves_pending_residue_for_retry(self) -> None:
        """mkdir 后同步失败保留空残留，原意图下再次准备可完成。"""
        managed = self._initialize()
        with patch("vet3d.adapters.workspace_directories.os.fsync", side_effect=OSError("sync unavailable")):
            with self.assertRaises(OSError):
                managed.directories.prepare(self.workspace_id)
        self.assertTrue(self._workspace_path().is_dir())
        managed.directories.prepare(self.workspace_id)

    def test_failed_reopen_releases_lock_without_deleting_evidence(self) -> None:
        """缺库导致的重开失败释放已取得锁，但保留原布局供显式处理。"""
        managed = self._initialize()
        database_path = managed.database_path
        managed.close()
        with self.assertRaises(FileNotFoundError):
            ManagedWorkspaceRoot.open(self.root)
        descriptor = os.open(database_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        reopened = ManagedWorkspaceRoot.open(self.root)
        self.addCleanup(reopened.close)
        reopened.validate()

    def test_control_database_symlink_and_hardlink_are_rejected(self) -> None:
        """重开拒绝链接注册文件，不以同用户文件的可读性冒充受管来源。"""
        managed = self._initialize()
        database = managed.database_path
        managed.close()
        target = self.root / "private-file"
        target.touch(mode=0o600)
        database.symlink_to(target)
        with self.assertRaises(OSError):
            ManagedWorkspaceRoot.open(self.root)
        database.unlink()
        os.link(target, database)
        with self.assertRaises(PermissionError):
            ManagedWorkspaceRoot.open(self.root)

    def test_failed_initialization_preserves_partial_layout_and_releases_lock(self) -> None:
        """初始化在锁同步处失败保留现场，不能再次初始化接管非空根。"""
        original_fsync = os.fsync

        def fail_lock_sync(descriptor: int) -> None:
            """在固定锁文件已打开后注入同步失败，其余真实目录同步照常执行。

            :param descriptor: 初始化过程传入的目录或锁文件描述符。
            :raises OSError: 当前描述符指向锁文件。
            """
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("lock sync unavailable")
            original_fsync(descriptor)

        with patch("vet3d.adapters.workspace_directories.os.fsync", side_effect=fail_lock_sync):
            with self.assertRaises(OSError):
                ManagedWorkspaceRoot.initialize(self.root)
        self.assertTrue((self.root / ".control" / "writer.lock").is_file())
        with self.assertRaises(FileExistsError):
            ManagedWorkspaceRoot.initialize(self.root)
        with self.assertRaises(FileNotFoundError):
            ManagedWorkspaceRoot.open(self.root)
        database = self.root / ".control" / "registry.sqlite3"
        descriptor = os.open(database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        reopened = ManagedWorkspaceRoot.open(self.root)
        self.addCleanup(reopened.close)
