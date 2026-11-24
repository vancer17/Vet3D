# 文件信息：L1-01 工作区仓储及 L1-04 共用注册数据库的生命周期入口。
# 作用：保存工作区事实，统一连接参数与 Schema 检查，并装配同线程单资产仓储。
# 边界：仅在 Bootstrap 所属工作线程使用；不创建目录、不授予文件或执行权限。
# 恢复：只打开既有库并接受 SQLite 日志恢复，不迁移、补表、扫描目录或伪造登记。
"""实现同步注册端口，由受信装配持有根锁并限定数据库父目录。"""

import os
import sqlite3
import stat
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import final

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from vet3d.identity import WorkspaceId
from vet3d.workspaces import (
    WorkspaceConflict,
    WorkspaceContractError,
    WorkspaceRecord,
    WorkspaceRepository,
)

from .artifact_repository import SqliteArtifactRepository
from .workspace_tables import WorkspaceRow, WorkspaceTableBase


class WorkspaceStorageError(RuntimeError):
    """表示注册库结构、文件身份或所属线程不符合当前存储边界。"""


def _check_database_file(database_path: Path) -> tuple[int, int]:
    """确认数据库是服务独占的普通文件，并返回本进程核对的文件身份。

    :param database_path: 受信装配提供的注册库绝对路径。
    :returns: 当前设备及 inode，不写入业务记录。
    :raises OSError: 文件不存在或无法读取属性。
    :raises WorkspaceStorageError: 类型、所有权、链接数或权限不满足要求。
    """
    info = database_path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise WorkspaceStorageError("注册库必须是当前用户独占的 0600 普通单链接文件")
    return info.st_dev, info.st_ino


def _record_from_row(row: WorkspaceRow) -> WorkspaceRecord:
    """在存储边界恢复唯一业务类型，并让损坏字段明确失败。

    :param row: 本次事务取得的注册行。
    :returns: 经业务契约验证的不可变记录。
    :raises ValueError: 身份、名称或时间字段不符合契约。
    """
    timestamp = None if row.registered_at is None else datetime.fromisoformat(row.registered_at)
    return WorkspaceRecord(WorkspaceId.parse(row.id), row.display_name, timestamp)


