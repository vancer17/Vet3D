# 文件信息：L0-03 文件引用、内容、定位和出处的纯交接校验。
# 边界：只核对显式传入值，不读取文件、不创建状态库、不判定文件业务质量。
"""核对调用方已经提供的确切身份和内容声明。"""

from vet3d.identity import ArtifactId, ArtifactIdentity

from ._checks import ArtifactContractError, _require_type
from .content import ContentFingerprint, FileReference
from .locations import WorkspaceFileLocation
from .provenance import ImportOrigin


def _require_artifact_id(actual: ArtifactId, expected: ArtifactId) -> None:
    """核对两个已校验结构中的产物身份，不用内容或名称代替身份。

    :param actual: 当前引用声明的产物身份。
    :param expected: 对照记录的确切产物身份。
    :raises ArtifactContractError: 两个引用不属于同一产物。
    """
    if actual != expected:
        raise ArtifactContractError("引用与提供记录的产物身份不匹配")


def validate_file_reference(reference: FileReference, *, artifact: ArtifactIdentity) -> None:
    """核对文件引用与产物归属记录的确切身份，不验证外部文件。

    :param reference: 需要交接的内容引用。
    :param artifact: 调用方已解析的产物身份及工作区归属。
    :raises TypeError: 输入记录类型错误。
    :raises ArtifactContractError: 引用不属于给定产物。
    """
    _require_type(reference, FileReference)
    _require_type(artifact, ArtifactIdentity)
    _require_artifact_id(reference.artifact_id, artifact.id)


def validate_content_binding(existing: FileReference, candidate: FileReference) -> None:
    """核对同一产物的内容绑定没有改变，不维护持久绑定历史。

    :param existing: 调用方提供的既有内容绑定。
    :param candidate: 声称仍为同一产物的候选绑定。
    :raises TypeError: 输入不是文件引用。
    :raises ArtifactContractError: 产物身份或内容描述不一致。
    """
    _require_type(existing, FileReference)
    _require_type(candidate, FileReference)
    _require_artifact_id(candidate.artifact_id, existing.artifact_id)
    if candidate.content != existing.content:
        raise ArtifactContractError("同一产物身份不能重新绑定不同内容")


def validate_content_observation(
    reference: FileReference, *, observed: ContentFingerprint,
) -> None:
    """比较传入的预期与观测指纹，不声称已经计算实际文件摘要。

    :param reference: 包含预期字节描述的文件引用。
    :param observed: 调用方显式提供的观测描述。
    :raises TypeError: 输入记录类型错误。
    :raises ArtifactContractError: 摘要或字节数不匹配。
    """
    _require_type(reference, FileReference)
    _require_type(observed, ContentFingerprint)
    if observed != reference.content:
        raise ArtifactContractError("传入的内容观测与预期摘要或字节数不匹配")


def validate_file_location(
    location: WorkspaceFileLocation, *, reference: FileReference,
) -> None:
    """核对定位引用的产物身份，不解析受管根或验证真实路径归属。

    :param location: 待交接的受管相对定位引用。
    :param reference: 该位置预期提供的确切文件引用。
    :raises TypeError: 输入记录类型错误。
    :raises ArtifactContractError: 定位与内容引用的产物身份不同。
    """
    _require_type(location, WorkspaceFileLocation)
    _require_type(reference, FileReference)
    _require_artifact_id(location.artifact_id, reference.artifact_id)


def validate_import_origin(origin: ImportOrigin, *, reference: FileReference) -> None:
    """核对导入出处所属的产物，不解析出处文本或验证其真实性。

    :param origin: 实际已知的导入出处说明。
    :param reference: 此说明所属的确切文件引用。
    :raises TypeError: 输入记录类型错误。
    :raises ArtifactContractError: 出处与内容引用的产物身份不同。
    """
    _require_type(origin, ImportOrigin)
    _require_type(reference, FileReference)
    _require_artifact_id(origin.artifact_id, reference.artifact_id)


def validate_file_set(
    references: tuple[FileReference, ...], *, artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对文件引用与产物记录的精确集合，不替代业务作用域校验。

    文件集合可以为空，也可以包含不同工作区的记录；调用方需要限定
    任务范围或观察目标时，应使用相应业务约束及 L0-02 目标校验。

    :param references: 本次交接的文件引用元组。
    :param artifacts: 恰好对应引用的已解析产物记录元组。
    :raises TypeError: 容器或成员不是规定的具体类型。
    :raises ArtifactContractError: 记录缺失、多余、重复或身份不匹配。
    """
    _require_type(references, tuple)
    _require_type(artifacts, tuple)
    reference_index: dict[ArtifactId, FileReference] = {}
    for reference in references:
        _require_type(reference, FileReference)
        if reference.artifact_id in reference_index:
            raise ArtifactContractError("提供的文件引用含重复产物身份")
        reference_index[reference.artifact_id] = reference
    artifact_index: dict[ArtifactId, ArtifactIdentity] = {}
    for artifact in artifacts:
        _require_type(artifact, ArtifactIdentity)
        if artifact.id in artifact_index:
            raise ArtifactContractError("提供的产物记录含重复身份")
        artifact_index[artifact.id] = artifact
    if reference_index.keys() != artifact_index.keys():
        raise ArtifactContractError("文件引用与产物记录的身份集合不一致")
    for artifact_id, reference in reference_index.items():
        validate_file_reference(reference, artifact=artifact_index[artifact_id])
