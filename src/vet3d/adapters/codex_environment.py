# 文件信息：L2-02 有限宿主使用的具体 Docker 原生任务环境。
# 作用：装配控制侧 app-server 与执行侧 exec-server，管理本实例拥有的环境及有限输出。
# 边界：不分派工具、不维护执行账本；工作文件为 tmpfs，环境删除后不能恢复。
"""复用原生远程环境、Docker 隔离及系统期限工具，不实现第二套 Agent 内核。"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
from tempfile import TemporaryFile
import time
from typing import Self
from uuid import uuid4


_PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
_LABEL = "vet3d.native-session"
# 原截止时间属于环境实例；控制容器重开也只取得剩余期限，不延长原任务环境。
_EXPIRING_COMMAND = (
    'remaining=$(( $1 - $(date +%s) )); shift; '
    '[ "$remaining" -gt 0 ] || exit 124; '
    'exec /usr/bin/timeout --signal=TERM --kill-after=5s "$remaining" "$@"'
)


def _owner_id() -> str:
    """生成环境清理所有权标识，不产生业务任务或执行身份。

    :returns: 本次环境独有的标签值。
    """
    return uuid4().hex


def _validate_materials(materials: Path) -> None:
    """拒绝授权材料中的链接和特殊文件，不把路径检查当作内容冻结。

    :param materials: 可信装配已经授权的独立材料目录。
    :raises ValueError: 材料不是普通目录、普通文件或包含链接。
    """
    for path in (materials, *materials.rglob("*")):
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("任务材料不允许符号链接或特殊文件")


class CodexEnvironmentCreationError(RuntimeError):
    """保存创建及清理同时失败时的原环境，允许所有者继续收口。"""

    def __init__(self, environment: "CodexDockerEnvironment", failures: BaseExceptionGroup[BaseException]) -> None:
        """保留可重试清理的原资源所有者和实际失败链。

        :param environment: 已请求部分资源但尚未完全清理的原实例。
        :param failures: 创建失败与清理失败的原始异常组。
        """
        super().__init__("环境创建失败且清理未完成；必须沿原 environment 继续清理")
        self.environment = environment
        self.failures = failures


@dataclass(slots=True)
class CodexDockerEnvironment:
    """管理本次原生会话环境，不维护其工具进程状态。

    :param docker_context: 所有管理及连接命令使用的同一 Docker context。
    :param deadline_epoch: 创建时确定的环境截止时间，重连不重新计时。
    :param exec_server_url: 原生 environment/add 使用的内部地址。
    """

    docker_context: str
    deadline_epoch: int
    exec_server_url: str = field(init=False, default="")
    _owner: str = field(default_factory=_owner_id, init=False)
    _containers: list[str] = field(default_factory=list, init=False)
    _network_requested: bool = field(default=False, init=False)

    @property
    def control_name(self) -> str:
        """返回本实例控制容器的确切名字。

        :returns: 原生会话控制容器名。
        """
        return f"vet3d-native-{self._owner}-control"

    @property
    def executor_name(self) -> str:
        """返回本实例执行容器的确切名字。

        :returns: 原生工具任务容器名。
        """
        return f"vet3d-native-{self._owner}-executor"

    @property
    def control_argv(self) -> tuple[str, ...]:
        """构造附着原控制容器的命令，不创建替代环境或延长期限。

        :returns: 交给唯一 stdio 客户端的参数序列。
        """
        return (*self._prefix(), "start", "-ia", self.control_name)

    def _prefix(self) -> tuple[str, ...]:
        """取得所有管理和连接命令共用的 Docker 目标。

        :returns: 显式固定 context 的 Docker 命令前缀。
        """
        return ("docker", "--context", self.docker_context)

    def _docker(self, *args: str, environment: dict[str, str] | None = None) -> str:
        """执行一个有期限的具体管理命令，不自动重试或隐藏失败。

        :param args: 不经 shell 解释的管理参数。
        :param environment: 控制容器创建时显式提供的凭证及代理环境。
        :returns: 管理命令标准输出。
        :raises subprocess.SubprocessError: 管理调用失败或超时，不能推导操作未受理。
        """
        return subprocess.run(
            (*self._prefix(), *args), check=True, capture_output=True, text=True,
            timeout=45, env=environment,
        ).stdout.strip()

    @classmethod
    def create(
        cls, *, image_id: str, codex_package: Path, control_home: Path,
        task_materials: Path, model_http_proxy: str | None = None,
        model_api_key_env: str | None = None, lifetime_seconds: int = 1200,
        docker_context: str = "default",
    ) -> Self:
        """准备具体双容器环境，模型轮次由已装配会话明确提交。

        :param image_id: 已存在并已核对来源的本地镜像，不下载或构建。
        :param codex_package: 含 bin/codex 的既有原生发行目录。
        :param control_home: 可信装配提供的专用控制目录，不挂入执行容器。
        :param task_materials: 已授权的独立材料；普通工作副本可由 Agent 修改。
        :param model_http_proxy: 仅控制侧使用的显式 HTTP 代理。
        :param model_api_key_env: 仅控制侧注入的模型凭证环境变量名。
        :param lifetime_seconds: 自创建起的环境期限，另有五秒系统强制停止宽限。
        :param docker_context: 所有创建、查询和 stdio 连接使用的显式 Docker context。
        :returns: 执行环境已经启动、控制容器尚未启动的实例。
        :raises ValueError: 路径、材料、身份参数、期限或凭证不合法。
        :raises OSError: 必需目录或程序不可访问。
        :raises subprocess.SubprocessError: 管理操作失败；不自动重试。
        :raises CodexEnvironmentCreationError: 创建和清理均失败，异常保留原环境及实际失败链。
        """
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 86400:
            raise ValueError("环境期限必须为 1 到 86400 秒的整数")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", docker_context):
            raise ValueError("必须提供明确 Docker context")
        if not image_id or image_id.startswith("-"):
            raise ValueError("必须提供明确的既有镜像")
        credential_args: tuple[str, ...] = ()
        model_api_key: str | None = None
        if model_api_key_env is not None:
            if re.fullmatch(r"[A-Z_][A-Z0-9_]*_API_KEY", model_api_key_env) is None:
                raise ValueError("模型凭证变量名必须为大写且以 _API_KEY 结尾")
            model_api_key = os.environ.get(model_api_key_env)
            if not model_api_key:
                raise ValueError("指定模型凭证缺失或为空")
            credential_args = ("--env", model_api_key_env)
        package, home, materials = (path.resolve(strict=True) for path in (
            codex_package, control_home, task_materials,
        ))
        if not all(path.is_dir() for path in (package, home, materials)) or not (package / "bin/codex").is_file():
            raise ValueError("需要既有发行目录、专用控制目录和任务材料目录")
        _validate_materials(materials)
        uid, gid = os.getuid(), os.getgid()
        if uid == 0:
            raise ValueError("有限宿主须使用非 root 用户，任务身份不能为 root")
        instance = cls(docker_context, int(time.time()) + lifetime_seconds)
        network = f"vet3d-native-{instance._owner}"
        expiry = (
            "/bin/sh", "-c", _EXPIRING_COMMAND, "vet3d-environment-deadline",
            str(instance.deadline_epoch), "/usr/bin/setpriv", f"--reuid={uid}", f"--regid={gid}",
            "--clear-groups", "--inh-caps=-all", "--ambient-caps=-all",
        )
        try:
            instance._network_requested = True
            instance._docker("network", "create", "--internal", "--label", f"{_LABEL}={instance._owner}",
                             "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated", network)
            common = [
                "--read-only", "--init", "--user", "0:0", "--cap-drop", "ALL",
                "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "KILL",
                "--security-opt", "no-new-privileges:true",
                "--sysctl", "net.ipv4.ip_forward=0", "--memory", "2g", "--memory-swap", "2g",
                "--cpus", "2", "--pids-limit", "128", "--ulimit", "fsize=33554432:33554432",
                "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864,mode=1777",
                "--tmpfs", f"/work:rw,nosuid,nodev,size=201326592,uid={uid},gid={gid},mode=0700",
                "--label", f"{_LABEL}={instance._owner}",
                "--mount", f"type=bind,source={package},target=/opt/codex,readonly",
            ]
            resource_mount: list[str] = []
            if (materials / "resources").is_dir():
                resource_mount = ["--mount", f"type=bind,source={materials / 'resources'},target=/work/resources,readonly"]
            instance._containers.append(instance.executor_name)
            instance._docker(
                "create", "--pull=never", "--name", instance.executor_name, "--network", network, *common, *resource_mount,
                *[part for name in _PROXY_NAMES for part in ("--env", name + "=")],
                "--env", "HOME=/work", "--env", "CODEX_HOME=/work", "--env", "NO_PROXY=", "--env", "no_proxy=",
                image_id, *expiry, "/opt/codex/bin/codex", "exec-server", "--listen", "ws://0.0.0.0:47001",
            )
            instance._docker("start", instance.executor_name)
            instance._copy_materials(materials)
            address = instance._docker(
                "inspect", "--format", '{{(index .NetworkSettings.Networks "' + network + '").IPAddress}}',
                instance.executor_name,
            )
            instance.exec_server_url = f"ws://{address}:47001"
            instance._containers.insert(0, instance.control_name)
            proxy_env = {**os.environ, **{name: "" for name in _PROXY_NAMES}}
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                proxy_env[name] = model_http_proxy or ""
            if model_api_key_env is not None and model_api_key is not None:
                proxy_env[model_api_key_env] = model_api_key
            instance._docker(
                "create", "--pull=never", "-i", "--name", instance.control_name, "--network", "bridge", *common,
                "--mount", f"type=bind,source={home},target=/control",
                "--env", "HOME=/control", "--env", "CODEX_HOME=/control",
                *[part for name in _PROXY_NAMES for part in ("--env", name)], *credential_args,
                "--env", f"NO_PROXY={address},localhost,127.0.0.1", "--env", f"no_proxy={address},localhost,127.0.0.1",
                image_id, *expiry, "/opt/codex/bin/codex", "--disable", "apps", "--disable", "plugins",
                "--disable", "remote_plugin", "--disable", "browser_use", "--disable", "computer_use",
                "--disable", "multi_agent", "-c", 'web_search="disabled"', "app-server", "--listen", "stdio://",
                environment=proxy_env,
            )
            instance._docker("network", "connect", network, instance.control_name)
            instance.require_running()
            return instance
        except BaseException as error:
            try:
                instance.cleanup()
            except Exception as cleanup_error:
                failures = BaseExceptionGroup("环境准备及清理均失败", [error, cleanup_error])
                raise CodexEnvironmentCreationError(instance, failures) from failures
            raise

    def _copy_materials(self, materials: Path) -> None:
        """复制授权普通工作材料；资源闭包已独立只读挂载，不重复写入。

        :param materials: 已在创建边界核对的受信材料目录。
        :raises subprocess.SubprocessError: 复制失败或超时，不启动模型轮次。
        """
        with TemporaryFile() as archive:
            with tarfile.open(fileobj=archive, mode="w") as stream:
                for path in materials.iterdir():
                    if path.name != "resources":
                        stream.add(path, arcname=path.name)
            archive.seek(0)
            subprocess.run(
                (*self._prefix(), "exec", "--user", f"{os.getuid()}:{os.getgid()}", "-i", self.executor_name,
                 "tar", "--no-same-owner", "-xf", "-", "-C", "/work"),
                stdin=archive, check=True, capture_output=True, timeout=45,
            )

    def _owns(self, kind: str, name: str) -> bool:
        """核对实际资源的本实例标签，不处理同名的其他所有者资源。

        :param kind: container 或 network。
        :param name: 本实例已经请求创建的确切名字。
        :returns: 资源存在且标签匹配；不存在返回假。
        :raises subprocess.SubprocessError: 无法取得可信实际状态。
        """
        label = ".Config.Labels" if kind == "container" else ".Labels"
        try:
            owner = self._docker(kind, "inspect", "--format", '{{index ' + label + ' "' + _LABEL + '"}}', name)
        except subprocess.CalledProcessError as error:
            if f"No such container: {name}" in error.stderr or f"network {name} not found" in error.stderr:
                return False
            raise
        return owner == self._owner

    def require_running(self) -> None:
        """核对原执行环境仍在运行且未过期；不要求控制进程正在运行。

        :raises RuntimeError: 原执行环境失效，不得新建空环境冒充恢复。
        """
        if time.time() >= self.deadline_epoch or not self._owns("container", self.executor_name):
            raise RuntimeError("原执行环境不存在或已过期，不能恢复任务文件")
        if self._docker("inspect", "--format", "{{.State.Running}}", self.executor_name) != "true":
            raise RuntimeError("原执行环境已经停止，不能恢复任务文件")

    def _stop_container(self, name: str) -> None:
        """沿本实例所有权停止一个容器，并核对实际停止事实。

        :param name: 本实例实际拥有的容器。
        :raises RuntimeError: 停止回包后仍未确认退出。
        :raises subprocess.SubprocessError: 管理或状态读取失败。
        """
        if not self._owns("container", name):
            return
        self._docker("stop", "--timeout", "5", name)
        if self._docker("inspect", "--format", "{{.State.Running}}", name) != "false":
            raise RuntimeError("容器停止尚未确认，不能释放环境所有权")

    def stop_control(self) -> None:
        """只停止原控制容器，用于原任务环境仍存活时的有限控制重开。

        :raises Exception: 无法确认原控制容器停止。
        """
        self._stop_container(self.control_name)

    def stop(self) -> None:
        """停止本实例控制及执行容器，不将轮次中断等同进程停止。

        :raises ExceptionGroup: 任一容器停止未确认，保留其所有权和现场。
        """
        errors: list[Exception] = []
        for name in self._containers:
            try:
                self._stop_container(name)
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("原生任务环境未完全停止", errors)

    def cleanup(self) -> None:
        """停止并删除本实例资源；不清理其他任务、控制历史或宿主材料。

        :raises ExceptionGroup: 任一步骤失败，不伪造环境已经完全释放。
        """
        errors: list[Exception] = []
        for name in self._containers:
            try:
                if self._owns("container", name):
                    self._stop_container(name)
                    self._docker("rm", name)
            except Exception as error:
                errors.append(error)
        network = f"vet3d-native-{self._owner}"
        try:
            if self._network_requested and self._owns("network", network):
                self._docker("network", "rm", network)
        except Exception as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup("原生任务环境清理未完成", errors)

    def copy_outputs(self, destination: Path) -> None:
        """有界接收 outputs 供诊断，不登记正式资产或承诺并发内容一致。

        :param destination: 尚不存在的诊断目标目录。
        :raises ValueError: 归档超 32 MiB／128 成员，或含链接、特殊文件和越界路径。
        :raises OSError: 目录不可创建或文件写入失败。
        :raises subprocess.SubprocessError: 输出传输失败，不自动重启任务。
        """
        self.require_running()
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        args = (*self._prefix(), "exec", "--user", f"{os.getuid()}:{os.getgid()}",
                self.executor_name, "tar", "-cf", "-", "-C", "/work", "outputs")
        with TemporaryFile() as archive:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                subprocess.run(("head", "-c", "33554433"), stdin=process.stdout, stdout=archive, check=True, timeout=45)
                if archive.tell() > 32 * 1024 * 1024:
                    raise ValueError("诊断输出归档超过 32 MiB")
                _, stderr = process.communicate(timeout=5)
                if process.returncode:
                    raise subprocess.CalledProcessError(process.returncode, args, stderr=stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode="r:") as stream:
                members: list[tarfile.TarInfo] = []
                for member in stream:
                    if len(members) >= 128 or not (member.isfile() or member.isdir()):
                        raise ValueError("诊断输出成员过多或包含链接、特殊文件")
                    if not (member.name == "outputs" or member.name.startswith("outputs/")):
                        raise ValueError("诊断输出必须位于 outputs 目录")
                    members.append(member)
                stream.extractall(destination, members=members, filter="data")
