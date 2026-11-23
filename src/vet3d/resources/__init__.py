# 文件信息：L1-03 受管资源身份、清单与读取端口的公共入口。
# 作用：集中导出唯一冻结记录、严格 JSON 边界及实际消费所需端口。
# 边界：导入不读取环境、安装资源、注册工具或执行脚本。
"""公开与工作区产物分离的固定资源快照契约。"""

from .manifest import fingerprint_bytes, parse_manifest, parse_resource_spec, serialize_manifest
from .ports import ResourceReader
from .records import (
    DocumentResource, InterpreterRequirement, ResourceContractError,
    ResourceDefinition, ResourceDescription, ResourceFile, ResourceKey,
    ResourceManifest, ResourceMetadata, ResourcePath, ResourceReference,
    ScriptResource, TemplateResource,
)

__all__ = [
    "DocumentResource", "InterpreterRequirement", "ResourceContractError",
    "ResourceDefinition", "ResourceDescription", "ResourceFile", "ResourceKey",
    "ResourceManifest", "ResourceMetadata", "ResourcePath", "ResourceReader",
    "ResourceReference", "ScriptResource", "TemplateResource", "fingerprint_bytes",
    "parse_manifest", "parse_resource_spec", "serialize_manifest",
]
