# 文件信息：L1-01 工作区注册包公共入口。
# 作用：向装配和后续消费者公开唯一记录、窄 I/O 端口与具体用例。
# 边界：导入不探测环境、不访问存储，不授予工作区文件或执行权限。
"""公开工作区创建和登记查询所需的稳定契约。"""

from .ports import WorkspaceDirectories, WorkspaceRepository
from .records import WorkspaceConflict, WorkspaceContractError, WorkspaceRecord
from .service import WorkspaceCreationError, WorkspaceService

__all__ = [
    "WorkspaceConflict",
    "WorkspaceContractError",
    "WorkspaceCreationError",
    "WorkspaceDirectories",
    "WorkspaceRecord",
    "WorkspaceRepository",
    "WorkspaceService",
]
