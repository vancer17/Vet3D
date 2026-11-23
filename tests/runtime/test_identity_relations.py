# 文件信息：L0-02 已解析身份关系校验测试。
# 作用：验证直接父引用、工作区归属、文件集合及验收证据对应。
# 范围：仅使用显式传入记录，不建立注册表、解析器、数据库或任务状态。
"""以实际关系错误检验同步校验接口，不宣称外部实体已存在。"""

import unittest
from uuid import uuid4

from vet3d.identity import (
    AcceptanceId,
    AcceptanceIdentity,
    ArtifactId,
    ArtifactIdentity,
    ArtifactSetTarget,
    AttemptId,
    AttemptIdentity,
    AttemptOutput,
    Derivation,
    EvidenceId,
    EvidenceIdentity,
    IdentityRelationError,
    JobId,
    JobIdentity,
    ModelFamilyId,
    ModelFamilyIdentity,
    ModelVersionId,
    ModelVersionIdentity,
    ModelVersionTarget,
    SessionId,
    SessionIdentity,
    TaskId,
    TaskIdentity,
    TurnId,
    TurnIdentity,
    WorkspaceId,
    validate_acceptance,
    validate_artifact_target,
    validate_attempt,
    validate_attempt_output,
    validate_derivation,
    validate_job,
    validate_model_version,
    validate_session,
    validate_turn,
    validate_version_target,
)


