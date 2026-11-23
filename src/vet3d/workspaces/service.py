# 文件信息：L1-01 工作区创建与查询的具体用例。
# 作用：按原身份协调预检、创建意图、目录准备和首次注册，保留可对账故障。
# 边界：同步且线程封闭；串行调用与取消等待由 Bootstrap 管理，不创建执行或验收事实。
"""通过窄端口完成有限本地恢复，不提供调度、授权或沙箱。"""

from vet3d.identity import WorkspaceId

from .ports import WorkspaceDirectories, WorkspaceRepository
from .records import (
    WorkspaceConflict,
    WorkspaceContractError,
    WorkspaceRecord,
    _validate_workspace_id,
)


class WorkspaceCreationError(RuntimeError):
    """携带创建失败的原身份和底层原因，便于调用方显式对账。"""

    def __init__(self, workspace_id: WorkspaceId, cause: Exception) -> None:
        """保留原身份及异常对象，不把失败解释为没有产生副作用。

        :param workspace_id: 失败操作的原工作区身份。
        :param cause: 端口操作报告的底层异常。
        """
        self.workspace_id = workspace_id
        self.cause = cause
        super().__init__(f"工作区创建未能确认完成：{workspace_id.value}")


class WorkspaceService:
    """由单一受信调用线程协调注册，不宣称直接多线程调用安全。

    :param repository: 创建用例拥有的注册仓储端口。
    :param directories: 创建用例拥有的受管目录端口。
    """

    def __init__(
        self, *, repository: WorkspaceRepository, directories: WorkspaceDirectories
    ) -> None:
        """接收装配入口提供的依赖，不选择具体存储或读取环境配置。

        :param repository: 保存原创建字段与首次注册时间的仓储。
        :param directories: 执行目标预检与受管目录准备的适配器。
        :raises TypeError: 必需依赖为空。
        """
        if repository is None or directories is None:
            raise TypeError("工作区服务需要仓储与目录端口")
        self._repository = repository
        self._directories = directories

    def create(self, *, workspace_id: WorkspaceId, display_name: str) -> WorkspaceRecord:
        """创建或沿原身份有限续做，只在目录核对和注册提交后返回。

        :param workspace_id: 首次调用前已保留的工作区身份。
        :param display_name: 与原请求精确相同的显示名。
        :returns: 原身份对应的已提交注册记录。
        :raises TypeError: 输入字段类型不正确。
        :raises WorkspaceContractError: 输入或适配器回包违反契约。
        :raises WorkspaceConflict: 同一身份被提交了不同名称。
        :raises WorkspaceCreationError: I/O 失败，原意图或注册可能已经提交。
        """
        requested = WorkspaceRecord(workspace_id, display_name, None)
        try:
            record = self.read(workspace_id)
            if record is not None:
                self._require_original_fields(record, requested)
                if record.registered_at is not None:
                    self._directories.require_existing(workspace_id)
                    return record
            else:
                self._directories.check_absent(workspace_id)
                record = self._validate_record(
                    self._repository.record_intent(workspace_id, display_name), workspace_id
                )
                self._require_original_fields(record, requested)
                if record.registered_at is not None:
                    raise WorkspaceContractError("新创建意图不能提前包含注册提交时间")
            self._directories.prepare(workspace_id)
            committed = self._validate_record(
                self._repository.confirm_registration(workspace_id), workspace_id
            )
            self._require_original_fields(committed, requested)
            if committed.registered_at is None:
                raise WorkspaceContractError("注册确认必须返回首次提交时间")
            return committed
        except WorkspaceContractError:
            raise
        except Exception as cause:
            raise WorkspaceCreationError(workspace_id, cause) from cause

    def read(self, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
        """读取登记元数据，不核对目录，也不把读取故障解释为不存在。

        :param workspace_id: 要核对的原工作区身份。
        :returns: 原记录或明确不存在的空值；未提交记录不授予文件访问权。
        :raises TypeError: 传入的身份类别不正确。
        :raises WorkspaceContractError: 仓储返回错误身份或记录类型。
        """
        _validate_workspace_id(workspace_id)
        record = self._repository.get(workspace_id)
        if record is None:
            return None
        return self._validate_record(record, workspace_id)

    @staticmethod
    def _validate_record(record: object, workspace_id: WorkspaceId) -> WorkspaceRecord:
        """在使用回包前核对其唯一记录类型及请求关联。

        :param record: 仓储返回的记录。
        :param workspace_id: 本次调用绑定的工作区身份。
        :returns: 与原身份一致的记录。
        :raises WorkspaceContractError: 回包类型或身份不符合契约。
        """
        if type(record) is not WorkspaceRecord:
            raise WorkspaceContractError("仓储必须返回 WorkspaceRecord")
        if record.id != workspace_id:
            raise WorkspaceContractError("仓储回包的工作区身份与请求不一致")
        return record

    @staticmethod
    def _require_original_fields(record: WorkspaceRecord, requested: WorkspaceRecord) -> None:
        """精确核对原创建字段，禁止同身份改参或静默名称规范化。

        :param record: 已读取或由仓储回传的记录。
        :param requested: 当前请求携带的原字段。
        :raises WorkspaceConflict: 名称与原字段不一致。
        """
        if record.display_name != requested.display_name:
            raise WorkspaceConflict("同一工作区身份不能更改原始显示名")
