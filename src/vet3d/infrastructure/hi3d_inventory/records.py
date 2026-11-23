# 文件信息
# 定义盘点各来源共享的字节身份，以及发行清单唯一的文件记录结构。
"""只读盘点的文件记录类型。"""

from typing import Literal, NotRequired, TypedDict


class FileFingerprint(TypedDict):
    """表示一个文件的路径、字节数和 SHA-256。"""

    path: str
    size: int
    sha256: str


class InventoryRecord(FileFingerprint):
    """表示一条带来源和可选证据字段的发行清单记录。"""

    scope: Literal["prebuilt-skill", "runtime", "resources", "asar-member"]
    declared_digest: NotRequired[bool]
    source_path: NotRequired[str]
    package: NotRequired[str]
    package_source: NotRequired[str]
    member_path: NotRequired[str]
    offset: NotRequired[int]
    integrity_verified: NotRequired[bool]
    kind: NotRequired[str]
    execution_hint: NotRequired[str]
