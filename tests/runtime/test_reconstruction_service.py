# 文件信息：L0-05 最小生成服务的独立机械验收测试。
# 作用：以显式端口替身验证准备集与提交选择、一次提交、原尝试续查和故障边界。
# 范围：只操作内存声明，不读取图片、不生成模型、不证明真实供应商或业务质量。
"""通过公共 API 检查生成消费方的关联、安全交接及副作用恢复规则。"""

import asyncio
from dataclasses import replace
import unittest
from uuid import uuid4

from vet3d.adapters import (
    FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository,
    SyntheticArtifactAccess,
)
from vet3d.application import (
    ReconstructionConflict, ReconstructionEvent, ReconstructionRecord,
    ReconstructionRecordingError, ReconstructionRepository, ReconstructionService,
)
from vet3d.artifacts import (
    ArtifactAccess, ArtifactContractError, ContentFingerprint, FileMissing,
    FileObservation, FilePresent, FileReference, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath,
)
from vet3d.execution import (
    AttemptActive, AttemptCancelled, AttemptSucceeded, CancellationAcknowledged,
    CancellationUnconfirmed, CapabilityUnavailable, InputInsufficient,
    QueryUnavailable, SubmissionUnconfirmed,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, AttemptOutput,
    JobId, JobIdentity, TaskId, TaskIdentity, WorkspaceId,
)
from vet3d.modeling import (
    CapabilityUnverified, GeneratedArtifact, GenerationPlan, PreparedView,
    PreparedViews, ReconstructionPort, ReconstructionRequest, ReconstructionUpdate,
    SubmissionCompatible, TaskReferences, ViewDirection,
)


class _CountingGenerator(ReconstructionPort):
    """只为测试记录实际端口调用，不复制生成状态机。"""

    def __init__(self, delegate: ReconstructionPort) -> None:
        """保留被测实现和独立调用计数。

        :param delegate: 实际执行固定行为的生成替身。
        """
        self.delegate = delegate
        self.submit_calls = 0
        self.query_calls = 0
        self.cancel_calls = 0

    def check(
        self, request: ReconstructionRequest,
    ) -> SubmissionCompatible | CapabilityUnavailable | CapabilityUnverified:
        """转交具体选图的本地语义匹配。

        :param request: 原生成请求。
        :returns: 被包装实现的明确匹配结果。
        """
        return self.delegate.check(request)

    async def submit(
        self, request: ReconstructionRequest,
    ) -> ReconstructionUpdate | SubmissionUnconfirmed:
        """记录提交调用，包括适配器可能自行去重的重复调用。

        :param request: 原生成请求。
        :returns: 被包装实现的提交回包。
        """
        self.submit_calls += 1
        return await self.delegate.submit(request)

    async def query(self, attempt_id: AttemptId) -> ReconstructionUpdate | QueryUnavailable:
        """记录并转交原尝试的查询。

        :param attempt_id: 原尝试身份。
        :returns: 可信观察或查询诊断。
        """
        self.query_calls += 1
        return await self.delegate.query(attempt_id)

    async def cancel(
        self, attempt_id: AttemptId,
    ) -> CancellationAcknowledged | CancellationUnconfirmed | CapabilityUnavailable:
        """记录并转交取消请求，不制造执行取消终态。

        :param attempt_id: 原尝试身份。
        :returns: 被包装实现的取消请求回执。
        """
        self.cancel_calls += 1
        return await self.delegate.cancel(attempt_id)


class _CancellationUnsupported(_CountingGenerator):
    """声明适配器没有取消能力，不伪造取消请求已发送。"""

    async def cancel(self, attempt_id: AttemptId) -> CapabilityUnavailable:
        """在发送前明确拒绝取消操作。

        :param attempt_id: 调用方希望取消的原尝试。
        :returns: 明确不支持取消的能力结果。
        """
        self.cancel_calls += 1
        return CapabilityUnavailable("测试适配器不支持远端取消")


