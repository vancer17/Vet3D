# 文件信息：L0-05 的重建生成依赖端口。
# 作用：由建模消费方拥有语义匹配、提交、原尝试查询和取消请求接口。
# 边界：不包含存储、LLM 对话、供应商字段、环境 Settings 或通用动作分发。
"""允许替换重建适配器，保持业务动作和执行事实的既有语义。"""

from typing import Protocol

from vet3d.execution import (
    CancellationAcknowledged,
    CancellationUnconfirmed,
    CapabilityUnavailable,
    QueryUnavailable,
    SubmissionUnconfirmed,
)
from vet3d.identity import AttemptId

from .generation import CapabilityUnverified, ReconstructionRequest, ReconstructionUpdate, SubmissionCompatible


class ReconstructionPort(Protocol):
    """限定单次重建请求及原尝试的后续动作，不代表真实供应商能力已验证。"""

    def check(
        self, request: ReconstructionRequest,
    ) -> SubmissionCompatible | CapabilityUnavailable | CapabilityUnverified:
        """无 I/O 地检查具体选图与已知适配规则，不发起生成或环境探测。

        :param request: 包含实际单次选图的重建请求。
        :returns: 已知匹配、已知不匹配或匹配规则未证实的明确结果。
        """
        ...

    async def submit(self, request: ReconstructionRequest) -> ReconstructionUpdate | SubmissionUnconfirmed:
        """提交一次明确的执行尝试，不因回执不明自动再次提交。

        :param request: 已由消费者校验和关联的执行请求。
        :returns: 原尝试的确认观察及产物，或受理尚未确认的诊断。
        """
        ...

    async def query(self, attempt_id: AttemptId) -> ReconstructionUpdate | QueryUnavailable:
        """查询已有尝试，不能创建替代尝试或冒充原任务恢复能力。

        :param attempt_id: 需要查询的原执行尝试身份。
        :returns: 此次取得的确认观察及产物，或未取得可信新观察的诊断。
        """
        ...

    async def cancel(
        self, attempt_id: AttemptId,
    ) -> CancellationAcknowledged | CancellationUnconfirmed | CapabilityUnavailable:
        """向原尝试发送取消请求，不把受理确认解释为执行已停止。

        :param attempt_id: 需要请求取消的原执行尝试身份。
        :returns: 取消请求回执；不支持发送取消时返回能力不可用，不伪造回执。
        """
        ...
