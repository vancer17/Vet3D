# 文件信息：L0-05 内存生成仓储的并发登记和事实归约测试。
# 作用：验证首次登记提交权、固定意图和拒绝事件的原子边界。
# 边界：仅覆盖单事件循环和实例内存，不证明线程安全、持久化或重启恢复。
"""通过公开入口验证仓储不会重复授予提交权或污染既有记录。"""

import asyncio
from dataclasses import FrozenInstanceError, replace
from typing import cast
import unittest
from uuid import uuid4

from vet3d.adapters import MemoryReconstructionRepository
from vet3d.application import ReconstructionConflict, ReconstructionEvent
from vet3d.artifacts import ArtifactContractError, ContentFingerprint, FileReference
from vet3d.execution import (
    AttemptActive, AttemptCancelled, AttemptFailed, AttemptSucceeded, CancellationAcknowledged,
    ExecutionContractError, QueryUnavailable, SubmissionUnconfirmed,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, AttemptOutput,
    IdentityRelationError, JobId, JobIdentity, TaskId, TaskIdentity, WorkspaceId,
)
from vet3d.modeling import (
    GeneratedArtifact, GenerationPlan, PreparedView, PreparedViews,
    ReconstructionRequest, ReconstructionUpdate, TaskReferences, ViewDirection,
)


