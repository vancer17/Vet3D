# 文件信息：L0-03 文件内容、位置和来源契约的公共入口。
# 边界：公开唯一具体类型和纯校验，不暴露 I/O、配置、状态或重复身份。
"""公开可独立使用的文件引用与内容交接契约。"""

from ._checks import ArtifactContractError
from .content import ContentFingerprint, FileReference
from .locations import WorkspaceFileLocation, WorkspaceRelativePath
from .provenance import ImportOrigin
from .validation import (
    validate_content_binding, validate_content_observation, validate_file_location,
    validate_file_reference, validate_file_set, validate_import_origin,
)

__all__ = [
    "ArtifactContractError", "ContentFingerprint", "FileReference", "ImportOrigin",
    "WorkspaceFileLocation", "WorkspaceRelativePath", "validate_content_binding",
    "validate_content_observation", "validate_file_location", "validate_file_reference",
    "validate_file_set", "validate_import_origin",
]
