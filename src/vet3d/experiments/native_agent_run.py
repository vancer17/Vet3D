# 文件信息：L2-02 阶段 A 的一次原生轮次实验消费者。
# 作用：提交目标、核对原生关联并等待原生终态；不解释工具错误或生成补救提示。
# 边界：调用方先落实任务环境隔离；超时仅请求原生中断，不证明工具或子进程停止。
"""以具体原生协议执行一轮实验，保留模型与工具循环的决策权。"""

import asyncio
from collections import Counter
from dataclasses import dataclass
import math

from vet3d.adapters import (
    AppServerStdioClient, NativeMessage, NativeProtocolError, NativeSessionBinding,
)


@dataclass(frozen=True, slots=True)
class TurnObservation:
    """保留原生终态和有限事件计数，不代替原生历史或业务验收。

    :param turn: 原生 turn/completed 提供的轮次对象。
    :param event_counts: 本消费者实际收到的通知数量，仅用于实验诊断。
    :param interruption_requested: 本消费者是否因本次等待期限请求原生中断。
    """

    turn: NativeMessage
    event_counts: dict[str, int]
    interruption_requested: bool


async def run_native_turn(
    client: AppServerStdioClient, binding: NativeSessionBinding, goal: str, *,
    skill_path: str | None = None, image_path: str | None = None,
    environments: list[NativeMessage] | None = None,
    timeout_seconds: float = 600.0,
) -> TurnObservation:
    """提交一个目标并等待同一原生轮次，不自行追加修复指令。

    :param client: 已握手且已绑定授权环境的具体实验连接。
    :param binding: 当前任务与原生线程的关联。
    :param goal: 用户目标或明确业务反馈，由调用方提供。
    :param skill_path: 可选的执行环境原生 Skill 路径。
    :param image_path: 可选的执行环境图片路径，交给原生输入机制读取。
    :param environments: 恢复后的首轮显式重绑原生任务环境；为空时沿原线程当前选择，不推导恢复成功。
    :param timeout_seconds: 本次实验等待期限，超时向原轮次请求中断。
    :returns: 实际收到的原生轮次终态及有限诊断。
    :raises ValueError: 显式环境列表为空，拒绝提交模型轮次。
    :raises NativeProtocolError: 关联、回执或终态不完整；不得据此重交任务。
    :raises TimeoutError: 请求中断后仍未在宽限内取得终态，实际运行状态未知。
    """
    if (
        not goal.strip() or type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
    ):
        raise ValueError("实验目标不能为空，等待期限必须为正数")
    inputs: list[NativeMessage] = [{"type": "text", "text": goal}]
    if skill_path is not None:
        inputs.append({"type": "skill", "name": "vet3d-stage-a", "path": skill_path})
    if image_path is not None:
        inputs.append({"type": "localImage", "path": image_path})
    start_params: NativeMessage = {
        "threadId": binding.thread_id, "input": list(inputs),
        "sandboxPolicy": {"type": "externalSandbox", "networkAccess": "restricted"},
    }
    if environments is not None:
        if not environments:
            raise ValueError("恢复实验不能将空环境列表解释为任务授权")
        start_params["environments"] = list(environments)
    reply = await client.request("turn/start", start_params)
    turn = reply.get("turn")
    if not isinstance(turn, dict) or not isinstance(turn.get("id"), str) or not turn["id"]:
        raise NativeProtocolError("启动回执没有实际轮次，不能重新提交")
    turn_id = turn["id"]
    assert isinstance(turn_id, str)
    counts: Counter[str] = Counter()
    interrupted = False
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            if interrupted:
                raise TimeoutError("原生中断后未取得终态，执行状态仍不确定")
            await client.request("turn/interrupt", {
                "threadId": binding.thread_id, "turnId": turn_id,
            })
            interrupted = True
            deadline = asyncio.get_running_loop().time() + 15.0
            continue
        try:
            event = await asyncio.wait_for(client.next_event(), remaining)
        except TimeoutError:
            continue
        binding.validate_event(event)
        method = event.get("method")
        if not isinstance(method, str):
            raise NativeProtocolError("原生通知没有方法名")
        # 线程用量等通知可以引用此前轮次；只有当前执行通知参与本轮关联校验。
        if method in ("turn/started", "turn/completed") or method.startswith("item/"):
            binding.validate_event(event, turn_id=turn_id)
        counts[method] += 1
        if method != "turn/completed":
            continue
        params = event.get("params")
        if not isinstance(params, dict) or params.get("threadId") != binding.thread_id:
            raise NativeProtocolError("终态缺少原线程身份")
        completed = params.get("turn")
        if not isinstance(completed, dict) or completed.get("id") != turn_id:
            raise NativeProtocolError("终态缺少原轮次身份")
        if completed.get("status") not in ("completed", "interrupted", "failed"):
            raise NativeProtocolError("没有取得本版本的原生轮次终态")
        return TurnObservation(completed, dict(counts), interrupted)
