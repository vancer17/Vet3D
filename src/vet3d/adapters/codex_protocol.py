# 文件信息：L2-02 原生会话关联与具体 Codex stdio 连接。
# 作用：以原 TaskIdentity 关联原生线程，以单一读取者处理请求回执及有界通知，保留原生反馈。
# 边界：不是通用执行端口、Agent 循环或执行账本；只管理自己启动的 app-server 连接进程。
"""验证具体 JSONL 接入及身份边界，不接管原生工具与建模决策。"""

import asyncio
from collections import deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Self, cast

from vet3d.identity import TaskIdentity


type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type NativeMessage = dict[str, JsonValue]


class NativeProtocolError(RuntimeError):
    """表示原生协议、关联或连接不满足当前接入约束。"""


class NativeResponseError(NativeProtocolError):
    """保留匹配原请求的服务端错误，不把错误回执当作成功。"""

    def __init__(self, error: JsonValue) -> None:
        """保存原生错误对象，供接入消费者判断具体失败。

        :param error: 服务端实际返回的错误内容。
        """
        super().__init__("app-server 返回请求错误")
        self.error = error


def validate_model_selection(reply: NativeMessage, *, model: str, provider: str | None) -> None:
    """在启动或恢复边界核对原生模型连接，拒绝静默替换。

    :param reply: 原生 thread/start 或 thread/resume 回执。
    :param model: 本次明确请求的模型名称。
    :param provider: 明确请求或原线程实际使用的 provider；为空时只要求返回真实名称。
    :raises NativeProtocolError: 模型、provider 缺失或与请求不符。
    """
    actual_provider = reply.get("modelProvider")
    if reply.get("model") != model or not isinstance(actual_provider, str) or not actual_provider:
        raise NativeProtocolError("原生模型连接缺失或与请求不符，不启动模型轮次")
    if provider is not None and actual_provider != provider:
        raise NativeProtocolError("原生 provider 与请求不符，不启动模型轮次")


def _native_id(value: object) -> str:
    """检查原生标识的基本形状，不转换或解释为业务 UUID。

    :param value: 原响应或事件中的标识。
    :returns: 原字符串。
    :raises NativeProtocolError: 标识不是非空字符串。
    """
    if type(value) is not str or not value:
        raise NativeProtocolError("原生标识必须是非空字符串")
    return value


@dataclass(frozen=True, slots=True)
class NativeSessionBinding:
    """保存已有业务任务到原生线程的唯一关联。

    :param task: 已有业务任务关系，工作区只从该对象取得。
    :param thread_id: 原生运行时返回的线程标识。
    """

    task: TaskIdentity
    thread_id: str

    def __post_init__(self) -> None:
        """拒绝错类任务和空线程，不登记会话或复制工具状态。

        :raises TypeError: 任务不是已有 TaskIdentity。
        :raises NativeProtocolError: 线程标识无效。
        """
        if type(self.task) is not TaskIdentity:
            raise TypeError("关联必须使用原 TaskIdentity")
        _native_id(self.thread_id)

    def validate_thread(self, thread_id: str) -> None:
        """核对启动或恢复回执仍属于原线程。

        :param thread_id: 原生回执给出的线程标识。
        :raises NativeProtocolError: 返回了另一线程。
        """
        if _native_id(thread_id) != self.thread_id:
            raise NativeProtocolError("原生线程与任务关联不匹配")

    def validate_event(self, event: NativeMessage, *, turn_id: str | None = None) -> None:
        """核对通知中实际存在的关联，不从未知通知推导执行成功。

        :param event: 未压缩的原生通知。
        :param turn_id: 消费者正在等待的原轮次；为空时不指定轮次。
        :raises NativeProtocolError: 已提供的线程、轮次或条目标识不匹配或无效。
        """
        if turn_id is not None:
            _native_id(turn_id)
        params = event.get("params")
        if not isinstance(params, dict):
            return
        if "threadId" in params:
            self.validate_thread(_native_id(params["threadId"]))
        thread = params.get("thread")
        if isinstance(thread, dict) and "id" in thread:
            self.validate_thread(_native_id(thread["id"]))
        actual_turns: list[str] = []
        if "turnId" in params:
            actual_turns.append(_native_id(params["turnId"]))
        turn = params.get("turn")
        if isinstance(turn, dict) and "id" in turn:
            actual_turns.append(_native_id(turn["id"]))
        if turn_id is not None and any(value != turn_id for value in actual_turns):
            raise NativeProtocolError(f"原生通知不属于正在等待的轮次：{event.get('method')}，{actual_turns}")
        if "itemId" in params:
            _native_id(params["itemId"])
        item = params.get("item")
        if isinstance(item, dict) and "id" in item:
            _native_id(item["id"])


