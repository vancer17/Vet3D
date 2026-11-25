# 文件信息：L2-02 阶段 A 的原生会话关联与 stdio 实验客户端。
# 作用：以原 TaskIdentity 关联原生线程，串行发送请求并交回未经业务摘要的原生通知。
# 边界：不是产品端口、Agent 循环或执行账本；只管理自己启动的 app-server 连接进程。
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
    """表示原生协议、关联或连接已不能继续用于本实验。"""


class NativeResponseError(NativeProtocolError):
    """保留匹配原请求的服务端错误，不把错误回执当作成功。"""

    def __init__(self, error: JsonValue) -> None:
        """保存原生错误对象，供实验调用方判断具体失败。

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
    """保存本实验任务到原生线程的唯一关联。

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
            raise TypeError("实验关联必须使用原 TaskIdentity")
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
    """阶段 A 专用的串行 JSONL 连接，不分派工具或保存工具历史。"""

    def __init__(
        self, process: asyncio.subprocess.Process, *, max_line_bytes: int,
        read_timeout_seconds: float,
    ) -> None:
        """保存本客户端拥有的连接和实例读取限额。

        :param process: 本客户端启动的连接进程，可能是容器 CLI 而非运行时本身。
        :param max_line_bytes: 单行包含换行符的最大字节数。
        :param read_timeout_seconds: 一次请求或通知等待的整体期限。
        """
        self._process = process
        self._max_line_bytes = max_line_bytes
        self._timeout = read_timeout_seconds
        self._lock = asyncio.Lock()
        self._events: deque[NativeMessage] = deque()
        self._next_id = 0
        self._usable = True
        self._closed = False
        self.initialization: NativeMessage | None = None

    @classmethod
    async def start(
        cls, argv: tuple[str, ...], *, cwd: Path, env: dict[str, str],
        max_line_bytes: int = 1_048_576, read_timeout_seconds: float = 30.0,
        initialize_params: NativeMessage | None = None,
    ) -> Self:
        """启动可信指定的运行时并完成 initialize／initialized 握手。

        :param argv: 可信装配给出的程序与参数，不通过 shell 解释。
        :param cwd: 此运行时连接的实际工作目录。
        :param env: 可信装配明确允许的进程环境；不会隐式复制宿主环境。
        :param max_line_bytes: 单行字节上限，图片事件由调用方配置足够空间。
        :param read_timeout_seconds: 每次请求的总等待期限，不随通知续期。
        :param initialize_params: 所选版本要求的握手字段；为空时使用实验客户端信息。
        :returns: 已完成握手的具体客户端。
        :raises ValueError: 参数为空或限额非法。
        :raises NativeProtocolError: 握手或连接失败；清理本客户端的进程后传播。
        """
        if not argv or any(type(value) is not str or not value for value in argv):
            raise ValueError("运行时 argv 必须包含非空字符串")
        if type(max_line_bytes) is not int or max_line_bytes <= 0:
            raise ValueError("单行限额必须为正整数")
        if (
            type(read_timeout_seconds) not in (float, int)
            or not math.isfinite(read_timeout_seconds) or read_timeout_seconds <= 0
        ):
            raise ValueError("读取期限必须是有限正数")
        process = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, limit=max_line_bytes + 1,
        )
        client = cls(process, max_line_bytes=max_line_bytes, read_timeout_seconds=read_timeout_seconds)
        try:
            client.initialization = await client.request(
                "initialize", initialize_params if initialize_params is not None else {
                    "clientInfo": {"name": "vet3d_stage_a", "version": "0.1.0"},
                },
            )
            await client.notify("initialized", {})
            return client
        except BaseException:
            await client.aclose()
            raise

    @property
    def pid(self) -> int:
        """返回本客户端启动的进程编号，供实验核对连接生命周期。

        :returns: 本地连接进程的编号，不代表容器内运行时或工具子进程。
        """
        return self._process.pid

    def _require_usable(self) -> None:
        """拒绝在请求结果不明或已关闭的连接上继续提交。

        :raises NativeProtocolError: 原连接不再可用。
        """
        if not self._usable or self._closed:
            raise NativeProtocolError("连接已关闭或原请求结果不明，不能继续提交")

    async def _write(self, message: NativeMessage) -> None:
        """向原生连接写入一行，不重试失败或重发请求。

        :param message: 原生请求、通知或明确错误回包。
        :raises NativeProtocolError: 输入流不可用或序列化行超过限额。
        """
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > self._max_line_bytes:
            raise NativeProtocolError("待发送原生消息超过单行限额")
        writer = self._process.stdin
        if writer is None or writer.is_closing():
            raise NativeProtocolError("app-server 输入流已关闭")
        writer.write(data)
        await writer.drain()

    async def _read(self) -> NativeMessage:
        """读取一个有界 JSON 对象，保留原生字段与反馈内容。

        :returns: 原生 JSON 对象。
        :raises NativeProtocolError: 断连、半行、超长或不是合法 JSON 对象。
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

    async def _notification(self, message: NativeMessage) -> NativeMessage:
        """确认通知或明确拒绝本实验未实现的服务端交互。

        :param message: 带原生方法的消息。
        :returns: 未改写的通知。
        :raises NativeProtocolError: 服务端请求交互，或通知缺少合法方法。
        """
        method = message.get("method")
        if type(method) is not str or not method:
            raise NativeProtocolError("原生通知缺少方法")
        if "id" in message:
            await self._write({
                "id": message["id"],
                "error": {"code": -32601, "message": "Vet3D 阶段 A 未支持此服务端交互请求"},
            })
            raise NativeProtocolError(f"未支持的服务端交互请求：{method}")
        return message

    async def request(self, method: str, params: NativeMessage) -> NativeMessage:
        """串行提交一次请求，在固定期限内消费其原生回执。

        :param method: 所选运行时协议的方法名。
        :param params: 原生参数，不转换为业务执行请求。
        :returns: 对应请求的原生结果对象。
        :raises NativeResponseError: 服务端给出与请求匹配的错误。
        :raises NativeProtocolError: 错回执、通知队列超限或不支持的交互。
        :raises TimeoutError: 请求整体超时；该连接不再接受新请求。
        """
        async with self._lock:
            self._require_usable()
            request_id = self._next_id
            self._next_id += 1
            try:
                async with asyncio.timeout(self._timeout):
                    await self._write({"id": request_id, "method": method, "params": params})
                    while True:
                        message = await self._read()
                        if "method" in message:
                            event = await self._notification(message)
                            if len(self._events) >= 128:
                                raise NativeProtocolError("等待回执期间的原生通知超过 128 条")
                            self._events.append(event)
                            continue
                        if type(message.get("id")) is not int or message["id"] != request_id:
                            raise NativeProtocolError("原生回执 ID 与唯一在途请求不匹配")
                        if "error" in message:
                            raise NativeResponseError(message["error"])
                        result = message.get("result")
                        if not isinstance(result, dict):
                            raise NativeProtocolError("原生回执缺少结果对象")
                        return result
            except NativeResponseError:
                raise
            except BaseException:
                self._usable = False
                raise

    async def notify(self, method: str, params: NativeMessage) -> None:
        """发送一次原生通知，不生成业务调用或等待伪回执。

        :param method: 所选协议的通知名。
        :param params: 原生通知参数。
        :raises NativeProtocolError: 原连接不可用。
        :raises TimeoutError: 通知写入超过期限。
        """
        async with self._lock:
            self._require_usable()
            try:
                async with asyncio.timeout(self._timeout):
                    await self._write({"method": method, "params": params})
            except BaseException:
                self._usable = False
                raise

    async def next_event(self) -> NativeMessage:
        """取得原生通知；空等超时不伪造终态，也不重新提交任务。

        :returns: 原始通知对象，未知通知也原样交回消费者。
        :raises NativeProtocolError: 断连、非法消息或服务端交互请求。
        :raises TimeoutError: 本次等待没有在期限内取得通知。
        """
        async with self._lock:
            self._require_usable()
            if self._events:
                return self._events.popleft()
            try:
                async with asyncio.timeout(self._timeout):
                    return await self._notification(await self._read())
            except (TimeoutError, asyncio.CancelledError):
                raise
            except BaseException:
                self._usable = False
                raise

    async def _discard_output(self) -> None:
        """关闭时排空连接输出，不累积或解释工具内容。"""
        reader = self._process.stdout
        if reader is not None:
            while await reader.read(65536):
                pass

    async def aclose(self) -> None:
        """关闭本连接并回收自己启动的连接进程，不声称运行时或工具已停止。

        :raises TimeoutError: 连接进程在有限关闭及强制终止后仍未排空。
        """
        async with self._lock:
            if self._closed:
                return
            self._usable = False
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
                self._closed = True
            finally:
                if not drain.done():
                    drain.cancel()
                    try:
                        await drain
                    except asyncio.CancelledError:
                        pass