class _HeldSubmission(_CountingGenerator):
    """在替身建立绑定后挂起回包，用明确事件控制并发和本地中断。"""

    def __init__(self) -> None:
        """创建成功替身及不依赖时钟的提交到达、回包放行事件。"""
        super().__init__(FiveViewGenerator())
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def submit(
        self, request: ReconstructionRequest,
    ) -> ReconstructionUpdate | SubmissionUnconfirmed:
        """先建立原绑定，再等待测试放行或调用方取消。

        :param request: 原生成请求。
        :returns: 放行后的原提交结果。
        :raises asyncio.CancelledError: 本地等待被取消。
        """
        result = await super().submit(request)
        self.entered.set()
        await self.release.wait()
        return result


class _UnconfirmedSubmission(_CountingGenerator):
    """保留已发生的提交，只把首次回包替换为受理不明。"""

    async def submit(self, request: ReconstructionRequest) -> SubmissionUnconfirmed:
        """模拟已提交却没有可信受理回执，不删除原绑定。

        :param request: 原生成请求。
        :returns: 原尝试的受理不明诊断。
        """
        await super().submit(request)
        return SubmissionUnconfirmed(request.attempt.id, "测试提交回执丢失")


class _RaisedSubmission(_CountingGenerator):
    """在建立原绑定后抛出指定异常，模拟外部交互中断。"""

    def __init__(self, error: Exception) -> None:
        """保存应原样传播的具体依赖异常。

        :param error: 提交已发生后抛出的异常实例。
        """
        super().__init__(FiveViewGenerator())
        self.error = error

    async def submit(self, request: ReconstructionRequest) -> ReconstructionUpdate:
        """建立原绑定后抛错，不能据异常推断远端执行失败。

        :param request: 原生成请求。
        :raises Exception: 测试指定的原异常。
        """
        await super().submit(request)
        raise self.error


class _EmptySuccess(_CountingGenerator):
    """只替换成功回包中的输出集合，保留真实执行观察类型。"""

    async def submit(self, request: ReconstructionRequest) -> ReconstructionUpdate:
        """模拟已确认执行成功但尚未取得任何产物声明。

        :param request: 原生成请求。
        :returns: 无输出的成功观察。
        """
        await super().submit(request)
        return ReconstructionUpdate(AttemptSucceeded(request.attempt.id))


class _FailOnceRepository(ReconstructionRepository):
    """仅在一次事实保存时抛错，用于检查副作用后的恢复边界。"""

    def __init__(self, error: Exception) -> None:
        """创建实际内存仓储并保存单次故障。

        :param error: 首次保存事件时抛出的具体异常。
        """
        self.delegate = MemoryReconstructionRepository()
        self.error: Exception | None = error

    async def claim(self, request: ReconstructionRequest) -> bool:
        """保持实际仓储的原子登记语义。

        :param request: 原提交意图。
        :returns: 是否取得首次提交权。
        """
        return await self.delegate.claim(request)

    async def get(self, attempt_id: AttemptId) -> ReconstructionRecord | None:
        """读取实际仓储中保留下来的原意图。

        :param attempt_id: 原尝试身份。
        :returns: 原记录或未登记。
        """
        return await self.delegate.get(attempt_id)

    async def record(
        self, attempt_id: AttemptId, event: ReconstructionEvent,
    ) -> ReconstructionRecord:
        """首次保存拒绝，随后转交实际原子归约。

        :param attempt_id: 原尝试身份。
        :param event: 本次需要保存的事实。
        :returns: 成功保存后的原记录。
        :raises Exception: 唯一一次受控的仓储故障。
        """
        if self.error is not None:
            error = self.error
            self.error = None
            raise error
        return await self.delegate.record(attempt_id, event)


class _RejectedClaimRepository(MemoryReconstructionRepository):
    """仅拒绝首次意图登记，其他行为沿用实际内存仓储。"""

    def __init__(self, error: OSError) -> None:
        """保存明确的登记故障，保持仓储初始为空。

        :param error: 登记阶段应原样传播的异常。
        """
        super().__init__()
        self.error = error

    async def claim(self, request: ReconstructionRequest) -> bool:
        """在授予提交权之前抛错，不登记伪造的执行事实。

        :param request: 尚未取得提交权的原请求。
        :raises OSError: 测试指定的登记异常。
        """
        raise self.error


