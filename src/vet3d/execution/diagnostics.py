# 文件信息：L0-04 查询、提交和等待诊断，以及执行前的明确拒绝。
# 边界：诊断不改写可信执行观察；执行前拒绝不为尚未执行的动作补造尝试身份。
"""分别表达未取得观察、受理不明和本地等待结束。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import final

from vet3d.identity import AttemptId

from ._checks import require_reason, require_type


@final
@dataclass(frozen=True, slots=True)
class QueryUnavailable:
    """表示本次查询未能取得可信观察，不表示尝试执行失败。

    :param attempt_id: 本次查询所针对的原执行尝试。
    :param reason: 未取得观察的非空白诊断。
    """

    attempt_id: AttemptId
    reason: str

    def __post_init__(self) -> None:
        """核对查询关联和诊断文本。

        :raises TypeError: 身份或原因类型错误。
        :raises ExecutionContractError: 原因空白或无法编码为 UTF-8。
        """
        require_type(self.attempt_id, AttemptId)
        require_reason(self.reason)


@final
@dataclass(frozen=True, slots=True)
class SubmissionUnconfirmed:
    """表示已尝试提交但未确认受理，不创建活动或失败观察。

    :param attempt_id: 发起提交时使用的原执行尝试。
    :param reason: 提交回执不明的非空白诊断。
    """

    attempt_id: AttemptId
    reason: str

    def __post_init__(self) -> None:
        """核对提交关联和诊断文本。

        :raises TypeError: 身份或原因类型错误。
        :raises ExecutionContractError: 原因空白或无法编码为 UTF-8。
        """
        require_type(self.attempt_id, AttemptId)
        require_reason(self.reason)


class WaitEndReason(StrEnum):
    """表示等待结束的原因，不是执行状态或重新提交许可。"""

    # 调用方的等待期限已到，不推断执行端是否停止。
    DEADLINE = "deadline"
    # 调用方已请求取消并结束等待，不等于执行端已确认取消。
    CANCEL_REQUESTED = "cancel_requested"


@final
@dataclass(frozen=True, slots=True)
class WaitEnded:
    """记录等待因期限或取消请求结束，不宣称执行端已经终止。

    :param attempt_id: 本次等待所针对的原执行尝试。
    :param reason: 等待结束的唯一分类，不复制为执行终态。
    """

    attempt_id: AttemptId
    reason: WaitEndReason

    def __post_init__(self) -> None:
        """核对等待关联和结束原因。

        :raises TypeError: 身份或原因不是规定的具体类型。
        """
        require_type(self.attempt_id, AttemptId)
        require_type(self.reason, WaitEndReason)


@final
@dataclass(frozen=True, slots=True)
class CapabilityUnavailable:
    """表示执行前缺少必要能力，不声明某个尝试已经失败。

    只表达本次执行前无法满足能力要求，不创建能力配置或推导协议，
    也不承诺永久不支持或自动重试。面向 BFF 的具体投影留待适配层。

    :param reason: 当前缺少能力的非空白说明。
    """

    reason: str

    def __post_init__(self) -> None:
        """核对执行前拒绝说明。

        :raises TypeError: 原因不是字符串。
        :raises ExecutionContractError: 原因空白或无法编码为 UTF-8。
        """
        require_reason(self.reason)


@final
@dataclass(frozen=True, slots=True)
class InputInsufficient:
    """表示执行前所需输入不足，不补造作业或尝试。

    :param reason: 缺少输入的非空白说明。
    """

    reason: str

    def __post_init__(self) -> None:
        """核对执行前拒绝说明。

        :raises TypeError: 原因不是字符串。
        :raises ExecutionContractError: 原因空白或无法编码为 UTF-8。
        """
        require_reason(self.reason)
