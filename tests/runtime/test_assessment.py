# 文件信息：L0-04 报告与验收交接契约测试。
# 作用：验证报告缺项派生、既有身份关联以及有用途范围的显式验收结论。
# 边界：使用内存声明和合成摘要，不证明报告已解析、证据充分或动物质量合格。
"""允许记录不完整事实，仅在具体交接守卫中拒绝缺少的必要条件。"""

from hashlib import sha256
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileReference
from vet3d.assessment import (
    AcceptanceOutcome,
    AcceptanceScope,
    AcceptanceVerdict,
    AssessmentContractError,
    ReportAssessment,
    ReportRequirements,
    missing_report_sections,
    require_accepted,
    require_complete_report,
    validate_acceptance_outcome,
    validate_attempt_report,
    validate_report_reference,
)
from vet3d.identity import (
    AcceptanceId,
    AcceptanceIdentity,
    ArtifactId,
    ArtifactIdentity,
    ArtifactSetTarget,
    AttemptId,
    AttemptIdentity,
    AttemptOutput,
    EvidenceId,
    EvidenceIdentity,
    IdentityRelationError,
    JobId,
    JobIdentity,
    ModelFamilyId,
    ModelVersionId,
    ModelVersionIdentity,
    ModelVersionTarget,
    ReviewTarget,
    TaskId,
    TaskIdentity,
    WorkspaceId,
)


class ReportAssessmentTests(unittest.TestCase):
    """验证报告声明的确定性关系，不将章节齐全当作执行或质量成功。"""

    def setUp(self) -> None:
        """准备同区执行链以及一份没有读取真实文件的报告声明。"""
        self.task = TaskIdentity(id=TaskId(uuid4()), workspace_id=WorkspaceId(uuid4()))
        self.job = JobIdentity(id=JobId(uuid4()), task_id=self.task.id)
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id)
        self.artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.task.workspace_id)
        self.reference = FileReference(
            artifact_id=self.artifact.id,
            content=ContentFingerprint(sha256=sha256(b"report").hexdigest(), byte_size=6),
        )
        self.requirements = ReportRequirements(
            contract_ref="mesh-report/v1", required_sections=frozenset({"summary", "checks"})
        )
        self.assessment = ReportAssessment(
            report_id=self.artifact.id,
            contract_ref=self.requirements.contract_ref,
            sections=frozenset({"summary", "checks", "diagnostics"}),
        )

    def test_missing_sections_are_derived_without_rejecting_incomplete_facts(self) -> None:
        """不完整报告可记录，缺项由要求单向计算，完整报告允许附加章节。"""
        partial = ReportAssessment(
            report_id=self.artifact.id,
            contract_ref=self.requirements.contract_ref,
            sections=frozenset({"summary"}),
        )
        self.assertEqual(missing_report_sections(partial, requirements=self.requirements), frozenset({"checks"}))
        with self.assertRaises(AssessmentContractError):
            require_complete_report(partial, requirements=self.requirements)
        require_complete_report(self.assessment, requirements=self.requirements)
        empty = ReportAssessment(
            report_id=self.artifact.id, contract_ref=self.requirements.contract_ref, sections=frozenset()
        )
        self.assertEqual(missing_report_sections(empty, requirements=self.requirements), self.requirements.required_sections)

    def test_complete_sections_from_another_contract_cannot_be_reused(self) -> None:
        """章节名称相同不能使旧报告契约满足另一契约。"""
        another = ReportRequirements(contract_ref="mesh-report/v2", required_sections=self.requirements.required_sections)
        with self.assertRaises(AssessmentContractError):
            missing_report_sections(self.assessment, requirements=another)
        with self.assertRaises(AssessmentContractError):
            require_complete_report(self.assessment, requirements=another)

    def test_report_reference_preserves_exact_identity_and_file_errors(self) -> None:
        """报告关联必须匹配确切身份，底层文件契约错误保持原类型。"""
        validate_report_reference(self.assessment, reference=self.reference, artifact=self.artifact)
        unrelated = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.task.workspace_id)
        with self.assertRaises(ArtifactContractError):
            validate_report_reference(self.assessment, reference=self.reference, artifact=unrelated)
        wrong_report = ReportAssessment(
            report_id=unrelated.id, contract_ref=self.requirements.contract_ref, sections=self.assessment.sections
        )
        with self.assertRaises(AssessmentContractError):
            validate_report_reference(wrong_report, reference=self.reference, artifact=self.artifact)

    def test_attempt_report_reuses_existing_output_and_rejects_stale_or_foreign_records(self) -> None:
        """报告沿已有产出边归属原尝试，旧尝试和跨工作区报告均不能替代。"""
        output = AttemptOutput(attempt_id=self.attempt.id, artifact_id=self.artifact.id)
        validate_attempt_report(
            self.assessment,
            output=output,
            attempt=self.attempt,
            job=self.job,
            task=self.task,
            reference=self.reference,
            artifact=self.artifact,
        )
        with self.assertRaises(IdentityRelationError):
            validate_attempt_report(
                self.assessment,
                output=output,
                attempt=AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id),
                job=self.job,
                task=self.task,
                reference=self.reference,
                artifact=self.artifact,
            )
        with self.assertRaises(IdentityRelationError):
            validate_attempt_report(
                self.assessment,
                output=output,
                attempt=self.attempt,
                job=self.job,
                task=self.task,
                reference=self.reference,
                artifact=ArtifactIdentity(id=self.artifact.id, workspace_id=WorkspaceId(uuid4())),
            )

    def test_report_contract_rejects_wrong_types_empty_requirements_and_invalid_text(self) -> None:
        """拒绝可变集合、错类身份和无效章节，不自动修正契约文字。"""
        with self.assertRaises(TypeError):
            ReportAssessment(
                report_id=cast(ArtifactId, self.task.id), contract_ref="report/v1", sections=frozenset()
            )
        with self.assertRaises(TypeError):
            ReportRequirements(contract_ref="report/v1", required_sections=cast(frozenset[str], {"summary"}))
        with self.assertRaises(AssessmentContractError):
            ReportRequirements(contract_ref="report/v1", required_sections=frozenset())
        for invalid_text in (" ", "\ud800"):
            with self.subTest(text=repr(invalid_text)):
                with self.assertRaises(AssessmentContractError):
                    ReportAssessment(report_id=self.artifact.id, contract_ref=invalid_text, sections=frozenset())
                with self.assertRaises(AssessmentContractError):
                    ReportRequirements(contract_ref="report/v1", required_sections=frozenset({invalid_text}))


