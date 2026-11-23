# 文件信息：L0-04 执行事实及 L0-05 取消回执契约的公共入口。
# 边界：不启动执行器、计时器或查询，不建立错误大全、重试策略或持久账本。
"""公开确认观察、独立诊断和执行前拒绝的唯一类型。"""

from ._checks import ExecutionContractError
from .cancellation import CancellationAcknowledged, CancellationReceipt, CancellationUnconfirmed
from .diagnostics import (
    CapabilityUnavailable, InputInsufficient, QueryUnavailable,
    SubmissionUnconfirmed, WaitEnded, WaitEndReason,
)
from .observations import (
    AttemptActive, AttemptCancelled, AttemptFailed, AttemptObservation, AttemptSucceeded,
)
from .validation import (
    preserve_after_query_failure, reconcile_observation, validate_attempt_fact,
)

__all__ = [
    "AttemptActive", "AttemptCancelled", "AttemptFailed", "AttemptObservation",
    "AttemptSucceeded", "CapabilityUnavailable", "ExecutionContractError",
    "InputInsufficient", "QueryUnavailable", "SubmissionUnconfirmed", "WaitEnded",
    "WaitEndReason", "preserve_after_query_failure", "reconcile_observation",
    "validate_attempt_fact",
    "CancellationAcknowledged", "CancellationReceipt", "CancellationUnconfirmed",
]
