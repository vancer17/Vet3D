# 文件信息：L0-04 报告完整性声明及交接校验。
# 作用：按报告契约单向计算缺项，并复用文件身份和执行产出关联。
# 边界：不读取或解析报告，不声明执行成功、文件存在或内容验收通过。
"""区分报告的完整性声明与执行、文件和业务质量事实。"""

from dataclasses import dataclass
from typing import final

from vet3d.artifacts import FileReference, validate_file_reference
from vet3d.identity import (
    ArtifactId,
    ArtifactIdentity,
    AttemptIdentity,
    AttemptOutput,
    JobIdentity,
    TaskIdentity,
    validate_attempt_output,
)

from ._checks import AssessmentContractError, require_text, require_text_set, require_type


@final
@dataclass(frozen=True, slots=True)
class ReportRequirements:
    """表达某个报告契约要求提供的章节，不充当环境配置。

    :param contract_ref: 业务拥有的报告契约引用，包含所需的版本区分。
    :param required_sections: 该契约要求的非空章节集合。
    """

    contract_ref: str
    required_sections: frozenset[str]

    def __post_init__(self) -> None:
        """核对完整性要求的结构，不选择或加载报告解析器。"""
        require_text(self.contract_ref)
        require_text_set(self.required_sections, nonempty=True)


@final
@dataclass(frozen=True, slots=True)
class ReportAssessment:
    """记录生产者对确切报告的章节声明，允许报告不完整。

    :param report_id: 报告所属的确切产物身份。
    :param contract_ref: 生产者据以判断章节的报告契约引用。
    :param sections: 生产者声明已取得的章节，可为空，不重复保存缺项或完整标记。
    """

    report_id: ArtifactId
    contract_ref: str
    sections: frozenset[str]

    def __post_init__(self) -> None:
        """核对声明结构，不验证报告字节、章节真实性或执行终态。"""
        require_type(self.report_id, ArtifactId)
        require_text(self.contract_ref)
        require_text_set(self.sections, nonempty=False)


def missing_report_sections(
    assessment: ReportAssessment, *, requirements: ReportRequirements,
) -> frozenset[str]:
    """从同一报告契约的要求和已知章节单向计算缺项。

    :param assessment: 生产者对报告章节的声明。
    :param requirements: 消费方当前要求的报告契约及章节。
    :returns: 尚未被声明覆盖的必需章节，不更新任何状态。
    :raises TypeError: 输入不是规定的具体记录。
    :raises AssessmentContractError: 报告声明使用了其他契约。
    """
    require_type(assessment, ReportAssessment)
    require_type(requirements, ReportRequirements)
    if assessment.contract_ref != requirements.contract_ref:
        raise AssessmentContractError("报告声明与所需报告契约不一致")
    return requirements.required_sections - assessment.sections


def require_complete_report(
    assessment: ReportAssessment, *, requirements: ReportRequirements,
) -> None:
    """要求报告章节声明覆盖必需项，不据此宣布业务内容合格。

    :param assessment: 需要交接的报告章节声明。
    :param requirements: 本次交接所需的报告契约及章节。
    :raises TypeError: 输入记录类型错误。
    :raises AssessmentContractError: 报告契约不符或仍有必需章节缺失。
    """
    if missing_report_sections(assessment, requirements=requirements):
        raise AssessmentContractError("报告缺少交接要求中的必需章节")


def validate_report_reference(
    assessment: ReportAssessment,
    *,
    reference: FileReference,
    artifact: ArtifactIdentity,
) -> None:
    """将报告声明关联到确切文件引用，不检查文件实际存在。

    :param assessment: 带有报告身份的章节声明。
    :param reference: 调用方提供的报告内容引用。
    :param artifact: 已解析的报告产物身份和工作区归属。
    :raises TypeError: 输入记录类型错误。
    :raises AssessmentContractError: 章节声明属于另一报告。
    :raises vet3d.artifacts.ArtifactContractError: 内容引用与产物身份不符。
    """
    require_type(assessment, ReportAssessment)
    validate_file_reference(reference, artifact=artifact)
    if assessment.report_id != reference.artifact_id:
        raise AssessmentContractError("报告声明与提供文件不是同一产物")


def validate_attempt_report(
    assessment: ReportAssessment,
    *,
    output: AttemptOutput,
    attempt: AttemptIdentity,
    job: JobIdentity,
    task: TaskIdentity,
    reference: FileReference,
    artifact: ArtifactIdentity,
) -> None:
    """核对报告属于所提供执行尝试，复用既有产出边及直接父链。

    :param assessment: 本次准备交接的报告章节声明。
    :param output: L0-02 已有的执行产出关联，不在报告内复制尝试字段。
    :param attempt: 需要关联报告的确切执行尝试。
    :param job: 该尝试直接所属的作业。
    :param task: 该作业直接所属的任务。
    :param reference: 报告的确切内容引用。
    :param artifact: 报告产物身份与工作区归属。
    :raises TypeError: 输入记录类型错误。
    :raises AssessmentContractError: 报告声明与所提供内容不匹配。
    :raises vet3d.artifacts.ArtifactContractError: 文件引用身份不匹配。
    :raises vet3d.identity.IdentityRelationError: 执行产出、父关联或工作区不匹配。
    """
    validate_report_reference(assessment, reference=reference, artifact=artifact)
    validate_attempt_output(output, attempt=attempt, job=job, task=task, artifact=artifact)
