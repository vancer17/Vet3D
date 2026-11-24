# 文件信息：L1-04 单资产目录的真实 SQLite 契约与恢复验证。
# 作用：验证单行提交、重开读回、不可变绑定、工作区隔离和存储故障传播。
# 证据边界：真实本地数据库与故障注入，不证明文件内容、断电、NFS 或执行隔离。
"""通过具体仓储的公共入口验证登记事实，不把元数据当作可读取文件。"""

import sqlite3
import tempfile
import unittest
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from vet3d.adapters import SqliteWorkspaceRepository, WorkspaceStorageError
from vet3d.artifacts import (
    ArtifactContractError, ArtifactRegistrationConflict, ArtifactRepository,
    ContentFingerprint, FileReference, ImportOrigin, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, TaskId, WorkspaceId
from vet3d.workspaces import WorkspaceContractError


def _execute(database_path: Path, statement: str, parameters: tuple[str, ...] = ()) -> None:
    """使用独立连接制造持久故障，不通过产品端口偷偷增加修改能力。

    :param database_path: 测试自有数据库。
    :param statement: 测试自有故障 SQL。
    :param parameters: 对应的绑定参数。
    """
    connection = sqlite3.connect(database_path.as_uri() + "?mode=rw", uri=True, autocommit=True)
    try:
        connection.execute(statement, parameters)
    finally:
        connection.close()


def _record(workspace_id: WorkspaceId, *, path: str | None = None) -> LocatedArtifact:
    """构造独立身份的单资产元数据，不宣称存在实际文件。

    :param workspace_id: 既有工作区归属。
    :param path: 需要验证位置唯一性时指定的位置。
    :returns: 经过既有领域构造器校验的记录。
    """
    artifact_id = ArtifactId(uuid4())
    return LocatedArtifact(
        ArtifactIdentity(artifact_id, workspace_id),
        FileReference(artifact_id, ContentFingerprint("a" * 64, 3)),
        WorkspaceFileLocation(artifact_id, WorkspaceRelativePath(path or f"assets/{artifact_id.value}/content")),
    )


class ArtifactRepositoryTests(unittest.TestCase):
    """验证真实提交及重开，不建立尚不存在的批次或自动恢复协议。"""

    def setUp(self) -> None:
        """为每例建立真实数据库、已提交工作区及其窄资产仓储。"""
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self._directory = Path(self._temporary.name)
        self._path = self._directory / "registry.sqlite3"
        self._owner = SqliteWorkspaceRepository.initialize(self._path)
        self.addCleanup(self._owner.close)
        self._workspace_id = WorkspaceId(uuid4())
        self._owner.record_intent(self._workspace_id, "猫的外观")
        self._owner.confirm_registration(self._workspace_id)
        self._repository = self._owner.artifacts(self._workspace_id)
        self._record = _record(self._workspace_id)

    def test_registration_and_original_origin_survive_close_and_reopen(self) -> None:
        """关闭重开读回唯一原字段和出处，同参调用保持原登记。"""
        repository: ArtifactRepository = self._repository
        origin = ImportOrigin(self._record.artifact.id, "  原始拍摄 🐈  ")
        self.assertEqual(repository.register(self._record, origin=origin), self._record)
        self.assertEqual(repository.register(self._record, origin=origin), self._record)
        self._owner.close()
        reopened = SqliteWorkspaceRepository.open(self._path)
        self.addCleanup(reopened.close)
        restored = reopened.artifacts(self._workspace_id)
        self.assertEqual(restored.get(self._record.artifact.id), self._record)
        self.assertEqual(restored.get_origin(self._record.artifact.id), origin)
        self.assertEqual(restored.register(self._record, origin=origin), self._record)

    def test_missing_and_origin_unknown_do_not_claim_file_availability(self) -> None:
        """真正未登记返回空值，无出处不妨碍登记，也不证明实际字节存在。"""
        self.assertIsNone(self._repository.get(self._record.artifact.id))
        self.assertIsNone(self._repository.get_origin(self._record.artifact.id))
        self._repository.register(self._record)
        self.assertEqual(self._repository.get(self._record.artifact.id), self._record)
        self.assertIsNone(self._repository.get_origin(self._record.artifact.id))
        self.assertFalse((self._directory / self._record.location.relative_path.value).exists())

    def test_same_identity_rejects_any_changed_binding_without_overwrite(self) -> None:
        """同一产物的摘要、长度、位置或出处改变时拒绝覆盖原行。"""
        original = self._record
        self._repository.register(original)
        variants = (
            replace(original, reference=FileReference(original.artifact.id, ContentFingerprint("b" * 64, 3))),
            replace(original, reference=FileReference(original.artifact.id, ContentFingerprint("a" * 64, 4))),
            replace(original, location=WorkspaceFileLocation(original.artifact.id, WorkspaceRelativePath("assets/other"))),
        )
        for record in variants:
            with self.subTest(record=record):
                with self.assertRaises(ArtifactRegistrationConflict):
                    self._repository.register(record)
        with self.assertRaises(ArtifactRegistrationConflict):
            self._repository.register(original, origin=ImportOrigin(original.artifact.id, "补写出处"))
        self.assertEqual(self._repository.get(original.artifact.id), original)
        self.assertIsNone(self._repository.get_origin(original.artifact.id))

    def test_existing_origin_cannot_be_removed_or_replaced(self) -> None:
        """原出处是不可变登记的一部分，删除和改写都不是幂等重放。"""
        origin = ImportOrigin(self._record.artifact.id, "拍摄")
        self._repository.register(self._record, origin=origin)
        for changed in (None, ImportOrigin(self._record.artifact.id, "推断")):
            with self.subTest(changed=changed):
                with self.assertRaises(ArtifactRegistrationConflict):
                    self._repository.register(self._record, origin=changed)
        self.assertEqual(self._repository.get_origin(self._record.artifact.id), origin)

    def test_cross_workspace_known_identity_is_rejected_instead_of_hidden(self) -> None:
        """知道身份不授予读取和写入权限，已知跨区资产明确拒绝。"""
        other_id = WorkspaceId(uuid4())
        self._owner.record_intent(other_id, "另一只猫")
        self._owner.confirm_registration(other_id)
        other_repository = self._owner.artifacts(other_id)
        self._repository.register(self._record)
        with self.assertRaises(ArtifactContractError):
            other_repository.get(self._record.artifact.id)
        with self.assertRaises(ArtifactContractError):
            other_repository.get_origin(self._record.artifact.id)
        with self.assertRaises(ArtifactContractError):
            other_repository.register(self._record)
        other_record = _record(other_id, path=self._record.location.relative_path.value)
        self.assertEqual(other_repository.register(other_record), other_record)
        self.assertEqual(self._repository.get(self._record.artifact.id), self._record)

    def test_requires_committed_workspace_at_factory_and_each_transaction(self) -> None:
        """缺失、仅登记意图以及后续被破坏的工作区均不能支持资产操作。"""
        pending = WorkspaceId(uuid4())
        with self.assertRaises(WorkspaceContractError):
            self._owner.artifacts(pending)
        self._owner.record_intent(pending, "未提交")
        with self.assertRaises(WorkspaceContractError):
            self._owner.artifacts(pending)
        _execute(self._path, "UPDATE workspaces SET registered_at=NULL WHERE id=?", (str(self._workspace_id.value),))
        with self.assertRaises(WorkspaceContractError):
            self._repository.register(self._record)
        with self.assertRaises(WorkspaceContractError):
            self._repository.get(self._record.artifact.id)

    def test_wrong_identity_and_unrelated_origin_are_rejected(self) -> None:
        """其他身份类型和指向另一产物的出处不能混入原登记。"""
        with self.assertRaises(TypeError):
            self._repository.get(cast(ArtifactId, TaskId(uuid4())))
        with self.assertRaises(ArtifactContractError):
            self._repository.register(self._record, origin=ImportOrigin(ArtifactId(uuid4()), "错误关联"))
        self.assertIsNone(self._repository.get(self._record.artifact.id))

    def test_unique_location_rejects_alias_while_equal_bytes_keep_distinct_identities(self) -> None:
        """同工作区同位置不能绑定两个身份，内容相同不强制合并不同产物。"""
        self._repository.register(self._record)
        alias = _record(self._workspace_id, path=self._record.location.relative_path.value)
        with self.assertRaises(IntegrityError):
            self._repository.register(alias)
        self.assertIsNone(self._repository.get(alias.artifact.id))
        distinct = _record(self._workspace_id)
        self.assertEqual(self._repository.register(distinct), distinct)

    def test_failed_transaction_rolls_back_and_query_failures_propagate(self) -> None:
        """真实数据库写入故障回滚，查询表缺失向上传播而非变成未登记。"""
        _execute(self._path, "CREATE TRIGGER refuse_asset BEFORE INSERT ON artifacts BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        with self.assertRaises(IntegrityError):
            self._repository.register(self._record)
        self.assertIsNone(self._repository.get(self._record.artifact.id))
        _execute(self._path, "DROP TRIGGER refuse_asset")
        self._repository.register(self._record)
        _execute(self._path, "DROP TABLE artifacts")
        with self.assertRaises(OperationalError):
            self._repository.get(self._record.artifact.id)
        with self.assertRaises(OperationalError):
            self._repository.get_origin(self._record.artifact.id)

    def test_commit_response_loss_can_be_read_back_after_reopen(self) -> None:
        """真实事务提交后注入回执异常，重开从已提交行恢复，不需要登记意图。"""
        original_transaction = self._owner._transaction

        @contextmanager
        def commit_then_fail() -> Iterator[Session]:
            """保留真实 SQLite 提交，只在返回调用者前模拟响应丢失。

            :yields: 原所有者的真实事务。
            :raises OSError: 已提交后的模拟回执异常。
            """
            with original_transaction() as session:
                yield session
            raise OSError("登记提交后的回执丢失")

        with patch.object(self._owner, "_transaction", commit_then_fail):
            with self.assertRaises(OSError):
                self._repository.register(self._record)
        self._owner.close()
        reopened = SqliteWorkspaceRepository.open(self._path)
        self.addCleanup(reopened.close)
        repository = reopened.artifacts(self._workspace_id)
        self.assertEqual(repository.get(self._record.artifact.id), self._record)
        self.assertEqual(repository.register(self._record), self._record)

    def test_foreign_keys_are_enforced_on_each_real_owner_connection(self) -> None:
        """每个实际连接拒绝不存在工作区的资产行，不能只验证配置意图。"""
        for _ in range(2):
            connection = self._owner._connect()
            try:
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone(), (1,))
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO artifacts(id, workspace_id, relative_path, sha256, byte_size, source_label) VALUES(?,?,?,?,?,?)",
                        (str(uuid4()), str(uuid4()), "assets/example", "a" * 64, 3, None),
                    )
                connection.rollback()
            finally:
                connection.close()

    def test_borrowed_repository_shares_owner_thread_close_and_database_identity(self) -> None:
        """借用仓储不能跨线程、跨关闭寿命或改用同路径替代数据库。"""
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(WorkspaceStorageError):
                executor.submit(self._repository.get, self._record.artifact.id).result()
        self._path.rename(self._directory / "original.sqlite3")
        replacement = SqliteWorkspaceRepository.initialize(self._path)
        self.addCleanup(replacement.close)
        with self.assertRaises(WorkspaceStorageError):
            self._repository.get(self._record.artifact.id)
        self._owner.close()
        with self.assertRaises(WorkspaceStorageError):
            self._repository.get(self._record.artifact.id)

    def test_corrupt_content_and_origin_fail_instead_of_becoming_absent(self) -> None:
        """损坏持久字段由现行契约拒绝，不能被查询接口隐藏。"""
        self._repository.register(self._record)
        _execute(self._path, "UPDATE artifacts SET sha256='broken'")
        with self.assertRaises(ArtifactContractError):
            self._repository.get(self._record.artifact.id)
        _execute(self._path, "UPDATE artifacts SET sha256=?, source_label=''", ("a" * 64,))
        with self.assertRaises(ArtifactContractError):
            self._repository.get_origin(self._record.artifact.id)

    def test_old_workspace_only_schema_is_rejected_without_repair(self) -> None:
        """旧结构不自动迁移或补表，失败后完整保留既有数据库字节。"""
        path = self._directory / "old.sqlite3"
        path.touch(mode=0o600)
        _execute(path, "CREATE TABLE workspaces (id TEXT NOT NULL PRIMARY KEY, display_name TEXT NOT NULL, registered_at TEXT)")
        original = path.read_bytes()
        with self.assertRaises(WorkspaceStorageError):
            SqliteWorkspaceRepository.open(path)
        self.assertEqual(path.read_bytes(), original)

    def test_missing_or_changed_asset_constraints_are_rejected_without_repair(self) -> None:
        """外键、唯一位置、检查约束和额外索引均参与结构核对。"""
        definitions = (
            "UNIQUE(workspace_id, relative_path), CHECK(byte_size >= 0)",
            "FOREIGN KEY(workspace_id) REFERENCES workspaces(id), CHECK(byte_size >= 0)",
            "FOREIGN KEY(workspace_id) REFERENCES workspaces(id), UNIQUE(workspace_id, relative_path)",
            "FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE, UNIQUE(workspace_id, relative_path), CHECK(byte_size >= 0)",
        )
        for index, definition in enumerate(definitions):
            with self.subTest(definition=definition):
                path = self._directory / f"wrong-assets-{index}.sqlite3"
                repository = SqliteWorkspaceRepository.initialize(path)
                repository.close()
                _execute(path, "DROP TABLE artifacts")
                _execute(path, "CREATE TABLE artifacts (id TEXT NOT NULL PRIMARY KEY, workspace_id TEXT NOT NULL, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL, source_label TEXT, " + definition + ")")
                original = path.read_bytes()
                with self.assertRaises(WorkspaceStorageError):
                    SqliteWorkspaceRepository.open(path)
                self.assertEqual(path.read_bytes(), original)
        self._owner.close()
        _execute(self._path, "CREATE INDEX artifact_digest ON artifacts(sha256)")
        original = self._path.read_bytes()
        with self.assertRaises(WorkspaceStorageError):
            SqliteWorkspaceRepository.open(self._path)
        self.assertEqual(self._path.read_bytes(), original)
