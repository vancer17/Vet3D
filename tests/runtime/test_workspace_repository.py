# 文件信息：L1-01 SQLite 注册仓储的真实文件与事务验证。
# 作用：覆盖幂等登记、提交恢复、结构拒绝、故障传播及所属线程约束。
# 证据边界：使用真实本地 SQLite，不证明断电恢复、网络盘或执行沙箱隔离。
"""通过公共仓储入口验证持久化边界，不以替身代替 SQLite 提交证据。"""

import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from vet3d.adapters import SqliteWorkspaceRepository, WorkspaceStorageError
from vet3d.identity import TaskId, WorkspaceId
from vet3d.workspaces import WorkspaceConflict, WorkspaceContractError, WorkspaceRepository


def _execute(database_path: Path, statement: str, parameters: tuple[str, ...] = ()) -> None:
    """通过独立 SQLite 连接制造已声明的外部故障夹具。

    :param database_path: 真实临时数据库路径。
    :param statement: 测试自有 SQL，不接受产品业务输入。
    :param parameters: SQL 的绑定值。
    """
    connection = sqlite3.connect(database_path.as_uri() + "?mode=rw", uri=True, autocommit=True)
    try:
        connection.execute(statement, parameters)
    finally:
        connection.close()


class WorkspaceRepositoryTests(unittest.TestCase):
    """验证注册事实的持久提交及失败时不能返回伪成功。"""

    def setUp(self) -> None:
        """为每例创建独立受信目录及真实注册库。"""
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self._directory = Path(self._temporary.name)
        self._path = self._directory / "registry.sqlite3"
        self._repository = SqliteWorkspaceRepository.initialize(self._path)
        self.addCleanup(self._repository.close)
        self._id = WorkspaceId(uuid4())

    def test_intent_and_registration_survive_reopen_with_original_utc_time(self) -> None:
        """重开真实库可分别读回未提交意图和首次提交时间，重复提交保持原值。"""
        repository: WorkspaceRepository = self._repository
        name = "  小猫／测试 🐈  "
        intent = repository.record_intent(self._id, name)
        self.assertIsNone(intent.registered_at)
        self._repository.close()
        reopened = SqliteWorkspaceRepository.open(self._path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(self._id), intent)
        registered = reopened.confirm_registration(self._id)
        assert registered.registered_at is not None
        self.assertEqual(registered.registered_at.utcoffset(), timedelta(0))
        self.assertEqual(registered.display_name, name)
        reopened.close()
        again = SqliteWorkspaceRepository.open(self._path)
        self.addCleanup(again.close)
        self.assertEqual(again.get(self._id), registered)
        self.assertEqual(again.confirm_registration(self._id), registered)
        self.assertEqual(again.record_intent(self._id, name), registered)

    def test_same_identity_rejects_changed_fields_and_same_name_allows_other_identity(self) -> None:
        """原身份的改参被拒绝，名称重复不会合并两个工作区。"""
        first = self._repository.record_intent(self._id, "动物")
        self.assertEqual(self._repository.record_intent(self._id, "动物"), first)
        with self.assertRaises(WorkspaceConflict):
            self._repository.record_intent(self._id, " 动物")
        self.assertEqual(self._repository.get(self._id), first)
        other_id = WorkspaceId(uuid4())
        second = self._repository.record_intent(other_id, "动物")
        self.assertNotEqual(second.id, first.id)
        self.assertEqual(self._repository.get(other_id), second)

    def test_missing_intent_cannot_be_confirmed(self) -> None:
        """真正缺行返回空值，但不能通过确认接口隐式新建登记。"""
        self.assertIsNone(self._repository.get(self._id))
        with self.assertRaises(WorkspaceContractError):
            self._repository.confirm_registration(self._id)
        self.assertIsNone(self._repository.get(self._id))

    def test_invalid_business_input_is_rejected_before_persistence(self) -> None:
        """名称与身份不满足唯一领域契约时不写入登记。"""
        for name in ("", " \t", "\ud800"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(WorkspaceContractError):
                    self._repository.record_intent(self._id, name)
        wrong_id = cast(WorkspaceId, TaskId(uuid4()))
        with self.assertRaises(TypeError):
            self._repository.get(wrong_id)
        with self.assertRaises(TypeError):
            self._repository.confirm_registration(wrong_id)
        with self.assertRaises(TypeError):
            self._repository.record_intent(wrong_id, "动物")
        self.assertIsNone(self._repository.get(self._id))

    def test_missing_database_is_not_recreated(self) -> None:
        """重开缺失注册库失败，既有仓储后续访问也不创建替代文件。"""
        missing = self._directory / "missing.sqlite3"
        with self.assertRaises(FileNotFoundError):
            SqliteWorkspaceRepository.open(missing)
        self.assertFalse(missing.exists())
        self._path.unlink()
        with self.assertRaises(FileNotFoundError):
            self._repository.get(self._id)
        self.assertFalse(self._path.exists())

    def test_initialization_never_overwrites_existing_file(self) -> None:
        """显式初始化拒绝已有对象并保留其原始字节。"""
        content = self._path.read_bytes()
        with self.assertRaises(FileExistsError):
            SqliteWorkspaceRepository.initialize(self._path)
        self.assertEqual(self._path.read_bytes(), content)
        self.assertEqual(self._path.stat().st_mode & 0o777, 0o600)

    def test_empty_corrupt_and_wrong_schemas_are_not_repaired(self) -> None:
        """空库、损坏库和不匹配结构只报告失败，不补表、迁移或重建。"""
        statements = (
            None,
            "CREATE TABLE unrelated (id TEXT PRIMARY KEY)",
            "CREATE TABLE workspaces (id TEXT NOT NULL PRIMARY KEY, display_name TEXT NOT NULL)",
            "CREATE TABLE workspaces (id TEXT NOT NULL, display_name TEXT NOT NULL, registered_at TEXT)",
            "CREATE TABLE workspaces (id TEXT NOT NULL PRIMARY KEY, display_name TEXT UNIQUE NOT NULL, registered_at TEXT)",
            "CREATE TABLE workspaces (id TEXT NOT NULL PRIMARY KEY, display_name TEXT NOT NULL CHECK(length(display_name)>0), registered_at TEXT)",
            "CREATE TABLE workspaces (id TEXT NOT NULL PRIMARY KEY, display_name TEXT NOT NULL, registered_at INTEGER)",
        )
        for index, statement in enumerate(statements):
            with self.subTest(statement=statement):
                path = self._directory / f"schema-{index}.sqlite3"
                path.touch(mode=0o600)
                if statement is not None:
                    _execute(path, statement)
                content = path.read_bytes()
                with self.assertRaises(WorkspaceStorageError):
                    SqliteWorkspaceRepository.open(path)
                self.assertEqual(path.read_bytes(), content)
        corrupt = self._directory / "corrupt.sqlite3"
        corrupt.touch(mode=0o600)
        corrupt.write_bytes(b"not a SQLite database")
        with self.assertRaises(DatabaseError):
            SqliteWorkspaceRepository.open(corrupt)
        self.assertEqual(corrupt.read_bytes(), b"not a SQLite database")

    def test_extra_view_trigger_index_and_wal_are_not_silently_adopted(self) -> None:
        """既有库出现额外行为或不同日志模式时，打开不默默接受或切换。"""
        statements = (
            "CREATE VIEW names AS SELECT display_name FROM workspaces",
            "CREATE TRIGGER guard BEFORE INSERT ON workspaces BEGIN SELECT RAISE(ABORT, 'blocked'); END",
            "CREATE INDEX name_lookup ON workspaces(display_name)",
            "PRAGMA journal_mode=WAL",
        )
        for index, statement in enumerate(statements):
            with self.subTest(statement=statement):
                path = self._directory / f"extra-{index}.sqlite3"
                repository = SqliteWorkspaceRepository.initialize(path)
                repository.close()
                _execute(path, statement)
                with self.assertRaises(WorkspaceStorageError):
                    SqliteWorkspaceRepository.open(path)

    def test_symlink_hardlink_permissions_and_in_process_replacement_are_rejected(self) -> None:
        """文件类型、权限或身份改变明确失败，不继续使用替代注册库。"""
        symbolic = self._directory / "symbolic.sqlite3"
        symbolic.symlink_to(self._path)
        with self.assertRaises(WorkspaceStorageError):
            SqliteWorkspaceRepository.open(symbolic)
        linked = self._directory / "linked.sqlite3"
        os.link(self._path, linked)
        try:
            with self.assertRaises(WorkspaceStorageError):
                self._repository.get(self._id)
        finally:
            linked.unlink()
        self._path.chmod(0o644)
        with self.assertRaises(WorkspaceStorageError):
            SqliteWorkspaceRepository.open(self._path)
        self._path.chmod(0o600)
        self._path.rename(self._directory / "original.sqlite3")
        replacement = SqliteWorkspaceRepository.initialize(self._path)
        self.addCleanup(replacement.close)
        with self.assertRaises(WorkspaceStorageError):
            self._repository.record_intent(self._id, "动物")
        self.assertIsNone(replacement.get(self._id))

    def test_transaction_failure_preserves_intent_and_does_not_report_success(self) -> None:
        """真实 SQLite 写入失败回滚事务，恢复后仍可用原身份继续。"""
        _execute(self._path, "CREATE TRIGGER refuse_insert BEFORE INSERT ON workspaces BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        with self.assertRaises(IntegrityError):
            self._repository.record_intent(self._id, "动物")
        self.assertIsNone(self._repository.get(self._id))
        _execute(self._path, "DROP TRIGGER refuse_insert")
        intent = self._repository.record_intent(self._id, "动物")
        _execute(self._path, "CREATE TRIGGER refuse_update BEFORE UPDATE ON workspaces BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        with self.assertRaises(IntegrityError):
            self._repository.confirm_registration(self._id)
        self.assertEqual(self._repository.get(self._id), intent)
        _execute(self._path, "DROP TRIGGER refuse_update")
        self.assertIsNotNone(self._repository.confirm_registration(self._id).registered_at)

    def test_commit_lock_failure_does_not_report_success_or_leave_a_record(self) -> None:
        """其他读者阻止提交时有限等待后回滚，不将已经执行的写入视为提交成功。"""
        connection = sqlite3.connect(self._path, autocommit=False)
        try:
            connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()
            with self.assertRaises(OperationalError):
                self._repository.record_intent(self._id, "动物")
            connection.rollback()
        finally:
            connection.close()
        self.assertIsNone(self._repository.get(self._id))

    def test_database_read_failures_and_invalid_rows_do_not_become_missing(self) -> None:
        """坏时间和损坏表向上报告错误，不能降级成没有记录。"""
        self._repository.record_intent(self._id, "动物")
        _execute(self._path, "UPDATE workspaces SET registered_at=? WHERE id=?", ("2026-01-01T00:00:00", str(self._id.value)))
        with self.assertRaises(WorkspaceContractError):
            self._repository.get(self._id)
        _execute(self._path, "DROP TABLE workspaces")
        with self.assertRaises(OperationalError):
            self._repository.get(self._id)

    def test_repository_rejects_cross_thread_and_closed_use(self) -> None:
        """Session 所属线程由适配器维护，跨线程或关闭后的访问明确拒绝。"""
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(WorkspaceStorageError):
                executor.submit(self._repository.get, self._id).result()
            with self.assertRaises(WorkspaceStorageError):
                executor.submit(self._repository.close).result()
        self.assertIsNone(self._repository.get(self._id))
        self._repository.close()
        self._repository.close()
        with self.assertRaises(WorkspaceStorageError):
            self._repository.get(self._id)
