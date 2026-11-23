# 文件信息：L0-03 的不可变字节内容描述及文件引用。
# 边界：只保存调用方声明的摘要与长度，不计算文件摘要，也不证明文件存在。
"""以已有产物身份绑定一份确切内容描述。"""

from dataclasses import dataclass
import re
from typing import final

from vet3d.identity import ArtifactId

from ._checks import ArtifactContractError, _require_type


@final
@dataclass(frozen=True, slots=True)
class ContentFingerprint:
    """描述原始字节的 SHA-256 与长度，不引入内容版本身份。

    :param sha256: 六十四个小写十六进制字符组成的完整摘要。
    :param byte_size: 非负字节数，零长度文件允许表达。
    """

    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        """检查摘要和长度结构，不为声明值补造文件读取证据。

        :raises TypeError: 摘要不是字符串，或长度不是非布尔整数。
        :raises ArtifactContractError: 摘要格式无效或长度为负数。
        """
        _require_type(self.sha256, str)
        _require_type(self.byte_size, int)
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ArtifactContractError("SHA-256 必须是六十四个小写十六进制字符")
        if self.byte_size < 0:
            raise ArtifactContractError("字节数不能为负数")


@final
@dataclass(frozen=True, slots=True)
class FileReference:
    """将产物身份绑定到一份不可变的内容描述。

    内容变化应采用新的产物身份；本记录不保存工作区、位置或来源边。

    :param artifact_id: L0-02 已定义的确切产物身份。
    :param content: 此身份预期指向的原始字节描述。
    """

    artifact_id: ArtifactId
    content: ContentFingerprint

    def __post_init__(self) -> None:
        """核对文件引用的身份和内容类型。

        :raises TypeError: 输入不是规定的具体身份或内容类型。
        """
        _require_type(self.artifact_id, ArtifactId)
        _require_type(self.content, ContentFingerprint)