class AcceptanceOutcomeTests(unittest.TestCase):
    """验证显式结论及其交接范围，不从完整报告或检查数量制造通过。"""

    def setUp(self) -> None:
        """准备候选目标、关联证据以及一个明确的静态外观验收范围。"""
        target = ArtifactSetTarget(artifact_ids=frozenset({ArtifactId(uuid4())}))
        self.evidence = EvidenceIdentity(id=EvidenceId(uuid4()), target=target)
        self.acceptance = AcceptanceIdentity(
            id=AcceptanceId(uuid4()), target=target, evidence_ids=frozenset({self.evidence.id})
        )
        self.scope = AcceptanceScope(
            purpose="静态外观", policy_ref="appearance/v1", required_checks=frozenset({"shape", "texture"})
        )

    def _make_outcome(
        self,
        verdict: AcceptanceVerdict,
        *,
        covered_checks: frozenset[str] | None = None,
    ) -> AcceptanceOutcome:
        """生成同一验收身份的测试声明，不运行实际质量检查。

        :param verdict: 测试需要保存的生产者结论。
        :param covered_checks: 显式覆盖集合；省略时使用当前要求。
        :returns: 可由交接守卫核对的冻结结论。
        """
        return AcceptanceOutcome(
            acceptance_id=self.acceptance.id,
            purpose=self.scope.purpose,
            policy_ref=self.scope.policy_ref,
            covered_checks=self.scope.required_checks if covered_checks is None else covered_checks,
            verdict=verdict,
            explanation="合成声明，仅验证交接约束",
        )

    def test_explicit_pass_with_matching_scope_and_evidence_can_be_handed_over(self) -> None:
        """明确通过且满足作用范围、覆盖和证据关联时允许交接。"""
        outcome = self._make_outcome(AcceptanceVerdict.PASSED, covered_checks=self.scope.required_checks | {"diagnostics"})
        require_accepted(
            outcome, target=self.acceptance.target, scope=self.scope, acceptance=self.acceptance, evidence=(self.evidence,)
        )

    def test_complete_report_and_coverage_do_not_turn_nonpassing_verdicts_into_passes(self) -> None:
        """完整报告和充分声明覆盖也不能将拒绝、不足或不支持改写成通过。"""
        requirements = ReportRequirements(contract_ref="report/v1", required_sections=frozenset({"result"}))
        require_complete_report(
            ReportAssessment(report_id=ArtifactId(uuid4()), contract_ref="report/v1", sections=frozenset({"result"})),
            requirements=requirements,
        )
        for verdict in (AcceptanceVerdict.REJECTED, AcceptanceVerdict.INSUFFICIENT, AcceptanceVerdict.UNSUPPORTED):
            with self.subTest(verdict=verdict):
                outcome = self._make_outcome(verdict)
                validate_acceptance_outcome(outcome, acceptance=self.acceptance, evidence=(self.evidence,))
                with self.assertRaises(AssessmentContractError):
                    require_accepted(
                        outcome, target=self.acceptance.target, scope=self.scope,
                        acceptance=self.acceptance, evidence=(self.evidence,),
                    )

    def test_declared_pass_with_incomplete_coverage_is_recordable_but_not_releasable(self) -> None:
        """生产者的通过声明仍可记录，缺少必要检查时拒绝本次交接。"""
        for coverage in (frozenset(), frozenset({"shape"})):
            with self.subTest(coverage=coverage):
                outcome = self._make_outcome(AcceptanceVerdict.PASSED, covered_checks=coverage)
                validate_acceptance_outcome(outcome, acceptance=self.acceptance, evidence=(self.evidence,))
                with self.assertRaises(AssessmentContractError):
                    require_accepted(
                        outcome, target=self.acceptance.target, scope=self.scope,
                        acceptance=self.acceptance, evidence=(self.evidence,),
                    )

    def test_declared_pass_without_evidence_does_not_release_the_target(self) -> None:
        """无证据关联的结论可保留，但显式通过也不能绕过必要证据门槛。"""
        acceptance = AcceptanceIdentity(id=self.acceptance.id, target=self.acceptance.target, evidence_ids=frozenset())
        outcome = self._make_outcome(AcceptanceVerdict.PASSED)
        validate_acceptance_outcome(outcome, acceptance=acceptance, evidence=())
        with self.assertRaises(AssessmentContractError):
            require_accepted(outcome, target=acceptance.target, scope=self.scope, acceptance=acceptance, evidence=())

    def test_acceptance_purpose_and_policy_must_match_the_requested_scope(self) -> None:
        """静态外观通过不能代替动画用途或另一版本策略的验收。"""
        outcome = self._make_outcome(AcceptanceVerdict.PASSED)
        scopes = (
            AcceptanceScope(purpose="动画", policy_ref=self.scope.policy_ref, required_checks=self.scope.required_checks),
            AcceptanceScope(purpose=self.scope.purpose, policy_ref="appearance/v2", required_checks=self.scope.required_checks),
        )
        for scope in scopes:
            with self.subTest(purpose=scope.purpose, policy=scope.policy_ref):
                with self.assertRaises(AssessmentContractError):
                    require_accepted(
                        outcome, target=self.acceptance.target, scope=scope,
                        acceptance=self.acceptance, evidence=(self.evidence,),
                    )

    def test_outcome_and_evidence_keep_exact_acceptance_and_target_bindings(self) -> None:
        """拒绝另一验收身份或观察另一目标的证据，保留身份层错误类型。"""
        outcome = self._make_outcome(AcceptanceVerdict.PASSED)
        with self.assertRaises(AssessmentContractError):
            validate_acceptance_outcome(
                outcome,
                acceptance=AcceptanceIdentity(
                    id=AcceptanceId(uuid4()), target=self.acceptance.target, evidence_ids=self.acceptance.evidence_ids
                ),
                evidence=(self.evidence,),
            )
        wrong_evidence = EvidenceIdentity(
            id=self.evidence.id, target=ArtifactSetTarget(artifact_ids=frozenset({ArtifactId(uuid4())}))
        )
        with self.assertRaises(IdentityRelationError):
            require_accepted(
                outcome, target=self.acceptance.target, scope=self.scope,
                acceptance=self.acceptance, evidence=(wrong_evidence,),
            )
        with self.assertRaises(IdentityRelationError):
            require_accepted(outcome, target=self.acceptance.target, scope=self.scope, acceptance=self.acceptance, evidence=())

    def test_version_acceptance_cannot_release_another_version_or_target_category(self) -> None:
        """同一组文件也不能让版本甲的验收放行版本乙或改成文件集合目标。"""
        family_id = ModelFamilyId(uuid4())
        artifact_ids = frozenset({ArtifactId(uuid4())})
        first = ModelVersionIdentity(id=ModelVersionId(uuid4()), family_id=family_id, artifact_ids=artifact_ids)
        second = ModelVersionIdentity(id=ModelVersionId(uuid4()), family_id=family_id, artifact_ids=artifact_ids)
        target = ModelVersionTarget(version_id=first.id)
        evidence = EvidenceIdentity(id=self.evidence.id, target=target)
        acceptance = AcceptanceIdentity(id=self.acceptance.id, target=target, evidence_ids=frozenset({evidence.id}))
        outcome = self._make_outcome(AcceptanceVerdict.PASSED)
        require_accepted(outcome, target=target, scope=self.scope, acceptance=acceptance, evidence=(evidence,))
        wrong_targets: tuple[ReviewTarget, ...] = (
            ModelVersionTarget(version_id=second.id),
            ArtifactSetTarget(artifact_ids=artifact_ids),
        )
        for wrong_target in wrong_targets:
            with self.subTest(target=wrong_target):
                with self.assertRaises(AssessmentContractError):
                    require_accepted(
                        outcome, target=wrong_target, scope=self.scope, acceptance=acceptance, evidence=(evidence,)
                    )

    def test_artifact_subset_cannot_impersonate_the_exact_accepted_target(self) -> None:
        """证据允许观察目标子集，但放行对象仍必须等于验收的完整目标。"""
        first_id, second_id = ArtifactId(uuid4()), ArtifactId(uuid4())
        accepted_target = ArtifactSetTarget(artifact_ids=frozenset({first_id, second_id}))
        requested_target = ArtifactSetTarget(artifact_ids=frozenset({first_id}))
        evidence = EvidenceIdentity(id=self.evidence.id, target=accepted_target)
        acceptance = AcceptanceIdentity(
            id=self.acceptance.id, target=accepted_target, evidence_ids=frozenset({evidence.id})
        )
        outcome = self._make_outcome(AcceptanceVerdict.PASSED)
        validate_acceptance_outcome(outcome, acceptance=acceptance, evidence=(evidence,))
        with self.assertRaises(AssessmentContractError):
            require_accepted(
                outcome, target=requested_target, scope=self.scope, acceptance=acceptance, evidence=(evidence,)
            )

    def test_acceptance_contract_rejects_wrong_enum_and_invalid_scope(self) -> None:
        """拒绝裸字符串结论、可变覆盖集合和空要求，保持明确业务类型。"""
        with self.assertRaises(TypeError):
            self._make_outcome(cast(AcceptanceVerdict, "passed"))
        with self.assertRaises(TypeError):
            self._make_outcome(AcceptanceVerdict.PASSED, covered_checks=cast(frozenset[str], {"shape"}))
        with self.assertRaises(TypeError):
            require_accepted(
                self._make_outcome(AcceptanceVerdict.PASSED), target=cast(ReviewTarget, "latest"),
                scope=self.scope, acceptance=self.acceptance, evidence=(self.evidence,),
            )
        with self.assertRaises(AssessmentContractError):
            AcceptanceScope(purpose="静态外观", policy_ref="appearance/v1", required_checks=frozenset())
        for invalid_text in (" ", "\ud800"):
            with self.subTest(text=repr(invalid_text)):
                with self.assertRaises(AssessmentContractError):
                    AcceptanceOutcome(
                        acceptance_id=self.acceptance.id,
                        purpose=self.scope.purpose,
                        policy_ref=self.scope.policy_ref,
                        covered_checks=self.scope.required_checks,
                        verdict=AcceptanceVerdict.INSUFFICIENT,
                        explanation=invalid_text,
                    )
