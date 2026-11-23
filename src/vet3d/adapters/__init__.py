# 文件信息：L0-01 演示及 L0-05 生成链路替身适配器的公共入口。
# 边界：只导出明确实现，不进行插件发现、环境驱动能力切换或全局装配。
"""公开内存实现与显式合成替身，不宣告真实建模能力。"""

from .demo import DemoAdapter
from .reconstruction import (
    FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository, SyntheticArtifactAccess,
)

__all__ = [
    "DemoAdapter", "FiveViewGenerator", "FourViewGenerator",
    "MemoryReconstructionRepository", "SyntheticArtifactAccess",
]