class IdentityRelationTests(unittest.TestCase):
    """验证本次显式提供的事实，不把内存夹具当作权威状态库。"""

    def setUp(self) -> None:
        """准备独立工作区内的直接父关联和两个文件身份。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.task = TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id)
        self.session = SessionIdentity(id=SessionId(uuid4()), task_id=self.task.id)
        self.turn = TurnIdentity(id=TurnId(uuid4()), session_id=self.session.id)
        self.job = JobIdentity(id=JobId(uuid4()), task_id=self.task.id)
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id)
        self.first = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        self.second = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        self.family = ModelFamilyIdentity(id=ModelFamilyId(uuid4()), workspace_id=self.workspace_id)
        self.version = ModelVersionIdentity(
            id=ModelVersionId(uuid4()),
            family_id=self.family.id,
            artifact_ids=frozenset({self.first.id, self.second.id}),
        )

    def test_direct_parent_relations_require_the_referenced_record(self) -> None:
        """允许正常父关联，并拒绝同类别但并非所引用对象的父记录。"""
        validate_session(self.session, self.task)
        validate_turn(self.turn, self.session)
        validate_job(self.job, self.task)
        validate_attempt(self.attempt, self.job)
        other_task = TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id)
        with self.assertRaises(IdentityRelationError):
            validate_session(self.session, other_task)
        with self.assertRaises(IdentityRelationError):
            validate_job(self.job, other_task)
        with self.assertRaises(IdentityRelationError):
            validate_turn(self.turn, SessionIdentity(id=SessionId(uuid4()), task_id=self.task.id))
        with self.assertRaises(IdentityRelationError):
            validate_attempt(self.attempt, JobIdentity(id=JobId(uuid4()), task_id=self.task.id))

    def test_known_derivation_does_not_require_an_execution_job(self) -> None:
        """已知文件派生可以单独校验，不强迫本地变换建立作业或尝试。"""
        output = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        derivation = Derivation(output_id=output.id, source_ids=frozenset({self.first.id, self.second.id}))
        validate_derivation(derivation, output=output, sources=(self.second, self.first))

    def test_derivation_rejects_missing_mismatched_or_foreign_records(self) -> None:
        """来源缺件、输出身份不符或跨工作区的派生无法通过。"""
        derivation = Derivation(output_id=self.second.id, source_ids=frozenset({self.first.id}))
        with self.assertRaises(IdentityRelationError):
            validate_derivation(derivation, output=self.second, sources=())
        with self.assertRaises(IdentityRelationError):
            validate_derivation(derivation, output=self.first, sources=(self.first,))
        foreign_source = ArtifactIdentity(id=self.first.id, workspace_id=WorkspaceId(uuid4()))
        with self.assertRaises(IdentityRelationError):
            validate_derivation(derivation, output=self.second, sources=(foreign_source,))

    def test_attempt_output_requires_matching_execution_chain_and_workspace(self) -> None:
        """产出关联沿已提供执行链核对，不用产出引用推断执行成功。"""
        output = AttemptOutput(attempt_id=self.attempt.id, artifact_id=self.first.id)
        validate_attempt_output(output, attempt=self.attempt, job=self.job, task=self.task, artifact=self.first)
        with self.assertRaises(IdentityRelationError):
            validate_attempt_output(
                output,
                attempt=AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id),
                job=self.job,
                task=self.task,
                artifact=self.first,
            )
        with self.assertRaises(IdentityRelationError):
            validate_attempt_output(
                output,
                attempt=self.attempt,
                job=JobIdentity(id=JobId(uuid4()), task_id=self.task.id),
                task=self.task,
                artifact=self.first,
            )
        with self.assertRaises(IdentityRelationError):
            validate_attempt_output(
                output,
                attempt=self.attempt,
                job=self.job,
                task=self.task,
                artifact=ArtifactIdentity(id=self.first.id, workspace_id=WorkspaceId(uuid4())),
            )

    def test_model_version_requires_matching_family_and_artifact_workspace(self) -> None:
        """版本绑定确切家族和文件集合，不接受其他家族或跨区文件。"""
        validate_model_version(self.version, family=self.family, artifacts=(self.first, self.second))
        with self.assertRaises(IdentityRelationError):
            validate_model_version(
                self.version,
                family=ModelFamilyIdentity(id=ModelFamilyId(uuid4()), workspace_id=self.workspace_id),
                artifacts=(self.first, self.second),
            )
        with self.assertRaises(IdentityRelationError):
            validate_model_version(
                self.version,
                family=self.family,
                artifacts=(self.first, ArtifactIdentity(id=self.second.id, workspace_id=WorkspaceId(uuid4()))),
            )

    def test_artifact_target_requires_exactly_the_referenced_set(self) -> None:
        """缺失、多余和重复记录均被拒绝，记录顺序不改变文件集合目标。"""
        target = ArtifactSetTarget(artifact_ids=self.version.artifact_ids)
        validate_artifact_target(target, artifacts=(self.second, self.first))
        extra = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        invalid_sets = (
            (),
            (self.first,),
            (self.first, self.second, extra),
            (self.first, self.second, self.first),
        )
        for artifacts in invalid_sets:
            with self.subTest(ids=[artifact.id for artifact in artifacts]):
                with self.assertRaises(IdentityRelationError):
                    validate_artifact_target(target, artifacts=artifacts)
        with self.assertRaises(IdentityRelationError):
            validate_artifact_target(
                target,
                artifacts=(
                    self.first,
                    ArtifactIdentity(id=self.second.id, workspace_id=WorkspaceId(uuid4())),
                ),
            )

    def test_version_target_requires_the_exact_version_and_its_files(self) -> None:
        """版本目标不因家族或文件相同而接受另一版本，也不接受缺件。"""
        target = ModelVersionTarget(version_id=self.version.id)
        validate_version_target(target, version=self.version, family=self.family, artifacts=(self.first, self.second))
        with self.assertRaises(IdentityRelationError):
            validate_version_target(
                target,
                version=ModelVersionIdentity(
                    id=ModelVersionId(uuid4()),
                    family_id=self.family.id,
                    artifact_ids=self.version.artifact_ids,
                ),
                family=self.family,
                artifacts=(self.first, self.second),
            )
        with self.assertRaises(IdentityRelationError):
            validate_version_target(target, version=self.version, family=self.family, artifacts=(self.first,))

    def test_acceptance_allows_evidence_for_a_subset_of_its_artifact_target(self) -> None:
        """文件集合验收可引用分别观察其子集的证据，不推断已充分验收。"""
        target = ArtifactSetTarget(artifact_ids=self.version.artifact_ids)
        first_evidence = EvidenceIdentity(id=EvidenceId(uuid4()), target=ArtifactSetTarget(artifact_ids=frozenset({self.first.id})))
        second_evidence = EvidenceIdentity(id=EvidenceId(uuid4()), target=ArtifactSetTarget(artifact_ids=frozenset({self.second.id})))
        acceptance = AcceptanceIdentity(
            id=AcceptanceId(uuid4()),
            target=target,
            evidence_ids=frozenset({first_evidence.id, second_evidence.id}),
        )
        validate_acceptance(acceptance, evidence=(second_evidence, first_evidence))
        validate_acceptance(AcceptanceIdentity(id=AcceptanceId(uuid4()), target=target, evidence_ids=frozenset()), evidence=())

    def test_acceptance_rejects_evidence_for_an_outside_artifact(self) -> None:
        """证据观察集合超出被验目标时拒绝，不能只凭证据身份存在放行。"""
        target = ArtifactSetTarget(artifact_ids=frozenset({self.first.id}))
        evidence = EvidenceIdentity(id=EvidenceId(uuid4()), target=ArtifactSetTarget(artifact_ids=self.version.artifact_ids))
        acceptance = AcceptanceIdentity(id=AcceptanceId(uuid4()), target=target, evidence_ids=frozenset({evidence.id}))
        with self.assertRaises(IdentityRelationError):
            validate_acceptance(acceptance, evidence=(evidence,))

    def test_acceptance_requires_matching_version_and_target_category(self) -> None:
        """版本证据必须指向同一版本，不在版本与文件目标之间隐式转换。"""
        target = ModelVersionTarget(version_id=self.version.id)
        evidence_id = EvidenceId(uuid4())
        acceptance = AcceptanceIdentity(id=AcceptanceId(uuid4()), target=target, evidence_ids=frozenset({evidence_id}))
        validate_acceptance(acceptance, evidence=(EvidenceIdentity(id=evidence_id, target=target),))
        with self.assertRaises(IdentityRelationError):
            validate_acceptance(
                acceptance,
                evidence=(EvidenceIdentity(id=evidence_id, target=ModelVersionTarget(version_id=ModelVersionId(uuid4()))),),
            )
        with self.assertRaises(IdentityRelationError):
            validate_acceptance(
                acceptance,
                evidence=(EvidenceIdentity(id=evidence_id, target=ArtifactSetTarget(artifact_ids=self.version.artifact_ids)),),
            )

    def test_acceptance_requires_exactly_the_referenced_evidence(self) -> None:
        """显式证据记录缺失、多余或重复时失败，不创建或查询缺失记录。"""
        target = ModelVersionTarget(version_id=self.version.id)
        evidence = EvidenceIdentity(id=EvidenceId(uuid4()), target=target)
        extra = EvidenceIdentity(id=EvidenceId(uuid4()), target=target)
        acceptance = AcceptanceIdentity(id=AcceptanceId(uuid4()), target=target, evidence_ids=frozenset({evidence.id}))
        for records in ((), (evidence, extra), (evidence, evidence)):
            with self.subTest(ids=[record.id for record in records]):
                with self.assertRaises(IdentityRelationError):
                    validate_acceptance(acceptance, evidence=records)
