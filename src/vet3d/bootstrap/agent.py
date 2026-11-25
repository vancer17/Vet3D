# 文件信息：L2-02 阶段 B 的有限原生会话装配。
# 作用：把受信任务、已登记工作区、明确资料和原生连接注入同一隔离环境。
# 边界：只持有本进程关联，不登记业务作业、不解释模型反馈、不承诺宿主崩溃恢复。
"""集中管理原生接入的部署副作用，业务包不依赖 Codex 协议。"""

import asyncio
from dataclasses import dataclass
import fcntl
import logging
import os
from pathlib import Path
import shutil
import stat
import tempfile
import tomllib
from typing import Self

from vet3d.adapters import (
    AppServerStdioClient, CodexAgentSession, CodexDockerEnvironment,
    CodexEnvironmentCreationError, NativeProtocolError,
)
from vet3d.identity import TaskIdentity
from vet3d.resources import ResourceReference

from .environment import _collect
from .resources import ResourceRuntime
from .settings import Settings
from .workspaces import WorkspaceRuntime

_LOGGER = logging.getLogger("vet3d")


@dataclass(frozen=True, slots=True)
class _NativeConfiguration:
    """保存从唯一原生配置解析的连接选择，不建立另一套配置来源。

    :param text: 经本期支持字段校验的原 TOML。
    :param model: 原配置声明的模型。
    :param provider: 原配置声明的 provider。
    :param key_environment: 原 provider 声明的凭证环境变量名。
    """

    text: str
    model: str
    provider: str
    key_environment: str


def _read_native_configuration(path: Path) -> _NativeConfiguration:
    """读取专用原生配置，拒绝把开发目录或扩展配置带入控制面。

    :param path: 可信部署方选择的普通 TOML 文件。
    :returns: 原配置和直接派生的连接选择，不包含凭证值。
    :raises ValueError: 配置不是本期支持的单 provider 原生 Responses 连接。
    """
    with path.open("rb") as source:
        data = source.read(65537)
    if len(data) > 65536:
        raise ValueError("专用原生配置超过 64 KiB")
    text = data.decode("utf-8")
    value = tomllib.loads(text)
    allowed = {"model", "model_provider", "model_providers", "model_reasoning_effort", "model_reasoning_summary"}
    if set(value) - allowed:
        raise ValueError("原生配置仅接受模型和单 provider；不复制开发授权、扩展或行为开关")
    model, provider, providers = value.get("model"), value.get("model_provider"), value.get("model_providers")
    if not isinstance(model, str) or not model.strip() or not isinstance(provider, str) or not provider.strip():
        raise ValueError("必须在原生配置显式选择模型及 provider")
    if not isinstance(providers, dict) or set(providers) != {provider}:
        raise ValueError("本期只接受一个明确的原生 provider")
    selected = providers[provider]
    if not isinstance(selected, dict) or set(selected) != {"name", "base_url", "env_key", "wire_api"}:
        raise ValueError("provider 需要 name/base_url/env_key/wire_api，不接受内联凭证或扩展")
    if selected["wire_api"] != "responses" or not all(isinstance(item, str) and item for item in selected.values()):
        raise ValueError("本期连接需要原生 Responses 及非空文本字段")
    return _NativeConfiguration(text, model, provider, str(selected["env_key"]))