class _HeldRecordRepository(MemoryReconstructionRepository):
    """只挂起首次事件保存，供测试在合法外部结果返回后取消本地调用。"""

    def __init__(self) -> None:
        """保留实际仓储，并创建首次保存的到达和放行事件。"""
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def record(
        self, attempt_id: AttemptId, event: ReconstructionEvent,
    ) -> ReconstructionRecord:
        """首次保存先挂起，后续续查事件直接执行实际原子归约。

        :param attempt_id: 已取得提交权的原尝试。
        :param event: 外部已返回但尚未保存的合法事件。
        :returns: 实际仓储保存后的记录。
        :raises asyncio.CancelledError: 首次保存等待被本地取消。
        """
        if not self.entered.is_set():
            self.entered.set()
            await self.release.wait()
        return await super().record(attempt_id, event)


class _SecondReadFailsRepository(MemoryReconstructionRepository):
    """首次查询正常，后续读取失败；登记与事件保存仍可独立成功。"""

    def __init__(self) -> None:
        """创建空仓储及明确的读取故障计数。"""
        super().__init__()
        self.get_calls = 0

    async def get(self, attempt_id: AttemptId) -> ReconstructionRecord | None:
        """仅允许首次提交前的记录检查，暴露成功登记后的冗余读取。

        :param attempt_id: 正在检查的原尝试身份。
        :returns: 第一次读取时的实际记录。
        :raises OSError: 第二次及后续读取触发的独立存储故障。
        """
        self.get_calls += 1
        if self.get_calls > 1:
            raise OSError("测试后续读取暂时不可用")
        return await super().get(attempt_id)


