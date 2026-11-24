# 文件信息：演示、生成链路替身及真实工作区／文件／资源存储适配器的公共入口。
# 边界：只导出明确实现，不进行插件发现、环境驱动能力切换或全局装配。
"""公开实际存储与显式合成替身，不宣告真实建模能力。"""

from .demo import DemoAdapter
from .reconstruction import (
    FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository, SyntheticArtifactAccess,
)
from .workspace_directories import LocalWorkspaceDirectories, ManagedWorkspaceRoot
from .workspace_repository import SqliteWorkspaceRepository, WorkspaceStorageError
from .artifact_repository import SqliteArtifactRepository
from .staged_inputs import open_staged_input
from .artifact_files import LocalArtifactFileStore, validate_file_byte_limit
from .resource_io import ResourceLimits
from .resource_build import build_resource_bundle
from .resource_files import LocalResourceReader, LocalResourceStore

__all__ = [
    "DemoAdapter", "FiveViewGenerator", "FourViewGenerator",
    "MemoryReconstructionRepository", "SyntheticArtifactAccess",
    "LocalWorkspaceDirectories", "ManagedWorkspaceRoot",
    "SqliteWorkspaceRepository", "WorkspaceStorageError", "SqliteArtifactRepository",
    "open_staged_input",
    "LocalArtifactFileStore", "validate_file_byte_limit",
    "ResourceLimits", "build_resource_bundle",
    "LocalResourceReader", "LocalResourceStore",
]
