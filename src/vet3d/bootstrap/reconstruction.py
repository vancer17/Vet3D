# 文件信息：L0-05 生成用例的显式装配及有限契约探针。
# 作用：用同一消费者连接两种生成替身、素材观察替身和真实内存记录读写。
# 边界：所有素材与产物均为合成声明；不访问磁盘图片、模型、HTTP 或数据库。
"""验证跨包协议和装配，不能作为动物建模或环境就绪证明。"""

import asyncio
from hashlib import sha256
import logging
import math
from uuid import uuid4

from vet3d.adapters import (
    FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository, SyntheticArtifactAccess,
)
from vet3d.application import (
    ReconstructionRecord, ReconstructionRepository, ReconstructionService,
)
from vet3d.artifacts import (
    ArtifactAccess, ContentFingerprint, FilePresent, FileReference, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath,
)
from vet3d.execution import AttemptActive, AttemptSucceeded, QueryUnavailable
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, JobId, JobIdentity,
    TaskId, TaskIdentity, WorkspaceId,
)
from vet3d.modeling import (
    GenerationPlan, PreparedView, PreparedViews, ReconstructionPort,
    ReconstructionRequest, TaskReferences, ViewDirection,
)

from .invocation import InvocationTimeoutError, _record_termination

_LOGGER = logging.getLogger("vet3d")


def assemble_reconstruction(
    *, task: TaskIdentity, artifacts: ArtifactAccess,
    generator: ReconstructionPort, repository: ReconstructionRepository,
) -> ReconstructionService:
    """将具体依赖显式注入同一生成消费者，不读取模式或供应商环境变量。

    :param task: 实例的唯一任务作用域。
    :param artifacts: 素材解析与观察实现。
    :param generator: 生成能力实现，拥有其原尝试绑定。
    :param repository: 本用例意图及事实仓储。
    :returns: 不依赖宿主和具体适配器的稳定服务。
    """
    return ReconstructionService(task=task, artifacts=artifacts, generator=generator, repository=repository)


async def _exercise_probe() -> tuple[ReconstructionRecord, ReconstructionRecord]:
    """以同一任务的五图和四图计划验证保存、续查、读回及候选引用交接。

    :returns: 两条已读回的成功记录，仍未执行文件生成或质量验收。
    :raises RuntimeError: 任一替身结果违反本探针预期的机械协议。
    """
    task = TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4()))
    located: list[LocatedArtifact] = []
    views: list[PreparedView] = []
    for direction in ViewDirection:
        payload = f"synthetic-view:{direction.value}".encode("utf-8")
        artifact = ArtifactIdentity(ArtifactId(uuid4()), task.workspace_id)
        reference = FileReference(artifact.id, ContentFingerprint(sha256(payload).hexdigest(), len(payload)))
        location = WorkspaceFileLocation(artifact.id, WorkspaceRelativePath(f"probe/{direction.value}.png"))
        located.append(LocatedArtifact(artifact, reference, location))
        views.append(PreparedView(artifact.id, direction))
    prepared = PreparedViews(tuple(views), ())
    references = TaskReferences(task.id, views[0].artifact_id, ("保留主体外观；本探针不判断质量",), frozenset(ViewDirection))
    artifacts = SyntheticArtifactAccess(
        records=tuple(located),
        observations=tuple(FilePresent(item.location, item.reference.content) for item in located),
    )
    repository = MemoryReconstructionRepository()
    completed: list[ReconstructionRecord] = []
    generators: tuple[ReconstructionPort, ...] = (FiveViewGenerator(), FourViewGenerator())
    selected_sets = (tuple(views), tuple(view for view in views if view.direction is not ViewDirection.TOP))
    for generator, inputs in zip(generators, selected_sets, strict=True):
        job = JobIdentity(JobId(uuid4()), task.id)
        request = ReconstructionRequest(
            task=task, job=job, attempt=AttemptIdentity(AttemptId(uuid4()), job.id),
            references=references, prepared=prepared,
            plan=GenerationPlan(tuple(view.artifact_id for view in inputs)),
            files=tuple(item.reference for item in located),
        )
        service = assemble_reconstruction(task=task, artifacts=artifacts, generator=generator, repository=repository)
        result = await service.start(request)
        if not isinstance(result, ReconstructionRecord):
            raise RuntimeError("探针的显式生成计划未通过预检")
        if isinstance(result.observation, AttemptActive):
            failed_query = await service.query(request.attempt.id)
            if not isinstance(failed_query.diagnostic, QueryUnavailable) or failed_query.observation != result.observation:
                raise RuntimeError("查询失败未保留上次可信观察")
            result = await service.query(request.attempt.id)
        if not isinstance(result.observation, AttemptSucceeded):
            raise RuntimeError("有限探针步骤未取得预期的替身成功观察")
        reopened = assemble_reconstruction(task=task, artifacts=artifacts, generator=generator, repository=repository)
        if await reopened.read(request.attempt.id) != result:
            raise RuntimeError("新的消费实例未读回已保存的原记录")
        if await reopened.candidate_references(request.attempt.id) != result.outputs:
            raise RuntimeError("候选引用交接与保存结果不符")
        completed.append(result)
    return completed[0], completed[1]


async def run_reconstruction_probe(
    *, timeout_seconds: float = 5.0,
) -> tuple[ReconstructionRecord, ReconstructionRecord]:
    """在真实宿主期限内执行固定有限步骤，异常只在此边界记录一次。

    :param timeout_seconds: 正有限宿主期限，不进入业务策略或能力声明。
    :returns: 两种替身经同一消费者保存并读回的结果。
    :raises ValueError: 宿主期限不合法。
    :raises InvocationTimeoutError: 本地期限到达，不声称远端执行停止。
    :raises asyncio.CancelledError: 调用者取消，继续传播取消语义。
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("探针期限必须是正有限秒数")
    call_id = uuid4().hex
    deadline = asyncio.timeout(timeout_seconds)
    _LOGGER.info("contract_probe_started call_id=%s", call_id)
    try:
        async with deadline:
            results = await _exercise_probe()
        if deadline.expired():
            raise InvocationTimeoutError("契约探针超过宿主期限")
    except asyncio.CancelledError as error:
        _record_termination(error, logging.INFO, "contract_probe_cancelled", call_id)
        raise
    except TimeoutError as error:
        if deadline.expired():
            timeout = InvocationTimeoutError("契约探针超过宿主期限")
            _record_termination(timeout, logging.WARNING, "contract_probe_timed_out", call_id)
            raise timeout from None
        _record_termination(error, logging.ERROR, "contract_probe_failed", call_id, with_traceback=True)
        raise
    except Exception as error:
        _record_termination(error, logging.ERROR, "contract_probe_failed", call_id, with_traceback=True)
        raise
    _LOGGER.info("contract_probe_completed call_id=%s", call_id)
    return results
