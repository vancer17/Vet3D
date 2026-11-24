# 文件信息：L1-05 运维诊断的显式装配、日志接收和异步生命周期。
# 作用：通过有界队列将事件交给唯一文件线程，同时提供按已知身份读取的端口。
# 边界：日志损失显式可查，但不抛入业务调用改变提交、取消或发布判断。
"""管理诊断所有者；模块导入不读取配置、不启动线程或修改日志。"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from queue import Empty, Full, Queue
import re
import sys
from threading import Event, Lock, Thread
from types import TracebackType
from typing import TextIO
from uuid import UUID, uuid4

from vet3d.adapters import LocalDiagnosticFiles
from vet3d.identity import ArtifactId, AttemptId, TaskId, TaskIdentity, WorkspaceId
from vet3d.operations import DiagnosticLimits, DiagnosticRead, DiagnosticReader, DiagnosticStatus

_PLACEHOLDER = re.compile(r"%%|%[sdr]")


def _scalar(value: object) -> str:
    """有限格式化明确标量，不调用任意对象的字符串或表示方法。

    :param value: 日志参数或异常的单个参数。
    :returns: 最多五百一十二个字符的诊断文本。
    """
    if type(value) is str:
        return value[:512]
    if value is None or type(value) in (bool, float):
        return str(value)
    if type(value) is int:
        return str(value) if value.bit_length() < 256 else "[大整数]"
    if type(value) is UUID:
        return str(value)
    return f"[{type(value).__name__[:64]}]"


def _message(record: logging.LogRecord) -> str:
    """有界展开常用标量占位符，并保留有限异常帧而不读取源码或局部变量。

    :param record: 日志生产者提交的原记录。
    :returns: 有界消息及异常上下文；不尝试格式化任意大对象。
    """
    template = record.msg[:2048] if type(record.msg) is str else "[非文本日志消息]"
    arguments = record.args[:8] if isinstance(record.args, tuple) else ()
    index = 0

    def replace(match: re.Match[str]) -> str:
        """按出现顺序展开有限参数，拒绝宽度与映射格式造成的大量计算。

        :param match: 已识别的固定占位符。
        :returns: 有界参数文本或原占位符。
        """
        nonlocal index
        if match.group() == "%%":
            return "%"
        if index >= len(arguments):
            return match.group()
        result = _scalar(arguments[index])
        index += 1
        return result

    result = _PLACEHOLDER.sub(replace, template)
    if record.exc_info is not None and record.exc_info[1] is not None:
        error = record.exc_info[1]
        reason = _scalar(error.args[0]) if error.args else ""
        parts = [result, f"{type(error).__name__[:64]}: {reason}", "Traceback (most recent call last):"]
        trace = record.exc_info[2]
        count = 0
        while trace is not None and count < 12:
            code = trace.tb_frame.f_code
            parts.append(f"  {code.co_filename[-256:]}:{trace.tb_lineno} {code.co_name[:128]}")
            trace = trace.tb_next
            count += 1
        if trace is not None:
            parts.append("  [其余堆栈已截断]")
        result = "\n".join(parts)
    return result


def _encode(record: logging.LogRecord, runtime_id: str, limit: int) -> bytes:
    """编码有界 UTF-8 JSON，不把消息中的 ID 解析为权威关联。

    :param record: 携带可选结构化身份字段的原事件。
    :param runtime_id: 本进程的不可解析运行关联。
    :param limit: 包含换行的最终字节上限。
    :returns: 始终保持合法 JSON 的完整一行。
    :raises ValueError: 结构化身份字段无效，调用方应记录诊断损失。
    """
    message = _message(record)
    value: dict[str, object] = {
        "schema": 1, "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
        "runtime_id": runtime_id, "level": record.levelname[:32], "message": message,
    }
    for name, identity_type in (
        ("workspace_id", WorkspaceId), ("task_id", TaskId),
        ("attempt_id", AttemptId), ("artifact_id", ArtifactId),
    ):
        supplied: object = record.__dict__.get(name)
        value[name] = str(identity_type.parse(supplied).value) if isinstance(supplied, str) else None
        if supplied is not None and type(supplied) is not str:
            raise ValueError("结构化诊断身份必须使用规范文本")
    if value["task_id"] is not None and value["workspace_id"] is None:
        raise ValueError("任务诊断必须同时携带已知工作区")
    while True:
        data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) <= limit:
            return data
        message = message[:len(message) // 2]
        value["message"] = message + " [诊断已截断]"


@dataclass(frozen=True, slots=True)
class _ReadRequest:
    """封闭一次有界读取与事件循环上的回执，不持久化查询意图。

    :param workspace_id: 读取范围。
    :param task_id: 可选的额外任务过滤。
    :param limit: 有界返回数量。
    :param future: 由宿主循环拥有的结果回执。
    """

    workspace_id: WorkspaceId
    task_id: TaskId | None
    limit: int
    future: asyncio.Future[DiagnosticRead]


class DiagnosticBusyError(RuntimeError):
    """表示诊断队列已满，本次查询没有取得准入。"""


class DiagnosticClosedError(RuntimeError):
    """表示诊断宿主已关闭、正在关闭或被跨循环使用。"""


class DiagnosticHandler(logging.Handler):
    """将有限记录交给宿主；故障仅进入诊断状态，不传播到业务动作。"""

    def __init__(self, owner: "DiagnosticRuntime") -> None:
        """固定唯一所有者，不在生产者线程进行文件 I/O。

        :param owner: 已初始化的诊断宿主。
        """
        super().__init__(logging.INFO)
        self._owner = owner

    def emit(self, record: logging.LogRecord) -> None:
        """有界编码并非阻塞入队，队列满或编码异常均显式累计。

        :param record: 当前业务或运维事件。
        """
        try:
            self._owner._submit(_encode(record, self._owner.runtime_id, self._owner._limits.max_record_bytes))
        except Exception as error:
            self._owner._lost(f"diagnostic_encoding_failed: {type(error).__name__}")


class DiagnosticRuntime(DiagnosticReader):
    """拥有单个诊断根、有限队列及真实后台线程；也实现只读消费者端口。"""

    def __init__(self, root: Path, limits: DiagnosticLimits, stream: TextIO | None) -> None:
        """建立宿主对象，启动由装配函数明确控制。

        :param root: 已冻结的私有诊断目录。
        :param limits: 唯一预算对象。
        :param stream: 供 Docker 或终端采集的镜像输出；测试可显式关闭。
        """
        self.runtime_id = str(uuid4())
        self.reader: DiagnosticReader = self
        self._root = root
        self._limits = limits
        self._stream = stream
        self._loop = asyncio.get_running_loop()
        self._queue: Queue[bytes | _ReadRequest] = Queue(maxsize=limits.queue_capacity)
        self._stopping = Event()
        self._state_lock = Lock()
        self._dropped = 0
        self._write_error: str | None = None
        self._started: asyncio.Future[None] = self._loop.create_future()
        self._closed: asyncio.Future[None] = self._loop.create_future()
        self._thread = Thread(target=self._run, name="vet3d-diagnostics")
        self._handler = DiagnosticHandler(self)
        self._previous: tuple[list[logging.Handler], int, bool] | None = None

    def status(self) -> DiagnosticStatus:
        """读取当前进程的诊断损失；不据此改变业务结果。

        :returns: 不可变的丢失数量与首次故障说明。
        """
        with self._state_lock:
            return DiagnosticStatus(self._dropped, self._write_error)

    def _lost(self, error: str | None = None) -> None:
        """累计未保存记录，并只保留首次故障的有限原因。

        :param error: 可选固定错误类别，不包含任意对象或配置转储。
        """
        with self._state_lock:
            self._dropped += 1
            if error is not None and self._write_error is None:
                self._write_error = error[:256]

    def _failed(self, error: str) -> None:
        """保存首次输出故障，不虚构丢失记录数量。

        :param error: 已有界的失败位置和类别。
        """
        with self._state_lock:
            if self._write_error is None:
                self._write_error = error[:256]

    def _submit(self, data: bytes) -> None:
        """非阻塞提交记录；生命周期结束或队列满时记录明确损失。

        :param data: 已有字节上限的完整记录。
        """
        with self._state_lock:
            if self._stopping.is_set():
                self._dropped += 1
                return
            try:
                self._queue.put_nowait(data)
            except Full:
                self._dropped += 1

    def _notify(self, callback: Callable[[], None]) -> None:
        """把线程回执送回原循环，不从文件线程操作 asyncio Future。

        :param callback: 在原事件循环执行的无参函数。
        """
        self._loop.call_soon_threadsafe(callback)

    def _resolve_start(self, error: Exception | None) -> None:
        """在原循环交付启动结果。

        :param error: 文件线程初始化失败时的原异常。
        """
        if error is None:
            self._started.set_result(None)
        else:
            self._started.set_exception(error)

    def _resolve_read(self, request: _ReadRequest, result: DiagnosticRead | Exception) -> None:
        """在原循环交付有限读取结果，调用方取消后仍消费实际 I/O 终态。

        :param request: 原读取请求。
        :param result: 真实查询结果或原异常。
        """
        if request.future.cancelled():
            return
        if isinstance(result, Exception):
            request.future.set_exception(result)
        else:
            request.future.set_result(result)

    def _run(self) -> None:
        """在唯一线程初始化、写入、读取和关闭，不建立无限后台任务。"""
        from functools import partial

        files: LocalDiagnosticFiles | None = None
        broken = False
        notified = False
        try:
            try:
                files = LocalDiagnosticFiles(self._root, self._limits)
            except Exception as error:
                self._notify(partial(self._resolve_start, error))
                return
            self._notify(partial(self._resolve_start, None))
            while not self._stopping.is_set() or not self._queue.empty():
                try:
                    entry = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                if isinstance(entry, bytes):
                    if broken:
                        self._lost()
                    else:
                        try:
                            files.append(entry)
                        except Exception as error:
                            broken = True
                            self._lost(f"diagnostic_write_failed: {type(error).__name__}")
                    if self._stream is not None:
                        try:
                            self._stream.write(entry.decode("utf-8"))
                            self._stream.flush()
                        except Exception as error:
                            self._failed(f"diagnostic_stderr_failed: {type(error).__name__}")
                            self._stream = None
                else:
                    try:
                        records, truncated, malformed = files.read(entry.workspace_id, entry.task_id, entry.limit)
                        result: DiagnosticRead | Exception = DiagnosticRead(records, truncated, malformed, self.status())
                    except Exception as error:
                        result = error
                    self._notify(partial(self._resolve_read, entry, result))
                current = self.status()
                if not notified and (current.dropped_records or current.write_error is not None) and self._stream is not None:
                    notified = True
                    try:
                        self._stream.write("ERROR diagnostic_output_incomplete; inspect Operations diagnostic status\n")
                        self._stream.flush()
                    except Exception as error:
                        self._failed(f"diagnostic_stderr_failed: {type(error).__name__}")
                        self._stream = None
        finally:
            if files is not None:
                try:
                    files.close()
                except Exception as error:
                    self._failed(f"diagnostic_close_failed: {type(error).__name__}")
            self._notify(self._complete_close)

    def _complete_close(self) -> None:
        """在原循环确认真实文件线程已经释放句柄和根锁。"""
        if self._previous is not None:
            logger = logging.getLogger("vet3d")
            logger.removeHandler(self._handler)
            previous, level, propagation = self._previous
            logger.handlers = previous
            logger.setLevel(level)
            logger.propagate = propagation
            self._previous = None
        self._closed.set_result(None)

    async def _read(self, workspace_id: WorkspaceId, task_id: TaskId | None, limit: int) -> DiagnosticRead:
        """将已校验读取放入有限队列，取消只影响等待，不中断实际文件读取。

        :param workspace_id: 具体工作区。
        :param task_id: 可选任务身份。
        :param limit: 一至一千的结果上限。
        :returns: 真实读取结果或显式故障。
        :raises DiagnosticBusyError: 队列满，本次读取没有提交。
        :raises DiagnosticClosedError: 生命周期或事件循环不符。
        """
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("诊断读取上限必须为一至一千的非布尔整数")
        if asyncio.get_running_loop() is not self._loop or self._stopping.is_set():
            raise DiagnosticClosedError("诊断宿主已关闭或属于其他事件循环")
        future: asyncio.Future[DiagnosticRead] = self._loop.create_future()
        try:
            self._queue.put_nowait(_ReadRequest(workspace_id, task_id, limit, future))
        except Full:
            raise DiagnosticBusyError("诊断队列已满，本次读取未提交") from None
        return await future

    async def read_workspace(self, workspace_id: WorkspaceId, *, limit: int = 100) -> DiagnosticRead:
        """按已授权的工作区读取有限保留窗口。

        :param workspace_id: 原工作区身份。
        :param limit: 最大返回数量。
        :returns: 最近记录与当前诊断损失信息。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("诊断查询必须使用 WorkspaceId")
        return await self._read(workspace_id, None, limit)

    async def read_task(self, task: TaskIdentity, *, limit: int = 100) -> DiagnosticRead:
        """同时过滤权威任务关系中的工作区和任务身份。

        :param task: 原 TaskIdentity，不从日志建立其归属。
        :param limit: 最大返回数量。
        :returns: 同时满足两个过滤条件的最近事件。
        """
        if type(task) is not TaskIdentity:
            raise TypeError("任务诊断查询必须使用 TaskIdentity")
        return await self._read(task.workspace_id, task.id, limit)

    async def aclose(self) -> DiagnosticStatus:
        """停止接收并排空真实队列；取消等待不提前释放根锁。

        :returns: 最终观察到的诊断损失；日志失败不改写业务事实。
        :raises asyncio.CancelledError: 调用方停止等待，但线程仍继续有序关闭。
        """
        if asyncio.get_running_loop() is not self._loop:
            raise DiagnosticClosedError("关闭必须在原事件循环执行")
        with self._state_lock:
            self._stopping.set()
        await asyncio.shield(self._closed)
        self._thread.join(timeout=0)
        return self.status()

    async def __aenter__(self) -> "DiagnosticRuntime":
        """进入由调用方负责关闭的宿主范围。

        :returns: 原诊断宿主。
        """
        return self

    async def __aexit__(
        self, error_type: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        """退出范围时排空真实诊断工作，不吞掉调用方异常。

        :param error_type: 调用方异常类型。
        :param error: 调用方原异常。
        :param traceback: 调用方原堆栈。
        """
        await self.aclose()


def is_diagnostics_active() -> bool:
    """供日志初始化入口阻止移除仍有真实文件工作的活动处理器。

    :returns: 当前 Vet3D logger 是否由诊断宿主管理。
    """
    return any(isinstance(handler, DiagnosticHandler) for handler in logging.getLogger("vet3d").handlers)


async def open_diagnostics(
    root: Path, *, limits: DiagnosticLimits = DiagnosticLimits(), stderr: TextIO | None = sys.stderr,
) -> DiagnosticRuntime:
    """装配单写入诊断根并接管 Vet3D logger，不改变根日志器。

    :param root: 独立私有目录，父目录由部署负责建立。
    :param limits: 唯一存储与排队预算。
    :param stderr: 后台镜像输出通道；None 用于显式关闭镜像的测试装配。
    :returns: 初始化完成的实际诊断宿主。
    :raises RuntimeError: 已有另一个活动诊断宿主管理当前 logger。
    :raises OSError: 私有目录或独占写入约束不成立。
    """
    if is_diagnostics_active():
        raise RuntimeError("当前进程已有活动诊断宿主")
    runtime = DiagnosticRuntime(root, limits, stderr)
    runtime._thread.start()
    try:
        await asyncio.shield(runtime._started)
        if is_diagnostics_active():
            raise RuntimeError("当前进程已有活动诊断宿主")
        logger = logging.getLogger("vet3d")
        runtime._previous = (list(logger.handlers), logger.level, logger.propagate)
        logger.handlers = [runtime._handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        return runtime
    except BaseException:
        await runtime.aclose()
        if runtime._started.done() and not runtime._started.cancelled():
            runtime._started.exception()
        raise
