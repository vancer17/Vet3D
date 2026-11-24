# 文件信息：L0-01 单次协程调用的宿主边界。
# 负责期限、关联日志和取消传播；没有重试、后台作业、持久记录或重启恢复。
"""管理一次演示调用的宿主生命周期。"""

import asyncio
from collections.abc import Mapping
import logging
import math
from uuid import uuid4

from vet3d.application import (
    DemoReply, DemoRequest, DemoService, InvalidDemoReply, InvalidDemoRequest,
)

_LOGGER = logging.getLogger("vet3d")


class InvocationTimeoutError(TimeoutError):
    """仅表示本调用的宿主期限实际到期，不代表依赖自身的超时错误。"""


def _record_termination(
    error: BaseException,
    level: int,
    event: str,
    call_id: str,
    *,
    with_traceback: bool = False,
    context: Mapping[str, str] | None = None,
) -> None:
    """记录异常终态，日志故障作为原因附加而不替换原终态。

    :param error: 调用方仍必须观察到的原异常或宿主超时。
    :param level: 本事件的日志严重程度。
    :param event: 不含请求内容的固定事件名称。
    :param call_id: 宿主本次调用的关联串。
    :param with_traceback: 非预期异常是否在本边界记录一次堆栈。
    :param context: 生产者已知身份的单向诊断投影，不用于业务决策。
    :raises BaseException: 日志失败时重新抛出原终态，并保留日志故障原因链。
    """
    try:
        _LOGGER.log(
            level, "%s call_id=%s reason=%s", event, call_id, type(error).__name__,
            exc_info=error if with_traceback else None,
            extra=context,
        )
    except Exception as logging_error:
        error.add_note("本次终态日志写入失败；日志故障保留在异常原因链中。")
        raise error from logging_error


async def invoke_demo(
    service: DemoService,
    request: DemoRequest,
    *,
    timeout_seconds: float = 5.0,
) -> DemoReply:
    """执行有期限、零重试的调用，并在边界记录一次终止原因。

    :param service: 装配完成的稳定应用服务。
    :param request: 交给应用校验的单次输入。
    :param timeout_seconds: 宿主给本次调用的正有限秒数，不进入业务输入。
    :returns: 应用核对过的演示回包。
    :raises ValueError: 宿主期限不为正有限值。
    :raises InvocationTimeoutError: 本次宿主期限实际到期。
    :raises asyncio.CancelledError: 调用方取消，清理后继续向上传播。
    :raises InvalidDemoRequest: 应用拒绝输入。
    :raises InvalidDemoReply: 应用拒绝依赖回包。
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("调用期限必须为正有限秒数")
    call_id = uuid4().hex
    deadline = asyncio.timeout(timeout_seconds)
    _LOGGER.info("demo_started call_id=%s", call_id)
    try:
        async with deadline:
            reply = await service.execute(request)
        # 协作式适配器必须继续传播取消；即使它吞掉取消，也不能发布超期成功。
        if deadline.expired():
            raise InvocationTimeoutError("演示调用超过宿主期限")
    except asyncio.CancelledError as error:
        _record_termination(error, logging.INFO, "demo_cancelled", call_id)
        raise
    except (InvalidDemoRequest, InvalidDemoReply) as error:
        _record_termination(error, logging.WARNING, "demo_rejected", call_id)
        raise
    except TimeoutError as error:
        if deadline.expired():
            timeout = InvocationTimeoutError("演示调用超过宿主期限")
            _record_termination(timeout, logging.WARNING, "demo_timed_out", call_id)
            raise timeout from None
        _record_termination(error, logging.ERROR, "demo_failed", call_id, with_traceback=True)
        raise
    except Exception as error:
        _record_termination(error, logging.ERROR, "demo_failed", call_id, with_traceback=True)
        raise
    _LOGGER.info("demo_completed call_id=%s", call_id)
    return reply
