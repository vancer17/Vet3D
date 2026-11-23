# 文件信息：L0-03 建模照片引用与五向选择契约测试。
# 作用：验证任务主体基准、单次操作输入和重建视图的不同作用域。
# 边界：使用合成字节声明摘要；不读取真实照片，不证明照片方向或动物一致性。
"""通过业务不变量验证引用集合，不将结构通过解释为视觉质量合格。"""

from hashlib import sha256
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileReference
from vet3d.identity import ArtifactId, ArtifactIdentity, IdentityRelationError, TaskId, TaskIdentity, WorkspaceId
from vet3d.modeling import (
    ImageOperationReferences,
    ModelingContractError,
    ReconstructionView,
    ReviewReference,
    SelectedViews,
    TaskReferences,
    ViewDirection,
    validate_operation_references,
    validate_selected_views,
    validate_task_references,
)


class ModelingReferenceTests(unittest.TestCase):
    """核对显式传入的内容记录及业务角色，不建立解析器或质量评审。"""

    def setUp(self) -> None:
        """准备一个任务、五向合成内容和独立的验收参考。"""
        self.workspace_id = WorkspaceId(uuid4())
        self.task = TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id)
        self.photos = {direction: self._photo(direction.value.encode("utf-8")) for direction in ViewDirection}
        self.front_file, self.front_identity = self.photos[ViewDirection.FRONT]
        self.left_file, self.left_identity = self.photos[ViewDirection.LEFT]
        self.review_file, self.review_identity = self._photo(b"review")
        self.references = TaskReferences(
            task_id=self.task.id,
            subject_reference_id=self.front_file.artifact_id,
            preserve_features=("保留左侧斑纹",),
            required_directions=frozenset(ViewDirection),
        )
        self.reconstruction = tuple(
            ReconstructionView(artifact_id=file.artifact_id, direction=direction)
            for direction, (file, _) in self.photos.items()
        )
        self.files = tuple(file for file, _ in self.photos.values())
        self.artifacts = tuple(artifact for _, artifact in self.photos.values())

    def _photo(self, content: bytes) -> tuple[FileReference, ArtifactIdentity]:
        """创建当前工作区的合成内容声明，作为引用校验的输入。

        :param content: 仅用于构造摘要和长度的合成字节。
        :returns: 共享同一文件身份的内容引用及身份记录。
        """
        artifact_id = ArtifactId(uuid4())
        return (
            FileReference(
                artifact_id=artifact_id,
                content=ContentFingerprint(sha256=sha256(content).hexdigest(), byte_size=len(content)),
            ),
            ArtifactIdentity(id=artifact_id, workspace_id=self.workspace_id),
        )

    def test_subject_and_operation_main_are_independent_and_reusable(self) -> None:
        """操作可使用另一主图，主体基准可同时作为补充或重建照片。"""
        validate_task_references(
            self.references, task=self.task, files=(self.front_file,), artifacts=(self.front_identity,)
        )
        operation = ImageOperationReferences(
            main_image_id=self.left_file.artifact_id,
            supplementary_ids=frozenset({self.front_file.artifact_id}),
            target_direction=ViewDirection.TOP,
        )
        validate_operation_references(
            operation,
            references=self.references,
            task=self.task,
            files=(self.left_file, self.front_file),
            artifacts=(self.front_identity, self.left_identity),
        )
        validate_selected_views(
            SelectedViews(reconstruction=self.reconstruction, review_only=()),
            references=self.references,
            task=self.task,
            files=self.files,
            artifacts=self.artifacts,
        )

    def test_review_only_and_unknown_direction_do_not_fill_a_required_view(self) -> None:
        """验收参考可不标方向；即使标顶视也不能补齐缺失的重建顶视。"""
        selection = SelectedViews(
            reconstruction=self.reconstruction,
            review_only=(ReviewReference(artifact_id=self.review_file.artifact_id),),
        )
        validate_selected_views(
            selection,
            references=self.references,
            task=self.task,
            files=(*self.files, self.review_file),
            artifacts=(*self.artifacts, self.review_identity),
        )
        without_top = tuple(view for view in self.reconstruction if view.direction is not ViewDirection.TOP)
        top_file, _ = self.photos[ViewDirection.TOP]
        for direction in (None, ViewDirection.TOP):
            with self.subTest(review_direction=direction):
                with self.assertRaises(ModelingContractError):
                    validate_selected_views(
                        SelectedViews(
                            reconstruction=without_top,
                            review_only=(ReviewReference(artifact_id=top_file.artifact_id, direction=direction),),
                        ),
                        references=self.references,
                        task=self.task,
                        files=self.files,
                        artifacts=self.artifacts,
                    )

    def test_distinct_artifact_ids_cannot_reuse_content_to_fill_two_views(self) -> None:
        """相同内容换一个文件身份后仍不能同时充当前向和左向重建输入。"""
        duplicate_file, duplicate_identity = self._photo(b"front")
        selection = SelectedViews(
            reconstruction=(
                ReconstructionView(artifact_id=self.front_file.artifact_id, direction=ViewDirection.FRONT),
                ReconstructionView(artifact_id=duplicate_file.artifact_id, direction=ViewDirection.LEFT),
            ),
            review_only=(),
        )
        references = TaskReferences(
            task_id=self.task.id,
            subject_reference_id=self.front_file.artifact_id,
            preserve_features=(),
            required_directions=frozenset({ViewDirection.FRONT, ViewDirection.LEFT}),
        )
        with self.assertRaises(ModelingContractError):
            validate_selected_views(
                selection,
                references=references,
                task=self.task,
                files=(self.front_file, duplicate_file),
                artifacts=(self.front_identity, duplicate_identity),
            )

    def test_selected_roles_and_reconstruction_directions_are_unambiguous(self) -> None:
        """同一选择内的文件角色互斥，两个不同文件不能占据同一重建方向。"""
        front = ReconstructionView(artifact_id=self.front_file.artifact_id, direction=ViewDirection.FRONT)
        with self.assertRaises(ModelingContractError):
            SelectedViews(
                reconstruction=(front,),
                review_only=(ReviewReference(artifact_id=self.front_file.artifact_id),),
            )
        with self.assertRaises(ModelingContractError):
            SelectedViews(
                reconstruction=(
                    front,
                    ReconstructionView(artifact_id=self.left_file.artifact_id, direction=ViewDirection.FRONT),
                ),
                review_only=(),
            )
        with self.assertRaises(ModelingContractError):
            SelectedViews(reconstruction=(front, front), review_only=())
        with self.assertRaises(ModelingContractError):
            ImageOperationReferences(
                main_image_id=self.front_file.artifact_id,
                supplementary_ids=frozenset({self.front_file.artifact_id}),
                target_direction=ViewDirection.LEFT,
            )

    def test_subject_records_must_be_exact_and_belong_to_the_task_workspace(self) -> None:
        """主体引用拒绝缺项、多项、重复项以及同身份的跨工作区记录。"""
        invalid_files = ((), (self.front_file, self.left_file), (self.front_file, self.front_file))
        for files in invalid_files:
            with self.subTest(files=files):
                with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
                    validate_task_references(
                        self.references, task=self.task, files=files, artifacts=(self.front_identity,)
                    )
        invalid_artifacts = (
            (),
            (self.front_identity, self.left_identity),
            (self.front_identity, self.front_identity),
            (ArtifactIdentity(id=self.front_identity.id, workspace_id=WorkspaceId(uuid4())),),
        )
        for artifacts in invalid_artifacts:
            with self.subTest(artifacts=artifacts):
                with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
                    validate_task_references(
                        self.references, task=self.task, files=(self.front_file,), artifacts=artifacts
                    )

    def test_operation_requires_the_subject_even_when_using_another_main_image(self) -> None:
        """操作引用按基准与操作输入的并集解析，不能遗漏独立主体记录。"""
        operation = ImageOperationReferences(
            main_image_id=self.left_file.artifact_id,
            supplementary_ids=frozenset(),
            target_direction=ViewDirection.BACK,
        )
        with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
            validate_operation_references(
                operation,
                references=self.references,
                task=self.task,
                files=(self.left_file,),
                artifacts=(self.left_identity,),
            )
        with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
            validate_operation_references(
                operation,
                references=self.references,
                task=self.task,
                files=(self.front_file, self.left_file),
                artifacts=(
                    self.front_identity,
                    ArtifactIdentity(id=self.left_identity.id, workspace_id=WorkspaceId(uuid4())),
                ),
            )

    def test_selected_views_require_exact_records_in_the_task_workspace(self) -> None:
        """完整五向声明不能绕过缺件、额外内容或跨工作区的解析边界。"""
        selection = SelectedViews(reconstruction=self.reconstruction, review_only=())
        for files in (self.files[:-1], (*self.files, self.review_file), (*self.files, self.front_file)):
            with self.subTest(files=files):
                with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
                    validate_selected_views(
                        selection, references=self.references, task=self.task, files=files, artifacts=self.artifacts
                    )
        with self.assertRaises((ModelingContractError, ArtifactContractError, IdentityRelationError)):
            validate_selected_views(
                selection,
                references=self.references,
                task=self.task,
                files=self.files,
                artifacts=(
                    ArtifactIdentity(id=self.artifacts[0].id, workspace_id=WorkspaceId(uuid4())),
                    *self.artifacts[1:],
                ),
            )

    def test_another_task_and_empty_photo_cannot_supply_the_subject(self) -> None:
        """任务身份不符或零字节文件不能成为主体照片，不推断真实图像格式。"""
        with self.assertRaises(ModelingContractError):
            validate_task_references(
                self.references,
                task=TaskIdentity(id=TaskId(uuid4()), workspace_id=self.workspace_id),
                files=(self.front_file,),
                artifacts=(self.front_identity,),
            )
        empty = FileReference(
            artifact_id=self.front_file.artifact_id,
            content=ContentFingerprint(sha256=sha256(b"").hexdigest(), byte_size=0),
        )
        with self.assertRaises(ModelingContractError):
            validate_task_references(
                self.references, task=self.task, files=(empty,), artifacts=(self.front_identity,)
            )

    def test_direction_and_reference_collections_reject_implicit_coercion(self) -> None:
        """原始字符串、空需求和可变集合不能悄悄进入稳定业务契约。"""
        with self.assertRaises(TypeError):
            ReconstructionView(artifact_id=self.front_file.artifact_id, direction=cast(ViewDirection, "front"))
        with self.assertRaises(TypeError):
            ReviewReference(artifact_id=cast(ArtifactId, TaskId(uuid4())))
        with self.assertRaises(TypeError):
            TaskReferences(
                task_id=self.task.id,
                subject_reference_id=self.front_file.artifact_id,
                preserve_features=(),
                required_directions=cast(frozenset[ViewDirection], {ViewDirection.FRONT}),
            )
        with self.assertRaises(ModelingContractError):
            TaskReferences(
                task_id=self.task.id,
                subject_reference_id=self.front_file.artifact_id,
                preserve_features=(),
                required_directions=frozenset(),
            )
