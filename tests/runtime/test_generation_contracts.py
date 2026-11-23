# 文件信息：L0-05 生成请求、产物及更新的契约测试。
# 作用：验证业务准备与单次选图分离，以及原尝试、确切内容和输出关联。
# 边界：合成摘要仅作为声明，不调用供应商、不生成实际模型、不证明业务质量。
"""通过公开入口验证具体生成数据，不复制执行枚举或构造兼容模式。"""

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from typing import cast
import unittest
from uuid import uuid4

from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileReference
from vet3d.execution import AttemptActive, AttemptFailed, AttemptObservation, AttemptSucceeded, QueryUnavailable
from vet3d.identity import (
    ArtifactId,
    ArtifactIdentity,
    AttemptId,
    AttemptIdentity,
    AttemptOutput,
    IdentityRelationError,
    JobId,
    JobIdentity,
    TaskId,
    TaskIdentity,
    WorkspaceId,
)
from vet3d.modeling import (
    CapabilityUnverified,
    GeneratedArtifact,
    GenerationPlan,
    ModelingContractError,
    PreparedView,
    PreparedViews,
    ReconstructionRequest,
    ReconstructionUpdate,
    ReviewReference,
    TaskReferences,
    ViewDirection,
    validate_prepared_views,
)


class GenerationContractTests(unittest.TestCase):
    """检查准备、选图及结果的不同权威边界，不声明适配器已可运行。"""

    def setUp(self) -> None:
        """准备同一任务中的五向引用和一份独立的验收参考。"""
        self.task = TaskIdentity(id=TaskId(uuid4()), workspace_id=WorkspaceId(uuid4()))
        self.job = JobIdentity(id=JobId(uuid4()), task_id=self.task.id)
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.job.id)
        self.views = tuple(PreparedView(artifact_id=ArtifactId(uuid4()), direction=direction) for direction in ViewDirection)
        self.review_id = ArtifactId(uuid4())
        self.prepared = PreparedViews(
            views=self.views, review_only=(ReviewReference(artifact_id=self.review_id),)
        )
        self.references = TaskReferences(
            task_id=self.task.id,
            subject_reference_id=self.views[0].artifact_id,
            preserve_features=("保留左侧斑纹",),
            required_preparation_directions=frozenset(ViewDirection),
        )
        self.files = tuple(
            FileReference(
                artifact_id=view.artifact_id,
                content=ContentFingerprint(
                    sha256=sha256(view.direction.value.encode("utf-8")).hexdigest(),
                    byte_size=len(view.direction.value),
                ),
            )
            for view in self.views
        ) + (
            FileReference(artifact_id=self.review_id, content=ContentFingerprint(sha256=sha256(b"review").hexdigest(), byte_size=6)),
        )
        self.artifacts = tuple(
            ArtifactIdentity(id=reference.artifact_id, workspace_id=self.task.workspace_id)
            for reference in self.files
        )
        self.request = ReconstructionRequest(
            task=self.task,
            job=self.job,
            attempt=self.attempt,
            references=self.references,
            prepared=self.prepared,
            plan=GenerationPlan(input_ids=tuple(view.artifact_id for view in self.views)),
            files=self.files,
        )

    def _generated_artifact(self) -> GeneratedArtifact:
        """构造属于原尝试的输出声明，不模拟文件落盘或生成质量。

        :returns: 身份、内容和产出边相互匹配的冻结记录。
        """
        artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=self.task.workspace_id)
        return GeneratedArtifact(
            artifact=artifact,
            file=FileReference(
                artifact_id=artifact.id,
                content=ContentFingerprint(sha256=sha256(b"candidate").hexdigest(), byte_size=9),
            ),
            origin=AttemptOutput(attempt_id=self.attempt.id, artifact_id=artifact.id),
        )

    def test_five_prepared_views_allow_five_four_or_one_generation_inputs(self) -> None:
        """五向业务准备完成后可选择五图、四图或单图，准备目标保持不变。"""
        validate_prepared_views(
            self.prepared, references=self.references, task=self.task, files=self.files, artifacts=self.artifacts
        )
        selections = (
            tuple(view.artifact_id for view in self.views),
            tuple(view.artifact_id for view in self.views if view.direction is not ViewDirection.TOP),
            (self.views[0].artifact_id,),
        )
        for input_ids in selections:
            with self.subTest(count=len(input_ids)):
                request = replace(self.request, plan=GenerationPlan(input_ids=input_ids))
                self.assertEqual(request.plan.input_ids, input_ids)
                self.assertIs(request.references, self.references)
                self.assertIs(request.prepared, self.prepared)
                self.assertEqual(request.references.required_preparation_directions, frozenset(ViewDirection))

    def test_input_order_selects_the_operation_main_without_changing_subject_reference(self) -> None:
        """计划首项选择操作主参考，既有任务主体基准和方向记录不被重写。"""
        left = next(view for view in self.views if view.direction is ViewDirection.LEFT)
        request = replace(
            self.request,
            plan=GenerationPlan(input_ids=(left.artifact_id, self.references.subject_reference_id)),
        )
        self.assertEqual(request.plan.input_ids[0], left.artifact_id)
        self.assertNotEqual(request.plan.input_ids[0], request.references.subject_reference_id)
        self.assertEqual(tuple(view.direction for view in request.prepared.views), tuple(ViewDirection))

    def test_review_only_and_unprepared_artifacts_cannot_be_submitted(self) -> None:
        """验收参考及未准备的产物不能因拥有合法身份就成为生成输入。"""
        for artifact_id in (self.review_id, ArtifactId(uuid4())):
            with self.subTest(artifact_id=artifact_id):
                with self.assertRaises(ModelingContractError):
                    replace(self.request, plan=GenerationPlan(input_ids=(artifact_id,)))

    def test_request_does_not_replace_service_preparation_and_file_validation(self) -> None:
        """请求可关联未齐的准备声明，服务解析后仍须执行唯一完整性校验。"""
        partial = replace(
            self.request,
            prepared=PreparedViews(views=(self.views[0],), review_only=()),
            plan=GenerationPlan(input_ids=(self.views[0].artifact_id,)),
            files=(self.files[0],),
        )
        with self.assertRaises(ModelingContractError):
            validate_prepared_views(
                partial.prepared,
                references=partial.references,
                task=partial.task,
                files=partial.files,
                artifacts=(self.artifacts[0],),
            )

    def test_request_rejects_wrong_parent_chain_and_task_reference(self) -> None:
        """原尝试须属于当前任务的作业，主体要求也必须属于同一任务。"""
        with self.assertRaises(IdentityRelationError):
            replace(self.request, job=JobIdentity(id=self.job.id, task_id=TaskId(uuid4())))
        with self.assertRaises(IdentityRelationError):
            replace(self.request, attempt=AttemptIdentity(id=self.attempt.id, job_id=JobId(uuid4())))
        with self.assertRaises(ModelingContractError):
            replace(self.request, references=replace(self.references, task_id=TaskId(uuid4())))

    def test_plan_requires_nonempty_unique_ordered_artifact_ids(self) -> None:
        """拒绝空计划、重复产物、可变容器和错类身份，不隐式补齐或排序。"""
        first_id = self.views[0].artifact_id
        for input_ids in ((), (first_id, first_id)):
            with self.subTest(input_ids=input_ids):
                with self.assertRaises(ModelingContractError):
                    GenerationPlan(input_ids=input_ids)
        with self.assertRaises(TypeError):
            GenerationPlan(input_ids=cast(tuple[ArtifactId, ...], [first_id]))
        with self.assertRaises(TypeError):
            GenerationPlan(input_ids=(cast(ArtifactId, self.task.id),))

    def test_request_keeps_expected_file_content_frozen_and_strictly_typed(self) -> None:
        """登记请求持有不可变内容引用，不能就地替换预期内容或传入裸值。"""
        with self.assertRaises(FrozenInstanceError):
            setattr(self.request, "files", ())
        with self.assertRaises(TypeError):
            replace(self.request, files=cast(tuple[FileReference, ...], list(self.files)))
        with self.assertRaises(TypeError):
            replace(self.request, files=(cast(FileReference, self.views[0].artifact_id),))
        with self.assertRaises(TypeError):
            replace(self.request, attempt=cast(AttemptIdentity, self.attempt.id))

    def test_generated_artifact_requires_matching_file_and_origin_ids(self) -> None:
        """内容引用和产出边都必须属于确切输出产物，保留已有文件异常。"""
        output = self._generated_artifact()
        with self.assertRaises(ArtifactContractError):
            replace(output, file=replace(output.file, artifact_id=ArtifactId(uuid4())))
        with self.assertRaises(ModelingContractError):
            replace(output, origin=AttemptOutput(attempt_id=self.attempt.id, artifact_id=ArtifactId(uuid4())))

    def test_updates_allow_no_outputs_and_partial_outputs_after_execution_failure(self) -> None:
        """执行成功不补造产物，活动或失败也不抹除已知输出。"""
        ReconstructionUpdate(observation=AttemptSucceeded(self.attempt.id))
        output = self._generated_artifact()
        for observation in (
            AttemptActive(self.attempt.id),
            AttemptFailed(self.attempt.id, reason="执行端报告失败但已有候选"),
        ):
            with self.subTest(observation=observation):
                update = ReconstructionUpdate(observation=observation, outputs=(output,))
                self.assertIs(update.outputs[0], output)

    def test_update_rejects_duplicate_or_foreign_attempt_outputs_and_diagnostic_observation(self) -> None:
        """输出须唯一且属于原观察尝试，查询诊断不能伪装成执行观察。"""
        output = self._generated_artifact()
        observation = AttemptSucceeded(self.attempt.id)
        with self.assertRaises(ModelingContractError):
            ReconstructionUpdate(observation=observation, outputs=(output, output))
        with self.assertRaises(ModelingContractError):
            ReconstructionUpdate(observation=AttemptSucceeded(AttemptId(uuid4())), outputs=(output,))
        with self.assertRaises(TypeError):
            ReconstructionUpdate(
                observation=cast(AttemptObservation, QueryUnavailable(self.attempt.id, reason="未取得可信观察"))
            )
        with self.assertRaises(TypeError):
            ReconstructionUpdate(observation=observation, outputs=cast(tuple[GeneratedArtifact, ...], [output]))

    def test_unverified_capability_requires_a_real_diagnostic(self) -> None:
        """未证实适配规则必须保留有效原因，不把空文字补成能力判断。"""
        for reason in ("", " \n", "未证实\ud800"):
            with self.subTest(reason=repr(reason)):
                with self.assertRaises(ModelingContractError):
                    CapabilityUnverified(reason=reason)
        with self.assertRaises(TypeError):
            CapabilityUnverified(reason=cast(str, False))
