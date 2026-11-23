# 文件信息：L1-01 工作区和 L1-02 文件存储的显式装配与异步宿主边界。
# 作用：在一个专用线程内管理真实目录、注册库和服务，提供无等待队列的有限准入。
# 边界：等待取消不终止已开始的 I/O；实际工作及关闭完成前不释放根级写入资格。
"""装配工作区服务并管理线程封闭、期限、诊断和关闭。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from functools import partial
import logging
import math
import os
from pathlib import Path
from types import TracebackType
from typing import cast

from vet3d.adapters import (
    LocalArtifactFileStore, ManagedWorkspaceRoot, SqliteWorkspaceRepository,
    open_staged_input, validate_file_byte_limit,
)
from vet3d.artifacts import (
    ArtifactContractError, ArtifactFileStore, FileObservation, FilePresent, FileReference,
    FileUnavailable, WorkspaceFileLocation,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
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
        :raises ValueError: 根包含禁止的上级路径段。
        :raises RuntimeError: 当前没有运行中的事件循环。
        """
        if not isinstance(root, Path):
            raise TypeError("工作区存储根必须使用 Path")
        if ".." in root.parts:
            raise ValueError("工作区存储根不能包含上级路径段")
        self._path = Path(os.path.abspath(root))
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

    def _observe(
        self, event: str, identity: str, artifact_id: ArtifactId | None, future: asyncio.Future[object],
    ) -> None:
        """始终观察实际工作终态，等待者取消后也不丢失晚期异常。

        :param event: 固定操作名称。
        :param identity: 已知工作区身份；启动阶段为 storage。
        :param artifact_id: 文件调用的原产物身份，仅用于诊断关联。
        :param future: 不直接交给调用方取消的实际工作 Future。
        """
        error = future.exception()
        if error is None and artifact_id is not None:
            result = future.result()
            if isinstance(result, FileUnavailable):
                _LOGGER.warning(
                    "workspace_%s_unavailable workspace_id=%s artifact_id=%s reason=%s",
                    event, identity, artifact_id.value, result.reason,
                )
            else:
                _LOGGER.info(
                    "workspace_%s_completed workspace_id=%s artifact_id=%s result=%s",
                    event, identity, artifact_id.value, type(result).__name__,
                )
        elif error is None:
            _LOGGER.info("workspace_%s_completed workspace_id=%s", event, identity)
        elif isinstance(error, (WorkspaceContractError, ArtifactContractError, TypeError, ValueError, FileExistsError)):
            _LOGGER.warning(
                "workspace_%s_rejected workspace_id=%s artifact_id=%s reason=%s",
                event, identity, artifact_id.value if artifact_id else "-", type(error).__name__,
            )
        else:
            _LOGGER.error(
                "workspace_%s_failed workspace_id=%s artifact_id=%s", event, identity,
                artifact_id.value if artifact_id else "-", exc_info=error,
            )

    async def _invoke[T](
        self, operation: Callable[[], T], *, event: str, identity: str,
        timeout_seconds: float | None, artifact_id: ArtifactId | None = None,
    ) -> T:
        """在无内部等待队列的准入后，异步等待实际存储调用。

        :param operation: 将在唯一工作线程执行的具体调用。
        :param event: 固定诊断事件。
        :param identity: 本次调用的原身份。
        :param timeout_seconds: 仅限制等待的正有限秒数；None 表示由调用方管理期限。
        :param artifact_id: 可选产物诊断关联，不决定准入或存储行为。
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
            raise WorkspaceBusyError("受管存储繁忙；本次未提交，请沿原身份对账")
        # 在提交前处理已有取消；后续直到保存 Future 没有协程挂起点。
        await asyncio.sleep(0)
        if self._closing is not None:
            raise WorkspaceClosedError("工作区宿主已经开始关闭")
        if self._pending is not None and not self._pending.done():
            raise WorkspaceBusyError("受管存储繁忙；本次未提交")
        if artifact_id is None:
            _LOGGER.info("workspace_%s_started workspace_id=%s", event, identity)
        else:
            _LOGGER.info("workspace_%s_started workspace_id=%s artifact_id=%s", event, identity, artifact_id.value)
        future: asyncio.Future[object] = self._loop.run_in_executor(self._executor, operation)
        self._pending = future
        future.add_done_callback(partial(self._observe, event, identity, artifact_id))
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

    def _bind_file_store(self, workspace_id: WorkspaceId, max_file_bytes: int) -> ArtifactFileStore:
        """在资源所属线程核对已提交登记，建立固定工作区的文件端口。

        :param workspace_id: 本次绑定后不再由文件命令重定义的工作区。
        :param max_file_bytes: 已由宿主提供的单文件资源上限。
        :returns: 共享现有根所有者的具体文件适配器。
        :raises WorkspaceContractError: 工作区尚未登记或只有未完成意图。
        """
        record = self._ready_service().read(workspace_id)
        if record is None or record.registered_at is None:
            raise WorkspaceContractError("文件访问需要已提交的工作区登记")
        assert self._root is not None
        self._root.directories.require_existing(workspace_id)
        return LocalArtifactFileStore(self._root, workspace_id, max_file_bytes=max_file_bytes)

    async def files(
        self, workspace_id: WorkspaceId, *, input_root: Path, max_file_bytes: int,
    ) -> WorkspaceFiles:
        """为可信宿主绑定文件范围及暂存输入位置，不建立产物目录或登记。

        :param workspace_id: 已提交登记的固定工作区身份。
        :param input_root: 与受管存储分开的私有输入暂存根，输入操作时安全打开。
        :param max_file_bytes: 显式正整数资源预算，不进入业务能力或文件身份。
        :returns: 共用本宿主准入和生命周期的具体文件入口。
        :raises ValueError: 根配置包含上级段或与受管存储重叠。
        :raises WorkspaceContractError: 工作区尚未完成注册。
        """
        if type(workspace_id) is not WorkspaceId or not isinstance(input_root, Path):
            raise TypeError("文件装配需要 WorkspaceId 和 Path 暂存根")
        validate_file_byte_limit(max_file_bytes)
        if ".." in input_root.parts:
            raise ValueError("输入暂存根不能包含上级路径段")
        source_root = Path(os.path.abspath(input_root))
        managed_root = Path(os.path.abspath(self._path))
        if source_root.is_relative_to(managed_root) or managed_root.is_relative_to(source_root):
            raise ValueError("输入暂存根必须与受管存储分开")
        store = await self._invoke(
            partial(self._bind_file_store, workspace_id, max_file_bytes),
            event="files_bind", identity=str(workspace_id.value), timeout_seconds=None,
        )
        return WorkspaceFiles(self, workspace_id, source_root, store)

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


class WorkspaceFiles:
    """固定工作区与暂存输入范围，通过根所有者发起文件 I/O。

    :param runtime: 持有根锁和线程生命周期的唯一宿主。
    :param workspace_id: 已经完成登记核对的实例作用域。
    :param input_root: 可信装配解析的私有上传暂存位置。
    :param store: 由工作线程建立的文件端口，仅 location_for 是无 I/O 方法。
    """

    def __init__(
        self, runtime: WorkspaceRuntime, workspace_id: WorkspaceId,
        input_root: Path, store: ArtifactFileStore,
    ) -> None:
        """接收装配结果，不另外打开根或复制登记状态。

        :param runtime: 所属根的资源所有者。
        :param workspace_id: 固定工作区范围，只用于日志关联。
        :param input_root: 暂存文件的可信根，不来自逐次文件请求。
        :param store: 已绑定归属和预算的文件端口。
        """
        self._runtime = runtime
        self._workspace_id = workspace_id
        self._input_root = input_root
        self._store = store

    def location_for(self, artifact: ArtifactIdentity) -> WorkspaceFileLocation:
        """派生调用方可预先保留的位置，不证明已保存或已登记。

        :param artifact: 必须属于实例固定范围的产物身份。
        :returns: 由适配器唯一派生的相对位置。
        """
        return self._store.location_for(artifact)

    def _store_new(
        self, artifact: ArtifactIdentity, reference: FileReference, input_name: str,
    ) -> FilePresent:
        """由工作线程独立持有输入至保存终结，取消等待不会关闭源文件。

        :param artifact: 原产物身份。
        :param reference: 原预期内容引用。
        :param input_name: 可信暂存根下的单文件名。
        :returns: 实际保存位置及字节观察。
        """
        with open_staged_input(self._input_root, input_name) as source:
            return self._store.store_new(artifact, reference, source)

    async def store_new(
        self, artifact: ArtifactIdentity, reference: FileReference, input_name: str,
        *, timeout_seconds: float | None = 5.0,
    ) -> FilePresent:
        """保存新文件，目标已存在时拒绝；不登记产物或自动恢复导入。

        :param artifact: 原产物身份及归属。
        :param reference: 调用前保留的完整预期内容。
        :param input_name: 已完成上传的单文件名，不接受路径或 URL。
        :param timeout_seconds: 仅限制本次等待，实际 I/O 仍受宿主管理。
        :returns: 文件存储事实，不代表业务登记、验收或发布。
        """
        self._store.location_for(artifact)
        return await self._runtime._invoke(
            partial(self._store_new, artifact, reference, input_name), event="file_store",
            identity=str(self._workspace_id.value), artifact_id=artifact.id, timeout_seconds=timeout_seconds,
        )

    async def observe(
        self, artifact: ArtifactIdentity, location: WorkspaceFileLocation,
        *, timeout_seconds: float | None = 5.0,
    ) -> FileObservation:
        """观察原位置的实际内容，不从结果反推登记或先前操作成功。

        :param artifact: 受信调用方保留的产物身份及归属。
        :param location: 原确切位置，适配器核对其与固定布局一致。
        :param timeout_seconds: 本次等待期限，超时不证明实际读取停止。
        :returns: 已有的文件存在、缺失或不可用事实类型。
        """
        self._store.location_for(artifact)
        return await self._runtime._invoke(
            partial(self._store.observe, artifact, location), event="file_observe",
            identity=str(self._workspace_id.value), artifact_id=artifact.id, timeout_seconds=timeout_seconds,
        )


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
