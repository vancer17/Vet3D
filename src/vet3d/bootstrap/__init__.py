# 文件信息：L0-01 装配与调用生命周期的公共入口。
# 宿主通过此包构造应用、初始化日志和执行有期限调用；业务不反向导入本包。
"""公开宿主装配、基础日志及单次调用入口。"""

from .composition import assemble_application, build_demo_application
from .invocation import InvocationTimeoutError, invoke_demo
from .logging_setup import configure_logging

__all__ = [
    "InvocationTimeoutError", "assemble_application", "build_demo_application",
    "configure_logging", "invoke_demo",
]
