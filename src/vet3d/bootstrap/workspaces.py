# 文件信息：工作区、真实文件及单资产目录的显式装配与异步宿主边界。
# 作用：短元数据操作保持线程封闭，耗时文件 I/O 使用独立有限线程，无内部等待队列。
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
    ArtifactAccess, ArtifactContractError, ArtifactFileStore, ArtifactRepository,
    FileObservation, FilePresent, FileReference, FileUnavailable, ImportOrigin,
    LocatedArtifact, WorkspaceFileLocation, require_matching_file, validate_registration,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
from vet3d.workspaces import (
    WorkspaceContractError, WorkspaceRecord, WorkspaceService,
)

from .invocation import _record_termination

_LOGGER = logging.getLogger("vet3d")


def _log_context(identity: str, artifact_id: ArtifactId | None) -> dict[str, str]:
    """把调用方已有的原身份投影为可过滤字段，不从日志文字推导关联。

    :param identity: 原工作区 UUID 文本；存储启动事件使用 storage 且不赋予工作区。
    :param artifact_id: 已知的原产物身份，不从路径解析。
    :returns: 本事件实际掌握的关联字段。
    """
    context = {} if identity == "storage" else {"workspace_id": identity}
    if artifact_id is not None:
        context["artifact_id"] = str(artifact_id.value)
    return context


class WorkspaceBusyError(RuntimeError):
    """表示宿主尚有实际存储调用在途，本次请求没有取得准入。"""


class WorkspaceClosedError(RuntimeError):
    """表示工作区宿主已开始关闭或调用来自其他事件循环。"""


class WorkspaceTimeoutError(TimeoutError):
    """表示宿主等待期限耗尽，不证明实际存储操作已停止或未提交。"""


class _WorkspaceWorker:
    """持有一个部署限额对应的线程池及事件循环内的真实在途集合。"""

    def __init__(self, limit: int, name: str) -> None:
        """建立有限执行资源，不建立业务状态或内部等待队列。

        :param limit: 实际并行名额上限。
        :param name: 用于线程诊断的固定名称。
        """
        if type(limit) is not int or limit <= 0:
            raise ValueError("文件并行上限必须为非布尔正整数")
        self.limit = limit
        self.executor = ThreadPoolExecutor(max_workers=limit, thread_name_prefix=name)
        self.pending: set[asyncio.Future[object]] = set()

    def available(self) -> bool:
        """只从实际 Future 终态派生剩余名额，不复制繁忙状态。

        :returns: 当前是否可以立即提交一次实际操作。
        """
        return sum(not future.done() for future in self.pending) < self.limit


