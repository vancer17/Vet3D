# 文件信息：L0-03 文件内容、相对定位及导入出处的公开契约测试。
# 作用：验证输入拒绝、不可变内容绑定及与 L0-02 关系的实际交接。
# 范围：仅构造内存声明值，不读取文件，也不将摘要比较称为磁盘验证。
"""通过公共导出核对文件契约，不模拟持久内容库或读取服务。"""

from dataclasses import FrozenInstanceError
import unittest
from typing import cast
from uuid import uuid4

from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileReference, ImportOrigin,
    WorkspaceFileLocation, WorkspaceRelativePath, validate_content_binding,
    validate_content_observation, validate_file_location, validate_file_reference,
    validate_file_set, validate_import_origin,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, ArtifactSetTarget, AttemptId, AttemptIdentity,
    AttemptOutput, Derivation, IdentityRelationError, JobId, JobIdentity,
    ModelFamilyId, ModelFamilyIdentity, ModelVersionId, ModelVersionIdentity,
    ModelVersionTarget, TaskId, TaskIdentity, WorkspaceId, validate_artifact_target,
    validate_attempt_output, validate_derivation, validate_version_target,
)


class ArtifactContractTests(unittest.TestCase):
    """验证显式传入的文件事实，不推断文件存在或来源真实。"""

    def setUp(self) -> None:
        """为每个用例准备独立身份和未经过文件读取的内容声明。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        self.content = ContentFingerprint(sha256="a" * 64, byte_size=12)
        self.reference = FileReference(artifact_id=self.artifact.id, content=self.content)

    def test_fingerprint_requires_canonical_sha256_and_nonnegative_integer_size(self) -> None:
        """拒绝非规范摘要、负长度和布尔长度，同时允许表达零字节内容。"""
        ContentFingerprint(sha256="0" * 64, byte_size=0)
        for digest in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"):
            with self.subTest(digest=repr(digest)):
                with self.assertRaises(ArtifactContractError):
                    ContentFingerprint(sha256=digest, byte_size=12)
        with self.assertRaises(ArtifactContractError):
            ContentFingerprint(sha256="a" * 64, byte_size=-1)
        for size in (True, False, 12.0, "12", None):
            with self.subTest(size=size):
                with self.assertRaises(TypeError):
                    ContentFingerprint(sha256="a" * 64, byte_size=cast(int, size))
        with self.assertRaises(TypeError):
            ContentFingerprint(sha256=cast(str, b"a" * 64), byte_size=12)

    def test_file_contracts_reject_wrong_identity_and_nested_value_types(self) -> None:
        """相同底层 UUID 也不能把作业身份用作产物，嵌套描述不得用裸值替代。"""
        wrong_id = cast(ArtifactId, JobId(self.artifact.id.value))
        with self.assertRaises(TypeError):
            FileReference(artifact_id=wrong_id, content=self.content)
        with self.assertRaises(TypeError):
            FileReference(artifact_id=self.artifact.id, content=cast(ContentFingerprint, {}))
        with self.assertRaises(TypeError):
            WorkspaceFileLocation(artifact_id=wrong_id, relative_path=WorkspaceRelativePath("cat.png"))
        with self.assertRaises(TypeError):
            WorkspaceFileLocation(artifact_id=self.artifact.id, relative_path=cast(WorkspaceRelativePath, "cat.png"))
        with self.assertRaises(TypeError):
            ImportOrigin(artifact_id=wrong_id, source_label="用户提供")

    def test_content_reference_and_location_cannot_be_rewritten_in_place(self) -> None:
        """冻结的内容、引用和定位不能在原对象上被改写。"""
        path = WorkspaceRelativePath("photos/cat.png")
        location = WorkspaceFileLocation(artifact_id=self.artifact.id, relative_path=path)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.content, "byte_size", 13)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.reference, "content", ContentFingerprint(sha256="b" * 64, byte_size=12))
        with self.assertRaises(FrozenInstanceError):
            setattr(path, "value", "photos/dog.png")
        with self.assertRaises(FrozenInstanceError):
            setattr(location, "artifact_id", ArtifactId(uuid4()))

    def test_reference_requires_the_exact_artifact_record(self) -> None:
        """文件引用精确匹配产物身份，不因记录处于同一工作区而接受错配。"""
        validate_file_reference(self.reference, artifact=self.artifact)
        other = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        with self.assertRaises(ArtifactContractError):
            validate_file_reference(self.reference, artifact=other)
        with self.assertRaises(TypeError):
            validate_file_reference(self.reference, artifact=cast(ArtifactIdentity, self.artifact.id))

    def test_binding_requires_same_identity_and_unchanged_content(self) -> None:
        """相同身份必须保持同一指纹，相同指纹也不能替代另一产物身份。"""
        equivalent = FileReference(
            artifact_id=self.artifact.id,
            content=ContentFingerprint(sha256=self.content.sha256, byte_size=self.content.byte_size),
        )
        validate_content_binding(self.reference, equivalent)
        candidates = (
            FileReference(artifact_id=self.artifact.id, content=ContentFingerprint(sha256="b" * 64, byte_size=12)),
            FileReference(artifact_id=self.artifact.id, content=ContentFingerprint(sha256="a" * 64, byte_size=13)),
            FileReference(artifact_id=ArtifactId(uuid4()), content=self.content),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ArtifactContractError):
                    validate_content_binding(self.reference, candidate)

    def test_observation_compares_both_declared_digest_and_size(self) -> None:
        """只比较传入指纹，摘要或长度任何一项不符都拒绝。"""
        validate_content_observation(self.reference, observed=self.content)
        observations = (
            ContentFingerprint(sha256="b" * 64, byte_size=12),
            ContentFingerprint(sha256="a" * 64, byte_size=13),
        )
        for observed in observations:
            with self.subTest(observed=observed):
                with self.assertRaises(ArtifactContractError):
                    validate_content_observation(self.reference, observed=observed)
        with self.assertRaises(TypeError):
            validate_content_observation(self.reference, observed=cast(ContentFingerprint, self.content.sha256))

    def test_relative_path_preserves_valid_text_without_normalization(self) -> None:
        """规范相对路径保留中文和实际空格，不修剪文件名或改写路径。"""
        for value in ("cat.png", "原始照片/猫的左侧.png", " folder/file name ", "images/cat..png"):
            with self.subTest(value=value):
                path = WorkspaceRelativePath(value)
                self.assertEqual(path.value, value)

    def test_relative_path_rejects_external_and_noncanonical_locations(self) -> None:
        """拒绝绝对路径、协议、盘符、非规范段、控制字符及无效 UTF-8。"""
        invalid_paths = (
            "", "/tmp/cat.png", "//server/share/cat.png", "C:/cat.png", "C:cat.png",
            "file:cat.png", "https://example.test/cat.png", "s3:bucket/cat.png",
            "photos\\cat.png", ".", "..", "./cat.png", "../cat.png", "photos/./cat.png",
            "photos/../cat.png", "photos//cat.png", "photos/", "photos/\x00cat.png",
            "photos/\tcat.png", "photos/\ncat.png", "photos/\rcat.png", "photos/\x7fcat.png",
            "photos/\x85cat.png", "photos/\ud800.png",
        )
        for value in invalid_paths:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ArtifactContractError):
                    WorkspaceRelativePath(value)
        with self.assertRaises(TypeError):
            WorkspaceRelativePath(cast(str, b"photos/cat.png"))

    def test_relocation_keeps_content_identity_but_rejects_another_artifact(self) -> None:
        """移动位置不重绑内容，不同产物的位置仍必须拒绝。"""
        for path in ("photos/cat.png", "archived/cat.png"):
            validate_file_location(
                WorkspaceFileLocation(artifact_id=self.artifact.id, relative_path=WorkspaceRelativePath(path)),
                reference=self.reference,
            )
        with self.assertRaises(ArtifactContractError):
            validate_file_location(
                WorkspaceFileLocation(artifact_id=ArtifactId(uuid4()), relative_path=WorkspaceRelativePath("photos/cat.png")),
                reference=self.reference,
            )

    def test_import_origin_preserves_known_label_without_treating_it_as_location(self) -> None:
        """出处可保留历史绝对路径文字，仅核对关联，不将文字当读取入口。"""
        label = "  用户提供：C:\\照片\\cat.png  "
        origin = ImportOrigin(artifact_id=self.artifact.id, source_label=label)
        self.assertEqual(origin.source_label, label)
        validate_import_origin(origin, reference=self.reference)
        with self.assertRaises(ArtifactContractError):
            validate_import_origin(ImportOrigin(artifact_id=ArtifactId(uuid4()), source_label=label), reference=self.reference)
        for invalid in ("", "来源\ud800"):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ArtifactContractError):
                    ImportOrigin(artifact_id=self.artifact.id, source_label=invalid)
        with self.assertRaises(TypeError):
            ImportOrigin(artifact_id=self.artifact.id, source_label=cast(str, None))

    def test_file_set_matches_exact_records_without_imposing_workspace_scope(self) -> None:
        """相同内容可有独立身份；精确集合检查不代替业务目标的同区要求。"""
        second = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=WorkspaceId(uuid4()))
        second_reference = FileReference(artifact_id=second.id, content=self.content)
        validate_file_set((second_reference, self.reference), artifacts=(self.artifact, second))
        validate_file_set((), artifacts=())
        with self.assertRaises(IdentityRelationError):
            validate_artifact_target(
                ArtifactSetTarget(artifact_ids=frozenset({self.artifact.id, second.id})),
                artifacts=(self.artifact, second),
            )

    def test_file_set_rejects_missing_extra_and_duplicate_identities(self) -> None:
        """缺失、多余和任一侧重复身份都无法成为有效文件集合。"""
        other = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        other_reference = FileReference(artifact_id=other.id, content=self.content)
        invalid_sets = (
            ((self.reference,), ()),
            ((), (self.artifact,)),
            ((self.reference,), (self.artifact, other)),
            ((self.reference, other_reference), (self.artifact,)),
            ((self.reference, self.reference), (self.artifact,)),
            ((self.reference,), (self.artifact, self.artifact)),
            ((self.reference,), (other,)),
        )
        for references, artifacts in invalid_sets:
            with self.subTest(references=references, artifacts=artifacts):
                with self.assertRaises(ArtifactContractError):
                    validate_file_set(references, artifacts=artifacts)
        with self.assertRaises(TypeError):
            validate_file_set(cast(tuple[FileReference, ...], [self.reference]), artifacts=(self.artifact,))
        with self.assertRaises(TypeError):
            validate_file_set((self.reference,), artifacts=cast(tuple[ArtifactIdentity, ...], [self.artifact]))

    def test_changed_content_uses_new_identity_and_existing_derivation_relation(self) -> None:
        """新内容用新产物身份，经既有派生边交接，不在文件描述内重存来源。"""
        output = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.workspace_id)
        output_reference = FileReference(artifact_id=output.id, content=ContentFingerprint(sha256="b" * 64, byte_size=24))
        validate_file_set((self.reference, output_reference), artifacts=(self.artifact, output))
        validate_derivation(
            Derivation(output_id=output.id, source_ids=frozenset({self.artifact.id})),
            output=output,
            sources=(self.artifact,),
        )
        with self.assertRaises(ArtifactContractError):
            validate_content_binding(self.reference, output_reference)

    def test_execution_output_reuses_existing_attempt_relation(self) -> None:
        """已有尝试产出边可关联文件引用，不向内容或出处再写尝试字段。"""
        task = TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id)
        job = JobIdentity(id=JobId(uuid4()), task_id=task.id)
        attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job.id)
        validate_file_reference(self.reference, artifact=self.artifact)
        validate_attempt_output(
            AttemptOutput(attempt_id=attempt.id, artifact_id=self.artifact.id),
            attempt=attempt,
            job=job,
            task=task,
            artifact=self.artifact,
        )

    def test_version_target_keeps_its_exact_file_identity_after_new_content_exists(self) -> None:
        """模型版本目标继续引用原文件身份，新内容不能借用该目标的旧引用。"""
        family = ModelFamilyIdentity(id=ModelFamilyId(uuid4()), workspace_id=self.workspace_id)
        version = ModelVersionIdentity(
            id=ModelVersionId(uuid4()),
            family_id=family.id,
            artifact_ids=frozenset({self.artifact.id}),
        )
        validate_version_target(
            ModelVersionTarget(version_id=version.id),
            version=version,
            family=family,
            artifacts=(self.artifact,),
        )
        validate_file_set((self.reference,), artifacts=(self.artifact,))
        revised = FileReference(artifact_id=ArtifactId(uuid4()), content=ContentFingerprint(sha256="b" * 64, byte_size=24))
        with self.assertRaises(ArtifactContractError):
            validate_file_set((revised,), artifacts=(self.artifact,))
