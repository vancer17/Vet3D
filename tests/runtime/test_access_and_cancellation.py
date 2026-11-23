# 文件信息：L0-05 产物访问结果与取消命令回执的契约测试。
# 作用：核对解析记录关联、文件事实独立性，以及取消受理不能冒充执行终态。
# 边界：仅使用内存声明，不实现端口替身，不证明磁盘访问或真实远端取消。
"""验证跨包公开契约和必要拒绝路径，不执行文件或网络操作。"""

from dataclasses import FrozenInstanceError, replace
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileObservation, FilePresent,
    FileMissing, FileReference, FileUnavailable, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath, require_matching_file,
    validate_file_observation,
)
from vet3d.execution import (
    AttemptActive, AttemptCancelled, AttemptObservation, AttemptSucceeded,
    CancellationAcknowledged, CancellationReceipt, CancellationUnconfirmed,
    ExecutionContractError, QueryUnavailable, preserve_after_query_failure,
    reconcile_observation, validate_attempt_fact,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, JobId, WorkspaceId,
)


class ArtifactAccessContractTests(unittest.TestCase):
    """验证解析结果只组合已有记录，不把登记提升为文件存在。"""

    def setUp(self) -> None:
        """准备没有磁盘实体承诺的产物、内容与位置声明。"""
        self.artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=WorkspaceId(uuid4()))
        self.reference = FileReference(
            artifact_id=self.artifact.id,
            content=ContentFingerprint(sha256="a" * 64, byte_size=12),
        )
        self.location = WorkspaceFileLocation(
            artifact_id=self.artifact.id,
            relative_path=WorkspaceRelativePath("declared/source.png"),
        )
        self.located = LocatedArtifact(self.artifact, self.reference, self.location)

    def test_resolved_records_require_one_exact_artifact(self) -> None:
        """同区其他产物的内容或位置都不能拼入当前解析结果。"""
        other_id = ArtifactId(uuid4())
        with self.assertRaises(ArtifactContractError):
            LocatedArtifact(
                self.artifact, replace(self.reference, artifact_id=other_id), self.location,
            )
        with self.assertRaises(ArtifactContractError):
            LocatedArtifact(
                self.artifact, self.reference, replace(self.location, artifact_id=other_id),
            )
        with self.assertRaises(ArtifactContractError):
            LocatedArtifact(
                replace(self.artifact, id=other_id), self.reference, self.location,
            )

    def test_resolved_fields_reject_ids_or_records_of_another_concept(self) -> None:
        """不能用裸身份或结构相似的记录替代具体归属、内容和位置。"""
        with self.assertRaises(TypeError):
            LocatedArtifact(cast(ArtifactIdentity, self.artifact.id), self.reference, self.location)
        with self.assertRaises(TypeError):
            LocatedArtifact(self.artifact, cast(FileReference, self.location), self.location)
        with self.assertRaises(TypeError):
            LocatedArtifact(self.artifact, self.reference, cast(WorkspaceFileLocation, self.reference))

    def test_registered_metadata_allows_missing_or_unavailable_file_facts(self) -> None:
        """已经解析到元数据仍可观察到缺失或不可访问，二者都不满足文件交接。"""
        observations: tuple[FileObservation, ...] = (
            FileMissing(self.located.location),
            FileUnavailable(self.located.location, reason="本次访问未取得文件事实"),
        )
        for observation in observations:
            with self.subTest(observation=observation):
                validate_file_observation(
                    observation, reference=self.located.reference, artifact=self.located.artifact,
                )
                with self.assertRaises(ArtifactContractError):
                    require_matching_file(
                        observation, reference=self.located.reference, artifact=self.located.artifact,
                    )

    def test_observed_content_does_not_rebind_the_registered_reference(self) -> None:
        """不同内容可作为观察保留，但匹配守卫拒绝，登记内容仍指向原快照。"""
        observation = FilePresent(
            self.located.location, observed=ContentFingerprint(sha256="b" * 64, byte_size=12),
        )
        validate_file_observation(
            observation, reference=self.located.reference, artifact=self.located.artifact,
        )
        with self.assertRaises(ArtifactContractError):
            require_matching_file(
                observation, reference=self.located.reference, artifact=self.located.artifact,
            )
        require_matching_file(
            FilePresent(self.located.location, observed=self.reference.content),
            reference=self.located.reference, artifact=self.located.artifact,
        )

    def test_resolved_records_cannot_be_rebound_in_place(self) -> None:
        """解析结果冻结后不能原地替换内容引用或位置。"""
        with self.assertRaises(FrozenInstanceError):
            setattr(self.located, "reference", replace(self.reference, artifact_id=ArtifactId(uuid4())))
        with self.assertRaises(FrozenInstanceError):
            setattr(self.located, "location", replace(self.location, artifact_id=ArtifactId(uuid4())))


