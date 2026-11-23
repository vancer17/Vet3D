# 文件信息：L1-01 工作区记录及创建服务的机械契约测试。
# 作用：验证身份、原始参数、调用顺序及显式同身份续做，不重复保存派生状态。
# 边界：内存替身不证明 SQLite 持久化、真实目录安全、进程重启或执行隔离。
"""通过公共入口检查工作区创建的高价值契约与故障窗口。"""

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from typing import cast
from uuid import uuid4

from vet3d.identity import TaskId, WorkspaceId
from vet3d.workspaces import (
    WorkspaceConflict,
    WorkspaceContractError,
    WorkspaceCreationError,
    WorkspaceDirectories,
    WorkspaceRecord,
    WorkspaceRepository,
    WorkspaceService,
)


_REGISTERED_AT = datetime(2026, 11, 23, 12, tzinfo=UTC)


class _Repository(WorkspaceRepository):
    """保存测试记录并注入提交前后故障，仅验证服务机械协议。"""

    def __init__(self, events: list[str]) -> None:
        """准备受本用例控制的记录与故障点。

        :param events: 与目录替身共享的操作顺序。
        """
        self.events = events
        self.records: dict[WorkspaceId, WorkspaceRecord] = {}
        self.fail_before: dict[str, Exception] = {}
        self.fail_after: dict[str, Exception] = {}
        self.replies: dict[str, WorkspaceRecord] = {}

    def _begin(self, operation: str) -> None:
        """记录调用并注入任何修改前的故障。

        :param operation: 当前仓储方法名。
        """
        self.events.append(operation)
        if operation in self.fail_before:
            raise self.fail_before[operation]

    def _finish(self, operation: str, record: WorkspaceRecord) -> WorkspaceRecord:
        """模拟副作用已完成但应答失败或违反约定。

        :param operation: 当前仓储方法名。
        :param record: 当前真实保存的替身记录。
        :returns: 正常或故意破坏的回包。
        """
        if operation in self.fail_after:
            raise self.fail_after[operation]
        return self.replies.get(operation, record)

    def get(self, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
        """读取原记录或注入查询失败。

        :param workspace_id: 原工作区身份。
        :returns: 替身现存记录或指定异常回包。
        """
        self._begin("get")
        return self.replies.get("get", self.records.get(workspace_id))

    def record_intent(self, workspace_id: WorkspaceId, display_name: str) -> WorkspaceRecord:
        """保存创建意图，不模拟真实数据库事务。

        :param workspace_id: 原工作区身份。
        :param display_name: 原始显示名。
        :returns: 记录或注入的异常回包。
        """
        self._begin("record_intent")
        record = self.records.setdefault(
            workspace_id, WorkspaceRecord(workspace_id, display_name, None)
        )
        if record.display_name != display_name:
            raise WorkspaceConflict("替身拒绝同身份改参")
        return self._finish("record_intent", record)

    def confirm_registration(self, workspace_id: WorkspaceId) -> WorkspaceRecord:
        """填入固定测试时间后模拟提交应答。

        :param workspace_id: 已登记意图的身份。
        :returns: 已提交记录或注入的异常回包。
        """
        self._begin("confirm_registration")
        record = self.records[workspace_id]
        if record.registered_at is None:
            record = WorkspaceRecord(record.id, record.display_name, _REGISTERED_AT)
            self.records[workspace_id] = record
        return self._finish("confirm_registration", record)


class _Directories(WorkspaceDirectories):
    """仅模拟目录存在与缺失，不替代真实路径和归属验证。"""

    def __init__(self, events: list[str]) -> None:
        """准备目录存在集合和可注入故障。

        :param events: 与仓储替身共享的操作顺序。
        """
        self.events = events
        self.existing: set[WorkspaceId] = set()
        self.prepare_error: Exception | None = None

    def check_absent(self, workspace_id: WorkspaceId) -> None:
        """拒绝首次意图登记前的既有目标。

        :param workspace_id: 尚未登记的身份。
        """
        self.events.append("check_absent")
        if workspace_id in self.existing:
            raise FileExistsError("替身目标已经存在")

    def prepare(self, workspace_id: WorkspaceId) -> None:
        """模拟目录准备，可在开始前失败。

        :param workspace_id: 已登记但未提交的身份。
        """
        self.events.append("prepare")
        if self.prepare_error is not None:
            raise self.prepare_error
        self.existing.add(workspace_id)

    def require_existing(self, workspace_id: WorkspaceId) -> None:
        """拒绝已登记目录缺失，不自动修复。

        :param workspace_id: 已提交注册的身份。
        """
        self.events.append("require_existing")
        if workspace_id not in self.existing:
            raise FileNotFoundError("替身原目录丢失")


class WorkspaceRecordTests(unittest.TestCase):
    """验证唯一注册记录的不可变字段和非路径显示名。"""

    def test_original_unicode_name_is_preserved_and_record_is_frozen(self) -> None:
        """保留名称原字节语义和空格，不裁剪、归一化或允许原地改名。"""
        name = "  小猫 e\u0301 / ../原始名  "
        record = WorkspaceRecord(WorkspaceId(uuid4()), name, None)
        self.assertEqual(record.display_name, name)
        with self.assertRaises(FrozenInstanceError):
            setattr(record, "display_name", "另一名称")

    def test_wrong_identity_and_field_types_are_rejected(self) -> None:
        """拒绝相似身份类别和非字符串、非时间字段。"""
        workspace_id = WorkspaceId(uuid4())
        with self.assertRaises(TypeError):
            WorkspaceRecord(cast(WorkspaceId, TaskId(uuid4())), "猫", None)
        with self.assertRaises(TypeError):
            WorkspaceRecord(workspace_id, cast(str, 12), None)
        with self.assertRaises(TypeError):
            WorkspaceRecord(workspace_id, "猫", cast(datetime, "2026-11-23"))

    def test_blank_and_unencodable_names_are_rejected(self) -> None:
        """无业务名称或包含代理码位的输入无法形成创建意图。"""
        for name in ("", " \t\n\u3000", "猫\ud800"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(WorkspaceContractError):
                    WorkspaceRecord(WorkspaceId(uuid4()), name, None)

    def test_registration_time_requires_aware_utc(self) -> None:
        """拒绝无时区和非零偏移，接受不依赖具体时区对象的 UTC 时间。"""
        workspace_id = WorkspaceId(uuid4())
        for timestamp in (
            datetime(2026, 11, 23),
            datetime(2026, 11, 23, tzinfo=timezone(timedelta(hours=8))),
        ):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(WorkspaceContractError):
                    WorkspaceRecord(workspace_id, "猫", timestamp)
        timestamp = datetime(2026, 11, 23, tzinfo=timezone(timedelta(0), "零偏移"))
        self.assertEqual(WorkspaceRecord(workspace_id, "猫", timestamp).registered_at, timestamp)


class WorkspaceServiceTests(unittest.TestCase):
    """验证短创建用例顺序及原身份恢复，不模拟真实执行或权限隔离。"""

    def setUp(self) -> None:
        """为每个用例装配互不共享记录的显式协议替身。"""
        self.events: list[str] = []
        self.repository = _Repository(self.events)
        self.directories = _Directories(self.events)
        self.service = WorkspaceService(repository=self.repository, directories=self.directories)
        self.workspace_id = WorkspaceId(uuid4())

    def test_create_checks_absence_before_intent_and_returns_committed_record(self) -> None:
        """正常创建先确认没有陌生目标，再登记、准备和提交。"""
        record = self.service.create(workspace_id=self.workspace_id, display_name=" 猫 ")
        self.assertEqual(record, WorkspaceRecord(self.workspace_id, " 猫 ", _REGISTERED_AT))
        self.assertEqual(self.events, [
            "get", "check_absent", "record_intent", "prepare", "confirm_registration",
        ])

    def test_same_request_reads_back_without_rewriting_registration(self) -> None:
        """重复创建只读回并检查原目录，保留第一次提交时间。"""
        first = self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.events.clear()
        repeated = self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIs(repeated, first)
        self.assertEqual(self.events, ["get", "require_existing"])

    def test_same_name_does_not_merge_distinct_identities(self) -> None:
        """名称不充当唯一键，不同工作区可以保持相同名称。"""
        first = self.service.create(workspace_id=self.workspace_id, display_name="猫")
        other_id = WorkspaceId(uuid4())
        other = self.service.create(workspace_id=other_id, display_name="猫")
        self.assertNotEqual(first.id, other.id)
        self.assertEqual(set(self.repository.records), {self.workspace_id, other_id})

    def test_invalid_inputs_have_no_io(self) -> None:
        """调用参数在查询或目标预检前就被拒绝。"""
        with self.assertRaises(TypeError):
            self.service.create(workspace_id=cast(WorkspaceId, TaskId(uuid4())), display_name="猫")
        with self.assertRaises(WorkspaceContractError):
            self.service.create(workspace_id=self.workspace_id, display_name=" \n")
        with self.assertRaises(TypeError):
            self.service.read(cast(WorkspaceId, str(self.workspace_id.value)))
        self.assertEqual(self.events, [])

    def test_changed_fields_are_rejected_for_pending_and_committed_records(self) -> None:
        """未提交与已提交身份均拒绝改参，不通过规范化隐藏变化。"""
        for registered_at in (None, _REGISTERED_AT):
            with self.subTest(registered_at=registered_at):
                original = WorkspaceRecord(self.workspace_id, " 猫 ", registered_at)
                self.repository.records[self.workspace_id] = original
                self.events.clear()
                with self.assertRaises(WorkspaceConflict):
                    self.service.create(workspace_id=self.workspace_id, display_name="猫")
                self.assertEqual(self.events, ["get"])
                self.assertIs(self.repository.records[self.workspace_id], original)

    def test_existing_unregistered_target_does_not_acquire_an_intent(self) -> None:
        """目标预检失败时不先写入意图，后续请求不能认领该目录。"""
        self.directories.existing.add(self.workspace_id)
        with self.assertRaises(WorkspaceCreationError) as caught:
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertEqual(caught.exception.workspace_id, self.workspace_id)
        self.assertIsInstance(caught.exception.cause, FileExistsError)
        self.assertEqual(self.repository.records, {})
        self.assertEqual(self.events, ["get", "check_absent"])

    def test_read_is_metadata_only_and_retains_pending_records(self) -> None:
        """查询返回真实不存在或待提交意图，不调用目录或修复状态。"""
        self.assertIsNone(self.service.read(self.workspace_id))
        pending = WorkspaceRecord(self.workspace_id, "猫", None)
        self.repository.records[self.workspace_id] = pending
        self.assertIs(self.service.read(self.workspace_id), pending)
        self.assertEqual(self.events, ["get", "get"])

    def test_read_failure_propagates_and_create_does_not_treat_it_as_absence(self) -> None:
        """查询故障不得触发新意图，创建错误携带同一底层原因。"""
        cause = OSError("注册存储暂不可读")
        self.repository.fail_before["get"] = cause
        with self.assertRaises(OSError) as direct:
            self.service.read(self.workspace_id)
        self.assertIs(direct.exception, cause)
        with self.assertRaises(WorkspaceCreationError) as caught:
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIs(caught.exception.cause, cause)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertEqual(self.events, ["get", "get"])

    def test_intent_response_failure_requires_explicit_original_id_retry(self) -> None:
        """意图已记录但回包失败时停止，本次调用不自动重复提交。"""
        self.repository.fail_after["record_intent"] = OSError("意图应答丢失")
        with self.assertRaises(WorkspaceCreationError):
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertEqual(self.events, ["get", "check_absent", "record_intent"])
        self.assertIsNone(self.repository.records[self.workspace_id].registered_at)
        self.repository.fail_after.clear()
        self.events.clear()
        record = self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIsNotNone(record.registered_at)
        self.assertEqual(self.events, ["get", "prepare", "confirm_registration"])

    def test_prepare_failure_preserves_intent_for_explicit_retry(self) -> None:
        """目录失败保留原意图，再次显式创建不重新登记或预认领。"""
        self.directories.prepare_error = OSError("目录准备失败")
        with self.assertRaises(WorkspaceCreationError):
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIsNone(self.repository.records[self.workspace_id].registered_at)
        self.assertNotIn("confirm_registration", self.events)
        self.directories.prepare_error = None
        self.events.clear()
        self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertEqual(self.events, ["get", "prepare", "confirm_registration"])

    def test_commit_failure_preserves_directory_and_pending_intent(self) -> None:
        """注册提交前失败保留目录与意图，不补发成功或删除现场。"""
        self.repository.fail_before["confirm_registration"] = OSError("提交失败")
        with self.assertRaises(WorkspaceCreationError):
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIn(self.workspace_id, self.directories.existing)
        self.assertIsNone(self.repository.records[self.workspace_id].registered_at)
        self.repository.fail_before.clear()
        self.events.clear()
        self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertEqual(self.events, ["get", "prepare", "confirm_registration"])

    def test_commit_response_failure_recovers_by_reading_committed_record(self) -> None:
        """提交已完成但应答丢失时，下一次请求只核对已提交目录。"""
        self.repository.fail_after["confirm_registration"] = OSError("提交应答丢失")
        with self.assertRaises(WorkspaceCreationError):
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        committed = self.repository.records[self.workspace_id]
        self.assertIsNotNone(committed.registered_at)
        self.events.clear()
        self.assertIs(
            self.service.create(workspace_id=self.workspace_id, display_name="猫"), committed
        )
        self.assertEqual(self.events, ["get", "require_existing"])

    def test_missing_committed_directory_is_not_recreated(self) -> None:
        """已登记目录丢失仍保留登记事实，拒绝用空目录冒充原工作区。"""
        committed = self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.directories.existing.clear()
        self.events.clear()
        with self.assertRaises(WorkspaceCreationError) as caught:
            self.service.create(workspace_id=self.workspace_id, display_name="猫")
        self.assertIsInstance(caught.exception.cause, FileNotFoundError)
        self.assertIs(self.repository.records[self.workspace_id], committed)
        self.assertEqual(self.directories.existing, set())
        self.assertEqual(self.events, ["get", "require_existing"])

    def test_read_rejects_wrong_record_type_and_association(self) -> None:
        """不信任适配器回包声明，拒绝错误类型或其他工作区记录。"""
        for reply in (
            cast(WorkspaceRecord, object()),
            WorkspaceRecord(WorkspaceId(uuid4()), "猫", None),
        ):
            with self.subTest(reply=reply):
                self.repository.replies["get"] = reply
                with self.assertRaises(WorkspaceContractError):
                    self.service.read(self.workspace_id)

    def test_invalid_intent_reply_prevents_directory_prepare(self) -> None:
        """错误身份、改名或提前注册的意图回包都不能进入目录阶段。"""
        for reply in (
            WorkspaceRecord(WorkspaceId(uuid4()), "猫", None),
            WorkspaceRecord(self.workspace_id, "狗", None),
            WorkspaceRecord(self.workspace_id, "猫", _REGISTERED_AT),
        ):
            with self.subTest(reply=reply):
                self.repository.records.clear()
                self.events.clear()
                self.repository.replies["record_intent"] = reply
                with self.assertRaises(WorkspaceContractError):
                    self.service.create(workspace_id=self.workspace_id, display_name="猫")
                self.assertNotIn("prepare", self.events)
                self.assertNotIn("confirm_registration", self.events)

    def test_invalid_commit_reply_never_becomes_create_success(self) -> None:
        """提交回包必须关联原身份、原字段和非空首次注册时间。"""
        for reply in (
            WorkspaceRecord(WorkspaceId(uuid4()), "猫", _REGISTERED_AT),
            WorkspaceRecord(self.workspace_id, "狗", _REGISTERED_AT),
            WorkspaceRecord(self.workspace_id, "猫", None),
        ):
            with self.subTest(reply=reply):
                self.repository.records[self.workspace_id] = WorkspaceRecord(
                    self.workspace_id, "猫", None
                )
                self.repository.replies["confirm_registration"] = reply
                with self.assertRaises(WorkspaceContractError):
                    self.service.create(workspace_id=self.workspace_id, display_name="猫")


if __name__ == "__main__":
    unittest.main()
