# 文件信息：L1-01 工作区存储的显式装配与异步宿主边界。
# 作用：在一个专用线程内管理真实目录、注册库和服务，提供无等待队列的有限准入。
# 边界：等待取消不终止已开始的 I/O；实际工作及关闭完成前不释放根级写入资格。
"""装配工作区服务并管理线程封闭、期限、诊断和关闭。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from functools import partial
import logging
import math
from pathlib import Path
from types import TracebackType
from typing import cast

from vet3d.adapters import ManagedWorkspaceRoot, SqliteWorkspaceRepository
from vet3d.identity import WorkspaceId
from vet3d.workspaces import (
    WorkspaceContractError, WorkspaceRecord, WorkspaceService,
)

from .invocation import _record_termination

_LOGGER = logging.getLogger("vet3d")


class WorkspaceBusyError(RuntimeError):
    """表示宿主尚有实际存储调用在途，本次请求没有取得准入。"""


class WorkspaceClosedError(RuntimeError):
    """表示工作区宿主已开始关闭或调用来自其他事件循环。"""


class WorkspaceTimeoutError(TimeoutError):
    """表示宿主等待期限耗尽，不证明实际存储操作已停止或未提交。"""


class WorkspaceRuntime:
    """持有一个根的线程封闭存储，通过装配函数初始化后使用。"""

    def __init__(self, root: Path) -> None:
        """建立本事件循环内的资源所有者，尚不打开目录或注册库。

        :param root: Bootstrap 已解析的部署存储根，仅供内部初始化使用。
        :raises TypeError: 根不是 Path。
        :raises RuntimeError: 当前没有运行中的事件循环。
        """
        if not isinstance(root, Path):
            raise TypeError("工作区存储根必须使用 Path")
        self._path = root
        self._loop = asyncio.get_running_loop()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vet3d-workspaces")
        self._root: ManagedWorkspaceRoot | None = None
        self._repository: SqliteWorkspaceRepository | None = None
        self._service: WorkspaceService | None = None
        self._pending: asyncio.Future[object] | None = None
        self._closing: asyncio.Task[None] | None = None

    def _initialize(self) -> None:
        """在工作线程初始化新根及新注册库，失败时保留现场并释放根句柄。"""
        root = ManagedWorkspaceRoot.initialize(self._path)
        try:
            repository = SqliteWorkspaceRepository.initialize(root.database_path)
        except BaseException:
            root.close()
            raise
        self._root = root
        self._repository = repository
        self._service = WorkspaceService(repository=repository, directories=root.directories)

    def _open(self) -> None:
        """在工作线程打开既有存储，不自动创建缺失数据库或修复布局。"""
        root = ManagedWorkspaceRoot.open(self._path)
        try:
            repository = SqliteWorkspaceRepository.open(root.database_path)
        except BaseException:
            root.close()
            raise
        self._root = root
        self._repository = repository
        self._service = WorkspaceService(repository=repository, directories=root.directories)

    def _ready_service(self) -> WorkspaceService:
        """从工作线程核对仍受控的根并取得具体服务。

        :returns: 已初始化且仍具备原受管根的服务。
        :raises WorkspaceClosedError: 存储尚未初始化或已经释放。
        """
        if self._root is None or self._service is None:
            raise WorkspaceClosedError("工作区存储尚未打开或已经关闭")
        self._root.validate()
        return self._service

    def _create(self, workspace_id: WorkspaceId, display_name: str) -> WorkspaceRecord:
        """在唯一工作线程内执行整个创建临界段。

        :param workspace_id: 原工作区身份。
        :param display_name: 原创建名称。
        :returns: 已提交并核对的注册记录。
        """
        return self._ready_service().create(workspace_id=workspace_id, display_name=display_name)

    def _read(self, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
        """在唯一工作线程读取原记录，不观察工作区中的素材。

        :param workspace_id: 待查询身份。
        :returns: 原记录；没有登记时为 None。
        """
        return self._ready_service().read(workspace_id)

    def _check_loop(self) -> None:
        """拒绝跨事件循环使用，避免把线程封闭实例作为任意并发消费者。"""
        if asyncio.get_running_loop() is not self._loop:
            raise WorkspaceClosedError("工作区宿主只能由装配时的事件循环使用")

    def _observe(self, event: str, identity: str, future: asyncio.Future[object]) -> None:
        """始终观察实际工作终态，等待者取消后也不丢失晚期异常。

        :param event: 固定操作名称。
        :param identity: 已知工作区身份；启动阶段为 storage。
        :param future: 不直接交给调用方取消的实际工作 Future。
        """
        error = future.exception()
        if error is None:
            _LOGGER.info("workspace_%s_completed workspace_id=%s", event, identity)
        elif isinstance(error, (WorkspaceContractError, TypeError)):
            _LOGGER.warning("workspace_%s_rejected workspace_id=%s reason=%s", event, identity, type(error).__name__)
        else:
            _LOGGER.error("workspace_%s_failed workspace_id=%s", event, identity, exc_info=error)

    async def _invoke[T](
        self, operation: Callable[[], T], *, event: str, identity: str,
        timeout_seconds: float | None,
    ) -> T:
        """在无内部等待队列的准入后，异步等待实际存储调用。

        :param operation: 将在唯一工作线程执行的具体调用。
        :param event: 固定诊断事件。
        :param identity: 本次调用的原身份。
        :param timeout_seconds: 仅限制等待的正有限秒数；None 表示由调用方管理期限。
        :returns: 实际存储调用的结果。
        :raises WorkspaceBusyError: 原实际调用尚未终结，没有提交本次操作。
        :raises WorkspaceClosedError: 已开始关闭或事件循环不符。
        :raises WorkspaceTimeoutError: 等待期限耗尽，需按原身份对账。
        :raises asyncio.CancelledError: 调用方取消等待，实际工作仍由宿主管理。
        """
        self._check_loop()
        if self._closing is not None:
            raise WorkspaceClosedError("工作区宿主已经开始关闭")
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
        ):
            raise ValueError("等待期限必须为正有限秒数")
        if self._pending is not None and not self._pending.done():
            raise WorkspaceBusyError("注册存储繁忙；本次未提交，请沿原身份再次查询或创建")
        # 在提交前处理已有取消；后续直到保存 Future 没有协程挂起点。
        await asyncio.sleep(0)
        if self._closing is not None:
            raise WorkspaceClosedError("工作区宿主已经开始关闭")
        if self._pending is not None and not self._pending.done():
            raise WorkspaceBusyError("注册存储繁忙；本次未提交")
        _LOGGER.info("workspace_%s_started workspace_id=%s", event, identity)
        future: asyncio.Future[object] = self._loop.run_in_executor(self._executor, operation)
        self._pending = future
        future.add_done_callback(partial(self._observe, event, identity))
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                # wait 的取消不传播给实际 Future；终态由唯一 _observe 回调诊断。
                await asyncio.wait({future})
                return cast(T, future.result())
        except asyncio.CancelledError as error:
            _record_termination(error, logging.INFO, "workspace_wait_cancelled", identity)
            raise
        except TimeoutError:
            if deadline.expired():
                timeout = WorkspaceTimeoutError("等待超时；实际存储结果须按原身份对账")
                _record_termination(timeout, logging.INFO, "workspace_wait_timed_out", identity)
                raise timeout from None
            raise

    async def create(
        self, *, workspace_id: WorkspaceId, display_name: str, timeout_seconds: float | None = 5.0,
    ) -> WorkspaceRecord:
        """为可信宿主创建或读回原工作区，不执行自动重试。

        :param workspace_id: 调用前已保留的唯一身份。
        :param display_name: 与原创建意图精确相同的显示名称。
        :param timeout_seconds: 本次宿主等待期限，不进入业务记录。
        :returns: 已确认注册的原记录。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("创建必须使用 WorkspaceId")
        return await self._invoke(
            partial(self._create, workspace_id, display_name), event="create",
            identity=str(workspace_id.value), timeout_seconds=timeout_seconds,
        )

    async def read(
        self, workspace_id: WorkspaceId, *, timeout_seconds: float | None = 5.0,
    ) -> WorkspaceRecord | None:
        """查询原注册事实，结果不代表目录访问或执行权限。

        :param workspace_id: 待核对的原身份。
        :param timeout_seconds: 本次宿主等待期限。
        :returns: 持久记录；未登记时为空。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("查询必须使用 WorkspaceId")
        return await self._invoke(
            partial(self._read, workspace_id), event="read", identity=str(workspace_id.value),
            timeout_seconds=timeout_seconds,
        )

    def _close_storage(self) -> None:
        """在原工作线程内关闭注册库，再释放根级写入资格。"""
        try:
            if self._repository is not None:
                self._repository.close()
        finally:
            if self._root is not None:
                self._root.close()
            self._service = None
            self._repository = None
            self._root = None

    async def _drain[T](self, future: asyncio.Future[T]) -> T:
        """让内部清理任务等待真实工作完成，不因清理任务取消提前释放锁。

        :param future: 尚需确认终结的实际工作。
        :returns: 实际结果；实际工作异常保持原类型。
        """
        while not future.done():
            try:
                await asyncio.wait({future})
            except asyncio.CancelledError:
                # 只保护私有资源清理；公开调用方的取消仍立即传播。
                continue
        return future.result()

    async def _finish_close(self) -> None:
        """停止准入后排空原调用并关闭，最后回收线程资源。"""
        try:
            if self._pending is not None:
                try:
                    await self._drain(self._pending)
                except BaseException:
                    # 原调用错误由 _observe 及原调用方观察，关闭仍须继续。
                    pass
            closing = self._loop.run_in_executor(self._executor, self._close_storage)
            await self._drain(closing)
        finally:
            # 存储任务实际终结后才 join；此时不再有阻塞 I/O 在途。
            self._executor.shutdown(wait=True)

    def _observe_close(self, task: asyncio.Task[None]) -> None:
        """在关闭等待者取消时仍保留关闭失败诊断。

        :param task: 唯一关闭任务。
        """
        error = task.exception()
        if error is not None:
            _LOGGER.error("workspace_storage_close_failed", exc_info=error)
        else:
            _LOGGER.info("workspace_storage_closed")

    async def aclose(self) -> None:
        """停止新调用并等待真实工作及资源关闭；取消不解除在途根锁。

        :raises asyncio.CancelledError: 调用方取消关闭等待，内部清理仍继续。
        """
        self._check_loop()
        if self._closing is None:
            self._closing = self._loop.create_task(self._finish_close())
            self._closing.add_done_callback(self._observe_close)
        await asyncio.wait({self._closing})
        self._closing.result()

    async def __aenter__(self) -> WorkspaceRuntime:
        """将已装配宿主交给上下文调用方。

        :returns: 当前宿主实例。
        """
        self._check_loop()
        if self._closing is not None:
            raise WorkspaceClosedError("不能重新进入已关闭宿主")
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """在离开上下文时开始确定的资源回收。

        :param exc_type: 上下文异常类型。
        :param exc_value: 上下文异常实例。
        :param traceback: 原异常堆栈。
        """
        await self.aclose()


async def initialize_workspaces(root: Path) -> WorkspaceRuntime:
    """显式初始化新的受管存储，失败或取消时释放本次取得的资源。

    :param root: 不存在或安全空目录的部署根。
    :returns: 已打开的线程封闭工作区宿主。
    """
    runtime = WorkspaceRuntime(root)
    try:
        await runtime._invoke(runtime._initialize, event="initialize", identity="storage", timeout_seconds=None)
    except BaseException:
        await runtime.aclose()
        raise
    return runtime


async def open_workspaces(root: Path) -> WorkspaceRuntime:
    """只打开既有完整存储，缺库或布局异常不会触发初始化。

    :param root: 已初始化的部署根。
    :returns: 已核对并取得单写入资格的宿主。
    """
    runtime = WorkspaceRuntime(root)
    try:
        await runtime._invoke(runtime._open, event="open", identity="storage", timeout_seconds=None)
    except BaseException:
        await runtime.aclose()
        raise
    return runtime