class CancellationReceiptContractTests(unittest.TestCase):
    """核对取消命令回执的原尝试关联及与执行终态的分离。"""

    def setUp(self) -> None:
        """准备同一意图下两个尝试，避免将同作业误认为同次执行。"""
        job_id = JobId(uuid4())
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job_id)
        self.other_attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job_id)
        self.receipts: tuple[CancellationReceipt, ...] = (
            CancellationAcknowledged(self.attempt.id, reason="执行端确认受理取消请求"),
            CancellationUnconfirmed(self.attempt.id, reason="取消命令回执未取得"),
        )

    def test_cancellation_receipts_match_only_the_original_attempt(self) -> None:
        """两种取消回执都可核对原尝试，但不能借用同作业的另一次尝试。"""
        for receipt in self.receipts:
            with self.subTest(receipt=receipt):
                validate_attempt_fact(receipt, attempt=self.attempt)
                with self.assertRaises(ExecutionContractError):
                    validate_attempt_fact(receipt, attempt=self.other_attempt)

    def test_cancellation_receipts_reject_wrong_types_and_invalid_diagnostics(self) -> None:
        """取消回执要求具体尝试身份和非空白 UTF-8 原因，不隐式转换。"""
        for receipt_type in (CancellationAcknowledged, CancellationUnconfirmed):
            with self.subTest(receipt_type=receipt_type):
                with self.assertRaises(TypeError):
                    receipt_type(cast(AttemptId, JobId(self.attempt.id.value)), reason="取消说明")
                with self.assertRaises(TypeError):
                    receipt_type(self.attempt.id, reason=cast(str, None))
                for reason in ("", " \t\n", "诊断\ud800"):
                    with self.subTest(reason=repr(reason)):
                        with self.assertRaises(ExecutionContractError):
                            receipt_type(self.attempt.id, reason=reason)

    def test_cancellation_receipts_cannot_replace_execution_observations(self) -> None:
        """受理与受理不明都不能形成活动或终态，也不能覆盖已经取得的观察。"""
        for receipt in self.receipts:
            with self.subTest(receipt=receipt):
                with self.assertRaises(TypeError):
                    reconcile_observation(None, cast(AttemptObservation, receipt))
                with self.assertRaises(TypeError):
                    reconcile_observation(AttemptActive(self.attempt.id), cast(AttemptObservation, receipt))
                with self.assertRaises(TypeError):
                    reconcile_observation(cast(AttemptObservation, receipt), AttemptCancelled(self.attempt.id))

    def test_cancel_acknowledgement_does_not_predetermine_the_terminal(self) -> None:
        """请求受理后仍可查询到成功或已取消，只由确认观察决定终态。"""
        acknowledgement = CancellationAcknowledged(self.attempt.id, reason="取消请求已受理")
        validate_attempt_fact(acknowledgement, attempt=self.attempt)
        last = AttemptActive(self.attempt.id)
        for current in (AttemptSucceeded(self.attempt.id), AttemptCancelled(self.attempt.id)):
            with self.subTest(current=current):
                self.assertIs(reconcile_observation(last, current), current)
        self.assertIs(
            preserve_after_query_failure(
                last, failure=QueryUnavailable(self.attempt.id, reason="取消后本次查询未完成"),
                attempt=self.attempt,
            ),
            last,
        )

    def test_cancellation_receipts_preserve_text_and_are_frozen(self) -> None:
        """说明原文保持不变，回执不能原地改换尝试或诊断。"""
        reason = "  执行端已受理；终止仍待观察\n"
        for receipt_type in (CancellationAcknowledged, CancellationUnconfirmed):
            with self.subTest(receipt_type=receipt_type):
                receipt = receipt_type(self.attempt.id, reason=reason)
                self.assertEqual(receipt.reason, reason)
                with self.assertRaises(FrozenInstanceError):
                    setattr(receipt, "attempt_id", self.other_attempt.id)
                with self.assertRaises(FrozenInstanceError):
                    setattr(receipt, "reason", "已改写")