class ReconstructionServiceTests(unittest.IsolatedAsyncioTestCase):
    """验证明确任务范围内的一次提交、事实保存与原尝试继续观察。"""

    def setUp(self) -> None:
        """建立完整五向准备声明，各图内容指纹不同且均有明确存在观察。"""
        workspace_id = WorkspaceId(uuid4())
        self.task = TaskIdentity(TaskId(uuid4()), workspace_id)
        records: list[LocatedArtifact] = []
        views: list[PreparedView] = []
        for index, direction in enumerate(ViewDirection, start=1):
            artifact = ArtifactIdentity(ArtifactId(uuid4()), workspace_id)
            reference = FileReference(
                artifact.id, ContentFingerprint(f"{index:064x}", index + 10),
            )
            location = WorkspaceFileLocation(
                artifact.id, WorkspaceRelativePath(f"references/{direction.value}.png"),
            )
            records.append(LocatedArtifact(artifact, reference, location))
            views.append(PreparedView(artifact.id, direction))
        self.records = tuple(records)
        self.observations = tuple(
            FilePresent(record.location, record.reference.content) for record in self.records
        )
        self.access = SyntheticArtifactAccess(self.records, self.observations)
        self.prepared = PreparedViews(tuple(views), ())
        self.references = TaskReferences(
            task_id=self.task.id, subject_reference_id=self.records[0].artifact.id,
            preserve_features=("保留面部花纹",),
            required_preparation_directions=frozenset(ViewDirection),
        )

    def _request(self, *, four_views: bool = False) -> ReconstructionRequest:
        """创建一个新作业和尝试，保持本任务的准备集和主体要求不变。

        :param four_views: 是否仅提交前后左右准备图。
        :returns: 包含完整五向准备文件的冻结请求。
        """
        job = JobIdentity(JobId(uuid4()), self.task.id)
        attempt = AttemptIdentity(AttemptId(uuid4()), job.id)
        plan = GenerationPlan(tuple(
            view.artifact_id for view in self.prepared.views
            if not four_views or view.direction is not ViewDirection.TOP
        ))
        return ReconstructionRequest(
            task=self.task, job=job, attempt=attempt, references=self.references,
            prepared=self.prepared, plan=plan,
            files=tuple(record.reference for record in self.records),
        )

    def _service(
        self, generator: ReconstructionPort, repository: ReconstructionRepository,
        *, access: ArtifactAccess | None = None, task: TaskIdentity | None = None,
    ) -> ReconstructionService:
        """在测试边界显式注入服务依赖，不通过配置切换业务实现。

        :param generator: 当前需验证的生成依赖。
        :param repository: 当前需验证的原意图仓储。
        :param access: 可选的文件访问故障夹具。
        :param task: 可选的其他任务范围。
        :returns: 依赖明确的具体服务。
        """
        return ReconstructionService(
            task=self.task if task is None else task,
            artifacts=self.access if access is None else access,
            generator=generator, repository=repository,
        )

    def _output(self, request: ReconstructionRequest) -> GeneratedArtifact:
        """创建与原尝试关联的新产物声明，不创建实际模型文件。

        :param request: 产物所属的原提交请求。
        :returns: 有独立产物身份的合成输出。
        """
        artifact = ArtifactIdentity(ArtifactId(uuid4()), request.task.workspace_id)
        return GeneratedArtifact(
            artifact, FileReference(artifact.id, ContentFingerprint("f" * 64, 100)),
            AttemptOutput(request.attempt.id, artifact.id),
        )

    async def _read_required(
        self, service: ReconstructionService, attempt_id: AttemptId,
    ) -> ReconstructionRecord:
        """断言服务已保留原意图并取得具体记录。

        :param service: 需要读取的服务。
        :param attempt_id: 已预期登记的原尝试。
        :returns: 具体原记录。
        """
        record = await service.read(attempt_id)
        assert record is not None
        return record

    async def test_two_generators_share_consumer_and_keep_top_prepared(self) -> None:
        """同任务的五图和四图计划共用消费方，顶视继续保留在准备与文件中。"""
        repository = MemoryReconstructionRepository()
        five = _CountingGenerator(FiveViewGenerator())
        four = _CountingGenerator(FourViewGenerator())
        five_request = self._request()
        four_request = self._request(four_views=True)
        five_service = self._service(five, repository)
        four_service = self._service(four, repository)
        first = await five_service.start(five_request)
        second = await four_service.start(four_request)
        assert isinstance(first, ReconstructionRecord)
        assert isinstance(second, ReconstructionRecord)
        self.assertIsInstance(first.observation, AttemptSucceeded)
        self.assertIsInstance(second.observation, AttemptActive)
        self.assertEqual(first.request.task, second.request.task)
        self.assertEqual(first.request.references, second.request.references)
        self.assertEqual(first.request.prepared, second.request.prepared)
        top_id = next(
            view.artifact_id for view in four_request.prepared.views
            if view.direction is ViewDirection.TOP
        )
        self.assertNotIn(top_id, four_request.plan.input_ids)
        self.assertIn(top_id, {file.artifact_id for file in second.request.files})
        failed_query = await four_service.query(four_request.attempt.id)
        self.assertIsInstance(failed_query.diagnostic, QueryUnavailable)
        self.assertEqual(failed_query.observation, second.observation)
        completed = await four_service.query(four_request.attempt.id)
        self.assertIsInstance(completed.observation, AttemptSucceeded)
        self.assertEqual(await five_service.candidate_references(five_request.attempt.id), first.outputs)
        self.assertEqual(await four_service.candidate_references(four_request.attempt.id), completed.outputs)
        self.assertEqual((five.submit_calls, four.submit_calls), (1, 1))

    async def test_incompatible_plan_has_no_submission_or_intent(self) -> None:
        """把顶视直接交给四向替身时明确拒绝，不删图、不登记或偷偷改计划。"""
        request = self._request()
        generator = _CountingGenerator(FourViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        result = await service.start(request)
        self.assertIsInstance(result, CapabilityUnavailable)
        self.assertEqual(generator.submit_calls, 0)
        self.assertIsNone(await service.read(request.attempt.id))
        self.assertEqual(len(request.prepared.views), 5)
        self.assertEqual(len(request.plan.input_ids), 5)

    async def test_duplicate_uses_record_without_rechecking_changed_access(self) -> None:
        """重复原请求读回既有结果，即使后来素材不可访问也不能重新提交。"""
        request = self._request()
        repository = MemoryReconstructionRepository()
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, repository)
        original = await service.start(request)
        unavailable = self._service(
            generator, repository, access=SyntheticArtifactAccess((), ()),
        )
        self.assertEqual(await unavailable.start(request), original)
        self.assertEqual(generator.submit_calls, 1)

    async def test_concurrent_duplicate_observes_claim_without_second_submit(self) -> None:
        """两个服务实例共享仓储时，首次提交未返回的并发请求只能读到原意图。"""
        request = self._request()
        generator = _HeldSubmission()
        repository = MemoryReconstructionRepository()
        service = self._service(generator, repository)
        another_service = self._service(generator, repository)
        first = asyncio.create_task(service.start(request))
        try:
            await asyncio.wait_for(generator.entered.wait(), timeout=1)
            duplicate = await another_service.start(request)
            assert isinstance(duplicate, ReconstructionRecord)
            self.assertIsNone(duplicate.observation)
            self.assertEqual(generator.submit_calls, 1)
        finally:
            generator.release.set()
            await first

    async def test_changed_request_and_job_intent_cannot_reuse_claim(self) -> None:
        """同尝试改参或同作业换尝试再改输入，都不能绕过冻结意图。"""
        request = self._request()
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        await service.start(request)
        changed = replace(request, plan=GenerationPlan(tuple(reversed(request.plan.input_ids))))
        with self.assertRaises(ReconstructionConflict):
            await service.start(changed)
        with self.assertRaises(ReconstructionConflict):
            await service.start(replace(
                changed, attempt=AttemptIdentity(AttemptId(uuid4()), request.job.id),
            ))
        self.assertEqual(generator.submit_calls, 1)

    async def test_cross_task_reads_queries_and_cancels_are_rejected(self) -> None:
        """同工作区的其他任务也无权读回、查询或取消本任务原尝试。"""
        request = self._request(four_views=True)
        repository = MemoryReconstructionRepository()
        generator = _CountingGenerator(FourViewGenerator())
        service = self._service(generator, repository)
        await service.start(request)
        foreign = self._service(
            generator, repository, task=TaskIdentity(TaskId(uuid4()), self.task.workspace_id),
        )
        with self.assertRaises(ReconstructionConflict):
            await foreign.start(request)
        with self.assertRaises(ReconstructionConflict):
            await foreign.read(request.attempt.id)
        with self.assertRaises(ReconstructionConflict):
            await foreign.query(request.attempt.id)
        with self.assertRaises(ReconstructionConflict):
            await foreign.cancel(request.attempt.id)
        self.assertEqual((generator.submit_calls, generator.query_calls, generator.cancel_calls), (1, 0, 0))

    async def test_query_failure_preserves_observation_and_known_outputs(self) -> None:
        """查询不可用保留可信活动观察及先前产物，随后成功继续合并而不清空。"""
        request = self._request(four_views=True)
        repository = MemoryReconstructionRepository()
        generator = _CountingGenerator(FourViewGenerator())
        service = self._service(generator, repository)
        await service.start(request)
        output = self._output(request)
        original = await repository.record(
            request.attempt.id, ReconstructionUpdate(AttemptActive(request.attempt.id), (output,)),
        )
        failure = await service.query(request.attempt.id)
        self.assertIsInstance(failure.diagnostic, QueryUnavailable)
        self.assertEqual((failure.observation, failure.outputs), (original.observation, original.outputs))
        success = await service.query(request.attempt.id)
        self.assertIsInstance(success.observation, AttemptSucceeded)
        self.assertIn(output, success.outputs)
        self.assertEqual(generator.submit_calls, 1)

    async def test_unconfirmed_submission_only_continues_original_query(self) -> None:
        """提交受理不明保留原意图，重复入口不重交，原绑定查询仍能取得结果。"""
        request = self._request()
        generator = _UnconfirmedSubmission(FiveViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        result = await service.start(request)
        assert isinstance(result, ReconstructionRecord)
        self.assertIsNone(result.observation)
        self.assertIsInstance(result.diagnostic, SubmissionUnconfirmed)
        self.assertEqual(await service.start(request), result)
        queried = await service.query(request.attempt.id)
        self.assertIsInstance(queried.observation, AttemptSucceeded)
        self.assertEqual(generator.submit_calls, 1)

    async def test_cancel_acknowledgement_waits_for_actual_cancelled_observation(self) -> None:
        """取消受理仅增加独立回执，后续原尝试查询才可以确认执行已取消。"""
        request = self._request(four_views=True)
        generator = _CountingGenerator(FourViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        await service.start(request)
        receipt = await service.cancel(request.attempt.id)
        assert isinstance(receipt, ReconstructionRecord)
        self.assertIsInstance(receipt.cancellation, CancellationAcknowledged)
        self.assertIsInstance(receipt.observation, AttemptActive)
        self.assertIsInstance((await service.query(request.attempt.id)).observation, AttemptCancelled)
        with self.assertRaises(ReconstructionConflict):
            await service.candidate_references(request.attempt.id)
        self.assertEqual((generator.submit_calls, generator.cancel_calls), (1, 1))

    async def test_unsupported_cancellation_keeps_original_record_unchanged(self) -> None:
        """适配器明确不支持取消时保留原记录，不把未发送命令登记为回执不明。"""
        request = self._request(four_views=True)
        generator = _CancellationUnsupported(FourViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        original = await service.start(request)
        self.assertIsInstance(await service.cancel(request.attempt.id), CapabilityUnavailable)
        self.assertEqual(await service.read(request.attempt.id), original)
        self.assertEqual((generator.submit_calls, generator.cancel_calls), (1, 1))

    async def test_unregistered_input_stops_before_submission(self) -> None:
        """无登记只返回输入不足，不伪造磁盘缺失或开始执行。"""
        request = self._request()
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(
            generator, MemoryReconstructionRepository(), access=SyntheticArtifactAccess((), ()),
        )
        self.assertIsInstance(await service.start(request), InputInsufficient)
        self.assertEqual(generator.submit_calls, 0)
        self.assertIsNone(await service.read(request.attempt.id))

    async def test_missing_or_changed_unsubmitted_top_blocks_preflight(self) -> None:
        """未提交给四向替身的顶视也须通过完整准备资料的存在和内容预检。"""
        request = self._request(four_views=True)
        top = next(
            record for record in self.records
            if record.location.relative_path.value.endswith("top.png")
        )
        faults: tuple[FileObservation, ...] = (
            FileMissing(top.location),
            FilePresent(top.location, ContentFingerprint("e" * 64, 99)),
        )
        for fault in faults:
            with self.subTest(fault=type(fault).__name__):
                observations = tuple(
                    observation for observation in self.observations
                    if observation.location != top.location
                ) + (fault,)
                generator = _CountingGenerator(FourViewGenerator())
                service = self._service(
                    generator, MemoryReconstructionRepository(),
                    access=SyntheticArtifactAccess(self.records, observations),
                )
                with self.assertRaises(ArtifactContractError):
                    await service.start(request)
                self.assertEqual(generator.submit_calls, 0)
                self.assertIsNone(await service.read(request.attempt.id))

    async def test_result_record_failure_preserves_intent_and_original_query(self) -> None:
        """外部已返回成功但保存失败时暴露待对账事件，后续只查询原尝试。"""
        request = self._request()
        failure = OSError("测试结果保存失败")
        repository = _FailOnceRepository(failure)
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, repository)
        with self.assertRaises(ReconstructionRecordingError) as raised:
            await service.start(request)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertEqual(raised.exception.attempt_id, request.attempt.id)
        self.assertIsInstance(raised.exception.event, ReconstructionUpdate)
        intent = await self._read_required(service, request.attempt.id)
        self.assertIsNone(intent.observation)
        self.assertEqual(await service.start(request), intent)
        recovered = await service.query(request.attempt.id)
        self.assertIsInstance(recovered.observation, AttemptSucceeded)
        self.assertTrue(recovered.outputs)
        self.assertEqual(generator.submit_calls, 1)

    async def test_claim_failure_cannot_trigger_external_submission(self) -> None:
        """登记提交权失败原样传播，没有提交调用，也不声称已登记原意图。"""
        request = self._request()
        failure = OSError("测试首次意图登记失败")
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, _RejectedClaimRepository(failure))
        with self.assertRaises(OSError) as raised:
            await service.start(request)
        self.assertIs(raised.exception, failure)
        self.assertEqual(generator.submit_calls, 0)
        self.assertIsNone(await service.read(request.attempt.id))

    async def test_successful_claim_submits_without_redundant_repository_read(self) -> None:
        """取得提交权后直接使用原请求，即使后续读取故障也能完成首次提交和保存。"""
        request = self._request()
        repository = _SecondReadFailsRepository()
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, repository)
        result = await service.start(request)
        assert isinstance(result, ReconstructionRecord)
        self.assertIsInstance(result.observation, AttemptSucceeded)
        self.assertTrue(result.outputs)
        self.assertEqual(result.request, request)
        self.assertEqual(generator.submit_calls, 1)
        self.assertEqual(repository.get_calls, 1)
        with self.assertRaises(OSError):
            await service.read(request.attempt.id)
        self.assertEqual(repository.get_calls, 2)

    async def test_cancellation_during_result_recording_keeps_event_and_original_query(self) -> None:
        """合法成功回包保存时取消仍传播取消，并携带原事件供原尝试对账。"""
        request = self._request()
        repository = _HeldRecordRepository()
        generator = _CountingGenerator(FiveViewGenerator())
        service = self._service(generator, repository)
        running = asyncio.create_task(service.start(request))
        await asyncio.wait_for(repository.entered.wait(), timeout=1)
        running.cancel()
        with self.assertRaises(asyncio.CancelledError) as raised:
            await running
        recording_error = raised.exception.__cause__
        assert isinstance(recording_error, ReconstructionRecordingError)
        self.assertEqual(recording_error.attempt_id, request.attempt.id)
        event = recording_error.event
        assert isinstance(event, ReconstructionUpdate)
        self.assertEqual(event.observation, AttemptSucceeded(request.attempt.id))
        self.assertTrue(event.outputs)
        intent = await self._read_required(service, request.attempt.id)
        self.assertEqual(intent.request, request)
        self.assertIsNone(intent.observation)
        self.assertEqual(intent.outputs, ())
        self.assertEqual(await service.start(request), intent)
        recovered = await service.query(request.attempt.id)
        self.assertEqual((recovered.observation, recovered.outputs), (event.observation, event.outputs))
        self.assertEqual((generator.submit_calls, generator.query_calls), (1, 1))

    async def test_local_cancellation_keeps_intent_and_propagates(self) -> None:
        """本地协程取消继续传播且记录受理不明，不发远端取消也不授予重提。"""
        request = self._request()
        generator = _HeldSubmission()
        service = self._service(generator, MemoryReconstructionRepository())
        running = asyncio.create_task(service.start(request))
        await asyncio.wait_for(generator.entered.wait(), timeout=1)
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        intent = await self._read_required(service, request.attempt.id)
        self.assertIsInstance(intent.diagnostic, SubmissionUnconfirmed)
        self.assertIsNone(intent.observation)
        self.assertIsNone(intent.cancellation)
        self.assertEqual(await service.start(request), intent)
        self.assertIsInstance((await service.query(request.attempt.id)).observation, AttemptSucceeded)
        self.assertEqual((generator.submit_calls, generator.cancel_calls), (1, 0))

    async def test_host_timeout_does_not_release_submission_claim(self) -> None:
        """宿主停止等待只中断本地协程，原提交意图仍保留供确切尝试续查。"""
        request = self._request()
        generator = _HeldSubmission()
        service = self._service(generator, MemoryReconstructionRepository())
        running = asyncio.create_task(service.start(request))
        await asyncio.wait_for(generator.entered.wait(), timeout=1)
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(running, timeout=0.01)
        intent = await self._read_required(service, request.attempt.id)
        self.assertIsInstance(intent.diagnostic, SubmissionUnconfirmed)
        self.assertIsNone(intent.observation)
        self.assertEqual(await service.start(request), intent)
        self.assertIsInstance((await service.query(request.attempt.id)).observation, AttemptSucceeded)
        self.assertEqual((generator.submit_calls, generator.cancel_calls), (1, 0))

    async def test_dependency_errors_keep_original_exception_and_intent(self) -> None:
        """依赖自身的超时或访问异常原样传播，不被改写成可信执行失败。"""
        for error in (TimeoutError("依赖自己超时"), OSError("依赖连接断开")):
            with self.subTest(error=type(error).__name__):
                request = self._request()
                generator = _RaisedSubmission(error)
                service = self._service(generator, MemoryReconstructionRepository())
                with self.assertRaises(type(error)) as raised:
                    await service.start(request)
                self.assertIs(raised.exception, error)
                intent = await self._read_required(service, request.attempt.id)
                self.assertIsNone(intent.observation)
                self.assertIsInstance(intent.diagnostic, SubmissionUnconfirmed)
                self.assertEqual(await service.start(request), intent)
                self.assertEqual(generator.submit_calls, 1)

    async def test_secondary_record_error_does_not_mask_original_dependency_error(self) -> None:
        """提交抛错后诊断保存也失败，仍传播原异常并通过原因链保留记录故障。"""
        request = self._request()
        original_error = TimeoutError("提交等待超时")
        save_error = OSError("诊断保存失败")
        generator = _RaisedSubmission(original_error)
        service = self._service(generator, _FailOnceRepository(save_error))
        with self.assertRaises(TimeoutError) as raised:
            await service.start(request)
        self.assertIs(raised.exception, original_error)
        self.assertIsInstance(raised.exception.__cause__, ReconstructionRecordingError)
        assert raised.exception.__cause__ is not None
        self.assertIs(raised.exception.__cause__.__cause__, save_error)
        intent = await self._read_required(service, request.attempt.id)
        self.assertIsNone(intent.observation)
        self.assertEqual(await service.start(request), intent)
        self.assertEqual(generator.submit_calls, 1)

    async def test_success_without_outputs_cannot_handoff_candidate(self) -> None:
        """可信执行成功仍不能替代非空候选产物声明。"""
        request = self._request()
        generator = _EmptySuccess(FiveViewGenerator())
        service = self._service(generator, MemoryReconstructionRepository())
        result = await service.start(request)
        assert isinstance(result, ReconstructionRecord)
        self.assertIsInstance(result.observation, AttemptSucceeded)
        self.assertEqual(result.outputs, ())
        with self.assertRaises(ReconstructionConflict):
            await service.candidate_references(request.attempt.id)

    async def test_new_adapter_without_binding_cannot_restore_by_resubmission(self) -> None:
        """新适配器无原绑定时只能记录查询或取消不明，不能靠重复提交恢复。"""
        request = self._request(four_views=True)
        repository = MemoryReconstructionRepository()
        original = self._service(FourViewGenerator(), repository)
        before = await original.start(request)
        assert isinstance(before, ReconstructionRecord)
        replacement = _CountingGenerator(FourViewGenerator())
        service = self._service(replacement, repository)
        queried = await service.query(request.attempt.id)
        self.assertIsInstance(queried.diagnostic, QueryUnavailable)
        self.assertEqual(queried.observation, before.observation)
        cancelled = await service.cancel(request.attempt.id)
        assert isinstance(cancelled, ReconstructionRecord)
        self.assertIsInstance(cancelled.cancellation, CancellationUnconfirmed)
        self.assertEqual(cancelled.observation, before.observation)
        self.assertEqual(await service.start(request), cancelled)
        self.assertEqual(replacement.submit_calls, 0)

    async def test_invalid_output_event_is_atomic_and_does_not_pollute_record(self) -> None:
        """跨工作区或输入身份冒充输出被整体拒绝，合法输出的内容也不能被改写。"""
        request = self._request(four_views=True)
        repository = MemoryReconstructionRepository()
        service = self._service(FourViewGenerator(), repository)
        await service.start(request)
        original = await self._read_required(service, request.attempt.id)
        good = self._output(request)
        foreign = self._output(request)
        foreign = replace(foreign, artifact=replace(foreign.artifact, workspace_id=WorkspaceId(uuid4())))
        input_record = self.records[0]
        reused_input = GeneratedArtifact(
            input_record.artifact, input_record.reference,
            AttemptOutput(request.attempt.id, input_record.artifact.id),
        )
        for bad in (foreign, reused_input):
            with self.subTest(bad=bad.artifact.id):
                with self.assertRaises(ValueError):
                    await repository.record(
                        request.attempt.id,
                        ReconstructionUpdate(AttemptSucceeded(request.attempt.id), (good, bad)),
                    )
                self.assertEqual(await service.read(request.attempt.id), original)
        accepted = await repository.record(
            request.attempt.id, ReconstructionUpdate(AttemptActive(request.attempt.id), (good,)),
        )
        changed = replace(good, file=replace(good.file, content=ContentFingerprint("a" * 64, 55)))
        with self.assertRaises(ArtifactContractError):
            await repository.record(
                request.attempt.id, ReconstructionUpdate(AttemptActive(request.attempt.id), (changed,)),
            )
        self.assertEqual(await service.read(request.attempt.id), accepted)
        self.assertEqual(await repository.record(
            request.attempt.id, ReconstructionUpdate(AttemptActive(request.attempt.id), (good,)),
        ), accepted)
        self.assertEqual(await repository.record(
            request.attempt.id, ReconstructionUpdate(AttemptActive(request.attempt.id)),
        ), accepted)


if __name__ == "__main__":
    unittest.main()
