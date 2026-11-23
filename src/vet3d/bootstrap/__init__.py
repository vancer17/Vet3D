# 文件信息：演示、生成契约探针及工作区／文件／资源存储的装配公共入口。
# 作用：构造应用、初始化日志及执行有期限调用；业务不反向导入本包。
# 边界：导入不执行探针，不读取环境，不选择真实供应商或建立持久记录。
"""公开显式依赖注入、控制台日志与有限宿主调用入口。"""

from .composition import assemble_application, build_demo_application
from .invocation import InvocationTimeoutError, invoke_demo
from .logging_setup import configure_logging
from .reconstruction import assemble_reconstruction, run_reconstruction_probe
from .workspaces import (
    WorkspaceBusyError, WorkspaceClosedError, WorkspaceFiles, WorkspaceRuntime, WorkspaceTimeoutError,
    initialize_workspaces, open_workspaces,
)
from .resources import (
    PinnedResources, ResourceBusyError, ResourceClosedError, ResourceRuntime, ResourceTimeoutError,
    initialize_resources, open_resources,
)

__all__ = [
    "InvocationTimeoutError", "assemble_application", "build_demo_application",
    "configure_logging", "invoke_demo",
    "assemble_reconstruction", "run_reconstruction_probe",
    "WorkspaceBusyError", "WorkspaceClosedError", "WorkspaceRuntime", "WorkspaceTimeoutError",
    "initialize_workspaces", "open_workspaces",
    "WorkspaceFiles",
    "PinnedResources", "ResourceBusyError", "ResourceClosedError", "ResourceRuntime", "ResourceTimeoutError",
    "initialize_resources", "open_resources",
]
