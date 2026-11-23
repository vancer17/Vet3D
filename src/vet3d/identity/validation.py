# 文件信息：L0-02 的关系交接校验。
# 作用：对调用方提供的确切记录核对引用、范围和观察对象，结果只表示局部关系满足约束。
# 边界：不查询存储、不修改输入、不建立全局注册表，不证明字节、权限或业务质量。
"""通过纯同步函数核对消费方实际需要的身份关系。"""

from .identifiers import ArtifactId, EvidenceId
from .relations import (
    AcceptanceIdentity, ArtifactIdentity, ArtifactSetTarget, AttemptIdentity,
    AttemptOutput, Derivation, EvidenceIdentity, IdentityRelationError,
    JobIdentity, ModelFamilyIdentity, ModelVersionIdentity, ModelVersionTarget,
    SessionIdentity, TaskIdentity, TurnIdentity, _require_type,
)


def _require_reference(actual: object, expected: object) -> None:
    """核对引用与提供记录的身份，避免用同区的其他记录替代。

    :param actual: 关联声明的身份。
    :param expected: 调用方提供记录的实际身份。
    :raises IdentityRelationError: 二者不一致。
    """
    if actual != expected:
        raise IdentityRelationError("引用与提供记录的身份不匹配")


def _artifacts(
    expected: frozenset[ArtifactId], records: tuple[ArtifactIdentity, ...],
) -> dict[ArtifactId, ArtifactIdentity]:
    """取得本次校验所需的精确产物集合，不接受含糊的额外记录。

    :param expected: 关系声明的产物引用集合。
    :param records: 调用方已经解析的产物记录元组。
    :returns: 仅用于本次调用的身份索引。
    :raises TypeError: 记录容器或成员不是规定类型。
    :raises IdentityRelationError: 记录缺失、多余或身份重复。
    """
    _require_type(records, tuple)
    index: dict[ArtifactId, ArtifactIdentity] = {}
    for record in records:
        _require_type(record, ArtifactIdentity)
        if record.id in index:
            raise IdentityRelationError("提供的产物记录含重复身份")
        index[record.id] = record
    if index.keys() != expected:
        raise IdentityRelationError("提供的产物记录与所需引用集合不一致")
    return index


def validate_session(session: SessionIdentity, task: TaskIdentity) -> None:
    """核对会话的直接任务归属，不查询会话历史。

    :param session: 待交接的会话关联。
    :param task: 已解析的所属任务。
    :raises TypeError: 传入记录的类型错误。
    :raises IdentityRelationError: 任务引用不匹配。
    """
    _require_type(session, SessionIdentity)
    _require_type(task, TaskIdentity)
    _require_reference(session.task_id, task.id)


def validate_turn(turn: TurnIdentity, session: SessionIdentity) -> None:
    """核对轮次的直接会话归属，不推导会话的其他祖先事实。

    :param turn: 待交接的轮次关联。
    :param session: 已解析的所属会话。
    :raises TypeError: 传入记录的类型错误。
    :raises IdentityRelationError: 会话引用不匹配。
    """
    _require_type(turn, TurnIdentity)
    _require_type(session, SessionIdentity)
    _require_reference(turn.session_id, session.id)


def validate_job(job: JobIdentity, task: TaskIdentity) -> None:
    """核对执行意图的任务归属，不要求存在 LLM 会话。

    :param job: 待交接的作业关联。
    :param task: 已解析的所属任务。
    :raises TypeError: 传入记录的类型错误。
    :raises IdentityRelationError: 任务引用不匹配。
    """
    _require_type(job, JobIdentity)
    _require_type(task, TaskIdentity)
    _require_reference(job.task_id, task.id)


def validate_attempt(attempt: AttemptIdentity, job: JobIdentity) -> None:
    """核对尝试的作业归属，不创建重试或改变尝试身份。

    :param attempt: 待交接的执行尝试。
    :param job: 已解析的所属执行意图。
    :raises TypeError: 传入记录的类型错误。
    :raises IdentityRelationError: 作业引用不匹配。
    """
    _require_type(attempt, AttemptIdentity)
    _require_type(job, JobIdentity)
    _require_reference(attempt.job_id, job.id)


def validate_derivation(
    derivation: Derivation,
    *,
    output: ArtifactIdentity,
    sources: tuple[ArtifactIdentity, ...],
) -> None:
    """核对一条已知派生边的确切对象及同区归属。

    :param derivation: 输出及来源的身份关系。
    :param output: 已解析的输出产物。
    :param sources: 恰好覆盖来源引用的记录，不读取全历史关系。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 引用、集合或工作区不匹配。
    """
    _require_type(derivation, Derivation)
    _require_type(output, ArtifactIdentity)
    _require_reference(derivation.output_id, output.id)
    for source in _artifacts(derivation.source_ids, sources).values():
        if source.workspace_id != output.workspace_id:
            raise IdentityRelationError("派生来源与输出必须属于同一工作区")


