# 文件信息：L0-01 的显式依赖装配。
# 演示启动与测试通过构造参数选择实现，没有运行模式枚举或新旧架构开关。
"""集中构造应用及其具体依赖。"""

from vet3d.adapters import DemoAdapter
from vet3d.application import DemoPort, DemoService


def assemble_application(*, port: DemoPort) -> DemoService:
    """用调用方明确提供的依赖构造应用，供测试与宿主复用。

    :param port: 本次装配选定的端口实现。
    :returns: 不依赖 CLI 或环境配置的应用服务。
    :raises TypeError: 必需依赖未提供时抛出。
    """
    return DemoService(port)


def build_demo_application() -> DemoService:
    """建立正常骨架的演示装配，不宣告产品生产能力就绪。

    :returns: 使用内存演示适配器的应用服务。
    """
    return assemble_application(port=DemoAdapter())
