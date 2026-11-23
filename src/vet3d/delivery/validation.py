# 文件信息：L0-04 的任务内交接与完整性守卫。
# 作用：核对发布对象、加载操作和逐项保存；仅限制交接声明，不消除部分副作用。
# 边界：不发布、加载或保存文件，不管理活动视窗、账本、重试、幂等或恢复。
"""以调用方给出的确切关联校验有限范围的交接声明。"""

from vet3d.artifacts import (
    FileReference, validate_content_binding, validate_content_observation, validate_file_set,
)
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, JobIdentity,
    ModelFamilyIdentity, ModelVersionIdentity, ReviewTarget, TaskIdentity,
    validate_attempt, validate_job, validate_model_version,
)

from ._checks import DeliveryContractError, require_target, require_type
from .receipts import LoadReceipt, PublicationReceipt, SaveReceipt, SaveTarget


def _validate_attempt_scope(
    attempt_id: AttemptId, *, attempt: AttemptIdentity, job: JobIdentity, task: TaskIdentity,
) -> None:
    """沿唯一归属链核对任务操作，不从产物反推执行意图。

    :param attempt_id: 回执引用的执行身份。
    :param attempt: 调用方指定的本次操作。
    :param job: 操作所属执行意图。
    :param task: 执行意图所属任务。
    :raises ValueError: 操作身份或其直接父链不匹配，保留身份层异常。
    :raises TypeError: 输入类型错误。
    """
    validate_attempt(attempt, job)
    validate_job(job, task)
    if attempt_id != attempt.id:
        raise DeliveryContractError("回执不属于本次交接操作")


def validate_publication_receipt(
    receipt: PublicationReceipt, *, attempt: AttemptIdentity, job: JobIdentity,
    task: TaskIdentity, version: ModelVersionIdentity, family: ModelFamilyIdentity,
    files: tuple[FileReference, ...], artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对实际返回版本的文件及归属，不要求候选已经通过业务验收。

    :param receipt: 发布服务提供的确认。
    :param attempt: 本次发布操作。
    :param job: 发布操作所属执行意图。
    :param task: 发布意图所属任务。
    :param version: 实际返回版本，不能替换为请求中猜测的版本。
    :param family: 返回版本所属家族。
    :param files: 恰好对应返回版本的内容引用。
    :param artifacts: 恰好对应这些文件的产物记录。
    :raises TypeError: 输入结构类型错误。
    :raises ValueError: 操作、版本、文件或作用域不匹配，保留下层异常。
    """
    require_type(receipt, PublicationReceipt)
    _validate_attempt_scope(receipt.attempt_id, attempt=attempt, job=job, task=task)
    validate_model_version(version, family=family, artifacts=artifacts)
    validate_file_set(files, artifacts=artifacts)
    if receipt.version_id != version.id:
        raise DeliveryContractError("发布回执与实际提供的版本不一致")
    if family.workspace_id != task.workspace_id:
        raise DeliveryContractError("发布版本必须属于任务工作区")


def require_current_load(
    receipt: LoadReceipt, *, current_attempt_id: AttemptId, target: ReviewTarget,
) -> None:
    """核对当前组件范围内的加载确认，不把旧回执升级为当前画面。

    调用方负责解析目标归属并在正确组件范围提供当前操作；本函数
    不维护活动指针，不从回执反推当前操作，不证明视觉证据已取得。

    :param receipt: 实际加载确认。
    :param current_attempt_id: 调用方确认仍有效的本次加载操作。
    :param target: 此操作要求的确切对象。
    :raises TypeError: 参数类型错误。
    :raises DeliveryContractError: 操作已过期或目标不匹配。
    """
    require_type(receipt, LoadReceipt)
    require_type(current_attempt_id, AttemptId)
    require_target(target)
    if receipt.attempt_id != current_attempt_id or receipt.target != target:
        raise DeliveryContractError("加载确认不匹配当前操作及确切目标")


def _save_targets(
    targets: tuple[SaveTarget, ...], *, artifacts: tuple[ArtifactIdentity, ...],
    task: TaskIdentity,
) -> dict[str, SaveTarget]:
    """建立当前保存要求的唯一目标索引，允许同一源复制到多个目标。

    :param targets: 非空的冻结保存要求。
    :param artifacts: 恰好覆盖源产物并集的记录。
    :param task: 已核对的所属任务。
    :returns: 当前调用内使用的目标索引。
    :raises TypeError: 容器或记录类型错误。
    :raises ValueError: 目标重复、内容绑定冲突或源集合及工作区不匹配。
    """
    require_type(targets, tuple)
    if not targets:
        raise DeliveryContractError("保存要求必须至少有一个目标")
    index: dict[str, SaveTarget] = {}
    references: dict[ArtifactId, FileReference] = {}
    for item in targets:
        require_type(item, SaveTarget)
        if item.destination in index:
            raise DeliveryContractError("保存要求不能重复占用同一目标")
        index[item.destination] = item
        previous = references.get(item.reference.artifact_id)
        if previous is not None:
            validate_content_binding(previous, item.reference)
        references[item.reference.artifact_id] = item.reference
    validate_file_set(tuple(references.values()), artifacts=artifacts)
    if any(artifact.workspace_id != task.workspace_id for artifact in artifacts):
        raise DeliveryContractError("保存源必须属于任务工作区")
    return index


def validate_save_receipt(
    receipt: SaveReceipt, *, attempt: AttemptIdentity, job: JobIdentity, task: TaskIdentity,
    targets: tuple[SaveTarget, ...], artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对已有保存项的关联，保留部分确认和内容不匹配的真实声明。

    :param receipt: 已确认的项目集合，不要求全部保存成功。
    :param attempt: 本次保存操作。
    :param job: 保存操作所属执行意图。
    :param task: 执行意图所属任务。
    :param targets: 本次要求的确切源与目标。
    :param artifacts: 恰好覆盖源产物的归属记录。
    :raises TypeError: 参数结构类型错误。
    :raises ValueError: 关联错配或回执出现要求之外的目标。
    """
    require_type(receipt, SaveReceipt)
    _validate_attempt_scope(receipt.attempt_id, attempt=attempt, job=job, task=task)
    index = _save_targets(targets, artifacts=artifacts, task=task)
    for item in receipt.saved:
        expected = index.get(item.destination)
        if expected is None or item.artifact_id != expected.reference.artifact_id:
            raise DeliveryContractError("保存回执包含不属于本次要求的源或目标")


def require_complete_save(
    receipt: SaveReceipt, *, attempt: AttemptIdentity, job: JobIdentity, task: TaskIdentity,
    targets: tuple[SaveTarget, ...], artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """仅在全部目标及内容声明均匹配时允许声明本次保存完整。

    :param receipt: 接收端提供的逐项确认。
    :param attempt: 本次保存操作。
    :param job: 保存操作所属执行意图。
    :param task: 执行意图所属任务。
    :param targets: 本次完整保存要求。
    :param artifacts: 对应源产物的归属记录。
    :raises TypeError: 参数类型错误。
    :raises ValueError: 关联、确认数量或字节描述不匹配，保留下层异常。
    """
    validate_save_receipt(
        receipt, attempt=attempt, job=job, task=task, targets=targets, artifacts=artifacts,
    )
    if len(receipt.saved) != len(targets):
        raise DeliveryContractError("本次保存尚未确认全部目标")
    index = {item.destination: item.reference for item in targets}
    for item in receipt.saved:
        validate_content_observation(index[item.destination], observed=item.observed)
