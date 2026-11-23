# 文件信息：L0-05 最小候选生成消费方。
# 作用：在任务作用域内完成输入预检、一次提交、原尝试查询、取消及引用交接。
# 边界：不选择供应商、不补图、不运行自动修订循环，不将声明视为真实文件或质量。
"""以显式注入的端口串联生成契约，保持副作用前后的恢复边界。"""

import asyncio
import logging

from vet3d.artifacts import ArtifactAccess, LocatedArtifact, require_matching_file
from vet3d.execution import (
    AttemptSucceeded, CancellationAcknowledged, CancellationUnconfirmed,
    CapabilityUnavailable, InputInsufficient, QueryUnavailable, SubmissionUnconfirmed,
)
from vet3d.identity import AttemptId, TaskIdentity
from vet3d.modeling import (
    CapabilityUnverified, GeneratedArtifact, ReconstructionPort, ReconstructionRequest,
    ReconstructionUpdate, SubmissionCompatible, validate_prepared_views,
)

from .reconstruction_records import (
    ReconstructionConflict, ReconstructionEvent, ReconstructionRecord,
    ReconstructionRepository, apply_reconstruction_event,
)

_LOGGER = logging.getLogger("vet3d")


class ReconstructionRecordingError(RuntimeError):
    """表示外部交互后事实未确认保存，携带待对账事件而不授权重提。"""

    def __init__(self, attempt_id: AttemptId, event: ReconstructionEvent) -> None:
        """保留原尝试及已取得的结果，原仓储异常由原因链保留。

        :param attempt_id: 外部交互所属的原尝试。
        :param event: 本次未确认保存的事实，可能包含已有产物。
        """
        super().__init__("生成交互结果未确认保存；只能对账原尝试")
        self.attempt_id = attempt_id
        self.event = event