def validate_attempt_output(
    output: AttemptOutput,
    *,
    attempt: AttemptIdentity,
    job: JobIdentity,
    task: TaskIdentity,
    artifact: ArtifactIdentity,
) -> None:
    """沿直接父链核对已知执行产出，不把产出关联视为执行成功。

    :param output: 尝试与产物的关联。
    :param attempt: 已解析的产出尝试。
    :param job: 此尝试的所属作业。
    :param task: 此作业的所属任务。
    :param artifact: 已解析的产物记录。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 任一引用或工作区不匹配。
    """
    _require_type(output, AttemptOutput)
    _require_type(artifact, ArtifactIdentity)
    validate_attempt(attempt, job)
    validate_job(job, task)
    _require_reference(output.attempt_id, attempt.id)
    _require_reference(output.artifact_id, artifact.id)
    if task.workspace_id != artifact.workspace_id:
        raise IdentityRelationError("执行产物与所属任务必须位于同一工作区")


def validate_model_version(
    version: ModelVersionIdentity,
    *,
    family: ModelFamilyIdentity,
    artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对确切版本的家族与产物关联，不推断发布或字节有效性。

    :param version: 固定的版本关联。
    :param family: 已解析的所属家族。
    :param artifacts: 恰好覆盖版本引用的产物记录。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 家族引用、产物集合或工作区不匹配。
    """
    _require_type(version, ModelVersionIdentity)
    _require_type(family, ModelFamilyIdentity)
    _require_reference(version.family_id, family.id)
    for artifact in _artifacts(version.artifact_ids, artifacts).values():
        if artifact.workspace_id != family.workspace_id:
            raise IdentityRelationError("版本产物与模型家族必须属于同一工作区")


def validate_artifact_target(
    target: ArtifactSetTarget, *, artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对文件集合目标的精确记录及同区归属。

    :param target: 不要求模型已发布的文件集合目标。
    :param artifacts: 恰好覆盖目标引用的产物记录。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 记录不完整、含额外身份或跨工作区。
    """
    _require_type(target, ArtifactSetTarget)
    records = _artifacts(target.artifact_ids, artifacts)
    if len({record.workspace_id for record in records.values()}) != 1:
        raise IdentityRelationError("同一文件集合目标必须属于一个工作区")


def validate_version_target(
    target: ModelVersionTarget,
    *,
    version: ModelVersionIdentity,
    family: ModelFamilyIdentity,
    artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对目标版本及其家族、产物链，不采用家族最新项替代。

    :param target: 确切模型版本目标。
    :param version: 目标引用的版本记录。
    :param family: 此版本的模型家族。
    :param artifacts: 此版本的完整产物引用记录。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 版本身份或关联链不匹配。
    """
    _require_type(target, ModelVersionTarget)
    _require_type(version, ModelVersionIdentity)
    _require_reference(target.version_id, version.id)
    validate_model_version(version, family=family, artifacts=artifacts)


def validate_acceptance(
    acceptance: AcceptanceIdentity, *, evidence: tuple[EvidenceIdentity, ...],
) -> None:
    """核对证据引用及观察目标，不判定证据充分或业务合格。

    目标所引用实体的解析校验由对应目标校验函数负责。文件证据可覆盖
    被验集合的子集；版本证据必须指向同一版本，目标类型不隐式互转。

    :param acceptance: 被验对象及证据引用。
    :param evidence: 恰好覆盖引用集合的已解析证据，允许为空。
    :raises TypeError: 传入结构类型错误。
    :raises IdentityRelationError: 证据缺失、多余、重复或观察对象不匹配。
    """
    _require_type(acceptance, AcceptanceIdentity)
    _require_type(evidence, tuple)
    index: dict[EvidenceId, EvidenceIdentity] = {}
    for record in evidence:
        _require_type(record, EvidenceIdentity)
        if record.id in index:
            raise IdentityRelationError("提供的证据记录含重复身份")
        index[record.id] = record
    if index.keys() != acceptance.evidence_ids:
        raise IdentityRelationError("提供的证据记录与所需引用集合不一致")
    target = acceptance.target
    for record in index.values():
        observed = record.target
        if isinstance(target, ArtifactSetTarget) and isinstance(observed, ArtifactSetTarget):
            if observed.artifact_ids <= target.artifact_ids:
                continue
        elif isinstance(target, ModelVersionTarget) and isinstance(observed, ModelVersionTarget):
            if observed.version_id == target.version_id:
                continue
        raise IdentityRelationError("证据观察对象不适用于本次验收目标")
