# 文件信息：L1-01 工作区注册的唯一业务记录。
# 作用：复用 WorkspaceId，保存原始显示名与首次注册时间，供创建和查询用例消费。
# 边界：不保存路径、权限、活动选择或派生状态，不接触配置、存储及执行环境。
"""维护工作区注册字段与局部输入约束。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import final

from vet3d.identity import WorkspaceId


class WorkspaceContractError(ValueError):
    """表示工作区输入或适配器返回值违反当前注册契约。"""


class WorkspaceConflict(WorkspaceContractError):
    """表示同一工作区身份被提交了不同的原始创建字段。"""


def _validate_workspace_id(workspace_id: WorkspaceId) -> None:
    """保证创建与查询使用唯一的工作区身份类型。

    :param workspace_id: 调用边界提供的原工作区身份。
    :raises TypeError: 身份类别不正确。
    """
    if type(workspace_id) is not WorkspaceId:
        raise TypeError("工作区身份必须是 WorkspaceId")


@final
@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """保存创建意图或已提交注册，不把登记事实解释为目录或执行权限。

    :param id: 原工作区身份，同时作为创建幂等键。
    :param display_name: 可编码为 UTF-8 的非空白原始名称。
    :param registered_at: 首次提交的带时区 UTC 时间；空值仅表示创建意图。
    """

    id: WorkspaceId
    display_name: str
    registered_at: datetime | None

    def __post_init__(self) -> None:
        """核对字段类型和注册时间，不裁剪名称或派生另一份注册状态。

        :raises TypeError: 字段不符合其声明类型。
        :raises WorkspaceContractError: 名称空白、不可编码或注册时间不是带时区 UTC。
        """
        _validate_workspace_id(self.id)
        if type(self.display_name) is not str:
            raise TypeError("工作区显示名必须是字符串")
        if not self.display_name.strip():
            raise WorkspaceContractError("工作区显示名不得为空白")
        try:
            self.display_name.encode("utf-8")
        except UnicodeEncodeError as cause:
            raise WorkspaceContractError("工作区显示名必须可编码为 UTF-8") from cause
        if self.registered_at is not None:
            if type(self.registered_at) is not datetime:
                raise TypeError("注册时间必须是 datetime 或 None")
            if self.registered_at.utcoffset() != timedelta(0):
                raise WorkspaceContractError("注册时间必须是带时区 UTC 时间")