class MemoryReconstructionRepositoryTests(unittest.IsolatedAsyncioTestCase):
    """检查仓储公开结果，不借用私有字典或假设真实远端副作用。"""

    def setUp(self) -> None:
        """准备两个独立方向的请求和一个未登记的内存仓储。"""
        self.repository = MemoryReconstructionRepository()
        task = TaskIdentity(id=TaskId(uuid4()), workspace_id=WorkspaceId(uuid4()))
        job = JobIdentity(id=JobId(uuid4()), task_id=task.id)
        attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job.id)
        front_id, back_id = ArtifactId(uuid4()), ArtifactId(uuid4())
        self.request = ReconstructionRequest(
            task=task, job=job, attempt=attempt,
            references=TaskReferences(
                task_id=task.id, subject_reference_id=front_id,
                preserve_features=("保留已有斑纹",),
                required_preparation_directions=frozenset({ViewDirection.FRONT, ViewDirection.BACK}),
            ),
            prepared=PreparedViews(
                views=(
                    PreparedView(front_id, ViewDirection.FRONT),
                    PreparedView(back_id, ViewDirection.BACK),
                ),
                review_only=(),
            ),
            plan=GenerationPlan(input_ids=(front_id, back_id)),
            files=(
                FileReference(front_id, ContentFingerprint(sha256="a" * 64, byte_size=10)),
                FileReference(back_id, ContentFingerprint(sha256="b" * 64, byte_size=11)),
            ),
        )

    def _output(self, request: ReconstructionRequest) -> GeneratedArtifact:
        """构造属于所给请求的独立合成产物声明，不写文件。

        :param request: 产物所关联的生成请求。
        :returns: 拥有新身份、合成指纹和原尝试来源的产物。
        """
        artifact = ArtifactIdentity(id=ArtifactId(uuid4()), workspace_id=request.task.workspace_id)
        return GeneratedArtifact(
            artifact=artifact,
            file=FileReference(artifact.id, ContentFingerprint(sha256="c" * 64, byte_size=20)),
            origin=AttemptOutput(attempt_id=request.attempt.id, artifact_id=artifact.id),
        )

    async def test_claim_registers_once_and_get_returns_the_frozen_record(self) -> None:
        """未登记读回为空，首次登记可读回，重复请求不取得第二次提交权。"""
        self.assertIsNone(await self.repository.get(self.request.attempt.id))
        self.assertTrue(await self.repository.claim(self.request))
        original = await self.repository.get(self.request.attempt.id)
        assert original is not None
        self.assertEqual(original.request, self.request)
        self.assertIsNone(original.observation)
        self.assertEqual(original.outputs, ())
        self.assertFalse(await self.repository.claim(self.request))
        self.assertIs(await self.repository.get(self.request.attempt.id), original)
        with self.assertRaises(FrozenInstanceError):
            setattr(original, "observation", AttemptSucceeded(self.request.attempt.id))

    async def test_concurrent_identical_claims_grant_only_one_submission(self) -> None:
        """同事件循环内的并发首次请求仅一个取得提交权。"""
        claims = await asyncio.gather(*(self.repository.claim(self.request) for _ in range(8)))
        self.assertEqual(sum(claims), 1)
        record = await self.repository.get(self.request.attempt.id)
        assert record is not None
        self.assertEqual(record.request, self.request)

    async def test_same_attempt_cannot_change_plan_or_job(self) -> None:
        """原尝试改换选图或作业都被拒绝，原冻结记录保持。"""
        await self.repository.claim(self.request)
        original = await self.repository.get(self.request.attempt.id)
        changed_plan = replace(
            self.request, plan=GenerationPlan(input_ids=tuple(reversed(self.request.plan.input_ids))),
        )
        other_job = JobIdentity(id=JobId(uuid4()), task_id=self.request.task.id)
        changed_job = replace(
            self.request, job=other_job,
            attempt=AttemptIdentity(id=self.request.attempt.id, job_id=other_job.id),
        )
        for changed in (changed_plan, changed_job):
            with self.subTest(changed=changed):
                with self.assertRaises(ReconstructionConflict):
                    await self.repository.claim(changed)
                self.assertIs(await self.repository.get(self.request.attempt.id), original)

    async def test_same_job_unresolved_active_or_successful_attempt_blocks_new_submission(self) -> None:
        """受理不明、活动、成功或仅取消受理均不能通过换尝试身份取得提交权。"""
        events: tuple[ReconstructionEvent | None, ...] = (
            None,
            SubmissionUnconfirmed(self.request.attempt.id, reason="提交回执不明"),
            ReconstructionUpdate(AttemptActive(self.request.attempt.id)),
            ReconstructionUpdate(AttemptSucceeded(self.request.attempt.id)),
            CancellationAcknowledged(self.request.attempt.id, reason="仅取消请求已受理"),
        )
        for event in events:
            with self.subTest(event=type(event).__name__):
                repository = MemoryReconstructionRepository()
                await repository.claim(self.request)
                if event is not None:
                    await repository.record(self.request.attempt.id, event)
                original = await repository.get(self.request.attempt.id)
                next_attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.request.job.id)
                with self.assertRaises(ReconstructionConflict):
                    await repository.claim(replace(self.request, attempt=next_attempt))
                self.assertIsNone(await repository.get(next_attempt.id))
                self.assertFalse(await repository.claim(self.request))
                self.assertIs(await repository.get(self.request.attempt.id), original)

    async def test_same_job_confirmed_failure_or_cancellation_allows_explicit_same_intent(self) -> None:
        """确认失败或取消后允许显式同意图新尝试，但不创建重试或放行后续并发尝试。"""
        terminals = (
            AttemptFailed(self.request.attempt.id, reason="确认生成失败"),
            AttemptCancelled(self.request.attempt.id),
        )
        for terminal in terminals:
            with self.subTest(terminal=type(terminal).__name__):
                repository = MemoryReconstructionRepository()
                await repository.claim(self.request)
                original = await repository.record(
                    self.request.attempt.id, ReconstructionUpdate(terminal),
                )
                next_attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.request.job.id)
                repeated_intent = replace(self.request, attempt=next_attempt)
                changed_intent = replace(
                    repeated_intent, plan=GenerationPlan(input_ids=(self.request.plan.input_ids[0],)),
                )
                with self.assertRaises(ReconstructionConflict):
                    await repository.claim(changed_intent)
                self.assertIsNone(await repository.get(next_attempt.id))
                self.assertTrue(await repository.claim(repeated_intent))
                self.assertFalse(await repository.claim(repeated_intent))
                preserved = await repository.get(next_attempt.id)
                assert preserved is not None
                self.assertEqual(preserved.request, repeated_intent)
                self.assertIsNone(preserved.observation)
                self.assertIs(await repository.get(self.request.attempt.id), original)
                concurrent_attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=self.request.job.id)
                with self.assertRaises(ReconstructionConflict):
                    await repository.claim(replace(self.request, attempt=concurrent_attempt))
                self.assertIsNone(await repository.get(concurrent_attempt.id))

    async def test_different_jobs_keep_independent_frozen_intents(self) -> None:
        """不同作业允许独立选图，更新时仍不能混入另一作业尝试的事件。"""
        await self.repository.claim(self.request)
        other_job = JobIdentity(id=JobId(uuid4()), task_id=self.request.task.id)
        other_request = replace(
            self.request, job=other_job,
            attempt=AttemptIdentity(id=AttemptId(uuid4()), job_id=other_job.id),
            plan=GenerationPlan(input_ids=(self.request.plan.input_ids[1],)),
        )
        self.assertTrue(await self.repository.claim(other_request))
        original = await self.repository.get(self.request.attempt.id)
        with self.assertRaises(ExecutionContractError):
            await self.repository.record(
                self.request.attempt.id, ReconstructionUpdate(AttemptActive(other_request.attempt.id)),
            )
        self.assertIs(await self.repository.get(self.request.attempt.id), original)

    async def test_updates_accumulate_outputs_and_diagnostics_preserve_them(self) -> None:
        """后续空产物更新、查询失败和取消回执都不会删除已有输出或替换终态。"""
        await self.repository.claim(self.request)
        output = self._output(self.request)
        active = await self.repository.record(
            self.request.attempt.id,
            ReconstructionUpdate(AttemptActive(self.request.attempt.id), outputs=(output,)),
        )
        completed = await self.repository.record(
            self.request.attempt.id, ReconstructionUpdate(AttemptSucceeded(self.request.attempt.id)),
        )
        self.assertEqual(active.outputs, (output,))
        self.assertEqual(completed.outputs, (output,))
        for event in (
            QueryUnavailable(self.request.attempt.id, reason="后续查询暂不可用"),
            CancellationAcknowledged(self.request.attempt.id, reason="取消请求已受理"),
        ):
            with self.subTest(event=event):
                current = await self.repository.record(self.request.attempt.id, event)
                self.assertEqual(current.observation, completed.observation)
                self.assertEqual(current.outputs, (output,))

    async def test_conflicting_terminal_or_output_does_not_pollute_the_record(self) -> None:
        """完整归约失败时不写入已处理的部分事件或改换已有产物内容。"""
        await self.repository.claim(self.request)
        output = self._output(self.request)
        original = await self.repository.record(
            self.request.attempt.id,
            ReconstructionUpdate(AttemptSucceeded(self.request.attempt.id), outputs=(output,)),
        )
        changed = replace(
            output, file=replace(output.file, content=ContentFingerprint(sha256="d" * 64, byte_size=20)),
        )
        with self.assertRaises(ArtifactContractError):
            await self.repository.record(
                self.request.attempt.id,
                ReconstructionUpdate(
                    AttemptSucceeded(self.request.attempt.id), outputs=(self._output(self.request), changed),
                ),
            )
        self.assertIs(await self.repository.get(self.request.attempt.id), original)
        with self.assertRaises(ExecutionContractError):
            await self.repository.record(
                self.request.attempt.id,
                ReconstructionUpdate(AttemptFailed(self.request.attempt.id, reason="矛盾失败终态")),
            )
        self.assertIs(await self.repository.get(self.request.attempt.id), original)

    async def test_foreign_output_and_input_reuse_leave_original_record_unchanged(self) -> None:
        """不同工作区产物和输入冒充产出都在赋值前被拒绝。"""
        await self.repository.claim(self.request)
        original = await self.repository.get(self.request.attempt.id)
        output = self._output(self.request)
        foreign = replace(output, artifact=replace(output.artifact, workspace_id=WorkspaceId(uuid4())))
        with self.assertRaises(IdentityRelationError):
            await self.repository.record(
                self.request.attempt.id,
                ReconstructionUpdate(AttemptActive(self.request.attempt.id), outputs=(foreign,)),
            )
        source = self.request.files[0]
        reused_input = GeneratedArtifact(
            artifact=ArtifactIdentity(id=source.artifact_id, workspace_id=self.request.task.workspace_id),
            file=source,
            origin=AttemptOutput(attempt_id=self.request.attempt.id, artifact_id=source.artifact_id),
        )
        with self.assertRaises(ReconstructionConflict):
            await self.repository.record(
                self.request.attempt.id,
                ReconstructionUpdate(AttemptActive(self.request.attempt.id), outputs=(reused_input,)),
            )
        self.assertIs(await self.repository.get(self.request.attempt.id), original)

    async def test_unknown_attempt_and_invalid_types_do_not_create_records(self) -> None:
        """保存入口不替代登记，错误类型或未知事件也不能创建可信状态。"""
        with self.assertRaises(ReconstructionConflict):
            await self.repository.record(
                self.request.attempt.id, SubmissionUnconfirmed(self.request.attempt.id, reason="未确认提交"),
            )
        self.assertIsNone(await self.repository.get(self.request.attempt.id))
        with self.assertRaises(TypeError):
            await self.repository.get(cast(AttemptId, JobId(self.request.attempt.id.value)))
        with self.assertRaises(TypeError):
            await self.repository.claim(cast(ReconstructionRequest, self.request.attempt))
        await self.repository.claim(self.request)
        original = await self.repository.get(self.request.attempt.id)
        with self.assertRaises(TypeError):
            await self.repository.record(self.request.attempt.id, cast(ReconstructionEvent, object()))
        self.assertIs(await self.repository.get(self.request.attempt.id), original)
