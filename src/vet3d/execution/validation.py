# 文件信息：L0-04 执行事实及 L0-05 取消回执的身份核对与局部观察对账。
# 边界：只处理显式输入，顺序由调用方确认；不读墙钟、不持久化、不生成新尝试。
"""保留可信执行观察，不用查询或等待诊断覆盖终态。"""

from vet3d.identity import AttemptIdentity

from ._checks import ExecutionContractError, require_type
from .cancellation import CancellationAcknowledged, CancellationReceipt, CancellationUnconfirmed
from .diagnostics import QueryUnavailable, SubmissionUnconfirmed, WaitEnded
from .observations import (
    AttemptActive, AttemptCancelled, AttemptFailed, AttemptObservation, AttemptSucceeded,
)


def _require_observation(value: object) -> None:
    """只接受执行端已确认的观察，不把诊断或 Python 异常解释为终态。

    :param value: 待交接的确认观察。
    :raises TypeError: 输入不属于唯一观察联合的具体变体。
    """
    if type(value) not in (AttemptActive, AttemptSucceeded, AttemptFailed, AttemptCancelled):
        raise TypeError("此位置必须使用已确认的执行观察")


def validate_attempt_fact(
    fact: AttemptObservation | QueryUnavailable | SubmissionUnconfirmed | WaitEnded | CancellationReceipt,
    *,
    attempt: AttemptIdentity,
) -> None:
    """核对事实指向给定的原尝试，不解析或复制其上游归属。

    :param fact: 确认观察、具有尝试关联的诊断或取消命令回执。
    :param attempt: 调用方已解析的确切执行尝试。
    :raises TypeError: 输入不是规定的事实或尝试记录。
    :raises ExecutionContractError: 事实引用了其他尝试。
    """
    if type(fact) not in (
        AttemptActive, AttemptSucceeded, AttemptFailed, AttemptCancelled,
        QueryUnavailable, SubmissionUnconfirmed, WaitEnded,
        CancellationAcknowledged, CancellationUnconfirmed,
    ):
        raise TypeError("此位置必须使用具有关联尝试的执行事实")
    require_type(attempt, AttemptIdentity)
    if fact.attempt_id != attempt.id:
        raise ExecutionContractError("执行事实与提供的尝试身份不匹配")


def reconcile_observation(
    last: AttemptObservation | None, current: AttemptObservation,
) -> AttemptObservation:
    """核对调用方已确认先后顺序的两次观察，不猜测墙钟或接收顺序。

    活动观察可以保持活动或进入终态；终态只能接受相同具体类别的
    后续确认观察。相同失败终态可补充新的诊断，返回本次确认的值。

    :param last: 上一次可信观察；None 表示尚无可信观察。
    :param current: 调用方确认较新的可信观察。
    :returns: 本次可信观察，不产生其他阶段的完成结论。
    :raises TypeError: 输入是查询、提交、等待诊断、取消回执或其他非观察对象。
    :raises ExecutionContractError: 尝试错配、可信终态冲突或终态倒退。
    """
    _require_observation(current)
    if last is None:
        return current
    _require_observation(last)
    if last.attempt_id != current.attempt_id:
        raise ExecutionContractError("不能用另一次尝试的观察更新原尝试")
    if type(last) is AttemptActive or type(last) is type(current):
        return current
    raise ExecutionContractError("可信执行终态不能倒退或改为其他终态")


def preserve_after_query_failure(
    last: AttemptObservation | None,
    *,
    failure: QueryUnavailable,
    attempt: AttemptIdentity,
) -> AttemptObservation | None:
    """查询失败时原样保留已有可信观察，未知仍保持无观察。

    :param last: 此尝试已有的可信观察，尚未取得时为 None。
    :param failure: 本次未取得查询观察的诊断。
    :param attempt: 调用方明确查询的原执行尝试。
    :returns: 原 last 对象或 None，不创建执行失败或重新提交许可。
    :raises TypeError: 输入不是规定的观察、查询诊断或尝试记录。
    :raises ExecutionContractError: 查询或原观察不属于提供的尝试。
    """
    require_type(failure, QueryUnavailable)
    validate_attempt_fact(failure, attempt=attempt)
    if last is not None:
        _require_observation(last)
        validate_attempt_fact(last, attempt=attempt)
    return last
