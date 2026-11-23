# 文件信息：L0-04 文件观察事实及内容交接守卫。
# 作用：分别表达存在、缺失和访问不可用，允许保留与预期不符的观察内容。
# 边界：只核对传入记录，不读取文件、计算摘要或推断观察的新鲜度与质量。
"""分开记录文件观察事实和是否满足预期内容的交接条件。"""

from dataclasses import dataclass
from typing import final

from vet3d.identity import ArtifactIdentity

from ._checks import ArtifactContractError, _require_type, _require_utf8_text
from .content import ContentFingerprint, FileReference
from .locations import WorkspaceFileLocation
from .validation import (
    validate_content_observation, validate_file_location, validate_file_reference,
)


@final
@dataclass(frozen=True, slots=True)
class FilePresent:
    """记录调用方报告的文件位置及实际观察到的内容描述。

    观察指纹可以与预期不符；构造记录不证明本包已经读取文件。

    :param location: 已观察的位置，包含唯一的产物身份引用。
    :param observed: 调用方提供的观察指纹，不重复保存预期内容。
    """

    location: WorkspaceFileLocation
    observed: ContentFingerprint

    def __post_init__(self) -> None:
        """核对存在记录的具体位置和观察指纹类型。

        :raises TypeError: 位置或指纹类型不符合契约。
        """
        _require_type(self.location, WorkspaceFileLocation)
        _require_type(self.observed, ContentFingerprint)


@final
@dataclass(frozen=True, slots=True)
class FileMissing:
    """记录调用方已确认某个位置缺少文件。

    访问失败和没有观察记录都不能被转换为文件缺失。

    :param location: 已确认缺失的位置及产物身份引用。
    """

    location: WorkspaceFileLocation

    def __post_init__(self) -> None:
        """核对缺失记录的位置类型。

        :raises TypeError: 位置不是规定的具体类型。
        """
        _require_type(self.location, WorkspaceFileLocation)


@final
@dataclass(frozen=True, slots=True)
class FileUnavailable:
    """记录本次访问未能取得文件事实及其原因。

    不可用不声明文件存在或缺失，也不抹除其他观察记录。

    :param location: 本次尝试观察的位置及产物身份引用。
    :param reason: 非空白 UTF-8 原因文字，保留原文。
    """

    location: WorkspaceFileLocation
    reason: str

    def __post_init__(self) -> None:
        """核对位置类型及可诊断的原因文字，不改写输入。

        :raises TypeError: 位置或原因类型错误。
        :raises ArtifactContractError: 原因为空白或无法编码为 UTF-8。
        """
        _require_type(self.location, WorkspaceFileLocation)
        _require_utf8_text(self.reason)
        if not self.reason.strip():
            raise ArtifactContractError("文件不可用原因不能是空白文本")


type FileObservation = FilePresent | FileMissing | FileUnavailable


def validate_file_observation(
    observation: FileObservation,
    *,
    reference: FileReference,
    artifact: ArtifactIdentity,
) -> None:
    """核对观察、预期引用和产物身份关联，保留不匹配内容的事实。

    :param observation: 本次显式提供的文件观察变体。
    :param reference: 该产物预期绑定的内容引用。
    :param artifact: 已解析的产物身份与工作区归属记录。
    :raises TypeError: 观察或关联记录不是规定的具体类型。
    :raises ArtifactContractError: 位置、引用与产物身份不匹配。
    """
    if type(observation) not in (FilePresent, FileMissing, FileUnavailable):
        raise TypeError("文件观察必须使用已定义的具体变体")
    validate_file_reference(reference, artifact=artifact)
    validate_file_location(observation.location, reference=reference)


def require_matching_file(
    observation: FileObservation,
    *,
    reference: FileReference,
    artifact: ArtifactIdentity,
) -> None:
    """仅放行身份一致且观察内容符合预期的存在记录。

    本函数只比较调用方提供的事实，不执行文件访问或刷新旧观察。

    :param observation: 交接所依据的明确文件观察。
    :param reference: 下游所需的确切内容引用。
    :param artifact: 已解析的产物身份与工作区归属记录。
    :raises TypeError: 观察或关联记录不是规定的具体类型。
    :raises ArtifactContractError: 身份不匹配、文件未确认存在或内容不匹配。
    """
    validate_file_observation(observation, reference=reference, artifact=artifact)
    if not isinstance(observation, FilePresent):
        raise ArtifactContractError("文件交接需要明确的存在观察")
    validate_content_observation(reference, observed=observation.observed)
