# 文件信息：L0-05 的建模生成请求、输出及语义匹配声明。
# 作用：从业务准备集合选择单次生成输入，保持执行观察和产物关联可核对。
# 边界：不读取文件、选择供应商或执行模型，不把生成完成解释为业务验收通过。
"""维护一次重建调用的数据边界，复用身份、文件和执行事实。"""

from dataclasses import dataclass
from typing import final

from vet3d.artifacts import FileReference, validate_file_reference
from vet3d.execution import AttemptObservation, reconcile_observation
from vet3d.identity import (
    ArtifactId,
    ArtifactIdentity,
    AttemptIdentity,
    AttemptOutput,
    JobIdentity,
    TaskIdentity,
    validate_attempt,
    validate_job,
)

from ._checks import ModelingContractError, require_text, require_type
from .references import PreparedViews, TaskReferences


@final
@dataclass(frozen=True, slots=True)
class GenerationPlan:
    """指定单次生成实际使用的有序图片引用，不复制业务准备目标。

    :param input_ids: 非空且无重复的准备产物身份；首项是本次操作主参考。
    """

    input_ids: tuple[ArtifactId, ...]

    def __post_init__(self) -> None:
        """核对有序输入集合，不通过图片数量推断生成质量。"""
        require_type(self.input_ids, tuple)
        if not self.input_ids:
            raise ModelingContractError("单次生成必须明确至少一份输入")
        for artifact_id in self.input_ids:
            require_type(artifact_id, ArtifactId)
        if len(set(self.input_ids)) != len(self.input_ids):
            raise ModelingContractError("单次生成输入不能重复引用同一产物")


@final
@dataclass(frozen=True, slots=True)
class ReconstructionRequest:
    """关联一次生成的任务、原尝试、业务准备和实际选图。

    :param task: 本次建模所属的任务及工作区。
    :param job: 任务拥有的具体执行意图。
    :param attempt: 本次实际执行尝试，查询和取消继续引用此身份。
    :param references: 任务级主体基准、必保特征及准备方向要求。
    :param prepared: 可供本次业务使用的准备视图和额外验收参考。
    :param plan: 本次实际生成选图，不必覆盖全部准备方向。
    :param files: 本次登记时冻结的确切内容引用，后续解析必须与这些预期内容匹配。
    """

    task: TaskIdentity
    job: JobIdentity
    attempt: AttemptIdentity
    references: TaskReferences
    prepared: PreparedViews
    plan: GenerationPlan
    files: tuple[FileReference, ...]

    def __post_init__(self) -> None:
        """核对直接父链与选图归属；文件及准备完整性由服务解析后另验。

        :raises TypeError: 输入不是规定的具体记录。
        :raises ModelingContractError: 任务参考错配或计划引用了准备图之外的产物。
        :raises vet3d.identity.IdentityRelationError: 任务、作业和尝试的直接父链不符。
        """
        require_type(self.task, TaskIdentity)
        require_type(self.job, JobIdentity)
        require_type(self.attempt, AttemptIdentity)
        require_type(self.references, TaskReferences)
        require_type(self.prepared, PreparedViews)
        require_type(self.plan, GenerationPlan)
        require_type(self.files, tuple)
        for reference in self.files:
            require_type(reference, FileReference)
        validate_job(self.job, self.task)
        validate_attempt(self.attempt, self.job)
        if self.references.task_id != self.task.id:
            raise ModelingContractError("生成请求与任务主体参考不属于同一任务")
        prepared_ids = frozenset(view.artifact_id for view in self.prepared.views)
        if not frozenset(self.plan.input_ids) <= prepared_ids:
            raise ModelingContractError("生成输入只能引用业务准备图，不能提交额外验收参考或未知产物")


@final
@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    """关联生成产物的身份、内容声明和既有尝试产出边。

    :param artifact: 产物身份和工作区归属。
    :param file: 该产物绑定的确切内容引用。
    :param origin: 已知尝试产出关联，不意味着该尝试或产物已验收成功。
    """

    artifact: ArtifactIdentity
    file: FileReference
    origin: AttemptOutput

    def __post_init__(self) -> None:
        """核对三者的产物身份，完整执行父链由消费服务继续核对。

        :raises TypeError: 输入不是规定的具体记录。
        :raises ModelingContractError: 产出边指向另一产物。
        :raises vet3d.artifacts.ArtifactContractError: 内容引用与产物身份不同。
        """
        require_type(self.artifact, ArtifactIdentity)
        require_type(self.file, FileReference)
        require_type(self.origin, AttemptOutput)
        validate_file_reference(self.file, artifact=self.artifact)
        if self.origin.artifact_id != self.artifact.id:
            raise ModelingContractError("生成产物与尝试产出关联不是同一身份")


@final
@dataclass(frozen=True, slots=True)
class ReconstructionUpdate:
    """交接执行端确认观察及当前已知产物，不推导产物质量或发布状态。

    :param observation: 执行端对原尝试的确认观察。
    :param outputs: 当前明确取得的生成产物，可为空或部分完成。
    """

    observation: AttemptObservation
    outputs: tuple[GeneratedArtifact, ...] = ()

    def __post_init__(self) -> None:
        """复用唯一观察类型并核对输出唯一性及原尝试关联。

        :raises TypeError: 观察、输出容器或成员类型错误。
        :raises ModelingContractError: 输出产物身份重复或属于其他尝试。
        """
        reconcile_observation(None, self.observation)
        require_type(self.outputs, tuple)
        output_ids: set[ArtifactId] = set()
        for output in self.outputs:
            require_type(output, GeneratedArtifact)
            if output.artifact.id in output_ids:
                raise ModelingContractError("同次生成更新不能重复列出产物身份")
            if output.origin.attempt_id != self.observation.attempt_id:
                raise ModelingContractError("生成产物不属于本次确认观察的执行尝试")
            output_ids.add(output.artifact.id)


@final
@dataclass(frozen=True, slots=True)
class SubmissionCompatible:
    """声明此具体请求满足适配器的已知输入规则，不证明环境或模型已就绪。"""


@final
@dataclass(frozen=True, slots=True)
class CapabilityUnverified:
    """声明适配器尚不能证实此请求的语义匹配，不冒充已知不支持。

    :param reason: 尚未证实匹配规则的具体说明，不是部署资格或重试许可。
    """

    reason: str

    def __post_init__(self) -> None:
        """保留必要诊断，不从文字推导新的业务状态。"""
        require_text(self.reason)