class WorkspaceRuntime:
    """持有一个根的线程封闭存储，通过装配函数初始化后使用。"""

    def __init__(self, root: Path, *, max_file_operations: int = 2) -> None:
        """建立本事件循环内的资源所有者，尚不打开目录或注册库。

        :param root: Bootstrap 已解析的部署存储根，仅供内部初始化使用。
        :param max_file_operations: 独立文件线程的有界并行资源上限。
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
        self._file_worker = _WorkspaceWorker(max_file_operations, "vet3d-files")
        self._control_worker = _WorkspaceWorker(1, "vet3d-workspaces")
        self._root: ManagedWorkspaceRoot | None = None
        self._repository: SqliteWorkspaceRepository | None = None
        self._service: WorkspaceService | None = None
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
        self, worker: _WorkspaceWorker, event: str, identity: str,
        artifact_id: ArtifactId | None, future: asyncio.Future[object],
    ) -> None:
        """始终观察实际工作终态，等待者取消后也不丢失晚期异常。

        :param worker: 本次真实操作所占的线程资源。
        :param event: 固定操作名称。
        :param identity: 已知工作区身份；启动阶段为 storage。
        :param artifact_id: 文件调用的原产物身份，仅用于诊断关联。
        :param future: 不直接交给调用方取消的实际工作 Future。
        """
        worker.pending.discard(future)
        error = future.exception()
        context = _log_context(identity, artifact_id)
        if error is None and artifact_id is not None:
            result = future.result()
            if isinstance(result, FileUnavailable):
                _LOGGER.warning(
                    "workspace_%s_unavailable workspace_id=%s artifact_id=%s reason=%s",
                    event, identity, artifact_id.value, result.reason,
                    extra=context,
                )
            else:
                _LOGGER.info(
                    "workspace_%s_completed workspace_id=%s artifact_id=%s result=%s",
                    event, identity, artifact_id.value, type(result).__name__,
                    extra=context,
                )
        elif error is None:
            _LOGGER.info("workspace_%s_completed workspace_id=%s", event, identity, extra=context)
        elif isinstance(error, (WorkspaceContractError, ArtifactContractError, TypeError, ValueError, FileExistsError)):
            _LOGGER.warning(
                "workspace_%s_rejected workspace_id=%s artifact_id=%s reason=%s",
                event, identity, artifact_id.value if artifact_id else "-", type(error).__name__,
                extra=context,
            )
        else:
            _LOGGER.error(
                "workspace_%s_failed workspace_id=%s artifact_id=%s", event, identity,
                artifact_id.value if artifact_id else "-", exc_info=error,
                extra=context,
            )

    async def _invoke[T](
        self, operation: Callable[[], T], *, event: str, identity: str,
        timeout_seconds: float | None, artifact_id: ArtifactId | None = None,
        worker: _WorkspaceWorker | None = None,
    ) -> T:
        """在无内部等待队列的准入后，异步等待实际存储调用。

        :param operation: 在指定资源线程中执行的具体调用。
        :param event: 固定诊断事件。
        :param identity: 本次调用的原身份。
        :param timeout_seconds: 仅限制等待的正有限秒数；None 表示由调用方管理期限。
        :param artifact_id: 可选产物诊断关联，不决定准入或存储行为。
        :param worker: 指定文件线程池；省略时使用唯一元数据线程。
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
        selected = self._control_worker if worker is None else worker
        if not selected.available():
            raise WorkspaceBusyError("受管存储繁忙；本次未提交，请沿原身份对账")
        # 在提交前处理已有取消；后续直到保存 Future 没有协程挂起点。
        await asyncio.sleep(0)
        if self._closing is not None:
            raise WorkspaceClosedError("工作区宿主已经开始关闭")
        if not selected.available():
            raise WorkspaceBusyError("受管存储繁忙；本次未提交")
        context = _log_context(identity, artifact_id)
        if artifact_id is None:
            _LOGGER.info("workspace_%s_started workspace_id=%s", event, identity, extra=context)
        else:
            _LOGGER.info(
                "workspace_%s_started workspace_id=%s artifact_id=%s", event, identity, artifact_id.value,
                extra=context,
            )
        future: asyncio.Future[object] = self._loop.run_in_executor(selected.executor, operation)
        selected.pending.add(future)
        future.add_done_callback(partial(self._observe, selected, event, identity, artifact_id))
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                # wait 的取消不传播给实际 Future；终态由唯一 _observe 回调诊断。
                await asyncio.wait({future})
                return cast(T, future.result())
        except asyncio.CancelledError as error:
            _record_termination(error, logging.INFO, "workspace_wait_cancelled", identity, context=context)
            raise
        except TimeoutError:
            if deadline.expired():
                timeout = WorkspaceTimeoutError("等待超时；实际存储结果须按原身份对账")
                _record_termination(timeout, logging.INFO, "workspace_wait_timed_out", identity, context=context)
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

    def _bind_artifacts(self, workspace_id: WorkspaceId, max_file_bytes: int) -> WorkspaceArtifacts:
        """在控制线程绑定同一所有者的资产仓储及独立文件作用域。

        :param workspace_id: 已登记的固定工作区。
        :param max_file_bytes: 文件观察的部署字节上限。
        :returns: 实际消费 ArtifactAccess 的具体装配入口。
        """
        store = self._bind_file_store(workspace_id, max_file_bytes)
        assert self._repository is not None
        return WorkspaceArtifacts(self, workspace_id, self._repository.artifacts(workspace_id), store)

    async def artifacts(self, workspace_id: WorkspaceId, *, max_file_bytes: int) -> WorkspaceArtifacts:
        """建立固定工作区的真实资产目录消费者，不暴露根路径或上传权限。

        :param workspace_id: 已完成登记的实例作用域。
        :param max_file_bytes: 显式文件观察资源上限，不进入业务协议。
        :returns: 可注入生成服务的真实 ArtifactAccess，兼有可信单资产登记入口。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("资产装配必须使用 WorkspaceId")
        validate_file_byte_limit(max_file_bytes)
        return await self._invoke(
            partial(self._bind_artifacts, workspace_id, max_file_bytes),
            event="artifacts_bind", identity=str(workspace_id.value), timeout_seconds=None,
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
            for future in tuple(self._control_worker.pending | self._file_worker.pending):
                try:
                    await self._drain(future)
                except BaseException:
                    # 原调用错误由 _observe 及原调用方观察，关闭仍须继续。
                    pass
            closing = self._loop.run_in_executor(self._control_worker.executor, self._close_storage)
            await self._drain(closing)
        finally:
            # 先排空所有文件调用，再释放原根；此时回收线程不会等待文件 I/O。
            self._file_worker.executor.shutdown(wait=True)
            self._control_worker.executor.shutdown(wait=True)

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
            worker=self._runtime._file_worker,
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
            worker=self._runtime._file_worker,
        )


class WorkspaceArtifacts(ArtifactAccess):
    """组合固定工作区的持久目录及真实观察，不把登记视为文件或业务通过。"""

    def __init__(
        self, runtime: WorkspaceRuntime, workspace_id: WorkspaceId,
        repository: ArtifactRepository, store: ArtifactFileStore,
    ) -> None:
        """由 Bootstrap 注入窄端口，业务消费方只依赖 ArtifactAccess。

        :param runtime: 持有控制线程、文件线程和根锁的资源所有者。
        :param workspace_id: 固定的工作区及诊断关联。
        :param repository: 仅在控制线程调用的同步资产仓储。
        :param store: 各次调用独立取得文件描述符的实际文件端口。
        """
        self._runtime = runtime
        self._workspace_id = workspace_id
        self._repository = repository
        self._store = store

    def _metadata[T](self, operation: Callable[[], T]) -> T:
        """在唯一控制线程核对根仍受管后执行短仓储操作。

        :param operation: 固定仓储上的具体查询或单件提交。
        :returns: 仓储实际结果，不将异常降级为空。
        """
        self._runtime._ready_service()
        return operation()

    async def _call[T](self, operation: Callable[[], T], artifact_id: ArtifactId, event: str) -> T:
        """经所属宿主准入后调度短元数据调用，不把仓储交给文件线程。

        :param operation: 当前确切资产的仓储操作。
        :param artifact_id: 原产物诊断关联。
        :param event: 固定诊断名称。
        :returns: 已完成的元数据结果。
        """
        return await self._runtime._invoke(
            partial(self._metadata, operation), event=event, identity=str(self._workspace_id.value),
            artifact_id=artifact_id, timeout_seconds=None,
        )

    async def resolve(self, artifact_id: ArtifactId) -> LocatedArtifact | None:
        """查询已提交登记，文件缺失或改变不回写此元数据事实。

        :param artifact_id: 本次请求的确切产物身份。
        :returns: 原登记；没有登记时为空，查询失败仍传播异常。
        """
        if type(artifact_id) is not ArtifactId:
            raise TypeError("资产解析必须使用 ArtifactId")
        return await self._call(partial(self._repository.get, artifact_id), artifact_id, "artifact_resolve")

    async def get_origin(self, artifact_id: ArtifactId) -> ImportOrigin | None:
        """读取原出处，空值不证明未登记或来自真实拍摄。

        :param artifact_id: 要核对的原产物身份。
        :returns: 原导入说明；是否登记由 resolve 单独回答。
        """
        if type(artifact_id) is not ArtifactId:
            raise TypeError("出处查询必须使用 ArtifactId")
        return await self._call(partial(self._repository.get_origin, artifact_id), artifact_id, "artifact_origin")

    async def observe(self, location: WorkspaceFileLocation) -> FileObservation:
        """先核对已登记位置，再观察实际字节，不比较或改写原摘要。

        :param location: 从确切登记取得的原相对位置。
        :returns: 独立的文件存在、缺失或不可用事实。
        :raises ArtifactContractError: 未登记或位置不匹配，不能以文件存在认领资产。
        """
        if type(location) is not WorkspaceFileLocation:
            raise TypeError("资产观察必须使用 WorkspaceFileLocation")
        record = await self.resolve(location.artifact_id)
        if record is None or record.location != location:
            raise ArtifactContractError("资产观察需要确切的已登记位置")
        return await self._runtime._invoke(
            partial(self._store.observe, record.artifact, location), event="artifact_observe",
            identity=str(self._workspace_id.value), artifact_id=record.artifact.id,
            timeout_seconds=None, worker=self._runtime._file_worker,
        )

    def _existing(self, record: LocatedArtifact, origin: ImportOrigin | None) -> LocatedArtifact | None:
        """只对已有记录调用仓储的精确重放检查，不产生首次登记。

        :param record: 本次原身份、内容及位置声明。
        :param origin: 本次原出处声明。
        :returns: 完全匹配的原登记；未登记则为空。
        """
        if self._repository.get(record.artifact.id) is None:
            return None
        return self._repository.register(record, origin=origin)

    async def register(
        self, artifact: ArtifactIdentity, reference: FileReference, *,
        origin: ImportOrigin | None = None, timeout_seconds: float | None = 5.0,
    ) -> LocatedArtifact:
        """首次登记前核对真实文件，原身份精确重放只读回不可变记录。

        文件接收与目录登记分开；未完成观察不会自动推进后续数据库提交。
        已提交记录的重放不声称当前文件仍在，实际使用须另行 observe。

        :param artifact: 调用方已保留的原产物身份和工作区。
        :param reference: 原完整内容引用，不能由脚本报告替代实际字节。
        :param origin: 实际已知的导入出处，可为空，不推断来源类别。
        :param timeout_seconds: 整次等待期限，不进入登记记录或业务能力。
        :returns: 单件已提交登记；不代表验收或发布。
        :raises WorkspaceTimeoutError: 等待超时，已提交阶段需按原身份对账。
        :raises asyncio.CancelledError: 等待取消，已开始的实际 I/O 仍会终结。
        """
        location = self._store.location_for(artifact)
        record = LocatedArtifact(artifact, reference, location)
        validate_registration(record, workspace_id=self._workspace_id, origin=origin)
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
        ):
            raise ValueError("等待期限必须为正有限秒数")
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                existing = await self._call(partial(self._existing, record, origin), artifact.id, "artifact_replay")
                if existing is not None:
                    return existing
                observation = await self._runtime._invoke(
                    partial(self._store.observe, artifact, location), event="artifact_verify",
                    identity=str(self._workspace_id.value), artifact_id=artifact.id,
                    timeout_seconds=None, worker=self._runtime._file_worker,
                )
                require_matching_file(observation, reference=reference, artifact=artifact)
                return await self._call(
                    partial(self._repository.register, record, origin=origin), artifact.id, "artifact_register",
                )
        except TimeoutError:
            if deadline.expired():
                raise WorkspaceTimeoutError("登记等待超时；仅按原产物身份查询已提交事实") from None
            raise


async def initialize_workspaces(root: Path, *, max_file_operations: int = 2) -> WorkspaceRuntime:
    """显式初始化新的受管存储，失败或取消时释放本次取得的资源。

    :param root: 不存在或安全空目录的部署根。
    :param max_file_operations: 耗时文件 I/O 的有界并行上限，默认两个名额。
    :returns: 已打开的线程封闭工作区宿主。
    """
    runtime = WorkspaceRuntime(root, max_file_operations=max_file_operations)
    try:
        await runtime._invoke(runtime._initialize, event="initialize", identity="storage", timeout_seconds=None)
    except BaseException:
        await runtime.aclose()
        raise
    return runtime


async def open_workspaces(root: Path, *, max_file_operations: int = 2) -> WorkspaceRuntime:
    """只打开既有完整存储，缺库或布局异常不会触发初始化。

    :param root: 已初始化的部署根。
    :param max_file_operations: 本次部署的文件并行上限，不改变持久业务记录。
    :returns: 已核对并取得单写入资格的宿主。
    """
    runtime = WorkspaceRuntime(root, max_file_operations=max_file_operations)
    try:
        await runtime._invoke(runtime._open, event="open", identity="storage", timeout_seconds=None)
    except BaseException:
        await runtime.aclose()
        raise
    return runtime
