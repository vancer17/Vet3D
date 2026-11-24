# 文件信息：L1-04 单资产登记的局部关联契约测试。
# 作用：核对固定工作区及出处关联，避免将类型或声明当作真实登记证据。
# 边界：不重复测试既有文件字段规则，不使用替身证明数据库或实际文件访问。
"""通过公共导出验证单资产登记新增的作用域和出处组合门槛。"""

import unittest
from typing import cast
from uuid import uuid4

from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileReference, ImportOrigin, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath, validate_registration,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, TaskId, WorkspaceId


class ArtifactRegistrationContractTests(unittest.TestCase):
    """验证原声明的合法交接，不创建另一套登记状态或身份。"""

    def setUp(self) -> None:
        """建立一个固定工作区中尚无真实磁盘证据的产物声明。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        self.reference = FileReference(self.artifact.id, ContentFingerprint("a" * 64, 12))
        self.record = LocatedArtifact(
            self.artifact, self.reference,
            WorkspaceFileLocation(self.artifact.id, WorkspaceRelativePath("files/尚无磁盘文件")),
        )

    def test_matching_record_accepts_known_and_unknown_origin(self) -> None:
        """出处说明可以缺失；提供时保留原声明，不将说明解释为输入路径。"""
        validate_registration(self.record, workspace_id=self.workspace_id)
        origin = ImportOrigin(self.artifact.id, "用户明确提交的原说明：https://example.invalid/photo")
        validate_registration(self.record, workspace_id=self.workspace_id, origin=origin)
        self.assertEqual(origin.source_label, "用户明确提交的原说明：https://example.invalid/photo")

    def test_foreign_workspace_is_rejected(self) -> None:
        """身份和内容互相匹配仍不能覆盖实例的固定工作区范围。"""
        with self.assertRaises(ArtifactContractError):
            validate_registration(self.record, workspace_id=WorkspaceId(uuid4()))

    def test_origin_cannot_refer_to_another_artifact(self) -> None:
        """相同出处文字也不能把其他产物的说明附到本次登记。"""
        with self.assertRaises(ArtifactContractError):
            validate_registration(
                self.record, workspace_id=self.workspace_id,
                origin=ImportOrigin(ArtifactId(uuid4()), "用户提供的相同说明"),
            )

    def test_wrong_record_and_scope_types_are_rejected(self) -> None:
        """裸产物或同 UUID 的其他身份类别不能替代完整记录及工作区身份。"""
        with self.assertRaises(TypeError):
            validate_registration(cast(LocatedArtifact, self.artifact), workspace_id=self.workspace_id)
        with self.assertRaises(TypeError):
            validate_registration(
                self.record, workspace_id=cast(WorkspaceId, TaskId(self.workspace_id.value)),
            )

    def test_optional_origin_requires_the_existing_concrete_type(self) -> None:
        """提供出处时不能用裸文字或内容引用替代既有出处类型。"""
        for invalid in ("用户提供的说明", self.reference):
            with self.subTest(origin=invalid):
                with self.assertRaises(TypeError):
                    validate_registration(
                        self.record, workspace_id=self.workspace_id, origin=cast(ImportOrigin, invalid),
                    )


if __name__ == "__main__":
    unittest.main()
