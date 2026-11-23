# 文件信息：L0-03 文件契约、L0-04 文件观察及 L0-05 产物访问端口的公共入口。
# 边界：公开唯一具体类型、纯校验和访问接口，不执行 I/O 或装配具体存储。
"""公开文件引用、内容交接契约及消费方访问端口。"""

from ._checks import ArtifactContractError
from .content import ContentFingerprint, FileReference
from .locations import WorkspaceFileLocation, WorkspaceRelativePath
from .observations import (
    FileMissing, FileObservation, FilePresent, FileUnavailable, require_matching_file,
    validate_file_observation,
)
from .ports import ArtifactAccess, LocatedArtifact
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
    "FileMissing", "FileObservation", "FilePresent", "FileUnavailable",
    "require_matching_file", "validate_file_observation",
    "ArtifactAccess", "LocatedArtifact",
]
