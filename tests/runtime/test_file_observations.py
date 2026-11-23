# 文件信息：L0-04 文件观察及内容交接守卫的公开契约测试。
# 作用：验证不匹配事实可记录、交接必须匹配，以及缺失与访问失败的区别。
# 范围：只构造内存观察，不读取磁盘、不计算摘要或模拟持久恢复。
"""通过公共导出检查文件观察事实与交接约束。"""

from dataclasses import FrozenInstanceError
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileMissing, FileObservation, FilePresent,
    FileReference, FileUnavailable, WorkspaceFileLocation, WorkspaceRelativePath,
    require_matching_file, validate_file_observation,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId


class FileObservationTests(unittest.TestCase):
    """验证显式文件观察，不将结构校验解释为实际读取完成。"""

    def setUp(self) -> None:
        """为各用例构造相同身份关联下的预期内容和位置。"""
        self.artifact = ArtifactIdentity(
            id=ArtifactId(uuid4()), workspace_id=WorkspaceId(uuid4()),
        )
        self.content = ContentFingerprint(sha256="a" * 64, byte_size=12)
        self.reference = FileReference(artifact_id=self.artifact.id, content=self.content)
        self.location = WorkspaceFileLocation(
            artifact_id=self.artifact.id, relative_path=WorkspaceRelativePath("photos/cat.png"),
        )

    def test_matching_present_observation_can_be_handed_off(self) -> None:
        """相同内容值的存在观察可通过关联校验及交接守卫。"""
        observed = ContentFingerprint(sha256="a" * 64, byte_size=12)
        observation = FilePresent(location=self.location, observed=observed)
        validate_file_observation(observation, reference=self.reference, artifact=self.artifact)
        require_matching_file(observation, reference=self.reference, artifact=self.artifact)

    def test_mismatched_content_is_recordable_but_cannot_be_handed_off(self) -> None:
        """摘要或长度不匹配均保留为有效观察，交接守卫分别拒绝。"""
        for content in (
            ContentFingerprint(sha256="b" * 64, byte_size=12),
            ContentFingerprint(sha256="a" * 64, byte_size=13),
        ):
            with self.subTest(content=content):
                observation = FilePresent(location=self.location, observed=content)
                validate_file_observation(
                    observation, reference=self.reference, artifact=self.artifact,
                )
                with self.assertRaises(ArtifactContractError):
                    require_matching_file(
                        observation, reference=self.reference, artifact=self.artifact,
                    )

    def test_missing_and_unavailable_are_distinct_non_handoff_facts(self) -> None:
        """缺失和访问失败分别可记录，但都不能被解释为存在且匹配。"""
        observations: tuple[FileObservation, ...] = (
            FileMissing(location=self.location),
            FileUnavailable(location=self.location, reason="访问被拒绝"),
        )
        for observation in observations:
            with self.subTest(observation=observation):
                validate_file_observation(
                    observation, reference=self.reference, artifact=self.artifact,
                )
                with self.assertRaises(ArtifactContractError):
                    require_matching_file(
                        observation, reference=self.reference, artifact=self.artifact,
                    )

    def test_wrong_location_or_artifact_identity_is_rejected(self) -> None:
        """各变体均核对位置身份，匹配指纹也不能掩盖错配产物。"""
        other = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.artifact.workspace_id)
        other_location = WorkspaceFileLocation(
            artifact_id=other.id, relative_path=self.location.relative_path,
        )
        observations: tuple[FileObservation, ...] = (
            FilePresent(location=other_location, observed=self.content),
            FileMissing(location=other_location),
            FileUnavailable(location=other_location, reason="访问不可用"),
        )
        for observation in observations:
            with self.subTest(observation=observation):
                with self.assertRaises(ArtifactContractError):
                    validate_file_observation(
                        observation, reference=self.reference, artifact=self.artifact,
                    )
                with self.assertRaises(ArtifactContractError):
                    require_matching_file(
                        observation, reference=self.reference, artifact=self.artifact,
                    )
        with self.assertRaises(ArtifactContractError):
            validate_file_observation(
                FilePresent(location=self.location, observed=self.content),
                reference=self.reference, artifact=other,
            )

    def test_unavailable_reason_requires_nonblank_utf8_and_preserves_text(self) -> None:
        """保留合法原因原文，拒绝空白、不可编码文字及错误类型。"""
        reason = "  读取暂不可用：权限检查失败  "
        observation = FileUnavailable(location=self.location, reason=reason)
        self.assertEqual(observation.reason, reason)
        for invalid in ("", " \t\n", "失败\ud800"):
            with self.subTest(reason=repr(invalid)):
                with self.assertRaises(ArtifactContractError):
                    FileUnavailable(location=self.location, reason=invalid)
        with self.assertRaises(TypeError):
            FileUnavailable(location=self.location, reason=cast(str, b"unavailable"))

    def test_observations_are_frozen(self) -> None:
        """所有事实变体及其观察内容、原因字段不能被原地覆盖。"""
        present = FilePresent(location=self.location, observed=self.content)
        unavailable = FileUnavailable(location=self.location, reason="读取失败")
        observations: tuple[FileObservation, ...] = (
            present, FileMissing(location=self.location), unavailable,
        )
        for observation in observations:
            with self.subTest(observation=observation):
                with self.assertRaises(FrozenInstanceError):
                    setattr(observation, "location", self.location)
        with self.assertRaises(FrozenInstanceError):
            setattr(present, "observed", ContentFingerprint(sha256="b" * 64, byte_size=12))
        with self.assertRaises(FrozenInstanceError):
            setattr(unavailable, "reason", "新原因")

    def test_nested_values_require_concrete_contract_types(self) -> None:
        """位置和观察指纹必须使用已有具体类型，不能传裸值替代。"""
        invalid_location = cast(WorkspaceFileLocation, self.location.relative_path)
        with self.assertRaises(TypeError):
            FilePresent(location=invalid_location, observed=self.content)
        with self.assertRaises(TypeError):
            FileMissing(location=invalid_location)
        with self.assertRaises(TypeError):
            FileUnavailable(location=invalid_location, reason="读取失败")
        with self.assertRaises(TypeError):
            FilePresent(location=self.location, observed=cast(ContentFingerprint, "a" * 64))

    def test_validators_reject_absent_observation_and_wrong_related_types(self) -> None:
        """无观察记录不是第四种事实，错误引用和产物类型也不可交接。"""
        for invalid in (None, "missing", self.location):
            with self.subTest(observation=invalid):
                with self.assertRaises(TypeError):
                    validate_file_observation(
                        cast(FileObservation, invalid),
                        reference=self.reference, artifact=self.artifact,
                    )
                with self.assertRaises(TypeError):
                    require_matching_file(
                        cast(FileObservation, invalid),
                        reference=self.reference, artifact=self.artifact,
                    )
        observation = FilePresent(location=self.location, observed=self.content)
        with self.assertRaises(TypeError):
            validate_file_observation(
                observation, reference=cast(FileReference, self.content), artifact=self.artifact,
            )
        with self.assertRaises(TypeError):
            validate_file_observation(
                observation, reference=self.reference,
                artifact=cast(ArtifactIdentity, self.artifact.id),
            )


if __name__ == "__main__":
    unittest.main()
