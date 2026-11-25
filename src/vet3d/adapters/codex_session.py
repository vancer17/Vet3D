# 文件信息：L2-02 阶段 B 的具体 Codex 原生会话消费者。
# 作用：关联已有任务与原生线程，交付通知、继续和取消，不决定建模步骤。
# 边界：装配方负责环境授权和最终回收；原生终态不等于进程停止或业务验收。
"""在已授权任务环境中消费原生会话，不复制模型与工具循环。"""

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
import math
from pathlib import PurePosixPath
from typing import Self

from vet3d.identity import TaskIdentity

from .codex_protocol import (
    AppServerStdioClient, NativeMessage, NativeProtocolError, NativeSessionBinding,
    validate_model_selection,
)


def _positive(value: float, name: str) -> None:
    """检查具体连接等待期限，不将期限解释为业务资格。

    :param value: 装配给出的秒数。
    :param name: 诊断中的参数名。
    :raises ValueError: 期限不是有限正数。
    """
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} 必须为有限正数")


class CodexAgentSession:
    """承载一个任务的具体原生关联，支持一个在途轮次及独立取消请求。

    实例只保存当前协议操作所需关联，不持久化历史或建立工具状态机。
    环境注册、权限及实际文件边界由可信装配负责，知道线程标识不构成授权。
    """

    def __init__(
        self, client: AppServerStdioClient, binding: NativeSessionBinding, *,
        environment_id: str, cwd: str, turn_timeout_seconds: float,
        interrupt_grace_seconds: float,
    ) -> None:
        """保存已核对的关联和实例限制，构造本身不提交模型任务。

        :param client: 已握手并登记授权环境的连接。
        :param binding: 原任务与原生线程的唯一关联。
        :param environment_id: 本实例获准使用的远端环境标识。
        :param cwd: 该环境内的绝对任务目录。
        :param turn_timeout_seconds: 从提交轮次开始计算的总等待期限。
        :param interrupt_grace_seconds: 请求中断及等待终态共用的宽限。
        """
        self._client = client
        self._binding = binding
        self._environment_id = environment_id
        self._cwd = cwd
        self._timeout = turn_timeout_seconds
        self._grace = interrupt_grace_seconds
        self._closing: asyncio.Task[None] | None = None
        self._uncertain = False
        self._turn_id: str | None = None
        self._cancel_requested = asyncio.Event()
        self._accepted = asyncio.Event()
        self._finished = asyncio.Event()
        self._finished.set()
        self._interrupt_task: asyncio.Task[None] | None = None
        self._interrupt_deadline: float | None = None
        self._run_task: asyncio.Task[object] | None = None
        self._last_terminal: NativeMessage | None = None

    @staticmethod
    def _validate_options(
        environment_id: str, cwd: str, model: str, provider: str,
        turn_timeout_seconds: float, interrupt_grace_seconds: float,
    ) -> None:
        """在创建线程前核对受信装配的显式参数。

        :param environment_id: 原生远端环境标识，不接受控制侧 local。
        :param cwd: 远端任务目录。
        :param model: 明确选定的模型。
        :param provider: 明确选定的原生 provider。
        :param turn_timeout_seconds: 轮次等待限制。
        :param interrupt_grace_seconds: 中断宽限。
        :raises ValueError: 参数缺失、目录不明确或期限无效。
        """
        if any(type(value) is not str or not value.strip() for value in (environment_id, cwd, model, provider)):
            raise ValueError("原生环境、目录、模型与 provider 必须明确")
        if environment_id == "local":
            raise ValueError("有限任务会话不授权控制侧 local 环境")
        path = PurePosixPath(cwd)
        if not path.is_absolute() or ".." in path.parts or str(path) != cwd or cwd == "/" or "\x00" in cwd:
            raise ValueError("任务目录必须为规范的远端绝对路径且不能是根目录")
        _positive(turn_timeout_seconds, "轮次期限")
        _positive(interrupt_grace_seconds, "中断宽限")

    @classmethod
    async def open(
        cls, client: AppServerStdioClient, task: TaskIdentity, *,
        environment_id: str, cwd: str, model: str, provider: str,
        turn_timeout_seconds: float = 600.0, interrupt_grace_seconds: float = 15.0,
    ) -> Self:
        """创建原生线程，核对实际模型及未授权扩展后交给可信宿主。

        :param client: 已握手并登记环境的连接，失败由装配方关闭。
        :param task: 已有任务身份及其工作区归属，不自行登记或生成身份。
        :param environment_id: 明确授权的远端环境。
        :param cwd: 环境内可变任务目录。
        :param model: 请求模型，禁止静默 fallback。
        :param provider: 请求的原生 provider。
        :param turn_timeout_seconds: 每轮总等待期限。
        :param interrupt_grace_seconds: 中断后的有限宽限。
        :returns: 保有原关联的具体会话。
        :raises NativeProtocolError: 回执、关联或工具授权不符，不重新创建线程。
        """
        cls._validate_options(environment_id, cwd, model, provider, turn_timeout_seconds, interrupt_grace_seconds)
        if type(task) is not TaskIdentity:
            raise TypeError("会话必须使用原 TaskIdentity")
        reply = await client.request("thread/start", {
            "model": model, "modelProvider": provider, "approvalPolicy": "never",
            "cwd": cwd, "environments": [{"environmentId": environment_id, "cwd": cwd,
                                           "runtimeWorkspaceRoots": [cwd]}],
            "ephemeral": False, "allowProviderModelFallback": False,
        })
        validate_model_selection(reply, model=model, provider=provider)
        thread = reply.get("thread")
        if not isinstance(thread, dict) or type(thread.get("id")) is not str or not thread["id"]:
            raise NativeProtocolError("原生线程受理缺少身份，不得重新提交")
        thread_id = thread["id"]
        assert isinstance(thread_id, str)
        session = cls(client, NativeSessionBinding(task, thread_id), environment_id=environment_id,
                      cwd=cwd, turn_timeout_seconds=turn_timeout_seconds,
                      interrupt_grace_seconds=interrupt_grace_seconds)
        await session._check_extensions()
        return session

    @classmethod
    async def resume(
        cls, client: AppServerStdioClient, binding: NativeSessionBinding, *,
        environment_id: str, cwd: str, model: str, provider: str,
        turn_timeout_seconds: float = 600.0, interrupt_grace_seconds: float = 15.0,
    ) -> Self:
        """沿可信原关联恢复；装配方须先确认原环境与工作文件仍存在。

        :param client: 重新握手并登记原环境的连接。
        :param binding: 仍由可信调用方持有的原任务关联，不能由外部线程号代替。
        :param environment_id: 原授权环境。
        :param cwd: 原环境中的任务目录。
        :param model: 原模型设置。
        :param provider: 原 provider 设置。
        :param turn_timeout_seconds: 恢复后每轮等待期限。
        :param interrupt_grace_seconds: 中断宽限。
        :returns: 指向同一原生线程的新连接消费者。
        :raises NativeProtocolError: 未恢复原线程或模型／扩展不符，不以新线程替代。
        """
        cls._validate_options(environment_id, cwd, model, provider, turn_timeout_seconds, interrupt_grace_seconds)
        if type(binding) is not NativeSessionBinding:
            raise TypeError("恢复必须使用可信原会话关联")
        reply = await client.request("thread/resume", {
            "threadId": binding.thread_id, "excludeTurns": True,
            "model": model, "modelProvider": provider,
        })
        validate_model_selection(reply, model=model, provider=provider)
        thread = reply.get("thread")
        if not isinstance(thread, dict) or thread.get("id") != binding.thread_id:
            raise NativeProtocolError("恢复回执不是原线程，不创建替代会话")
        session = cls(client, binding, environment_id=environment_id, cwd=cwd,
                      turn_timeout_seconds=turn_timeout_seconds, interrupt_grace_seconds=interrupt_grace_seconds)
        await session._check_extensions()
        return session

    @property
    def binding(self) -> NativeSessionBinding:
        """返回唯一任务关联，供可信宿主持有及有限恢复。

        :returns: 原绑定对象，不额外登记会话身份。
        """
        return self._binding

    @property
    def last_terminal(self) -> NativeMessage | None:
        """交付最近取得的真实轮次终态，观察输出失败不能改写此事实。

        :returns: 原生终态的独立副本；从未取得终态时为空。
        """
        return deepcopy(self._last_terminal)

    @property
    def turn_timeout_seconds(self) -> float:
        """返回实例已有的轮次期限，供受信重连沿用。

        :returns: 本实例唯一保存的等待期限，不重复配置。
        """
        return self._timeout

    async def _check_extensions(self) -> None:
        """核对当前有限接入没有未授权外部 MCP／Apps 通路。

        :raises NativeProtocolError: 工具来源不为空或无法确认完整清单。
        """
        reply = await self._client.request("mcpServerStatus/list", {"threadId": self._binding.thread_id})
        if reply.get("data") != [] or reply.get("nextCursor") is not None:
            raise NativeProtocolError("当前会话存在未授权外部工具来源，不能启动轮次")

    def _require_open(self) -> None:
        """拒绝关闭或结果不明后的新操作，不把本地标志当作原生终态。

        :raises NativeProtocolError: 连接已关闭或先前操作需要对账。
        """
        if self._closing is not None or self._uncertain:
            raise NativeProtocolError("会话已关闭或原操作结果不明，不得继续提交")

    def ensure_resumable(self) -> None:
        """限定受信宿主的主动重连，只允许已结束且结果明确的会话。

        :raises NativeProtocolError: 会话已关闭、在途或结果不明，需要先核对原操作。
        """
        self._require_open()
        if self._run_task is not None:
            raise NativeProtocolError("原轮次仍在途中，不能重连后启动替代轮次")

    def _skill_input(self, name: str | None, path: str | None) -> NativeMessage | None:
        """检查显式 Skill 引用属于已授权目录，不冻结或读取其执行内容。

        :param name: 原生 Skill 名称。
        :param path: 原生环境内的 Skill 路径。
        :returns: 原生输入项，未选用时为空。
        :raises ValueError: 名称和路径不配套，或路径越出任务目录。
        """
        if name is None and path is None:
            return None
        if type(name) is not str or not name.strip() or type(path) is not str or not path:
            raise ValueError("Skill 名称和路径必须一起提供")
        candidate = PurePosixPath(path)
        if "\x00" in path or ".." in candidate.parts or str(candidate) != path or not candidate.is_relative_to(self._cwd):
            raise ValueError("Skill 必须位于授权任务目录内")
        return {"type": "skill", "name": name, "path": path}

    async def read(self) -> NativeMessage:
        """查询原生线程的当前记录，不复制为业务状态或自动重交。

        :returns: 原生 thread/read 回执。
        :raises NativeProtocolError: 原线程关联不符或连接不可使用。
        """
        if self._closing is not None:
            raise NativeProtocolError("会话已关闭，不能通过旧连接查询")
        reply = await self._client.request("thread/read", {"threadId": self._binding.thread_id, "includeTurns": True})
        thread = reply.get("thread")
        if not isinstance(thread, dict) or thread.get("id") != self._binding.thread_id:
            self._uncertain = True
            raise NativeProtocolError("查询没有返回原线程")
        return reply

    async def _interrupt_once(self) -> None:
        """至多向本轮原身份发送一次中断，重复调用等待同一个请求。

        :raises NativeProtocolError: 当前操作没有可信原轮次。
        :raises TimeoutError: 中断请求未在宽限内明确受理。
        """
        if self._turn_id is None:
            raise NativeProtocolError("尚无可信轮次身份，不能推定取消已受理")
        if self._interrupt_task is None:
            self._interrupt_deadline = asyncio.get_running_loop().time() + self._grace
            self._interrupt_task = asyncio.create_task(self._send_interrupt(self._turn_id))
        await asyncio.shield(self._interrupt_task)

    async def _send_interrupt(self, turn_id: str) -> None:
        """传递一个原生取消请求，取消回执不表示所有进程已经停止。

        :param turn_id: 本实例刚取得的原轮次身份。
        :raises Exception: 请求失败或超时，不能再次发送代替对账。
        """
        try:
            async with asyncio.timeout(self._grace):
                await self._client.request("turn/interrupt", {"threadId": self._binding.thread_id, "turnId": turn_id})
        except BaseException:
            self._uncertain = True
            raise

    async def cancel(self) -> None:
        """请求当前轮次取消；受理仍在途中时先等待原受理身份。

        :raises NativeProtocolError: 原请求未取得可信身份，取消结果未知。
        :raises TimeoutError: 中断回执超时。
        """
        if self._closing is not None:
            raise NativeProtocolError("会话已关闭，不能宣称取消成功")
        await self._cancel_active()

    async def _cancel_active(self) -> None:
        """协调原在途操作的取消，允许实际关闭操作消费同一请求。

        :raises NativeProtocolError: 原受理或执行结果不明。
        :raises TimeoutError: 中断受理未在宽限内完成。
        """
        if self._run_task is None:
            self._require_open()
            return
        self._cancel_requested.set()
        await self._accepted.wait()
        if self._uncertain:
            raise NativeProtocolError("原受理或执行结果不明，不能宣称取消已受理")
        if self._last_terminal is not None and self._last_terminal.get("id") == self._turn_id:
            return
        if self._run_task is not None:
            await self._interrupt_once()

    async def _wait_step[T](self, operation: Awaitable[T], deadline: float) -> T | None:
        """有界等待通知或观察回调，取消请求可唤醒正常轮次等待。

        :param operation: 一次通知读取或观察回调，不是模型或工具操作。
        :param deadline: 当前等待的单调时钟截止点。
        :returns: 原操作结果；被取消请求唤醒时为空。
        :raises TimeoutError: 当前轮次或中断宽限已耗尽。
        """
        pending = asyncio.ensure_future(operation)
        wake = asyncio.create_task(self._cancel_requested.wait())
        try:
            if self._cancel_requested.is_set():
                return await asyncio.wait_for(pending, max(0.0, deadline - asyncio.get_running_loop().time()))
            done, _ = await asyncio.wait({pending, wake}, timeout=max(0.0, deadline - asyncio.get_running_loop().time()),
                                         return_when=asyncio.FIRST_COMPLETED)
            if pending in done:
                return await pending
            if wake in done:
                return None
            raise TimeoutError("原生轮次等待期限已到")
        finally:
            for waiting in (pending, wake):
                if not waiting.done():
                    waiting.cancel()
            await asyncio.gather(pending, wake, return_exceptions=True)

    async def run(
        self, goal: str, *, on_event: Callable[[NativeMessage], Awaitable[None]] | None = None,
        skill_name: str | None = None, skill_path: str | None = None,
    ) -> NativeMessage:
        """提交一个目标或明确追加要求，反馈及建模修订仍归原生 Agent。

        :param goal: 用户目标或明确领域事实，不在接入层生成修复步骤。
        :param on_event: 有界观察原生通知；不替代模型侧工具反馈，取消时可中止观察等待。
        :param skill_name: 本次明确选用的原生 Skill 名称。
        :param skill_path: 已授权任务目录内的 Skill 路径。
        :returns: 原生 turn/completed 中的轮次对象，不附加业务通过结论。
        :raises ValueError: 目标为空或 Skill 参数不合法。
        :raises NativeProtocolError: 已有在途轮次、关联错误或结果不明。
        :raises TimeoutError: 提交或中断宽限结束后仍未取得可信结果。
        """
        self._require_open()
        if self._run_task is not None:
            raise NativeProtocolError("同一会话已有在途轮次，不排队或重复启动")
        if type(goal) is not str or not goal.strip():
            raise ValueError("任务目标不能为空")
        skill = self._skill_input(skill_name, skill_path)
        inputs: list[NativeMessage] = [{"type": "text", "text": goal}]
        if skill is not None:
            inputs.append(skill)
        self._run_task = asyncio.current_task()
        self._turn_id = None
        self._interrupt_task = None
        self._interrupt_deadline = None
        self._cancel_requested.clear()
        self._accepted.clear()
        self._finished.clear()
        deadline = asyncio.get_running_loop().time() + self._timeout
        confirmed_terminal: NativeMessage | None = None
        try:
            async with asyncio.timeout_at(deadline):
                reply = await self._client.request("turn/start", {
                    "threadId": self._binding.thread_id, "input": list(inputs),
                    "environments": [{"environmentId": self._environment_id, "cwd": self._cwd,
                                      "runtimeWorkspaceRoots": [self._cwd]}],
                    "approvalPolicy": "never",
                    "sandboxPolicy": {"type": "externalSandbox", "networkAccess": "restricted"},
                })
            turn = reply.get("turn")
            if not isinstance(turn, dict) or type(turn.get("id")) is not str or not turn["id"]:
                raise NativeProtocolError("轮次受理缺少原身份，不得重新提交")
            turn_id = turn["id"]
            assert isinstance(turn_id, str)
            self._turn_id = turn_id
            self._accepted.set()
            while True:
                if self._cancel_requested.is_set():
                    await self._interrupt_once()
                    assert self._interrupt_deadline is not None
                    deadline = self._interrupt_deadline
                try:
                    event = await self._wait_step(self._client.next_event(), deadline)
                except TimeoutError:
                    if asyncio.get_running_loop().time() < deadline:
                        continue
                    if self._cancel_requested.is_set():
                        raise TimeoutError("中断宽限内未取得原生终态，实际执行仍需核对") from None
                    self._cancel_requested.set()
                    continue
                if event is None:
                    continue
                self._binding.validate_event(event)
                method = event.get("method")
                if not isinstance(method, str):
                    raise NativeProtocolError("原生通知缺少方法名")
                if method in ("turn/started", "turn/completed") or method.startswith("item/"):
                    self._binding.validate_event(event, turn_id=turn_id)
                completed: NativeMessage | None = None
                if method == "turn/completed":
                    params = event.get("params")
                    if not isinstance(params, dict) or params.get("threadId") != self._binding.thread_id:
                        raise NativeProtocolError("原生终态缺少原线程身份")
                    candidate = params.get("turn")
                    if not isinstance(candidate, dict) or candidate.get("id") != turn_id:
                        raise NativeProtocolError("原生终态缺少原轮次身份")
                    if candidate.get("status") not in ("completed", "interrupted", "failed"):
                        raise NativeProtocolError("原生通知不是所选版本的轮次终态")
                    completed = candidate
                    confirmed_terminal = candidate
                    self._last_terminal = deepcopy(candidate)
                if on_event is not None:
                    await self._wait_step(on_event(deepcopy(event)), deadline)
                if completed is not None:
                    return completed
        except BaseException:
            self._uncertain = confirmed_terminal is None
            raise
        finally:
            self._accepted.set()
            self._finished.set()
            self._run_task = None

    async def _finish_close(self) -> None:
        """请求取消并排空本消费者，清理原生终端后关闭连接。

        最终隔离环境回收始终由装配方执行；本方法不证明脱离终端的进程已停止。

        :raises BaseExceptionGroup: 取消、原生清理或关闭失败，保留各实际错误。
        """
        errors: list[BaseException] = []
        try:
            if self._run_task is not None:
                try:
                    await self._cancel_active()
                    async with asyncio.timeout(self._grace):
                        await self._finished.wait()
                except BaseException as error:
                    errors.append(error)
                    if self._run_task is not None and self._run_task is not asyncio.current_task():
                        self._run_task.cancel()
                        await asyncio.gather(self._run_task, return_exceptions=True)
            try:
                await self._client.request("thread/backgroundTerminals/clean", {"threadId": self._binding.thread_id})
            except BaseException as error:
                errors.append(error)
        finally:
            try:
                await self._client.aclose()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("原生会话关闭未完整完成，环境仍由装配方回收", errors)

    async def aclose(self) -> None:
        """停止新调用并等待唯一关闭操作，取消等待不取消实际清理。

        :raises BaseExceptionGroup: 原生取消、清理或关闭失败，环境由装配方收口。
        """
        if self._closing is None:
            self._closing = asyncio.create_task(self._finish_close())
        await asyncio.shield(self._closing)
