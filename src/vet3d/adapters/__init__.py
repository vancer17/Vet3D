# 文件信息：L0-01 演示适配器的公共入口。
# 本包只导出明确的演示实现，不进行插件发现或环境驱动的能力切换。
"""公开无外部依赖的演示适配器。"""

from .demo import DemoAdapter

__all__ = ["DemoAdapter"]
