# 文件信息：L0-01 应用包的公共入口。
# 统一导出演示契约、消费方端口和服务，跨包调用只依赖本入口。
"""公开一次演示调用所需的唯一契约和应用服务。"""

from .demo import (
    DemoPort,
    DemoReply,
    DemoRequest,
    DemoService,
    InvalidDemoReply,
    InvalidDemoRequest,
)

__all__ = [
    "DemoPort", "DemoReply", "DemoRequest", "DemoService",
    "InvalidDemoReply", "InvalidDemoRequest",
]