def _reject_constant(value: str) -> None:
    """拒绝 JSON 标准以外的浮点常量。

    :param value: 解码器遇到的原常量。
    :raises ValueError: 常量不是合法 JSON 值。
    """
    raise ValueError(f"不支持的 JSON 常量：{value}")


class AppServerStdioClient:
    """具体 JSONL 连接，单一读取者交付回执和通知，不分派原生工具。"""

    def __init__(
        self, process: asyncio.subprocess.Process, *, max_line_bytes: int,
        read_timeout_seconds: float, max_pending_events: int = 128,
    ) -> None:
        """保存连接资源及有界接收配置，不读取环境或管理工具进程。

        :param process: 本客户端启动的连接进程，可能是容器 CLI。
        :param max_line_bytes: 原生消息的单行字节上限。
        :param read_timeout_seconds: 单次请求或通知等待期限。
        :param max_pending_events: 尚未被消费者读取的通知上限。
        """
        self._process = process
        self._max_line_bytes = max_line_bytes
        self._timeout = read_timeout_seconds
        self._max_pending_events = max_pending_events
        self._write_lock = asyncio.Lock()
        self._events: deque[NativeMessage] = deque()
        self._event_ready = asyncio.Event()
        self._pending: dict[int, asyncio.Future[NativeMessage]] = {}
        self._next_id = 0
        self._failure: NativeProtocolError | None = None
        self._close_task: asyncio.Task[None] | None = None
        self.initialization: NativeMessage | None = None
        self._reader_task = asyncio.create_task(self._read_messages())

    @classmethod
    async def start(
        cls, argv: tuple[str, ...], *, cwd: Path, env: dict[str, str],
        max_line_bytes: int = 1_048_576, read_timeout_seconds: float = 30.0,
        initialize_params: NativeMessage | None = None,
        max_pending_events: int = 128,
    ) -> Self:
        """启动可信指定的连接进程并完成 initialize／initialized 握手。

        :param argv: 可信装配给出的程序及参数，不经 shell 解释。
        :param cwd: 连接进程工作目录，不代表工具授权目录。
        :param env: 明确允许的环境，不隐式继承宿主凭证。
        :param max_line_bytes: 单行字节上限。
        :param read_timeout_seconds: 单次 RPC 的整体期限，不随通知延长。
        :param initialize_params: 所选版本的握手参数；为空时采用有限宿主信息。
        :param max_pending_events: 通知数量上限，总缓存另受单行限额约束。
        :returns: 完成握手的具体连接。
        :raises ValueError: 启动参数或限额无效。
        :raises NativeProtocolError: 握手失败，已关闭本次连接。
        """
        if not argv or any(type(value) is not str or not value for value in argv):
            raise ValueError("运行时 argv 必须包含非空字符串")
        if type(max_line_bytes) is not int or max_line_bytes <= 0:
            raise ValueError("单行限额必须为正整数")
        if type(max_pending_events) is not int or max_pending_events <= 0:
            raise ValueError("通知限额必须为正整数")
        if (
            type(read_timeout_seconds) not in (float, int)
            or not math.isfinite(read_timeout_seconds) or read_timeout_seconds <= 0
        ):
            raise ValueError("读取期限必须是有限正数")
        process = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, limit=max_line_bytes + 1,
        )
        client = cls(
            process, max_line_bytes=max_line_bytes,
            read_timeout_seconds=read_timeout_seconds, max_pending_events=max_pending_events,
        )
        try:
            client.initialization = await client.request(
                "initialize", initialize_params if initialize_params is not None else {
                    "clientInfo": {"name": "vet3d_native_host", "version": "0.1.0"},
                },
            )
            await client.notify("initialized", {})
            return client
        except BaseException:
            await client.aclose()
            raise

    @property
    def pid(self) -> int:
        """返回本客户端拥有的连接进程编号。

        :returns: 本地连接 PID，不是远端运行时或工具进程编号。
        """
        return self._process.pid

    def _require_usable(self) -> None:
        """拒绝在关闭或原操作结果不明后继续提交。

        :raises NativeProtocolError: 连接失效或已开始关闭。
        """
        if self._failure is not None:
            raise self._failure
        if self._close_task is not None:
            raise NativeProtocolError("连接正在关闭，不能继续提交")

    def _fail(self, error: NativeProtocolError) -> None:
        """传播连接故障，唤醒请求及通知等待者，不推导原生执行终态。

        :param error: 首个连接错误，后续故障不覆盖其原因。
        """
        if self._failure is None:
            self._failure = error
        for future in self._pending.values():
            if not future.done():
                future.set_exception(self._failure)
        self._event_ready.set()

    async def _write(self, message: NativeMessage) -> None:
        """串行写出一条消息，读取通知不占用此锁。

        :param message: 原生请求、通知或服务端交互拒绝。
        :raises NativeProtocolError: 行超限或连接输入已关闭。
        """
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > self._max_line_bytes:
            raise NativeProtocolError("待发送原生消息超过单行限额")
        async with self._write_lock:
            self._require_usable()
            writer = self._process.stdin
            if writer is None or writer.is_closing():
                raise NativeProtocolError("app-server 输入流已关闭")
            writer.write(data)
            await writer.drain()

    async def _read(self) -> NativeMessage:
        """由唯一读取协程取得一个有界 JSON 对象。

        :returns: 保留原字段的原生消息。
        :raises NativeProtocolError: 断连、半行、超限或 JSON 不合法。
        """
        reader = self._process.stdout
        if reader is None:
            raise NativeProtocolError("app-server 输出流不可用")
        try:
            data = await reader.readuntil(b"\n")
        except asyncio.IncompleteReadError as error:
            raise NativeProtocolError("app-server 在完整回执前断开") from error
        except asyncio.LimitOverrunError as error:
            raise NativeProtocolError("原生消息超过单行限额") from error
        if len(data) > self._max_line_bytes:
            raise NativeProtocolError("原生消息超过单行限额")
        try:
            value: object = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, UnicodeError) as error:
            raise NativeProtocolError("原生消息不是有效 UTF-8 JSON") from error
        if not isinstance(value, dict):
            raise NativeProtocolError("原生消息必须是 JSON 对象")
        return cast(NativeMessage, value)

    async def _receive_notification(self, message: NativeMessage) -> None:
        """交付原生通知或明确拒绝未支持的服务端交互。

        :param message: 带原生方法的消息，不改写为业务回执。
        :raises NativeProtocolError: 交互未支持、通知非法或接收缓冲已满。
        """
        method = message.get("method")
        if type(method) is not str or not method:
            raise NativeProtocolError("原生通知缺少方法")
        if "id" in message:
            async with asyncio.timeout(self._timeout):
                await self._write({
                    "id": message["id"],
                    "error": {"code": -32601, "message": "Vet3D 有限宿主未支持此服务端交互请求"},
                })
            raise NativeProtocolError(f"未支持的服务端交互请求：{method}")
        if len(self._events) >= self._max_pending_events:
            raise NativeProtocolError("原生通知超过有界缓冲，观察已不完整")
        self._events.append(message)
        self._event_ready.set()

    def _receive_response(self, message: NativeMessage) -> None:
        """按唯一请求号交付原回执，不重发或镜像执行状态。

        :param message: 原生成功或错误回执。
        :raises NativeProtocolError: 请求号不存在、重复回执或结果结构无效。
        """
        request_id = message.get("id")
        if type(request_id) is not int:
            raise NativeProtocolError("原生回执缺少有效请求 ID")
        future = self._pending.get(request_id)
        if future is None or future.done():
            raise NativeProtocolError("原生回执 ID 不属于当前在途请求")
        if "error" in message:
            if "result" in message:
                raise NativeProtocolError("原生回执同时包含结果和错误")
            future.set_exception(NativeResponseError(message["error"]))
            return
        result = message.get("result")
        if not isinstance(result, dict):
            raise NativeProtocolError("原生回执缺少结果对象")
        future.set_result(result)

    async def _read_messages(self) -> None:
        """独占读取连接并分派机械回执，失败只使连接失效。"""
        try:
            while self._failure is None:
                message = await self._read()
                if "method" in message:
                    await self._receive_notification(message)
                else:
                    self._receive_response(message)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            failure = error if isinstance(error, NativeProtocolError) else NativeProtocolError(str(error))
            self._fail(failure)

    async def request(self, method: str, params: NativeMessage) -> NativeMessage:
        """发送一次有期限请求，等待回执期间仍允许通知及取消请求。

        :param method: 所选协议的方法，不是业务动作注册。
        :param params: 原生参数，不转换成执行快照。
        :returns: 按原请求号取得的结果对象。
        :raises NativeResponseError: 原生服务明确拒绝本次请求，连接可继续使用。
        :raises NativeProtocolError: 连接故障、回执错误或在途请求超过固定限额。
        :raises TimeoutError: 整体请求超时，结果不明且不会重发。
        """
        self._require_usable()
        if len(self._pending) >= 32:
            raise NativeProtocolError("本连接最多允许 32 个在途协议请求")
        request_id = self._next_id
        self._next_id += 1
        future: asyncio.Future[NativeMessage] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with asyncio.timeout(self._timeout):
                await self._write({"id": request_id, "method": method, "params": params})
                return await future
        except NativeResponseError:
            raise
        except BaseException as error:
            self._fail(NativeProtocolError("原请求结果不明，连接不能继续提交"))
            if isinstance(error, (BrokenPipeError, ConnectionError)):
                raise NativeProtocolError("原生请求写入失败，不能重新提交") from error
            raise
        finally:
            self._pending.pop(request_id, None)
            if future.done() and not future.cancelled():
                future.exception()
            else:
                future.cancel()

    async def notify(self, method: str, params: NativeMessage) -> None:
        """发送一次原生通知，不等待伪回执或重试写入。

        :param method: 原生通知名称。
        :param params: 原通知参数。
        :raises NativeProtocolError: 连接已不可用或写入失败。
        :raises TimeoutError: 通知未在固定期限内写出。
        """
        self._require_usable()
        try:
            async with asyncio.timeout(self._timeout):
                await self._write({"method": method, "params": params})
        except BaseException:
            self._fail(NativeProtocolError("通知交接失败，连接不能继续提交"))
            raise

    async def next_event(self) -> NativeMessage:
        """等待原通知，不持有写锁，取消等待不取消原生轮次。

        :returns: 已完整接收的原通知，包括故障前已入队的事实和尚未识别的字段。
        :raises NativeProtocolError: 已接收通知耗尽后，观察因断连、超限或关闭而失效。
        :raises TimeoutError: 等待期限内没有通知，连接仍可使用。
        """
        async with asyncio.timeout(self._timeout):
            while True:
                if self._events:
                    event = self._events.popleft()
                    if not self._events:
                        self._event_ready.clear()
                    return event
                self._require_usable()
                self._event_ready.clear()
                await self._event_ready.wait()

    async def _discard_output(self) -> None:
        """原读取者已退出后排空关闭输出，不累积或解析工具内容。"""
        reader = self._process.stdout
        if reader is not None:
            while await reader.read(65536):
                pass

    async def _close(self) -> None:
        """关闭本连接并回收自身连接进程，不声明远端工具已停止。

        :raises TimeoutError: 自身进程或输出未在关闭宽限内排空。
        """
        self._fail(NativeProtocolError("连接已关闭，不能继续提交"))
        self._reader_task.cancel()
        try:
            await self._reader_task
        except asyncio.CancelledError:
            pass
        writer = self._process.stdin
        if writer is not None:
            writer.close()
        drain = asyncio.create_task(self._discard_output())
        try:
            try:
                await asyncio.wait_for(self._process.wait(), 2.0)
            except TimeoutError:
                if self._process.returncode is None:
                    self._process.kill()
                await asyncio.wait_for(self._process.wait(), 2.0)
            await asyncio.wait_for(drain, 2.0)
        finally:
            if not drain.done():
                drain.cancel()
            try:
                await drain
            except asyncio.CancelledError:
                pass

    async def aclose(self) -> None:
        """由单一关闭任务排空自身资源，调用方取消等待不撤销实际关闭。

        :raises TimeoutError: 本连接进程或输出未确认排空。
        """
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)