def _prepare_materials(source: Path, target: Path, input_root: Path) -> None:
    """以目录描述符逐层复制授权资料，限制实际读取字节及成员数量。

    :param source: 可信调用方选定的输入根内目录。
    :param target: 本次独占的新暂存目录，副本可继续修改。
    :param input_root: 配置允许的来源范围，不授予符号链接目标访问权。
    :raises ValueError: 路径越界、链接、特殊文件或超出 32 MiB／128 成员。
    :raises OSError: 实际打开或读取失败；不把部分复制当作成功。
    """
    actual_root, actual_source = input_root.absolute(), source.absolute()
    if ".." in actual_root.parts or ".." in actual_source.parts or not actual_source.is_relative_to(actual_root):
        raise ValueError("资料必须位于可信输入根，不能通过父路径越界")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open("/", directory_flags)
    size = count = 0

    def copy_directory(source_fd: int, destination: Path) -> None:
        """从已打开的原目录复制，后续路径替换不能切换到链接目标。

        :param source_fd: 已通过实际打开核对的目录描述符。
        :param destination: 本次私有暂存位置。
        :raises ValueError: 实际成员或读取内容不在允许范围。
        """
        nonlocal size, count
        destination.mkdir(mode=0o700)
        with os.scandir(source_fd) as entries:
            for entry in entries:
                count += 1
                if count > 128:
                    raise ValueError("任务资料超过 128 个成员")
                expected = entry.stat(follow_symlinks=False)
                is_directory = stat.S_ISDIR(expected.st_mode)
                if not is_directory and not stat.S_ISREG(expected.st_mode):
                    raise ValueError("任务资料不接受链接或特殊文件")
                flags = directory_flags if is_directory else os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                try:
                    child = os.open(entry.name, flags, dir_fd=source_fd)
                except OSError as error:
                    raise ValueError("任务资料在打开时已变化或不可访问") from error
                try:
                    actual = os.fstat(child)
                    if is_directory:
                        copy_directory(child, destination / entry.name)
                    else:
                        if not stat.S_ISREG(actual.st_mode):
                            raise ValueError("实际任务资料不是普通文件")
                        path = destination / entry.name
                        with path.open("xb") as output:
                            while data := os.read(child, min(65536, 32 * 1024 * 1024 - size + 1)):
                                size += len(data)
                                if size > 32 * 1024 * 1024:
                                    raise ValueError("任务资料实际读取超过 32 MiB")
                                output.write(data)
                        path.chmod(0o700 if actual.st_mode & 0o111 else 0o600)
                finally:
                    os.close(child)

    try:
        # 从固定根逐段打开全部目录，不让任一祖先符号链接改变授权范围。
        for part in actual_source.parts[1:]:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptor)
            except OSError as error:
                raise ValueError("资料必须是可信输入根内的真实目录") from error
            os.close(descriptor)
            descriptor = child
        copy_directory(descriptor, target)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class _OwnedSession:
    """保存一个任务实际拥有的资源及在途 I/O，不复制原生状态。

    :param environment: 唯一实际容器所有者，创建失败时同样保留。
    :param directory: 本次私有控制及材料目录。
    :param session: 已成功关联的会话；准备期间为空。
    :param connecting: 尚未交给会话的原连接，失败时仍需关闭。
    :param copying: 实际进行中的唯一输出复制操作。
    :param reconnecting: 原环境上的受信重连操作。
    :param closing: 单一关闭操作，取消等待不得撤销清理。
    """

    environment: CodexDockerEnvironment
    directory: Path
    session: CodexAgentSession | None = None
    connecting: AppServerStdioClient | None = None
    copying: asyncio.Task[None] | None = None
    reconnecting: asyncio.Task[CodexAgentSession] | None = None
    closing: asyncio.Task[None] | None = None


async def _drain[T](operation: asyncio.Task[T]) -> T:
    """在清理路径等待原操作排空，避免重复取消遗失仍在运行的 I/O。

    :param operation: 已经开始且由本宿主持有的原操作。
    :returns: 原操作的真实结果；其失败按原异常传播。
    """
    while True:
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            if operation.done():
                return operation.result()


