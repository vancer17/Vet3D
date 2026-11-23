# 文件信息：L1-02 固定工作区文件关联的纯契约测试。
# 作用：验证作用域、引用和位置的组合拒绝规则，复用已有权威类型。
# 边界：不模拟文件写入，不把 Protocol 或局部校验当作真实存储与隔离证据。
"""通过公共入口检查文件存储的必要身份关联。"""

import unittest
from typing import cast
from uuid import uuid4

from vet3d.artifacts import (
    ArtifactContractError,
    ContentFingerprint,
    FileReference,
    WorkspaceFileLocation,
    WorkspaceRelativePath,
    validate_file_scope,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, TaskId, WorkspaceId


class FileStorageScopeTests(unittest.TestCase):
    """核对固定实例归属，不重复测试内容字段和词法路径的已有规则。"""

    def setUp(self) -> None:
        """为各用例建立同一产物的归属、内容及位置声明。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        self.reference = FileReference(self.artifact.id, ContentFingerprint("a" * 64, 12))
        self.location = WorkspaceFileLocation(self.artifact.id, WorkspaceRelativePath("files/猫"))

    def test_same_scope_accepts_individual_and_combined_associations(self) -> None:
        """独立位置观察和带内容的保存都使用同一工作区关联规则。"""
        validate_file_scope(self.artifact, workspace_id=self.workspace_id)
        validate_file_scope(self.artifact, workspace_id=self.workspace_id, reference=self.reference)
        validate_file_scope(self.artifact, workspace_id=self.workspace_id, location=self.location)
        validate_file_scope(
            self.artifact, workspace_id=self.workspace_id,
            reference=self.reference, location=self.location,
        )

    def test_other_workspace_is_rejected_even_when_artifact_id_matches(self) -> None:
        """相同产物编号不能覆盖实例固定的工作区归属。"""
        foreign = ArtifactIdentity(self.artifact.id, WorkspaceId(uuid4()))
        with self.assertRaises(ArtifactContractError):
            validate_file_scope(
                foreign, workspace_id=self.workspace_id,
                reference=self.reference, location=self.location,
            )

    def test_reference_cannot_belong_to_another_artifact_in_same_workspace(self) -> None:
        """内容相同也不能将另一产物的引用绑定到当前身份。"""
        other = FileReference(ArtifactId(uuid4()), self.reference.content)
        with self.assertRaises(ArtifactContractError):
            validate_file_scope(self.artifact, workspace_id=self.workspace_id, reference=other)

    def test_location_association_is_checked_with_or_without_reference(self) -> None:
        """仅观察入口同样核对位置身份，不能借省略内容引用绕过关联。"""
        other = WorkspaceFileLocation(ArtifactId(uuid4()), self.location.relative_path)
        for reference in (None, self.reference):
            with self.subTest(reference=reference):
                with self.assertRaises(ArtifactContractError):
                    validate_file_scope(
                        self.artifact, workspace_id=self.workspace_id,
                        reference=reference, location=other,
                    )

    def test_matching_foreign_reference_and_location_do_not_replace_artifact(self) -> None:
        """引用和位置互相一致仍必须关联请求产物，不能形成第二个身份源。"""
        other_id = ArtifactId(uuid4())
        with self.assertRaises(ArtifactContractError):
            validate_file_scope(
                self.artifact, workspace_id=self.workspace_id,
                reference=FileReference(other_id, self.reference.content),
                location=WorkspaceFileLocation(other_id, self.location.relative_path),
            )

    def test_wrong_record_and_scope_types_are_rejected(self) -> None:
        """裸身份或其他类别的同值 UUID 不能替代具体归属记录和工作区。"""
        with self.assertRaises(TypeError):
            validate_file_scope(cast(ArtifactIdentity, self.artifact.id), workspace_id=self.workspace_id)
        with self.assertRaises(TypeError):
            validate_file_scope(
                self.artifact, workspace_id=cast(WorkspaceId, TaskId(self.workspace_id.value))
            )

    def test_optional_associations_reject_wrong_record_types(self) -> None:
        """可选字段不接受裸内容或裸路径，提供后必须使用唯一公开类型。"""
        with self.assertRaises(TypeError):
            validate_file_scope(
                self.artifact, workspace_id=self.workspace_id,
                reference=cast(FileReference, self.reference.content),
            )
        with self.assertRaises(TypeError):
            validate_file_scope(
                self.artifact, workspace_id=self.workspace_id,
                location=cast(WorkspaceFileLocation, self.location.relative_path),
            )


if __name__ == "__main__":
    unittest.main()
