# 文件信息：L0-02 的身份关联与局部结构约束。
# 作用：维护直接父引用、已知来源、执行产出和验收对象的单一表示。
# 边界：记录只描述身份关系；文件内容、业务状态、持久唯一性由后续条目负责。
"""定义无需数据库、宿主或模型框架的不可变关系。"""

from dataclasses import dataclass
from typing import final

from .identifiers import (
    AcceptanceId, ArtifactId, AttemptId, EvidenceId, JobId, ModelFamilyId,
    ModelVersionId, SessionId, TaskId, TurnId, WorkspaceId,
)


class IdentityRelationError(ValueError):
    """表示关系结构、引用或已提供记录之间的约束不满足。"""


def _require_type(value: object, expected: type[object]) -> None:
    """在关系边界拒绝错类对象，补足静态类型无法约束的输入。

    :param value: 待核对的字段或记录。
    :param expected: 此位置唯一允许的具体类型。
    :raises TypeError: 输入类型与契约不符。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def _require_ids(values: object, expected: type[object], *, nonempty: bool) -> None:
    """核对不可变身份集合，避免可变容器绕过冻结记录。

    :param values: 待核对的身份集合。
    :param expected: 集合成员的具体身份类型。
    :param nonempty: 此关系是否要求至少一个引用。
    :raises TypeError: 容器或成员类型错误。
    :raises IdentityRelationError: 必需集合为空。
    """
    if not isinstance(values, frozenset):
        raise TypeError("身份集合必须使用 frozenset")
    if nonempty and not values:
        raise IdentityRelationError("此关系必须包含至少一个身份")
    for value in values:
        _require_type(value, expected)


@final
@dataclass(frozen=True, slots=True)
class TaskIdentity:
    """保存业务目标的直接工作区归属。

    :param id: 业务任务身份。
    :param workspace_id: 唯一所属工作区。
    """

    id: TaskId
    workspace_id: WorkspaceId

    def __post_init__(self) -> None:
        """核对任务身份及直接归属的类型。"""
        _require_type(self.id, TaskId)
        _require_type(self.workspace_id, WorkspaceId)


@final
@dataclass(frozen=True, slots=True)
class SessionIdentity:
    """保存会话的唯一任务归属；任务不以会话存在为前提。

    :param id: 执行上下文身份。
    :param task_id: 所属任务，不重复工作区字段。
    """

    id: SessionId
    task_id: TaskId

    def __post_init__(self) -> None:
        """核对会话身份及任务引用的类型。"""
        _require_type(self.id, SessionId)
        _require_type(self.task_id, TaskId)


@final
@dataclass(frozen=True, slots=True)
class TurnIdentity:
    """保存受控处理轮次的直接会话归属。

    :param id: 可包含多次模型和工具调用的轮次身份。
    :param session_id: 所属执行上下文。
    """

    id: TurnId
    session_id: SessionId

    def __post_init__(self) -> None:
        """核对轮次身份及会话引用的类型。"""
        _require_type(self.id, TurnId)
        _require_type(self.session_id, SessionId)


@final
@dataclass(frozen=True, slots=True)
class JobIdentity:
    """保存具体执行意图的直接任务归属。

    :param id: 本地作业身份，不承载远端任务编号。
    :param task_id: 拥有此执行意图的业务任务。
    """

    id: JobId
    task_id: TaskId

    def __post_init__(self) -> None:
        """核对作业身份及任务引用的类型。"""
        _require_type(self.id, JobId)
        _require_type(self.task_id, TaskId)


@final
@dataclass(frozen=True, slots=True)
class AttemptIdentity:
    """保存实际执行尝试的直接作业归属。

    :param id: 执行尝试身份；轮询本身不产生新尝试。
    :param job_id: 此尝试所属的固定执行意图。
    """

    id: AttemptId
    job_id: JobId

    def __post_init__(self) -> None:
        """核对尝试身份及作业引用的类型。"""
        _require_type(self.id, AttemptId)
        _require_type(self.job_id, JobId)


@final
@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """保存素材或产物归属，不推断来源类别或字节身份。

    :param id: 原件与派生件共用的产物身份。
    :param workspace_id: 产物所属工作区。
    """

    id: ArtifactId
    workspace_id: WorkspaceId

    def __post_init__(self) -> None:
        """核对产物身份及工作区归属的类型。"""
        _require_type(self.id, ArtifactId)
        _require_type(self.workspace_id, WorkspaceId)


@final
@dataclass(frozen=True, slots=True)
class ModelFamilyIdentity:
    """保存模型家族归属，不用家族名表示身份。

    :param id: 模型家族身份。
    :param workspace_id: 家族所属工作区。
    """

    id: ModelFamilyId
    workspace_id: WorkspaceId

    def __post_init__(self) -> None:
        """核对家族身份及工作区归属的类型。"""
        _require_type(self.id, ModelFamilyId)
        _require_type(self.workspace_id, WorkspaceId)


@final
@dataclass(frozen=True, slots=True)
class ModelVersionIdentity:
    """固定版本的家族及产物关联，不规定文件格式和内容角色。

    :param id: 确切模型版本身份。
    :param family_id: 所属模型家族。
    :param artifact_ids: 此版本引用的非空产物集合。
    """

    id: ModelVersionId
    family_id: ModelFamilyId
    artifact_ids: frozenset[ArtifactId]

    def __post_init__(self) -> None:
        """核对版本结构，禁止以空产物集合建立版本关联。"""
        _require_type(self.id, ModelVersionId)
        _require_type(self.family_id, ModelFamilyId)
        _require_ids(self.artifact_ids, ArtifactId, nonempty=True)


@final
@dataclass(frozen=True, slots=True)
class ArtifactSetTarget:
    """表示尚未发布的候选或多文件集合这一确切观察目标。

    :param artifact_ids: 非空、去重的目标产物集合，不含方向或文件角色。
    """

    artifact_ids: frozenset[ArtifactId]

    def __post_init__(self) -> None:
        """拒绝空目标及错误或可变的身份集合。"""
        _require_ids(self.artifact_ids, ArtifactId, nonempty=True)


@final
@dataclass(frozen=True, slots=True)
class ModelVersionTarget:
    """表示确切版本目标，不接受家族或最新版本的间接选择。

    :param version_id: 必须单独解析并核对的模型版本身份。
    """

    version_id: ModelVersionId

    def __post_init__(self) -> None:
        """核对确切版本引用的类型。"""
        _require_type(self.version_id, ModelVersionId)


# 两种目标各有完整结构，不以类别字段加多个可空字段表示。
type ReviewTarget = ArtifactSetTarget | ModelVersionTarget


def _require_target(target: object) -> None:
    """核对证据与验收共享的目标结构，不解析目标的外部事实。

    :param target: 待核对的观察或验收对象。
    :raises TypeError: 输入不是允许的具体目标类型。
    """
    if type(target) not in (ArtifactSetTarget, ModelVersionTarget):
        raise TypeError("目标必须是文件集合或确切模型版本")


@final
@dataclass(frozen=True, slots=True)
class EvidenceIdentity:
    """关联证据与其实际观察对象，不保存质量结论。

    :param id: 证据身份。
    :param target: 此证据实际观察的对象。
    """

    id: EvidenceId
    target: ReviewTarget

    def __post_init__(self) -> None:
        """核对证据身份和观察目标的结构。"""
        _require_type(self.id, EvidenceId)
        _require_target(self.target)


@final
@dataclass(frozen=True, slots=True)
class AcceptanceIdentity:
    """关联验收记录、被验对象与证据，不表达已通过验收。

    :param id: 验收记录身份。
    :param target: 本记录的被验对象。
    :param evidence_ids: 已关联证据，可为空；不表示覆盖充分。
    """

    id: AcceptanceId
    target: ReviewTarget
    evidence_ids: frozenset[EvidenceId]

    def __post_init__(self) -> None:
        """核对验收关联结构，不从证据数量推导业务结果。"""
        _require_type(self.id, AcceptanceId)
        _require_target(self.target)
        _require_ids(self.evidence_ids, EvidenceId, nonempty=False)


@final
@dataclass(frozen=True, slots=True)
class Derivation:
    """记录一条已知派生关系，缺少此记录不表示产物是原件。

    :param output_id: 派生产物身份。
    :param source_ids: 非空的来源产物集合，不包含输出自身。
    """

    output_id: ArtifactId
    source_ids: frozenset[ArtifactId]

    def __post_init__(self) -> None:
        """核对派生结构并拒绝直接自引用，不宣称全图无环。"""
        _require_type(self.output_id, ArtifactId)
        _require_ids(self.source_ids, ArtifactId, nonempty=True)
        if self.output_id in self.source_ids:
            raise IdentityRelationError("派生产物不能直接引用自身作为来源")


@final
@dataclass(frozen=True, slots=True)
class AttemptOutput:
    """记录已知执行产出，不要求所有本地派生都创建执行尝试。

    :param attempt_id: 产生此产物的执行尝试。
    :param artifact_id: 此次尝试产生的产物身份。
    """

    attempt_id: AttemptId
    artifact_id: ArtifactId

    def __post_init__(self) -> None:
        """核对执行尝试与产物引用的类型。"""
        _require_type(self.attempt_id, AttemptId)
        _require_type(self.artifact_id, ArtifactId)