class ReconstructionService:
    """消费稳定端口的具体服务，实例级任务范围不由逐轮命令重定义。"""

    def __init__(
        self, *, task: TaskIdentity, artifacts: ArtifactAccess,
        generator: ReconstructionPort, repository: ReconstructionRepository,
    ) -> None:
        """固定业务范围及依赖，宿主负责实际装配。

        :param task: 本实例唯一允许的任务身份与工作区。
        :param artifacts: 文件记录解析和独立观察端口。
        :param generator: 固定装配的生成端口；原远端绑定由其实现负责。
        :param repository: 原意图与结果事实的权威仓储。
        :raises TypeError: 缺少必需依赖或任务类型错误。
        """
        if type(task) is not TaskIdentity or any(
            dependency is None for dependency in (artifacts, generator, repository)
        ):
            raise TypeError("生成服务需要明确任务与全部依赖")
        self._task = task
        self._artifacts = artifacts
        self._generator = generator
        self._repository = repository

    async def read(self, attempt_id: AttemptId) -> ReconstructionRecord | None:
        """读取并核对原记录，防止同一仓储中的跨任务访问。

        :param attempt_id: 本次访问的原尝试身份。
        :returns: 当前记录；未登记为 None，不表示远端不存在。
        :raises ValueError: 记录属于其他任务或返回了不同尝试。
        """
        if type(attempt_id) is not AttemptId:
            raise TypeError("查询必须使用 AttemptId")
        record = await self._repository.get(attempt_id)
        if record is not None:
            if type(record) is not ReconstructionRecord:
                raise TypeError("仓储必须返回具体生成记录")
            if record.request.task != self._task or record.request.attempt.id != attempt_id:
                raise ReconstructionConflict("生成记录不属于当前任务及原尝试")
        return record

    async def _required(self, attempt_id: AttemptId) -> ReconstructionRecord:
        """取得必须存在的原记录，不以新尝试冒充恢复。

        :param attempt_id: 待恢复的原尝试。
        :returns: 已核对任务范围的记录。
        :raises ReconstructionConflict: 本地没有原提交意图。
        """
        record = await self.read(attempt_id)
        if record is None:
            raise ReconstructionConflict("原提交意图未登记，不能查询或取消")
        return record

    async def _record(
        self, original: ReconstructionRecord, event: ReconstructionEvent,
    ) -> ReconstructionRecord:
        """先验证外部事实，再保存；保存故障保留结果供调用方诊断。

        :param original: 本次交互所针对的原记录。
        :param event: 本次交互取得的事实。
        :returns: 已保存且通过关联检查的记录。
        :raises ValueError: 回包身份、终态或产物非法。
        :raises ReconstructionRecordingError: 外部交互后的仓储操作失败。
        """
        apply_reconstruction_event(original, event)
        try:
            result = await self._repository.record(original.request.attempt.id, event)
        except asyncio.CancelledError as error:
            error.add_note("结果记录被中断，已取得的事件保留在原因链，禁止重新提交。")
            raise error from ReconstructionRecordingError(original.request.attempt.id, event)
        except Exception as error:
            raise ReconstructionRecordingError(original.request.attempt.id, event) from error
        if type(result) is not ReconstructionRecord or result.request != original.request:
            raise ReconstructionConflict("仓储回包改变了原提交意图")
        return result

    async def _remember_error(
        self, original: ReconstructionRecord, event: ReconstructionEvent, error: BaseException,
    ) -> None:
        """尽力记录未知交互结果，同时保留原异常和取消语义。

        :param original: 外部交互之前已登记的原意图。
        :param event: 无法确认回执的诊断，不能伪造执行失败。
        :param error: 仍需向调用方传播的原异常。
        :raises BaseException: 保存也失败时抛出原异常，并附加保存故障原因链。
        """
        try:
            await self._record(original, event)
        except Exception as recording_error:
            error.add_note("交互诊断未确认保存；原意图仍不能自动重提。")
            raise error from recording_error

    async def start(
        self, request: ReconstructionRequest,
    ) -> ReconstructionRecord | CapabilityUnavailable | CapabilityUnverified | InputInsufficient:
        """预检准备资料及具体计划，登记后最多调用一次生成提交。

        :param request: 冻结的任务、准备资料、文件指纹和本次输入选择。
        :returns: 保存的生成记录，或无生成副作用的输入／能力拒绝。
        :raises ValueError: 请求范围、文件观察或原意图冲突。
        :raises asyncio.CancelledError: 本地协程取消；不声明远端停止。
        :raises ReconstructionRecordingError: 提交结果未确认保存。
        """
        if type(request) is not ReconstructionRequest:
            raise TypeError("生成入口必须使用 ReconstructionRequest")
        if request.task != self._task:
            raise ReconstructionConflict("请求不属于当前服务的任务范围")
        existing = await self.read(request.attempt.id)
        if existing is not None:
            if existing.request != request:
                raise ReconstructionConflict("同一尝试不能改变已登记输入")
            return existing
        resolved_files: list[LocatedArtifact] = []
        for reference in request.files:
            resolved = await self._artifacts.resolve(reference.artifact_id)
            if resolved is None:
                return InputInsufficient("生成所需素材未登记；不据此断言磁盘文件缺失")
            if type(resolved) is not LocatedArtifact:
                raise TypeError("素材解析必须返回具体定位记录")
            if resolved.reference != reference:
                raise ReconstructionConflict("解析结果不符合请求冻结的文件身份和内容")
            resolved_files.append(resolved)
        validate_prepared_views(
            request.prepared, references=request.references, task=request.task,
            files=request.files, artifacts=tuple(item.artifact for item in resolved_files),
        )
        for resolved in resolved_files:
            observation = await self._artifacts.observe(resolved.location)
            if observation.location != resolved.location:
                raise ReconstructionConflict("文件观察来自其他位置")
            require_matching_file(observation, reference=resolved.reference, artifact=resolved.artifact)
        compatibility = self._generator.check(request)
        if isinstance(compatibility, (CapabilityUnavailable, CapabilityUnverified)):
            return compatibility
        if type(compatibility) is not SubmissionCompatible:
            raise TypeError("生成能力必须显式确认具体输入计划")
        if not await self._repository.claim(request):
            existing = await self._required(request.attempt.id)
            if existing.request != request:
                raise ReconstructionConflict("并发登记改变了原意图")
            return existing
        # 首次登记已确认，直接使用原意图；额外读回失败不应阻断首次提交。
        original = ReconstructionRecord(request)
        _LOGGER.info("reconstruction_submit attempt_id=%s", request.attempt.id.value)
        try:
            event = await self._generator.submit(request)
        except (Exception, asyncio.CancelledError) as error:
            await self._remember_error(
                original, SubmissionUnconfirmed(request.attempt.id, "提交调用未取得可信回执"), error,
            )
            raise
        if not isinstance(event, (ReconstructionUpdate, SubmissionUnconfirmed)):
            raise TypeError("提交回包不符合生成端口契约；保留原意图且禁止重提")
        return await self._record(original, event)

    async def query(self, attempt_id: AttemptId) -> ReconstructionRecord:
        """查询原尝试一次，查询失败保留已有观察和产物。

        :param attempt_id: 已登记且属于本任务的原尝试。
        :returns: 已保存本次观察或查询诊断的记录。
        :raises asyncio.CancelledError: 本地停止等待，不推导远端终态。
        """
        original = await self._required(attempt_id)
        try:
            event = await self._generator.query(attempt_id)
        except (Exception, asyncio.CancelledError) as error:
            await self._remember_error(
                original, QueryUnavailable(attempt_id, "查询调用未取得可信观察"), error,
            )
            raise
        if not isinstance(event, (ReconstructionUpdate, QueryUnavailable)):
            raise TypeError("查询回包不符合生成端口契约")
        result = await self._record(original, event)
        _LOGGER.debug("reconstruction_queried attempt_id=%s", attempt_id.value)
        return result

    async def cancel(self, attempt_id: AttemptId) -> ReconstructionRecord | CapabilityUnavailable:
        """请求取消原尝试一次，只保存回执，不制造执行取消终态。

        :param attempt_id: 已登记的原尝试。
        :returns: 保存回执的原记录；不能发送取消时返回能力不可用且原记录不变。
        :raises asyncio.CancelledError: 本地请求调用被中断，远端取消结果仍未确认。
        """
        original = await self._required(attempt_id)
        try:
            receipt = await self._generator.cancel(attempt_id)
        except (Exception, asyncio.CancelledError) as error:
            await self._remember_error(
                original, CancellationUnconfirmed(attempt_id, "取消请求未取得可信回执"), error,
            )
            raise
        if isinstance(receipt, CapabilityUnavailable):
            return receipt
        if not isinstance(receipt, (CancellationAcknowledged, CancellationUnconfirmed)):
            raise TypeError("取消回包不能冒充执行终态")
        return await self._record(original, receipt)

    async def candidate_references(self, attempt_id: AttemptId) -> tuple[GeneratedArtifact, ...]:
        """交接成功尝试的非空候选引用，不宣告已下载、发布或验收通过。

        :param attempt_id: 当前需要交接的确切尝试。
        :returns: 已登记的候选文件声明与来源关系。
        :raises ReconstructionConflict: 尚无可信成功观察或没有输出引用。
        """
        record = await self._required(attempt_id)
        if not isinstance(record.observation, AttemptSucceeded) or not record.outputs:
            raise ReconstructionConflict("候选引用交接需要可信成功观察和非空输出")
        return record.outputs