class AgentRuntime:
    """向有限宿主交付具体会话，并持有其环境、准入和清理责任。"""

    def __init__(self, settings: Settings, workspaces: WorkspaceRuntime, resources: ResourceRuntime) -> None:
        """注入已打开的存储；本对象不替调用方获取业务授权。

        :param settings: 唯一配置入口的冻结部署值。
        :param workspaces: 已有工作区注册消费者。
        :param resources: 已有受管资源读取消费者。
        :raises ValueError: 没有显式 Agent 部署配置。
        """
        if settings.agent is None:
            raise ValueError("有限 Agent 接入需要显式 agent 配置")
        self._settings = settings.agent
        self._input_root = settings.files.input_root
        self._workspaces, self._resources = workspaces, resources
        self._configuration = _read_native_configuration(self._settings.native_config)
        self._loop = asyncio.get_running_loop()
        self._owned: dict[TaskIdentity, _OwnedSession] = {}
        self._opening: dict[TaskIdentity, asyncio.Task[CodexAgentSession]] = {}
        self._closing: asyncio.Task[None] | None = None
        root = self._settings.control_root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if root.resolve() != root.absolute() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("控制根必须是本用户拥有的私有真实目录")
        descriptor = os.open(root / ".owner.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(descriptor)
            raise
        self._lock: int | None = descriptor

    async def _connect(self, owned: _OwnedSession) -> AppServerStdioClient:
        """向原任务环境建立唯一原生连接，不重建工作文件。

        :param owned: 本宿主持有的确切环境。
        :returns: 已登记原环境的连接。
        """
        await asyncio.to_thread(owned.environment.require_running)
        client = await AppServerStdioClient.start(
            owned.environment.control_argv, cwd=owned.directory,
            env={"PATH": os.environ.get("PATH", os.defpath), "HOME": str(Path.home())},
            read_timeout_seconds=45, max_line_bytes=4 * 1024 * 1024,
            initialize_params={"clientInfo": {"name": "vet3d_stage_b", "version": "0.1.0"},
                               "capabilities": {"experimentalApi": True}},
        )
        owned.connecting = client
        initialized = client.initialization
        agent = initialized.get("userAgent") if initialized is not None else None
        if not isinstance(agent, str) or not agent.startswith("vet3d_stage_b/0.165.0 "):
            raise NativeProtocolError("本期仅核对 Codex 0.165.0；版本不符时不启动模型轮次")
        await client.request("environment/add", {
            "environmentId": "task", "execServerUrl": owned.environment.exec_server_url,
            "connectTimeoutMs": 5000,
        })
        return client

    async def _open(
        self, task: TaskIdentity, materials: Path, resource: ResourceReference | None,
        turn_timeout_seconds: float,
    ) -> CodexAgentSession:
        """在受保护的原装配操作中创建环境，取消等待也不遗失真实句柄。

        :param task: 可信调用方提供的原任务关系。
        :param materials: 明确授权的资料目录。
        :param resource: 可选的已安装根资源引用，其依赖按原清单读取。
        :param turn_timeout_seconds: 调用方的本次会话轮次等待预算。
        :returns: 已确认模型、线程和环境关联的原生会话。
        """
        if await self._workspaces.read(task.workspace_id) is None:
            raise ValueError("工作区尚未登记；任务身份不能替代登记或授权")
        directory = Path(tempfile.mkdtemp(prefix="session-", dir=self._settings.control_root))
        owned: _OwnedSession | None = None
        try:
            home = directory / "control"
            home.mkdir(mode=0o700)
            (home / "config.toml").write_text(self._configuration.text, encoding="utf-8")
            staging = directory / "materials"
            await asyncio.to_thread(_prepare_materials, materials, staging, self._input_root)
            if resource is not None:
                pinned = await self._resources.pin(resource.snapshot)
                destination = staging / "resources"
                destination.mkdir(exist_ok=False)
                written: set[str] = set()
                for description in _collect(pinned, resource):
                    for path in description.definition.files:
                        if path.value in written:
                            continue
                        data = await pinned.read_file(description.reference.key, path)
                        target = destination / path.value
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        target.chmod(0o444)
                        written.add(path.value)
            try:
                environment = await asyncio.to_thread(
                    CodexDockerEnvironment.create, image_id=self._settings.image_id,
                    codex_package=self._settings.codex_package, control_home=home, task_materials=staging,
                    model_http_proxy=self._settings.model_http_proxy,
                    model_api_key_env=self._configuration.key_environment,
                    lifetime_seconds=self._settings.lifetime_seconds, docker_context=self._settings.docker_context,
                )
            except CodexEnvironmentCreationError as error:
                owned = _OwnedSession(error.environment, directory)
                self._owned[task] = owned
                raise
            owned = _OwnedSession(environment, directory)
            self._owned[task] = owned
            client = await self._connect(owned)
            owned.connecting = client
            session = await CodexAgentSession.open(
                client, task, environment_id="task", cwd="/work", model=self._configuration.model,
                provider=self._configuration.provider, turn_timeout_seconds=turn_timeout_seconds,
            )
            owned.session, owned.connecting = session, None
            _LOGGER.info("agent_session_opened task=%s thread=%s", task.id.value, session.binding.thread_id)
            return session
        except BaseException as failure:
            try:
                if owned is not None:
                    await self._close_owned(task, owned)
                else:
                    shutil.rmtree(directory)
            except BaseException as cleanup_failure:
                raise BaseExceptionGroup("原生会话准备失败且清理未完成", [failure, cleanup_failure]) from None
            raise

    async def open_session(
        self, task: TaskIdentity, materials: Path, *, resource: ResourceReference | None = None,
        turn_timeout_seconds: float = 600,
    ) -> CodexAgentSession:
        """准入一个明确授权的任务，超额直接拒绝，不建立等待队列。

        :param task: 已有唯一任务关系，不逐工具创建任务。
        :param materials: 输入根内的授权资料目录。
        :param resource: 可选的原受管资源及其依赖闭包。
        :param turn_timeout_seconds: 会话的轮次等待预算，不修改环境硬寿命。
        :returns: 由本宿主持有的具体原生会话。
        :raises RuntimeError: 跨循环、关闭中、重复任务或并发限额已满。
        """
        if type(task) is not TaskIdentity:
            raise TypeError("会话必须使用原 TaskIdentity")
        if asyncio.get_running_loop() is not self._loop or self._closing is not None:
            raise RuntimeError("宿主关闭中或事件循环不符")
        if any(known.id == task.id for known in self._opening.keys() | self._owned.keys()):
            raise RuntimeError("同一任务已有会话，不重复启动")
        if len(self._opening.keys() | self._owned.keys()) >= self._settings.max_sessions:
            raise RuntimeError("原生环境并发限额已满")
        operation = asyncio.create_task(self._open(task, materials, resource, turn_timeout_seconds))
        self._opening[task] = operation
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            session = await _drain(operation)
            await _drain(asyncio.create_task(self.close_session(session)))
            raise
        finally:
            self._opening.pop(task, None)

    def _lookup(self, session: CodexAgentSession) -> _OwnedSession:
        """按原任务核对本实例真实会话，不接受外来或已替换的对象。

        :param session: 调用方持有的实际会话。
        :returns: 对应的唯一环境所有权。
        :raises ValueError: 会话不属于本宿主或已由重连替换。
        """
        owned = self._owned.get(session.binding.task)
        if owned is None or owned.session is not session:
            raise ValueError("会话不是本宿主当前持有的原关联")
        return owned

    def control_directory(self, session: CodexAgentSession) -> Path:
        """向受信诊断消费者定位原生记录，不交给建模代码。

        :param session: 本宿主当前持有的会话。
        :returns: 关闭前可读取的控制目录，不承诺长期保留。
        """
        return self._lookup(session).directory / "control"

    async def copy_outputs(self, session: CodexAgentSession, destination: Path) -> None:
        """持有并排空实际复制，不把取消等待当作文件 I/O 已停止。

        :param session: 本宿主当前持有的会话。
        :param destination: 尚不存在的诊断目录，不是正式资产登记。
        :raises RuntimeError: 关闭、重连或另一复制尚在进行。
        """
        owned = self._lookup(session)
        if self._closing is not None or owned.closing is not None or owned.reconnecting is not None or owned.copying is not None:
            raise RuntimeError("环境正在关闭、重连或复制，不能增加文件 I/O")
        operation = asyncio.create_task(asyncio.to_thread(owned.environment.copy_outputs, destination))
        owned.copying = operation
        try:
            await asyncio.shield(operation)
        except asyncio.CancelledError:
            await _drain(operation)
            raise
        finally:
            owned.copying = None

    async def reconnect(self, session: CodexAgentSession) -> CodexAgentSession:
        """在原环境和可信关联仍在时重开控制进程，不恢复整个宿主崩溃。

        :param session: 已结束且结果明确的当前会话。
        :returns: 保留原任务及 thread 的新连接消费者，旧对象不能再操作环境。
        :raises RuntimeError: 关闭、复制或重连已在进行。
        :raises NativeProtocolError: 原轮次不明或恢复回执不符。
        """
        owned = self._lookup(session)
        if self._closing is not None or owned.closing is not None or owned.copying is not None or owned.reconnecting is not None:
            raise RuntimeError("原环境已有关闭或 I/O，不能同时重连")
        session.ensure_resumable()
        operation = asyncio.create_task(self._reconnect(session, owned))
        owned.reconnecting = operation
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            try:
                await _drain(operation)
            finally:
                await _drain(asyncio.create_task(self._close_owned(session.binding.task, owned)))
            raise
        finally:
            owned.reconnecting = None

    async def _reconnect(self, session: CodexAgentSession, owned: _OwnedSession) -> CodexAgentSession:
        """重开原控制面并重绑原环境，失败时不释放其清理所有权。

        :param session: 拥有原 thread 和轮次预算的旧会话。
        :param owned: 本实例原环境，不创建替代工作文件。
        :returns: 沿原 thread 恢复的新消费者。
        """
        await session.aclose()
        await asyncio.to_thread(owned.environment.stop_control)
        client = await self._connect(owned)
        owned.connecting = client
        resumed = await CodexAgentSession.resume(
            client, session.binding, environment_id="task", cwd="/work",
            model=self._configuration.model, provider=self._configuration.provider,
            turn_timeout_seconds=session.turn_timeout_seconds,
        )
        owned.session, owned.connecting = resumed, None
        _LOGGER.info("agent_session_reconnected task=%s thread=%s", session.binding.task.id.value, session.binding.thread_id)
        return resumed

    async def close_session(self, session: CodexAgentSession) -> None:
        """关闭原环境，确认实际清理后才释放任务名额。

        :param session: 本宿主当前持有的会话。
        :raises BaseExceptionGroup: 原生关闭或环境清理失败，保留实际原因。
        """
        owned = self._lookup(session)
        await self._close_owned(session.binding.task, owned)

    async def _close_owned(self, task: TaskIdentity, owned: _OwnedSession) -> None:
        """关闭一个实际资源记录，未完成会话准备也使用同一清理路径。

        :param task: 资源所属的原任务。
        :param owned: 当前仍由本实例持有的资源。
        """
        if owned.closing is None or (owned.closing.done() and owned.closing.exception() is not None):
            owned.closing = asyncio.create_task(self._close_resources(task, owned))
        await asyncio.shield(owned.closing)

    async def _close_resources(self, task: TaskIdentity, owned: _OwnedSession) -> None:
        """排空已有 I/O 后收口原环境，原生关闭错误不能跳过实际清理。

        :param task: 原资源的唯一任务关联。
        :param owned: 本宿主实际拥有的环境和连接。
        :raises BaseExceptionGroup: 清理仍有未完成步骤；环境失败时保留名额。
        """
        for operation in (owned.copying, owned.reconnecting):
            if operation is not None:
                await asyncio.gather(operation, return_exceptions=True)
        errors: list[BaseException] = []
        if owned.session is not None:
            try:
                await owned.session.aclose()
            except BaseException as error:
                errors.append(error)
        if owned.connecting is not None:
            try:
                await owned.connecting.aclose()
            except BaseException as error:
                errors.append(error)
            else:
                owned.connecting = None
        try:
            await asyncio.to_thread(owned.environment.cleanup)
            shutil.rmtree(owned.directory)
        except BaseException as error:
            errors.append(error)
        else:
            self._owned.pop(task, None)
        if errors:
            raise BaseExceptionGroup("原生会话关闭存在未完成步骤", errors)

    async def _finish_close(self) -> None:
        """停止新准入后排空所有原创建和关闭，不遗失未完成环境。"""
        errors: list[BaseException] = []
        for operation in tuple(self._opening.values()):
            try:
                await operation
            except BaseException as error:
                errors.append(error)
        for task, owned in tuple(self._owned.items()):
            try:
                await self._close_owned(task, owned)
            except BaseException as error:
                errors.append(error)
        if not self._owned and self._lock is not None:
            os.close(self._lock)
            self._lock = None
        if errors:
            raise BaseExceptionGroup("有限原生宿主未完整关闭", errors)

    async def aclose(self) -> None:
        """停止新准入并等待原关闭，取消当前等待不取消实际清理。"""
        if self._closing is None or (self._closing.done() and self._closing.exception() is not None):
            self._closing = asyncio.create_task(self._finish_close())
        await asyncio.shield(self._closing)

    async def __aenter__(self) -> Self:
        """交付已装配的有限宿主。

        :returns: 当前实例。
        """
        return self

    async def __aexit__(self, *args: object) -> None:
        """退出时排空原环境；不保留另一套运行时后台循环。

        :param args: 上下文退出参数，不改变环境清理责任。
        """
        cancelled = False
        while True:
            try:
                await self.aclose()
                break
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
