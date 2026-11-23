# 文件信息：L0-05 候选生成用例的记录、归约规则与仓储端口。
# 作用：保留一次冻结提交、可信观察、已知产物和独立诊断；首次登记才授予提交权。
# 边界：不实现数据库、远端绑定、自动重试或质量判定；仓储由消费方拥有。
"""维护最小生成链路的单一记录，不复制执行状态枚举。"""

from dataclasses import dataclass, replace
from typing import Protocol, final

from vet3d.artifacts import validate_content_binding
from vet3d.execution import (
    AttemptObservation, CancellationAcknowledged, CancellationReceipt,
    CancellationUnconfirmed, QueryUnavailable, SubmissionUnconfirmed,
    reconcile_observation, validate_attempt_fact,
)
from vet3d.identity import AttemptId, validate_attempt_output
from vet3d.modeling import GeneratedArtifact, ReconstructionRequest, ReconstructionUpdate


class ReconstructionConflict(ValueError):
    """表示原尝试、作业意图或产物引用存在冲突，不能通过重提消除。"""


type ReconstructionEvent = (
    ReconstructionUpdate | QueryUnavailable | SubmissionUnconfirmed | CancellationReceipt
)


@final
@dataclass(frozen=True, slots=True)
class ReconstructionRecord:
    """保存本次用例的独立事实，空观察不等于已受理。

    :param request: 首次登记的冻结输入与身份链，包含预期文件指纹。
    :param observation: 最近可信执行观察；尚未确认时为空。
    :param outputs: 累积已知产物声明，不表示文件存在或质量合格。
    :param diagnostic: 最近一次提交或查询诊断，后续成功不改写历史原因。
    :param cancellation: 最近取消请求回执，与执行终态分开。
    """

    request: ReconstructionRequest
    observation: AttemptObservation | None = None
    outputs: tuple[GeneratedArtifact, ...] = ()
    diagnostic: QueryUnavailable | SubmissionUnconfirmed | None = None
    cancellation: CancellationReceipt | None = None

    def __post_init__(self) -> None:
        """核对记录关联，拒绝原件冒充产出及其他任务的产物。

        :raises TypeError: 输入不是规定的具体记录。
        :raises ValueError: 身份、内容或产物来源不满足契约。
        """
        if type(self.request) is not ReconstructionRequest:
            raise TypeError("生成记录必须持有具体的冻结请求")
        if self.observation is not None:
            reconcile_observation(None, self.observation)
            validate_attempt_fact(self.observation, attempt=self.request.attempt)
        if type(self.outputs) is not tuple:
            raise TypeError("已知产物必须使用不可变元组")
        inputs = {file.artifact_id for file in self.request.files}
        seen = set(inputs)
        for output in self.outputs:
            if type(output) is not GeneratedArtifact:
                raise TypeError("已知产物必须使用 GeneratedArtifact")
            validate_attempt_output(
                output.origin, attempt=self.request.attempt, job=self.request.job,
                task=self.request.task, artifact=output.artifact,
            )
            if output.artifact.id in seen:
                raise ReconstructionConflict("产物不能重复或复用本次输入身份")
            seen.add(output.artifact.id)
        if self.diagnostic is not None:
            if type(self.diagnostic) not in (QueryUnavailable, SubmissionUnconfirmed):
                raise TypeError("生成诊断必须是提交不明或查询不可用")
            validate_attempt_fact(self.diagnostic, attempt=self.request.attempt)
        if self.cancellation is not None:
            if type(self.cancellation) not in (CancellationAcknowledged, CancellationUnconfirmed):
                raise TypeError("取消回执必须使用独立的请求结果")
            validate_attempt_fact(self.cancellation, attempt=self.request.attempt)


def apply_reconstruction_event(
    record: ReconstructionRecord, event: ReconstructionEvent,
) -> ReconstructionRecord:
    """单向合并新事实，查询失败和取消回执不会覆盖可信终态。

    :param record: 仓储当前已登记的原尝试记录。
    :param event: 本次确认的观察、独立诊断或取消请求回执。
    :returns: 核对关联后的新冻结记录；已有输出保持，新增输出逐项合并。
    :raises TypeError: 事件类型不属于本用例的协议。
    :raises ValueError: 终态冲突、关联错误或同一产物内容发生变化。
    """
    if type(record) is not ReconstructionRecord:
        raise TypeError("必须提供原生成记录")
    if isinstance(event, ReconstructionUpdate):
        validate_attempt_fact(event.observation, attempt=record.request.attempt)
        outputs = {output.artifact.id: output for output in record.outputs}
        for output in event.outputs:
            previous = outputs.get(output.artifact.id)
            if previous is not None:
                validate_content_binding(previous.file, output.file)
                if previous != output:
                    raise ReconstructionConflict("已有产物的身份或来源不能变化")
            outputs[output.artifact.id] = output
        return replace(
            record, observation=reconcile_observation(record.observation, event.observation),
            outputs=tuple(outputs.values()),
        )
    if isinstance(event, (QueryUnavailable, SubmissionUnconfirmed)):
        return replace(record, diagnostic=event)
    if isinstance(event, (CancellationAcknowledged, CancellationUnconfirmed)):
        return replace(record, cancellation=event)
    raise TypeError("此位置只接受生成用例的确认事实或诊断")


class ReconstructionRepository(Protocol):
    """由生成用例拥有的最小仓储端口，不暴露通用表模型或全实体 CRUD。"""

    async def claim(self, request: ReconstructionRequest) -> bool:
        """原子登记意图，只有首次成功调用取得一次提交权。

        :param request: 已通过用例预检的冻结请求。
        :returns: 首次登记为真；完全相同的既有意图为假，禁止再次提交。
        :raises ReconstructionConflict: 同尝试改参、同作业改变意图，或其旧尝试尚未全部确认失败／取消。
        """
        ...

    async def get(self, attempt_id: AttemptId) -> ReconstructionRecord | None:
        """按确切原尝试读取记录，不创建任务或推断受理。

        :param attempt_id: 待查询的本地尝试身份。
        :returns: 原记录；未登记时为空。
        """
        ...

    async def record(
        self, attempt_id: AttemptId, event: ReconstructionEvent,
    ) -> ReconstructionRecord:
        """原子归约一个事件；拒绝未登记尝试和不合法事实。

        :param attempt_id: 已登记的原尝试身份。
        :param event: 核对后需要保存的单个事实。
        :returns: 保存后可读回的记录，符合 apply_reconstruction_event 的规则。
        :raises ReconstructionConflict: 尝试未登记或记录存在冲突。
        """
        ...
