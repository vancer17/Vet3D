# 文件信息：L0-04 已确认执行观察的唯一结果变体。
# 边界：只引用既有 AttemptId，不保存作业父链、文件状态、质量结论或重试许可。
"""表达执行仍活动或已经到达某一可信终态。"""

from dataclasses import dataclass
from typing import final

from vet3d.identity import AttemptId

from ._checks import require_reason, require_type


@final
@dataclass(frozen=True, slots=True)
class AttemptActive:
    """表示执行端已确认尝试仍活动，不由等待未结束推导。

    :param attempt_id: 已确认仍活动的确切执行尝试。
    """

    attempt_id: AttemptId

    def __post_init__(self) -> None:
        """核对执行尝试身份。

        :raises TypeError: 输入不是具体 AttemptId。
        """
        require_type(self.attempt_id, AttemptId)


@final
@dataclass(frozen=True, slots=True)
class AttemptSucceeded:
    """表示执行端确认成功，不证明文件、报告、验收或交付成功。

    :param attempt_id: 已确认执行成功的确切尝试。
    """

    attempt_id: AttemptId

    def __post_init__(self) -> None:
        """核对执行尝试身份。

        :raises TypeError: 输入不是具体 AttemptId。
        """
        require_type(self.attempt_id, AttemptId)


@final
@dataclass(frozen=True, slots=True)
class AttemptFailed:
    """表示执行端确认失败，不从原因文字自动决定是否重试。

    :param attempt_id: 已确认失败的确切执行尝试。
    :param reason: 已取得的非空白失败说明，不是全局错误码。
    """

    attempt_id: AttemptId
    reason: str

    def __post_init__(self) -> None:
        """核对身份及失败说明。

        :raises TypeError: 身份或原因类型错误。
        :raises ExecutionContractError: 原因空白或无法编码为 UTF-8。
        """
        require_type(self.attempt_id, AttemptId)
        require_reason(self.reason)


@final
@dataclass(frozen=True, slots=True)
class AttemptCancelled:
    """表示执行端确认已取消，不等于调用方结束等待或发出取消请求。

    :param attempt_id: 已确认取消的确切执行尝试。
    """

    attempt_id: AttemptId

    def __post_init__(self) -> None:
        """核对执行尝试身份。

        :raises TypeError: 输入不是具体 AttemptId。
        """
        require_type(self.attempt_id, AttemptId)


# 确认观察只有这些具体变体；查询和等待诊断不加入此联合。
type AttemptObservation = AttemptActive | AttemptSucceeded | AttemptFailed | AttemptCancelled
