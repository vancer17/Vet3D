# 文件信息：L0-04 具有用途和策略范围的验收结论。
# 作用：保存生产者明确提供的结论，并校验特定交接要求。
# 边界：目标和证据引用由既有身份记录拥有；本模块不评估图像或模型质量。
"""记录验收结果与必要交接约束，不从执行或报告成功推导通过。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import final

from vet3d.identity import (
    AcceptanceId,
    AcceptanceIdentity,
    ArtifactSetTarget,
    EvidenceIdentity,
    ModelVersionTarget,
    ReviewTarget,
    validate_acceptance,
)

from ._checks import AssessmentContractError, require_text, require_text_set, require_type


class AcceptanceVerdict(StrEnum):
    """表达生产者明确声明的验收结论，不充当执行状态或能力配置。"""

    # 生产者声明本次范围内的内容已通过验收。
    PASSED = "passed"
    # 生产者声明内容未满足本次验收要求。
    REJECTED = "rejected"
    # 已有证据不足以形成确定的内容通过结论。
    INSUFFICIENT = "insufficient"
    # 生产者声明当前不能提供本次要求的验收能力。
    UNSUPPORTED = "unsupported"


@final
@dataclass(frozen=True, slots=True)
class AcceptanceScope:
    """表达消费方此次交接要求的用途、策略及检查范围。

    :param purpose: 验收用途，不隐含全部动物建模或动画质量。
    :param policy_ref: 冻结业务策略的引用，包含所需的版本区分。
    :param required_checks: 此次交接要求覆盖的非空检查集合。
    """

    purpose: str
    policy_ref: str
    required_checks: frozenset[str]

    def __post_init__(self) -> None:
        """核对验收范围的结构，不读取策略配置或运行检查算法。"""
        require_text(self.purpose)
        require_text(self.policy_ref)
        require_text_set(self.required_checks, nonempty=True)


@final
@dataclass(frozen=True, slots=True)
class AcceptanceOutcome:
    """记录某条验收的明确结论及生产者声明的覆盖范围。

    :param acceptance_id: 拥有目标和证据引用的既有验收身份。
    :param purpose: 生产者实际作出本次判断的用途。
    :param policy_ref: 生产者实际使用的业务策略引用。
    :param covered_checks: 生产者声明已覆盖的检查项，可为空。
    :param verdict: 生产者给出的唯一结论，不从覆盖或证据数量计算。
    :param explanation: 保留诊断所需的结论说明。
    """

    acceptance_id: AcceptanceId
    purpose: str
    policy_ref: str
    covered_checks: frozenset[str]
    verdict: AcceptanceVerdict
    explanation: str

    def __post_init__(self) -> None:
        """核对结论声明结构，允许覆盖不足或其他不满足交接的事实。"""
        require_type(self.acceptance_id, AcceptanceId)
        require_text(self.purpose)
        require_text(self.policy_ref)
        require_text_set(self.covered_checks, nonempty=False)
        require_type(self.verdict, AcceptanceVerdict)
        require_text(self.explanation)


def validate_acceptance_outcome(
    outcome: AcceptanceOutcome,
    *,
    acceptance: AcceptanceIdentity,
    evidence: tuple[EvidenceIdentity, ...],
) -> None:
    """核对结论所属验收和已关联证据，不要求结论通过或覆盖充分。

    目标实体的实际解析仍由 L0-02 对应目标校验入口负责；此函数不读取
    证据内容，也不把存在的证据数量解释为质量合格。

    :param outcome: 生产者给出的验收结论。
    :param acceptance: 拥有确切目标及证据引用的验收记录。
    :param evidence: 恰好覆盖已关联证据身份的记录，可为空。
    :raises TypeError: 输入记录类型错误。
    :raises AssessmentContractError: 结论属于另一条验收记录。
    :raises vet3d.identity.IdentityRelationError: 证据集合或观察目标不匹配。
    """
    require_type(outcome, AcceptanceOutcome)
    require_type(acceptance, AcceptanceIdentity)
    if outcome.acceptance_id != acceptance.id:
        raise AssessmentContractError("验收结论与提供的验收身份不一致")
    validate_acceptance(acceptance, evidence=evidence)


def require_accepted(
    outcome: AcceptanceOutcome,
    *,
    target: ReviewTarget,
    scope: AcceptanceScope,
    acceptance: AcceptanceIdentity,
    evidence: tuple[EvidenceIdentity, ...],
) -> None:
    """限制一次交接使用的验收结论，不产生或补齐质量判断。

    调用方必须先取得真实评审结论。本守卫只核对用途与策略、显式通过、
    确切对象、所需覆盖及非空关联证据，不证明生产者判断正确或证据已经充分。

    :param outcome: 生产者明确提供的结论。
    :param target: 消费者此次要放行的确切对象，不由验收记录反向选择。
    :param scope: 当前交接的冻结业务要求。
    :param acceptance: 结论所属的验收身份、目标及证据引用。
    :param evidence: 本次明确提供的证据身份与观察目标。
    :raises TypeError: 输入记录类型错误。
    :raises AssessmentContractError: 对象或范围不符、未明确通过、覆盖不足或没有证据。
    :raises vet3d.identity.IdentityRelationError: 已关联证据集合或目标不匹配。
    """
    require_type(scope, AcceptanceScope)
    if type(target) not in (ArtifactSetTarget, ModelVersionTarget):
        raise TypeError("交接对象必须是文件集合或确切模型版本")
    validate_acceptance_outcome(outcome, acceptance=acceptance, evidence=evidence)
    if acceptance.target != target:
        raise AssessmentContractError("验收结论不属于当前需要放行的确切对象")
    if outcome.purpose != scope.purpose or outcome.policy_ref != scope.policy_ref:
        raise AssessmentContractError("验收结论不属于当前要求的用途与策略")
    if outcome.verdict is not AcceptanceVerdict.PASSED:
        raise AssessmentContractError("验收没有明确声明通过")
    if not scope.required_checks <= outcome.covered_checks:
        raise AssessmentContractError("验收声明未覆盖本次要求的全部检查项")
    if not acceptance.evidence_ids:
        raise AssessmentContractError("通过交接必须有关联到确切目标的证据")
