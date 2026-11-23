# 文件信息：L0-01 异步调用边界测试。
# 作用：验证取消、超时、失败传播及单边界日志。
# 范围：替身只证明协程机械协议，不证明子进程或持久任务恢复。
"""使用可控等待点验证本次调用的实际终止结果。"""

import asyncio
import logging
import unittest

from vet3d.application import DemoPort, DemoReply, DemoRequest
from vet3d.bootstrap import (
    InvocationTimeoutError,
    assemble_application,
    invoke_demo,
)


class WaitingPort(DemoPort):
    """可释放、可观察清理结果的异步替身。"""

    def __init__(self) -> None:
        """为每个测试实例创建独立等待与清理信号。"""
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.cleaned = asyncio.Event()

    async def execute(self, request: DemoRequest) -> DemoReply:
        """等待测试控制信号，并在任意退出路径标记清理完成。

        :param request: 应用传入的有效演示请求。
        :returns: 等待正常结束后的演示回执。
        :raises asyncio.CancelledError: 调用方或宿主取消等待。
        """
        self.entered.set()
        try:
            await self.release.wait()
            return DemoReply(text=request.text)
        finally:
            self.cleaned.set()


class FailingPort(DemoPort):
    """抛出固定异常的替身，用于核对错误来源和传播身份。"""

    def __init__(self, failure: Exception) -> None:
        """保存本次测试的异常对象。

        :param failure: 依赖执行时抛出的异常。
        """
        self.failure = failure

    async def execute(self, request: DemoRequest) -> DemoReply:
        """在依赖边界抛出预定异常。

        :param request: 已完成输入校验的请求。
        :raises Exception: 原样抛出测试指定的依赖异常。
        """
        raise self.failure


class TerminalFailureHandler(logging.Handler):
    """允许开始日志，仅在指定终态写入时发生故障的处理器。"""

    def __init__(self, terminal_event: str) -> None:
        """固定日志故障位置，并保留可核对的异常身份。

        :param terminal_event: 本用例预期发生写入故障的终态事件。
        """
        super().__init__()
        self.terminal_event = terminal_event
        self.failure = OSError("终态日志接收端已关闭")
        self.started = False

    def emit(self, record: logging.LogRecord) -> None:
        """接受开始记录，在指定终态暴露实际写入异常。

        :param record: 宿主正在输出的日志记录。
        :raises OSError: 到达本用例指定的终态记录。
        """
        message = record.getMessage()
        if message.startswith("demo_started "):
            self.started = True
        if message.startswith(f"{self.terminal_event} "):
            raise self.failure


class InvocationTests(unittest.IsolatedAsyncioTestCase):
    """核对调用终态，不构造额外状态枚举或持久恢复假象。"""

    async def test_caller_cancellation_cleans_and_propagates(self) -> None:
        """在宿主期限内主动取消，保留取消身份并等待替身清理。"""
        port = WaitingPort()
        service = assemble_application(port=port)
        with self.assertLogs("vet3d", level="INFO"):
            task = asyncio.create_task(
                invoke_demo(service, DemoRequest(text="取消"), timeout_seconds=2.0)
            )
            try:
                await asyncio.wait_for(port.entered.wait(), timeout=1.0)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(port.cleaned.is_set())
                self.assertTrue(task.cancelled())
            finally:
                if not task.done():
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

    async def test_host_deadline_cleans_before_returning_timeout(self) -> None:
        """宿主期限到期后先完成协程清理，再报告宿主超时。"""
        port = WaitingPort()
        with self.assertLogs("vet3d", level="INFO"):
            with self.assertRaises(InvocationTimeoutError):
                await invoke_demo(
                    assemble_application(port=port),
                    DemoRequest(text="超时"),
                    timeout_seconds=0.05,
                )
        self.assertTrue(port.entered.is_set())
        self.assertTrue(port.cleaned.is_set())

    async def test_dependency_timeout_is_not_a_host_deadline(self) -> None:
        """依赖自身的超时异常保持原身份，不被宿主重新分类。"""
        failure = TimeoutError("依赖自身失败")
        service = assemble_application(port=FailingPort(failure))
        with self.assertLogs("vet3d", level="INFO"):
            with self.assertRaises(TimeoutError) as captured:
                await invoke_demo(service, DemoRequest(text="依赖超时"))
        self.assertIs(captured.exception, failure)
        self.assertNotIsInstance(captured.exception, InvocationTimeoutError)

    async def test_unexpected_failure_is_logged_once_and_propagated(self) -> None:
        """非预期异常只在调用处理边界记一次堆栈，并保持原异常。"""
        failure = RuntimeError("受控故障")
        with self.assertLogs("vet3d", level="INFO") as captured_logs:
            with self.assertRaises(RuntimeError) as captured_failure:
                await invoke_demo(
                    assemble_application(port=FailingPort(failure)),
                    DemoRequest(text="故障"),
                )
        self.assertIs(captured_failure.exception, failure)
        errors = [record for record in captured_logs.records if record.levelno >= logging.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertIsNotNone(errors[0].exc_info)

    async def test_invalid_deadline_does_not_start_the_dependency(self) -> None:
        """非法期限在执行前失败，不创建悬挂调用。"""
        for timeout in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                port = WaitingPort()
                with self.assertRaises(ValueError):
                    await invoke_demo(
                        assemble_application(port=port),
                        DemoRequest(text="期限校验"),
                        timeout_seconds=timeout,
                    )
                self.assertFalse(port.entered.is_set())

    async def test_terminal_log_failure_preserves_cancellation_or_timeout(self) -> None:
        """终态日志故障不能覆盖取消或超时，写入异常通过原因链可见。"""
        cases: tuple[tuple[str, type[BaseException]], ...] = (
            ("demo_cancelled", asyncio.CancelledError),
            ("demo_timed_out", InvocationTimeoutError),
        )
        logger = logging.getLogger("vet3d")
        for terminal_event, exception_type in cases:
            with self.subTest(terminal_event=terminal_event):
                port = WaitingPort()
                handler = TerminalFailureHandler(terminal_event)
                previous_handlers = list(logger.handlers)
                previous_level = logger.level
                previous_propagation = logger.propagate
                logger.handlers = [handler]
                logger.setLevel(logging.INFO)
                logger.propagate = False
                task = asyncio.create_task(
                    invoke_demo(
                        assemble_application(port=port),
                        DemoRequest(text="终态与日志故障"),
                        timeout_seconds=2.0 if terminal_event == "demo_cancelled" else 0.05,
                    )
                )
                try:
                    if terminal_event == "demo_cancelled":
                        await asyncio.wait_for(port.entered.wait(), timeout=1.0)
                        task.cancel()
                    with self.assertRaises(exception_type) as captured:
                        await task
                    self.assertIs(captured.exception.__cause__, handler.failure)
                    self.assertTrue(handler.started)
                    self.assertTrue(port.cleaned.is_set())
                    self.assertEqual(task.cancelled(), terminal_event == "demo_cancelled")
                finally:
                    logger.handlers = previous_handlers
                    logger.setLevel(previous_level)
                    logger.propagate = previous_propagation
                    handler.close()
                    if not task.done():
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
