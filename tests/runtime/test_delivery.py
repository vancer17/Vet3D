# 文件信息：L0-04 发布、加载及保存交接的公开契约测试。
# 作用：验证任务和操作关联、实际返回目标、部分保存事实及完整交接守卫。
# 范围：只使用内存回执，不发布模型、不加载视窗、不访问保存目标或推导质量通过。
"""通过公共导出检查独立于业务验收的交接声明。"""

from dataclasses import FrozenInstanceError, replace
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileReference
from vet3d.delivery import (
    DeliveryContractError, LoadReceipt, PublicationReceipt, SavedFile, SaveReceipt,
    SaveTarget, require_complete_save, require_current_load, validate_publication_receipt,
    validate_save_receipt,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, ArtifactSetTarget, AttemptId, AttemptIdentity,
    IdentityRelationError, JobId, JobIdentity, ModelFamilyId, ModelFamilyIdentity,
    ModelVersionId, ModelVersionIdentity, ModelVersionTarget, ReviewTarget, TaskId,
    TaskIdentity, WorkspaceId,
)


class DeliveryContractTests(unittest.TestCase):
    """验证交接关联和完整性，不让记录存在变成实际执行或质量结论。"""

    def setUp(self) -> None:
        """为各用例构造本任务操作、单份内容及实际版本的关联。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.task = TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id)
        self.job = JobIdentity(id=JobId(uuid4()), task_id=self.task.id)
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id)
        self.artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        self.content = ContentFingerprint(sha256="a" * 64, byte_size=20)
        self.reference = FileReference(artifact_id=self.artifact.id, content=self.content)
        self.family = ModelFamilyIdentity(id=ModelFamilyId(uuid4()), workspace_id=self.workspace_id)
        self.version = ModelVersionIdentity(
            id=ModelVersionId(uuid4()), family_id=self.family.id,
            artifact_ids=frozenset({self.artifact.id}),
        )
        self.targets = (
            SaveTarget(reference=self.reference, destination="接收端甲/模型"),
            SaveTarget(reference=self.reference, destination="接收端乙/模型"),
        )
        self.saved = tuple(
            SavedFile(
                artifact_id=target.reference.artifact_id,
                destination=target.destination, observed=self.content,
            )
            for target in self.targets
        )

    def test_publication_accepts_actual_version_without_quality_decision(self) -> None:
        """实际返回版本及本任务归属一致即可登记确认，不要求验收通过记录。"""
        receipt = PublicationReceipt(attempt_id=self.attempt.id, version_id=self.version.id)
        validate_publication_receipt(
            receipt, attempt=self.attempt, job=self.job, task=self.task,
            version=self.version, family=self.family,
            files=(self.reference,), artifacts=(self.artifact,),
        )

    def test_publication_rejects_wrong_version_files_scope_and_attempt(self) -> None:
        """发布回执不能借用其他版本、文件、工作区或操作的关联。"""
        receipt = PublicationReceipt(attempt_id=self.attempt.id, version_id=self.version.id)
        with self.assertRaises(DeliveryContractError):
            validate_publication_receipt(
                replace(receipt, version_id=ModelVersionId(uuid4())),
                attempt=self.attempt, job=self.job, task=self.task,
                version=self.version, family=self.family,
                files=(self.reference,), artifacts=(self.artifact,),
            )
        with self.assertRaises(ArtifactContractError):
            validate_publication_receipt(
                receipt, attempt=self.attempt, job=self.job, task=self.task,
                version=self.version, family=self.family,
                files=(replace(self.reference, artifact_id=ArtifactId(uuid4())),),
                artifacts=(self.artifact,),
            )
        other_workspace = WorkspaceId(uuid4())
        with self.assertRaises(DeliveryContractError):
            validate_publication_receipt(
                receipt, attempt=self.attempt, job=self.job, task=self.task,
                version=self.version,
                family=replace(self.family, workspace_id=other_workspace),
                files=(self.reference,),
                artifacts=(replace(self.artifact, workspace_id=other_workspace),),
            )
        with self.assertRaises(DeliveryContractError):
            validate_publication_receipt(
                replace(receipt, attempt_id=AttemptId(uuid4())),
                attempt=self.attempt, job=self.job, task=self.task,
                version=self.version, family=self.family,
                files=(self.reference,), artifacts=(self.artifact,),
            )

    def test_load_requires_current_attempt_and_exact_target(self) -> None:
        """文件和版本目标均可加载确认，旧操作和错目标不能表示当前就绪。"""
        targets: tuple[ReviewTarget, ...] = (
            ArtifactSetTarget(artifact_ids=frozenset({self.artifact.id})),
            ModelVersionTarget(version_id=self.version.id),
        )
        for target in targets:
            with self.subTest(target=target):
                receipt = LoadReceipt(attempt_id=self.attempt.id, target=target)
                require_current_load(receipt, current_attempt_id=self.attempt.id, target=target)
                with self.assertRaises(DeliveryContractError):
                    require_current_load(receipt, current_attempt_id=AttemptId(uuid4()), target=target)
        receipt = LoadReceipt(attempt_id=self.attempt.id, target=targets[1])
        for wrong_target in (
            targets[0], ModelVersionTarget(version_id=ModelVersionId(uuid4())),
        ):
            with self.subTest(wrong_target=wrong_target):
                with self.assertRaises(DeliveryContractError):
                    require_current_load(
                        receipt, current_attempt_id=self.attempt.id, target=wrong_target,
                    )

    def test_same_source_can_be_saved_to_two_distinct_destinations(self) -> None:
        """同一确切源允许复制到两个目标，源归属记录只提供一次。"""
        receipt = SaveReceipt(attempt_id=self.attempt.id, saved=self.saved)
        validate_save_receipt(
            receipt, attempt=self.attempt, job=self.job, task=self.task,
            targets=self.targets, artifacts=(self.artifact,),
        )
        require_complete_save(
            receipt, attempt=self.attempt, job=self.job, task=self.task,
            targets=self.targets, artifacts=(self.artifact,),
        )

    def test_empty_and_partial_save_receipts_remain_recordable(self) -> None:
        """空确认和部分确认可保留，但都不能宣称本次全部目标已保存。"""
        confirmed_sets: tuple[tuple[SavedFile, ...], ...] = ((), self.saved[:1])
        for saved in confirmed_sets:
            with self.subTest(saved=saved):
                receipt = SaveReceipt(attempt_id=self.attempt.id, saved=saved)
                validate_save_receipt(
                    receipt, attempt=self.attempt, job=self.job, task=self.task,
                    targets=self.targets, artifacts=(self.artifact,),
                )
                with self.assertRaises(DeliveryContractError):
                    require_complete_save(
                        receipt, attempt=self.attempt, job=self.job, task=self.task,
                        targets=self.targets, artifacts=(self.artifact,),
                    )

    def test_save_content_mismatch_is_a_fact_but_blocks_complete_handoff(self) -> None:
        """目标齐全时仍逐项核对摘要与字节数，不丢弃不匹配的保存确认。"""
        for observed in (
            ContentFingerprint(sha256="b" * 64, byte_size=20),
            ContentFingerprint(sha256="a" * 64, byte_size=21),
        ):
            with self.subTest(observed=observed):
                receipt = SaveReceipt(
                    attempt_id=self.attempt.id,
                    saved=(replace(self.saved[0], observed=observed), self.saved[1]),
                )
                validate_save_receipt(
                    receipt, attempt=self.attempt, job=self.job, task=self.task,
                    targets=self.targets, artifacts=(self.artifact,),
                )
                with self.assertRaises(ArtifactContractError):
                    require_complete_save(
                        receipt, attempt=self.attempt, job=self.job, task=self.task,
                        targets=self.targets, artifacts=(self.artifact,),
                    )

    def test_duplicate_destinations_are_rejected_in_requirements_and_receipts(self) -> None:
        """重复目标不能依靠重复条目充当多个已保存项目。"""
        with self.assertRaises(DeliveryContractError):
            SaveReceipt(attempt_id=self.attempt.id, saved=(self.saved[0], self.saved[0]))
        with self.assertRaises(DeliveryContractError):
            validate_save_receipt(
                SaveReceipt(attempt_id=self.attempt.id, saved=()),
                attempt=self.attempt, job=self.job, task=self.task,
                targets=(self.targets[0], self.targets[0]), artifacts=(self.artifact,),
            )

    def test_same_source_identity_cannot_request_conflicting_content(self) -> None:
        """一个源身份复制到不同目标时仍只能绑定同一预期内容。"""
        changed = replace(
            self.reference, content=ContentFingerprint(sha256="b" * 64, byte_size=20),
        )
        conflicting_targets = (
            self.targets[0], replace(self.targets[1], reference=changed),
        )
        with self.assertRaises(ArtifactContractError):
            validate_save_receipt(
                SaveReceipt(attempt_id=self.attempt.id, saved=()),
                attempt=self.attempt, job=self.job, task=self.task,
                targets=conflicting_targets, artifacts=(self.artifact,),
            )

    def test_save_rejects_foreign_workspace_attempt_and_parent_chain(self) -> None:
        """保存源及回执必须属于本任务的本次操作，父链错误保持原异常。"""
        receipt = SaveReceipt(attempt_id=self.attempt.id, saved=())
        with self.assertRaises(DeliveryContractError):
            validate_save_receipt(
                receipt, attempt=self.attempt, job=self.job, task=self.task,
                targets=self.targets,
                artifacts=(replace(self.artifact, workspace_id=WorkspaceId(uuid4())),),
            )
        with self.assertRaises(DeliveryContractError):
            validate_save_receipt(
                replace(receipt, attempt_id=AttemptId(uuid4())),
                attempt=self.attempt, job=self.job, task=self.task,
                targets=self.targets, artifacts=(self.artifact,),
            )
        with self.assertRaises(IdentityRelationError):
            validate_save_receipt(
                receipt, attempt=self.attempt,
                job=replace(self.job, task_id=TaskId(uuid4())), task=self.task,
                targets=self.targets, artifacts=(self.artifact,),
            )

    def test_save_rejects_extra_targets_wrong_sources_and_unresolved_requirements(self) -> None:
        """额外目标、错误源和未解析要求不能混入部分保存记录。"""
        invalid_items = (
            replace(self.saved[0], destination="本次未要求的目标"),
            replace(self.saved[0], artifact_id=ArtifactId(uuid4())),
        )
        for item in invalid_items:
            with self.subTest(item=item):
                with self.assertRaises(DeliveryContractError):
                    validate_save_receipt(
                        SaveReceipt(attempt_id=self.attempt.id, saved=(item,)),
                        attempt=self.attempt, job=self.job, task=self.task,
                        targets=self.targets, artifacts=(self.artifact,),
                    )
        with self.assertRaises(ArtifactContractError):
            validate_save_receipt(
                SaveReceipt(attempt_id=self.attempt.id, saved=()),
                attempt=self.attempt, job=self.job, task=self.task,
                targets=self.targets, artifacts=(),
            )
        with self.assertRaises(DeliveryContractError):
            validate_save_receipt(
                SaveReceipt(attempt_id=self.attempt.id, saved=()),
                attempt=self.attempt, job=self.job, task=self.task,
                targets=(), artifacts=(),
            )

    def test_handoff_records_are_frozen_and_reject_invalid_boundary_inputs(self) -> None:
        """冻结保存确认并拒绝可变集合、错类目标及无效接收端文字。"""
        receipt = SaveReceipt(attempt_id=self.attempt.id, saved=self.saved)
        with self.assertRaises(FrozenInstanceError):
            setattr(receipt, "saved", ())
        with self.assertRaises(FrozenInstanceError):
            setattr(self.saved[0], "observed", ContentFingerprint(sha256="b" * 64, byte_size=20))
        with self.assertRaises(TypeError):
            SaveReceipt(attempt_id=self.attempt.id, saved=cast(tuple[SavedFile, ...], []))
        with self.assertRaises(TypeError):
            LoadReceipt(attempt_id=self.attempt.id, target=cast(ReviewTarget, self.version.id))
        for destination in ("", " \t\n", "目标\ud800"):
            with self.subTest(destination=repr(destination)):
                with self.assertRaises(DeliveryContractError):
                    SaveTarget(reference=self.reference, destination=destination)


if __name__ == "__main__":
    unittest.main()
