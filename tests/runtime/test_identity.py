# 文件信息：L0-02 身份值及局部关联记录测试。
# 作用：验证 UUID4、类别边界、冻结记录和必要集合约束。
# 范围：不验证持久唯一性、文件摘要、作业状态或恢复能力。
"""通过公开身份包验证结构约束，不重复测试简单字段读取。"""

import unittest
from dataclasses import FrozenInstanceError
from typing import cast
from uuid import UUID, uuid1, uuid4

from vet3d.identity import (
    ArtifactId,
    ArtifactSetTarget,
    Derivation,
    EvidenceId,
    IdentityRelationError,
    JobId,
    ModelFamilyId,
    ModelVersionId,
    ModelVersionIdentity,
    TaskId,
    TaskIdentity,
    WorkspaceId,
)


class IdentityValueTests(unittest.TestCase):
    """检查不透明身份类别和被公开接受的输入形式。"""

    def test_canonical_uuid4_round_trip_preserves_category(self) -> None:
        """规范文本可回到同类身份，相同 UUID 不合并不同业务类别。"""
        value = uuid4()
        workspace = WorkspaceId(value)
        self.assertEqual(WorkspaceId.parse(str(value)), workspace)
        self.assertEqual(TaskId.parse(str(value)), TaskId(value))
        self.assertNotEqual(workspace, TaskId(value))
        self.assertNotEqual(ArtifactId(value), ModelVersionId(value))

    def test_non_uuid4_and_noncanonical_text_are_rejected(self) -> None:
        """拒绝非 UUID4 及非规范文本，不提供隐式规范化或旧格式兼容。"""
        for value in (uuid1(), UUID(int=0)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    WorkspaceId(value)
                with self.assertRaises(ValueError):
                    WorkspaceId.parse(str(value))
        value = UUID("12345678-abcd-4abc-8abc-123456789abc")
        invalid_texts = (
            "",
            "not-an-id",
            value.hex,
            str(value).upper(),
            f"{{{value}}}",
            value.urn,
            f" {value}",
            f"{value}\n",
        )
        for text in invalid_texts:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    WorkspaceId.parse(text)

    def test_identity_requires_the_declared_input_type(self) -> None:
        """构造与文本解析拒绝错误原始类型，避免混淆解析入口。"""
        with self.assertRaises(TypeError):
            WorkspaceId(cast(UUID, str(uuid4())))
        with self.assertRaises(TypeError):
            WorkspaceId.parse(cast(str, uuid4()))

    def test_identity_and_parent_binding_are_frozen(self) -> None:
        """已构造身份及直接父关联不能原地修改。"""
        workspace = WorkspaceId(uuid4())
        task = TaskIdentity(id=TaskId(uuid4()), workspace_id=workspace)
        with self.assertRaises(FrozenInstanceError):
            setattr(workspace, "value", uuid4())
        with self.assertRaises(FrozenInstanceError):
            setattr(task, "workspace_id", WorkspaceId(uuid4()))

    def test_record_fields_reject_wrong_identity_categories_and_mutable_sets(self) -> None:
        """拒绝类别相近但无效的身份和可变集合，不依赖静态类型兜底。"""
        with self.assertRaises(TypeError):
            TaskIdentity(id=cast(TaskId, JobId(uuid4())), workspace_id=WorkspaceId(uuid4()))
        with self.assertRaises(TypeError):
            ArtifactSetTarget(artifact_ids=cast(frozenset[ArtifactId], {ArtifactId(uuid4())}))
        with self.assertRaises(TypeError):
            ArtifactSetTarget(artifact_ids=cast(frozenset[ArtifactId], frozenset({EvidenceId(uuid4())})))
        with self.assertRaises(TypeError):
            ModelVersionIdentity(
                id=ModelVersionId(uuid4()),
                family_id=cast(ModelFamilyId, ArtifactId(uuid4())),
                artifact_ids=frozenset({ArtifactId(uuid4())}),
            )

    def test_empty_subjects_are_rejected(self) -> None:
        """文件集合目标和模型版本必须绑定非空文件身份集合。"""
        with self.assertRaises(IdentityRelationError):
            ArtifactSetTarget(artifact_ids=frozenset())
        with self.assertRaises(IdentityRelationError):
            ModelVersionIdentity(
                id=ModelVersionId(uuid4()),
                family_id=ModelFamilyId(uuid4()),
                artifact_ids=frozenset(),
            )

    def test_derivation_requires_known_sources_and_rejects_direct_self_reference(self) -> None:
        """已知派生边必须含来源且不能直接引用自身，不推导完整来源类别。"""
        output_id = ArtifactId(uuid4())
        with self.assertRaises(IdentityRelationError):
            Derivation(output_id=output_id, source_ids=frozenset())
        with self.assertRaises(IdentityRelationError):
            Derivation(output_id=output_id, source_ids=frozenset({output_id}))
