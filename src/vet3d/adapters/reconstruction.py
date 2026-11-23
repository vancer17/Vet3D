# 文件信息：L0-05 生成链路的内存仓储、显式素材夹具和两种生成替身。
# 作用：验证端口替换、原尝试续查及取消回执边界，不装配真实模型或文件服务。
# 边界：状态仅在当前实例内存中保存；合成产物只是声明，不存在对应模型文件。
"""以固定且可核查的替身行为验证最小生成链路。"""

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import final
from uuid import uuid4

from vet3d.application import (
    ReconstructionConflict, ReconstructionEvent, ReconstructionRecord,
    ReconstructionRepository, apply_reconstruction_event,
)
from vet3d.artifacts import (
    ArtifactAccess, ArtifactContractError, ContentFingerprint, FileObservation,
    FileMissing, FilePresent, FileReference, FileUnavailable, LocatedArtifact,
    WorkspaceFileLocation,
)
from vet3d.execution import (
    AttemptActive, AttemptCancelled, AttemptFailed, AttemptSucceeded, CancellationAcknowledged,
    CancellationUnconfirmed, CapabilityUnavailable, QueryUnavailable, SubmissionUnconfirmed,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, AttemptId, AttemptOutput
from vet3d.modeling import (
    GeneratedArtifact, ModelingContractError, ReconstructionPort, ReconstructionRequest,
    ReconstructionUpdate, SubmissionCompatible, ViewDirection,
)


def _require_type(value: object, expected: type[object]) -> None:
    """检查适配器边界的具体类型，不隐式转换业务身份。

    :param value: 当前传入的对象。
    :param expected: 此位置接受的具体类型。
    :raises TypeError: 输入不属于所需类型。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


class MemoryReconstructionRepository(ReconstructionRepository):
    """在单个事件循环内原子登记与归约，不承诺线程、进程或重启安全。"""

    def __init__(self) -> None:
        """创建仅属于本实例的空记录集合，不建立持久账本。"""
        self._records: dict[AttemptId, ReconstructionRecord] = {}

    async def claim(self, request: ReconstructionRequest) -> bool:
        """首次登记取得一次提交权，同尝试相同请求只返回已有登记结果。

        本方法内部没有挂起点；比较、构造和赋值在单事件循环中连续完成。
        同作业仅在全部旧尝试确认失败或取消后接受显式新尝试；这是重复执行守卫，
        不自动创建重试，也不代替上层的重试策略与预算。

        :param request: 通过用例预检的冻结生成请求。
        :returns: 首次登记为真，同尝试完全相同的重复登记为假。
        :raises TypeError: 请求不是具体的生成请求。
        :raises ReconstructionConflict: 同尝试改参、同作业改变意图或旧尝试不允许再次执行。
        """
        _require_type(request, ReconstructionRequest)
        previous = self._records.get(request.attempt.id)
        if previous is not None:
            if previous.request != request:
                raise ReconstructionConflict("同一尝试不能改变已登记请求")
            return False
        for record in self._records.values():
            if record.request.job.id == request.job.id:
                if replace(request, attempt=record.request.attempt) != record.request:
                    raise ReconstructionConflict("同一作业的新尝试不能改变固定执行意图")
                if type(record.observation) not in (AttemptFailed, AttemptCancelled):
                    raise ReconstructionConflict("同一作业的已有尝试尚未全部确认失败或取消")
        candidate = ReconstructionRecord(request=request)
        self._records[request.attempt.id] = candidate
        return True

    async def get(self, attempt_id: AttemptId) -> ReconstructionRecord | None:
        """按原尝试读取当前冻结记录，未登记时不创建状态。

        :param attempt_id: 需要读取的确切原尝试。
        :returns: 本实例的原记录，未登记时为 None。
        :raises TypeError: 身份不是 AttemptId。
        """
        _require_type(attempt_id, AttemptId)
        return self._records.get(attempt_id)

    async def record(
        self, attempt_id: AttemptId, event: ReconstructionEvent,
    ) -> ReconstructionRecord:
        """完整归约成功后再赋值，拒绝的事件不会污染已有观察或输出。

        本方法内部没有挂起点；仅保证单事件循环内本次操作连续完成。

        :param attempt_id: 已登记的原尝试。
        :param event: 待核对并保存的单个生成事实。
        :returns: 保存后可读回的冻结记录，已有产物不会被空更新删除。
        :raises TypeError: 身份或事件类型不符合契约。
        :raises ValueError: 尝试未登记、关联不符或事实冲突，保留下层异常类型。
        """
        _require_type(attempt_id, AttemptId)
        original = self._records.get(attempt_id)
        if original is None:
            raise ReconstructionConflict("原尝试尚未登记，不能保存交互事实")
        candidate = apply_reconstruction_event(original, event)
        self._records[attempt_id] = candidate
        return candidate


class SyntheticArtifactAccess(ArtifactAccess):
    """提供显式内存登记与观察夹具，不自行推断文件存在或计算真实摘要。"""

    def __init__(
        self, records: tuple[LocatedArtifact, ...], observations: tuple[FileObservation, ...],
    ) -> None:
        """保存互相独立的登记和观察，不从一项自动生成另一项。

        :param records: 按产物身份唯一的明确登记记录。
        :param observations: 按完整工作区位置唯一的明确观察。
        :raises TypeError: 容器或成员不是规定的具体类型。
        :raises ArtifactContractError: 登记身份或观察位置重复。
        """
        _require_type(records, tuple)
        _require_type(observations, tuple)
        record_index: dict[ArtifactId, LocatedArtifact] = {}
        for record in records:
            _require_type(record, LocatedArtifact)
            if record.artifact.id in record_index:
                raise ArtifactContractError("合成素材登记包含重复产物身份")
            record_index[record.artifact.id] = record
        observation_index: dict[WorkspaceFileLocation, FileObservation] = {}
        for observation in observations:
            if type(observation) not in (FilePresent, FileMissing, FileUnavailable):
                raise TypeError("合成素材观察必须使用已定义的具体变体")
            if observation.location in observation_index:
                raise ArtifactContractError("合成素材观察包含重复位置")
            observation_index[observation.location] = observation
        self._records = record_index
        self._observations = observation_index

    async def resolve(self, artifact_id: ArtifactId) -> LocatedArtifact | None:
        """返回显式登记，未登记不会被解释成文件缺失。

        :param artifact_id: 所需的确切产物身份。
        :returns: 对应登记，未登记时为 None。
        :raises TypeError: 身份不是 ArtifactId。
        """
        _require_type(artifact_id, ArtifactId)
        return self._records.get(artifact_id)

    async def observe(self, location: WorkspaceFileLocation) -> FileObservation:
        """返回该位置的显式观察，夹具未提供时返回访问不可用诊断。

        :param location: 本次需要观察的确切位置。
        :returns: 原观察或 FileUnavailable，不补造 FileMissing。
        :raises TypeError: 位置不是具体 WorkspaceFileLocation。
        """
        _require_type(location, WorkspaceFileLocation)
        observation = self._observations.get(location)
        if observation is not None:
            return observation
        return FileUnavailable(location, reason="合成夹具未提供此位置的观察，不推断文件存在或缺失")


@final
@dataclass(frozen=True, slots=True)
class _SyntheticSubmission:
    """保存替身的单次绑定及后续固定行为，不暴露为业务状态。

    :param request: 首次真实传入该替身的冻结请求。
    :param update: 此替身最近确认的观察及输出。
    :param query_diagnostic_pending: 四向替身是否尚未返回一次预定的查询不可用。
    :param cancellation_requested: 四向替身是否已受理取消请求，等待随后查询确认终态。
    """

    request: ReconstructionRequest
    update: ReconstructionUpdate
    query_diagnostic_pending: bool = False
    cancellation_requested: bool = False


def _synthetic_output(request: ReconstructionRequest) -> GeneratedArtifact:
    """创建与任务和原尝试关联的合成产物声明，不写出模型文件。

    :param request: 已通过语义匹配的原生成请求。
    :returns: 使用新产物身份的固定合成字节描述及来源关系。
    """
    content = b"Vet3D L0-05 synthetic candidate declaration; not a model file\n"
    input_ids = {file.artifact_id for file in request.files}
    artifact_id = ArtifactId(uuid4())
    while artifact_id in input_ids:
        artifact_id = ArtifactId(uuid4())
    artifact = ArtifactIdentity(id=artifact_id, workspace_id=request.task.workspace_id)
    reference = FileReference(
        artifact_id=artifact_id,
        content=ContentFingerprint(sha256=sha256(content).hexdigest(), byte_size=len(content)),
    )
    return GeneratedArtifact(
        artifact=artifact, file=reference,
        origin=AttemptOutput(attempt_id=request.attempt.id, artifact_id=artifact_id),
    )


class FiveViewGenerator(ReconstructionPort):
    """接受一至五个业务准备方向并立即返回合成成功，不能证明真实建模能力。"""

    def __init__(self) -> None:
        """创建本实例的原尝试绑定，不接受运行模式或能力配置。"""
        self._submissions: dict[AttemptId, _SyntheticSubmission] = {}

    @property
    def submitted_requests(self) -> tuple[ReconstructionRequest, ...]:
        """取得实际首次提交到本替身的请求快照，不提供额外计数字段。

        :returns: 按首次提交顺序排列的冻结请求元组。
        """
        return tuple(binding.request for binding in self._submissions.values())

    def check(self, request: ReconstructionRequest) -> SubmissionCompatible | CapabilityUnavailable:
        """检查本次输入来自一至五个准备方向，不要求提交全部业务参考。

        :param request: 需要匹配的确切生成请求。
        :returns: 固定替身规则匹配或明确不匹配；不表示真实模型已就绪。
        :raises TypeError: 请求类型错误。
        """
        _require_type(request, ReconstructionRequest)
        if not 1 <= len(request.plan.input_ids) <= 5:
            return CapabilityUnavailable("五向生成替身只接受一至五个已准备的方向")
        return SubmissionCompatible()

    async def submit(self, request: ReconstructionRequest) -> ReconstructionUpdate | SubmissionUnconfirmed:
        """首次提交产生一次合成结果；重复原请求只返回已有结果。

        :param request: 业务已预检的原尝试请求。
        :returns: 原尝试的固定成功观察及一个合成产物引用。
        :raises ReconstructionConflict: 已绑定尝试收到不同请求。
        :raises ModelingContractError: 输入不符合本替身的固定规则。
        """
        _require_type(request, ReconstructionRequest)
        previous = self._submissions.get(request.attempt.id)
        if previous is not None:
            if previous.request != request:
                raise ReconstructionConflict("原尝试的生成参数不能改变")
            return previous.update
        compatibility = self.check(request)
        if isinstance(compatibility, CapabilityUnavailable):
            raise ModelingContractError(compatibility.reason)
        update = ReconstructionUpdate(
            observation=AttemptSucceeded(request.attempt.id), outputs=(_synthetic_output(request),),
        )
        self._submissions[request.attempt.id] = _SyntheticSubmission(request=request, update=update)
        return update

    async def query(self, attempt_id: AttemptId) -> ReconstructionUpdate | QueryUnavailable:
        """查询既有合成结果，未知绑定不触发提交。

        :param attempt_id: 原尝试身份。
        :returns: 原确认结果，或没有原绑定的查询诊断。
        :raises TypeError: 身份类型错误。
        """
        _require_type(attempt_id, AttemptId)
        binding = self._submissions.get(attempt_id)
        if binding is None:
            return QueryUnavailable(attempt_id, reason="当前替身实例没有原尝试绑定")
        return binding.update

    async def cancel(self, attempt_id: AttemptId) -> CancellationAcknowledged | CancellationUnconfirmed:
        """受理原尝试的取消请求，已成功的合成执行继续保留原终态。

        :param attempt_id: 请求取消的原尝试身份。
        :returns: 请求受理说明，或未知绑定的回执不明诊断。
        :raises TypeError: 身份类型错误。
        """
        _require_type(attempt_id, AttemptId)
        if attempt_id not in self._submissions:
            return CancellationUnconfirmed(attempt_id, reason="当前替身实例没有原尝试绑定")
        return CancellationAcknowledged(attempt_id, reason="合成取消请求已受理；既有执行终态保持")


class FourViewGenerator(ReconstructionPort):
    """只接受前后左右且首图前视，通过一次查询不可用后返回合成结果。"""

    def __init__(self) -> None:
        """创建本实例的原尝试绑定，不接受供应商模式或恢复配置。"""
        self._submissions: dict[AttemptId, _SyntheticSubmission] = {}

    @property
    def submitted_requests(self) -> tuple[ReconstructionRequest, ...]:
        """取得实际首次提交请求的冻结快照，不暴露内部进度结构。

        :returns: 按首次提交顺序排列的请求元组。
        """
        return tuple(binding.request for binding in self._submissions.values())

    def check(self, request: ReconstructionRequest) -> SubmissionCompatible | CapabilityUnavailable:
        """核对实际选图方向与首图规则，不因准备集合含顶视而拒绝合法子集。

        :param request: 包含业务准备集合和本次选图的请求。
        :returns: 固定规则匹配，或说明具体不匹配的能力结果。
        :raises TypeError: 请求类型错误。
        """
        _require_type(request, ReconstructionRequest)
        prepared = {view.artifact_id: view.direction for view in request.prepared.views}
        directions = tuple(prepared[artifact_id] for artifact_id in request.plan.input_ids)
        allowed = frozenset({ViewDirection.FRONT, ViewDirection.BACK, ViewDirection.LEFT, ViewDirection.RIGHT})
        if not 1 <= len(directions) <= 4 or not frozenset(directions) <= allowed:
            return CapabilityUnavailable("四向生成替身只接受前、后、左、右中的一至四张准备图")
        if directions[0] is not ViewDirection.FRONT:
            return CapabilityUnavailable("四向生成替身要求实际提交的首图为前视")
        return SubmissionCompatible()

    async def submit(self, request: ReconstructionRequest) -> ReconstructionUpdate | SubmissionUnconfirmed:
        """首次提交仅确认活动，重复原请求不产生第二次执行或新产物。

        :param request: 已经通过用例预检的原请求。
        :returns: 本尝试当前已确认的观察，首次为活动且没有产物。
        :raises ReconstructionConflict: 已绑定的尝试收到不同请求。
        :raises ModelingContractError: 选图不符合本替身规则。
        """
        _require_type(request, ReconstructionRequest)
        previous = self._submissions.get(request.attempt.id)
        if previous is not None:
            if previous.request != request:
                raise ReconstructionConflict("原尝试的生成参数不能改变")
            return previous.update
        compatibility = self.check(request)
        if isinstance(compatibility, CapabilityUnavailable):
            raise ModelingContractError(compatibility.reason)
        update = ReconstructionUpdate(observation=AttemptActive(request.attempt.id))
        self._submissions[request.attempt.id] = _SyntheticSubmission(
            request=request, update=update, query_diagnostic_pending=True,
        )
        return update

    async def query(self, attempt_id: AttemptId) -> ReconstructionUpdate | QueryUnavailable:
        """查询原尝试，按固定顺序返回诊断或终态，绝不通过重新提交续查。

        :param attempt_id: 需要继续观察的原尝试。
        :returns: 一次查询不可用后取得成功；已受理取消则在查询时确认取消。
        :raises TypeError: 身份类型错误。
        """
        _require_type(attempt_id, AttemptId)
        binding = self._submissions.get(attempt_id)
        if binding is None:
            return QueryUnavailable(attempt_id, reason="当前替身实例没有原尝试绑定")
        if not isinstance(binding.update.observation, AttemptActive):
            return binding.update
        if binding.cancellation_requested:
            update = ReconstructionUpdate(
                observation=AttemptCancelled(attempt_id), outputs=binding.update.outputs,
            )
            self._submissions[attempt_id] = replace(binding, update=update)
            return update
        if binding.query_diagnostic_pending:
            self._submissions[attempt_id] = replace(binding, query_diagnostic_pending=False)
            return QueryUnavailable(attempt_id, reason="合成查询本次未取得新观察；原尝试保持活动")
        update = ReconstructionUpdate(
            observation=AttemptSucceeded(attempt_id), outputs=(_synthetic_output(binding.request),),
        )
        self._submissions[attempt_id] = replace(binding, update=update)
        return update

    async def cancel(self, attempt_id: AttemptId) -> CancellationAcknowledged | CancellationUnconfirmed:
        """只受理取消请求，本方法不将活动观察改写为已取消。

        :param attempt_id: 需要请求取消的原尝试。
        :returns: 请求受理或原绑定不存在的回执不明，不是执行终态。
        :raises TypeError: 身份类型错误。
        """
        _require_type(attempt_id, AttemptId)
        binding = self._submissions.get(attempt_id)
        if binding is None:
            return CancellationUnconfirmed(attempt_id, reason="当前替身实例没有原尝试绑定")
        if isinstance(binding.update.observation, AttemptActive):
            self._submissions[attempt_id] = replace(binding, cancellation_requested=True)
        return CancellationAcknowledged(attempt_id, reason="合成取消请求已受理；终态由原尝试后续查询确认")