@final
class SqliteWorkspaceRepository(WorkspaceRepository):
    """在单一所属线程以每次调用独立 Session 保存登记，不跨目录操作持有事务。

    :param database_path: 已存在的受信注册库路径；调用方应使用 initialize 或 open。
    """

    def __init__(self, database_path: Path) -> None:
        """绑定当前线程及文件身份；公开生命周期入口负责建表或结构校验。

        :param database_path: 受管根已经保护的数据库路径。
        :raises WorkspaceStorageError: 文件属性不符合要求。
        """
        self._database_path = database_path.absolute()
        self._identity = _check_database_file(self._database_path)
        self._owner_thread = threading.get_ident()
        self._closed = False
        self._engine: Engine = create_engine(
            "sqlite+pysqlite://", creator=self._connect, poolclass=NullPool
        )

    @classmethod
    def initialize(cls, database_path: Path) -> "SqliteWorkspaceRepository":
        """独占创建新数据库并提交当前表结构，不覆盖或清理已有对象。

        :param database_path: 受管空根中尚不存在的注册库路径。
        :returns: 已提交结构并同步文件和父目录的仓储。
        :raises OSError: 文件已存在、创建或同步失败。
        :raises Exception: 建表失败；保留残留文件供诊断，不伪装成初始化成功。
        """
        descriptor = os.open(database_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        repository = cls(database_path)
        try:
            with repository._engine.begin() as connection:
                WorkspaceTableBase.metadata.create_all(connection)
            repository._sync_initialization()
            repository._assert_usable()
        except BaseException:
            repository.close()
            raise
        return repository

    @classmethod
    def open(cls, database_path: Path) -> "SqliteWorkspaceRepository":
        """验证并打开既有注册库，不误建缺失文件或自动修复错误结构。

        :param database_path: 受管根已有的注册库路径。
        :returns: 结构匹配且可访问的仓储。
        :raises OSError: 注册库缺失或不可访问。
        :raises WorkspaceStorageError: 结构或文件身份不匹配。
        """
        repository = cls(database_path)
        try:
            with repository._engine.connect() as connection:
                repository._validate_schema(connection)
            repository._assert_usable()
        except BaseException:
            repository.close()
            raise
        return repository

    def _assert_usable(self) -> None:
        """在每次访问核对生命周期、所属线程和当前文件身份。

        :raises WorkspaceStorageError: 已关闭、线程不匹配或文件被替换。
        :raises OSError: 当前文件不可访问。
        """
        if self._closed:
            raise WorkspaceStorageError("注册仓储已经关闭")
        if threading.get_ident() != self._owner_thread:
            raise WorkspaceStorageError("注册仓储只能在其创建线程使用")
        if _check_database_file(self._database_path) != self._identity:
            raise WorkspaceStorageError("注册库文件身份已经改变")

    def _connect(self) -> sqlite3.Connection:
        """只连接既有库，在事务外设置有界等待及持久化参数后启用显式事务。

        :returns: 属于当前线程的 SQLite 连接。
        :raises WorkspaceStorageError: 日志模式、同步设置或文件身份不符合要求。
        :raises sqlite3.Error: 数据库连接或参数设置失败。
        """
        self._assert_usable()
        connection = sqlite3.connect(
            self._database_path.as_uri() + "?mode=rw", uri=True, timeout=1.0, autocommit=True
        )
        try:
            journal = connection.execute("PRAGMA journal_mode").fetchone()
            if journal is None or journal[0] != "delete":
                raise WorkspaceStorageError("注册库只接受 DELETE 日志模式")
            connection.execute("PRAGMA synchronous=EXTRA")
            synchronous = connection.execute("PRAGMA synchronous").fetchone()
            if synchronous is None or synchronous[0] != 3:
                raise WorkspaceStorageError("注册库无法启用 EXTRA 同步")
            connection.execute("PRAGMA foreign_keys=ON")
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
            if foreign_keys is None or foreign_keys[0] != 1:
                raise WorkspaceStorageError("注册库无法启用外键约束")
            self._assert_usable()
            connection.autocommit = False
            return connection
        except BaseException:
            connection.close()
            raise

    def _validate_schema(self, connection: Connection) -> None:
        """从同一模型元数据比对现有表、列和约束，不调用建表修复。

        :param connection: 已启用显式事务的既有库连接。
        :raises WorkspaceStorageError: 结构出现缺失、额外对象或约束差异。
        """
        inspector = inspect(connection)
        tables = WorkspaceTableBase.metadata.tables
        if set(inspector.get_table_names()) != set(tables) or inspector.get_view_names():
            raise WorkspaceStorageError("注册库表或视图不符合当前结构")
        if connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).first():
            raise WorkspaceStorageError("注册库含有未声明的触发器")
        for table_name, table in tables.items():
            actual_columns = inspector.get_columns(table_name)
            expected_columns = [
                (column.name, str(column.type.compile(dialect=connection.dialect)).upper(), column.nullable, None)
                for column in table.columns
            ]
            observed_columns = [
                (column["name"], str(column["type"]).upper(), column["nullable"], column["default"])
                for column in actual_columns
            ]
            expected_unique = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
            actual_unique = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
            }
            expected_checks = {
                str(constraint.sqltext)
                for constraint in table.constraints
                if isinstance(constraint, CheckConstraint)
            }
            actual_checks = {constraint["sqltext"] for constraint in inspector.get_check_constraints(table_name)}
            expected_foreign = {
                (
                    tuple(element.parent.name for element in constraint.elements),
                    constraint.referred_table.schema,
                    constraint.referred_table.name,
                    tuple(element.column.name for element in constraint.elements),
                    tuple(
                        (key, value)
                        for key, value in (
                            ("deferrable", constraint.deferrable), ("initially", constraint.initially),
                            ("match", constraint.match), ("ondelete", constraint.ondelete),
                            ("onupdate", constraint.onupdate),
                        )
                        if value is not None
                    ),
                )
                for constraint in table.constraints
                if isinstance(constraint, ForeignKeyConstraint)
            }
            observed_foreign = inspector.get_foreign_keys(table_name)
            actual_foreign = {
                (
                    tuple(constraint["constrained_columns"]), constraint.get("referred_schema"),
                    constraint["referred_table"], tuple(constraint["referred_columns"]),
                    tuple(sorted(constraint.get("options", {}).items())),
                )
                for constraint in observed_foreign
            }
            expected_indexes = {
                (index.name, index.unique, tuple(column.name for column in index.columns))
                for index in table.indexes
            }
            actual_indexes = {
                (index["name"], bool(index["unique"]), tuple(index["column_names"]))
                for index in inspector.get_indexes(table_name)
            }
            if (
                observed_columns != expected_columns
                or inspector.get_pk_constraint(table_name)["constrained_columns"]
                != [column.name for column in table.primary_key.columns]
                or actual_unique != expected_unique
                or actual_checks != expected_checks
                or actual_foreign != expected_foreign
                or actual_indexes != expected_indexes
            ):
                raise WorkspaceStorageError("注册库列或约束不符合当前结构")

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        """为同包窄仓储提供独立短事务，保持唯一连接及关闭所有者。

        :yields: 仅供适配器在当前所属线程使用的本次 Session。
        :raises WorkspaceStorageError: 原所有者已关闭、跨线程或库被替换。
        """
        self._assert_usable()
        with Session(self._engine) as session, session.begin():
            yield session
        self._assert_usable()

    def artifacts(self, workspace_id: WorkspaceId) -> SqliteArtifactRepository:
        """为已提交工作区装配单资产仓储，不另建连接所有者或持有事务。

        :param workspace_id: 子仓储之后固定使用的工作区身份。
        :returns: 共享本实例线程、连接配置和关闭寿命的资产仓储。
        :raises WorkspaceContractError: 工作区尚未提交注册。
        """
        with self._transaction() as session:
            self._require_registered_workspace(session, workspace_id)
        return SqliteArtifactRepository(self, workspace_id)

    def _require_registered_workspace(self, session: Session, workspace_id: WorkspaceId) -> None:
        """在调用方的短事务内核对已提交工作区，共用唯一行编解码。

        :param session: 所属适配器的当前事务，不向业务层暴露。
        :param workspace_id: 必须已提交注册的原身份。
        :raises TypeError: 工作区身份类型错误。
        :raises WorkspaceContractError: 工作区缺失、未提交或记录损坏。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("工作区身份必须是 WorkspaceId")
        row = session.get(WorkspaceRow, str(workspace_id.value))
        if row is None or _record_from_row(row).registered_at is None:
            raise WorkspaceContractError("资产仓储需要已提交的工作区登记")

    def _sync_initialization(self) -> None:
        """在首次建表提交后同步数据库和父目录，不宣称覆盖所有断电场景。

        :raises OSError: 同步失败，初始化不能返回成功。
        """
        self._assert_usable()
        for path, flags in (
            (self._database_path, os.O_RDONLY | os.O_NOFOLLOW),
            (self._database_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW),
        ):
            descriptor = os.open(path, flags)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def get(self, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
        """读取原注册行，仅真实缺行时返回空值，存储故障向调用边界传播。

        :param workspace_id: 原工作区身份。
        :returns: 当前登记事实或确实缺失时的空值。
        :raises TypeError: 传入了其他身份类别。
        """
        self._assert_usable()
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("工作区身份必须是 WorkspaceId")
        with Session(self._engine) as session, session.begin():
            row = session.get(WorkspaceRow, str(workspace_id.value))
            record = None if row is None else _record_from_row(row)
        self._assert_usable()
        return record

    def record_intent(self, workspace_id: WorkspaceId, display_name: str) -> WorkspaceRecord:
        """以短事务登记原字段或读回原意图，原身份改参时拒绝覆盖。

        :param workspace_id: 创建幂等键。
        :param display_name: 原始显示名。
        :returns: 提交确认后的意图或原注册记录。
        :raises WorkspaceConflict: 同一身份已有不同显示名。
        """
        self._assert_usable()
        requested = WorkspaceRecord(workspace_id, display_name, None)
        with Session(self._engine) as session, session.begin():
            row = session.get(WorkspaceRow, str(workspace_id.value))
            if row is None:
                session.add(WorkspaceRow(id=str(workspace_id.value), display_name=display_name, registered_at=None))
                record = requested
            else:
                record = _record_from_row(row)
                if record.display_name != display_name:
                    raise WorkspaceConflict("同一工作区身份不能变更原始创建名称")
        self._assert_usable()
        return record

    def confirm_registration(self, workspace_id: WorkspaceId) -> WorkspaceRecord:
        """首次提交 UTC 注册时间，重放仅返回原提交，不重置时间。

        :param workspace_id: 已登记创建意图的原身份。
        :returns: 数据库提交确认后的注册记录。
        :raises WorkspaceContractError: 尚无原创建意图。
        """
        self._assert_usable()
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("工作区身份必须是 WorkspaceId")
        with Session(self._engine) as session, session.begin():
            row = session.get(WorkspaceRow, str(workspace_id.value))
            if row is None:
                raise WorkspaceContractError("缺少创建意图，不能提交注册")
            record = _record_from_row(row)
            if record.registered_at is None:
                row.registered_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                record = _record_from_row(row)
        self._assert_usable()
        return record

    def close(self) -> None:
        """在所属线程释放连接设施，重复关闭允许，文件故障不阻碍资源释放。

        :raises WorkspaceStorageError: 从非所属线程请求关闭。
        """
        if threading.get_ident() != self._owner_thread:
            raise WorkspaceStorageError("注册仓储只能在其创建线程关闭")
        if not self._closed:
            self._engine.dispose()
            self._closed = True
