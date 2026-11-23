# 文件信息：L0-05 取消命令的受理确认与回执不明契约。
# 作用：关联原执行尝试，分开取消请求受理与执行端实际取消终态。
# 边界：不发送取消、不终止执行、不创建新尝试或自动重交许可。
"""保留取消命令的回执事实，不改写已有可信执行观察。"""

from dataclasses import dataclass
from typing import final

from vet3d.identity import AttemptId

from ._checks import require_reason, require_type


@final
@dataclass(frozen=True, slots=True)
class CancellationAcknowledged:
    """表示执行端已确认受理取消请求，不表示尝试已经停止。

    :param attempt_id: 取消请求所针对的原执行尝试。
    :param reason: 实际取得的非空白受理说明，不用于推导执行终态。
    """

    attempt_id: AttemptId
    reason: str

    def __post_init__(self) -> None:
        """核对原尝试身份和取消受理说明。

        :raises TypeError: 身份或说明不是规定的具体类型。
        :raises ExecutionContractError: 说明为空白或无法编码为 UTF-8。
        """
        require_type(self.attempt_id, AttemptId)
        require_reason(self.reason)


@final
@dataclass(frozen=True, slots=True)
class CancellationUnconfirmed:
    """表示取消请求尚未取得受理确认，不声明拒绝、失败或已取消。

    :param attempt_id: 发起取消请求时关联的原执行尝试。
    :param reason: 受理回执不明的非空白诊断。
    """

    attempt_id: AttemptId
    reason: str

    def __post_init__(self) -> None:
        """核对原尝试身份和取消回执不明的诊断。

        :raises TypeError: 身份或诊断不是规定的具体类型。
        :raises ExecutionContractError: 诊断为空白或无法编码为 UTF-8。
        """
        require_type(self.attempt_id, AttemptId)
        require_reason(self.reason)


# 取消命令回执只有这两种变体，不加入已确认执行观察的联合。
type CancellationReceipt = CancellationAcknowledged | CancellationUnconfirmed
