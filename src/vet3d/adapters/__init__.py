# 文件信息：演示、生成链路替身和 L1-01 真实工作区存储适配器的公共入口。
# 边界：只导出明确实现，不进行插件发现、环境驱动能力切换或全局装配。
"""公开实际存储与显式合成替身，不宣告真实建模能力。"""

from .demo import DemoAdapter
from .reconstruction import (
    FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository, SyntheticArtifactAccess,
)
from .workspace_directories import LocalWorkspaceDirectories, ManagedWorkspaceRoot
from .workspace_repository import SqliteWorkspaceRepository, WorkspaceStorageError

__all__ = [
    "DemoAdapter", "FiveViewGenerator", "FourViewGenerator",
    "MemoryReconstructionRepository", "SyntheticArtifactAccess",
    "LocalWorkspaceDirectories", "ManagedWorkspaceRoot",
    "SqliteWorkspaceRepository", "WorkspaceStorageError",
]
