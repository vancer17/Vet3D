# 文件信息：L0-03 的工作区相对文件定位契约。
# 边界：仅核对路径文本；受管根解析、符号链接和真实文件归属留给 L1-02。
"""保存独立于字节内容的规范相对位置。"""

from dataclasses import dataclass
import re
from typing import final
import unicodedata

from vet3d.identity import ArtifactId

from ._checks import ArtifactContractError, _require_type, _require_utf8_text


@final
@dataclass(frozen=True, slots=True)
class WorkspaceRelativePath:
    """表示受管工作区内的规范相对 POSIX 路径文本。

    不修剪、归一化、展开环境变量或解析磁盘；历史绝对路径不是本类型。

    :param value: 非空、可编码为 UTF-8 的规范相对路径。
    """

    value: str

    def __post_init__(self) -> None:
        """拒绝绝对位置、非规范路径段和控制字符。

        :raises TypeError: 输入不是字符串。
        :raises ArtifactContractError: 路径不满足本项定位契约。
        """
        _require_utf8_text(self.value)
        if self.value.startswith("/") or "\\" in self.value:
            raise ArtifactContractError("文件位置必须是使用正斜杠的相对路径")
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", self.value) is not None:
            raise ArtifactContractError("文件位置不能以盘符或 URI 协议开头")
        if any(part in ("", ".", "..") for part in self.value.split("/")):
            raise ArtifactContractError("路径不能含空、当前目录或上级目录段")
        if any(unicodedata.category(character) == "Cc" for character in self.value):
            raise ArtifactContractError("路径不能包含控制字符")


@final
@dataclass(frozen=True, slots=True)
class WorkspaceFileLocation:
    """关联产物和受管相对位置，不重复保存工作区或内容摘要。

    :param artifact_id: 此位置应提供的产物身份。
    :param relative_path: 需要由后续存储边界解析的相对位置。
    """

    artifact_id: ArtifactId
    relative_path: WorkspaceRelativePath

    def __post_init__(self) -> None:
        """核对定位引用的身份和路径类型。

        :raises TypeError: 输入不是规定的具体身份或路径类型。
        """
        _require_type(self.artifact_id, ArtifactId)
        _require_type(self.relative_path, WorkspaceRelativePath)
