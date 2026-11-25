# 文件信息：L2-02 阶段 A 的具体 Docker 双容器实验装配。
# 作用：控制面承载原生 app-server，任务环境承载原生 exec-server；不增加执行转发或 Agent 循环。
# 边界：仅用于有限实验；临时任务文件不跨容器重启保存，输出复制不是正式资产接收或登记。
"""复用 Docker isolated 网络和原生远程环境，不启动模型轮次。"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
from tempfile import TemporaryFile
from typing import Self
from uuid import uuid4


_PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def _docker(*args: str, environment: dict[str, str] | None = None) -> str:
    """运行有限 Docker 管理命令，失败保留原始诊断。

    :param args: 不经 shell 解析的参数；凭证不得放入参数。
    :param environment: 仅控制容器创建时显式传入代理及模型凭证环境。
    :returns: 标准输出。
    :raises subprocess.SubprocessError: 命令失败或超过管理期限，不能认定操作已完成。
    """
    return subprocess.run(
        ("docker", *args), check=True, capture_output=True, text=True,
        timeout=45, env=environment,
    ).stdout.strip()


def _copy_materials(materials: Path, executor: str) -> None:
    """将受信准备材料送入固定 /work，保留只读根文件系统。

    :param materials: prepare_task_materials 创建的本次材料目录。
    :param executor: 本次拥有的执行容器。
    :raises ValueError: 材料包含符号链接或特殊文件。
    :raises subprocess.SubprocessError: 受信复制失败或超时，不启动模型。
    """
    for path in materials.rglob("*"):
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("实验准备材料不允许符号链接或特殊文件")
    with TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode="w") as stream:
            stream.add(materials, arcname=".")
        archive.seek(0)
        subprocess.run(
            ("docker", "exec", "-i", executor, "tar", "--no-same-owner", "-xf", "-", "-C", "/work"),
            stdin=archive, check=True, capture_output=True, timeout=45,
        )


def _owner_id() -> str:
    """生成本次临时资源标签，不创建业务身份。

    :returns: 仅用于清理所有权的随机标识。
    """
    return uuid4().hex


@dataclass(slots=True)
class NativeAgentDockerEnvironment:
    """保存本次具体实验拥有的 Docker 资源及原生连接入口。

    :param control_argv: 交给现有 stdio 客户端的启动命令。
    :param exec_server_url: 原生 environment/add 使用的内部地址。
    """

    control_argv: tuple[str, ...] = field(init=False, default=())
    exec_server_url: str = field(init=False, default="")
    _owner: str = field(default_factory=_owner_id, init=False)
    _containers: list[str] = field(default_factory=list, init=False)
    _network_requested: bool = field(default=False, init=False)

    @classmethod
    def create(
        cls, *, image_id: str, codex_package: Path, control_home: Path,
        task_materials: Path, model_http_proxy: str | None = None,
        model_api_key_env: str | None = None,
    ) -> Self:
        """准备隔离任务和控制容器，模型会话仍由调用方明确创建。

        :param image_id: 已存在且经调用方确认来源的本地镜像身份；不拉取或构建。
        :param codex_package: 包含 bin/codex 的本地原生发行目录，只读挂载。
        :param control_home: 专用控制面目录，可含运行时认证；绝不挂入执行容器。
        :param task_materials: 受信准备的本次任务目录，复制到执行容器 /work。
        :param model_http_proxy: 控制面模型 HTTP/HTTPS 代理；为空则显式禁用代理。
        :param model_api_key_env: 宿主中非空模型凭证的变量名；须为大写且以 _API_KEY 结尾，仅注入控制容器。
        :returns: 尚未启动控制 app-server 的具体实验环境。
        :raises OSError: 显式目录或原生程序不可用。
        :raises ValueError: 凭证变量名不符合限定格式或变量缺失／为空；创建资源前拒绝。
        :raises subprocess.SubprocessError: Docker 操作失败，已请求资源按所有权清理。
        """
        credential_args: tuple[str, ...] = ()
        model_api_key: str | None = None
        if model_api_key_env is not None:
            if re.fullmatch(r"[A-Z_][A-Z0-9_]*_API_KEY", model_api_key_env) is None:
                raise ValueError("模型凭证变量名必须为大写环境变量且以 _API_KEY 结尾")
            model_api_key = os.environ.get(model_api_key_env)
            if not model_api_key:
                raise ValueError("指定的模型凭证环境变量缺失或为空")
            credential_args = ("--env", model_api_key_env)
        package, home, materials = (path.resolve(strict=True) for path in (
            codex_package, control_home, task_materials,
        ))
        if not all(path.is_dir() for path in (package, home, materials)) or not (package / "bin/codex").is_file():
            raise ValueError("实验需要现有原生发行目录、控制目录和任务材料目录")
        instance = cls()
        network = f"vet3d-stage-a-{instance._owner}"
        control, executor = network + "-control", network + "-executor"
        try:
            instance._network_requested = True
            _docker("network", "create", "--internal", "--label", f"vet3d.stage-a={instance._owner}",
                    "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated", network)
            uid, gid = os.getuid(), os.getgid()
            common = ["--read-only", "--user", f"{uid}:{gid}", "--cap-drop", "ALL",
                      "--security-opt", "no-new-privileges:true", "--sysctl", "net.ipv4.ip_forward=0",
                      "--memory", "2g", "--memory-swap", "2g", "--cpus", "2", "--pids-limit", "128",
                      "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                      "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864,mode=1777",
                      "--tmpfs", f"/work:rw,nosuid,nodev,size=201326592,uid={uid},gid={gid},mode=0700",
                      "--label", f"vet3d.stage-a={instance._owner}",
                      "--mount", f"type=bind,source={package},target=/opt/codex,readonly"]
            instance._containers.append(executor)
            _docker("create", "--name", executor, "--network", network, *common,
                    *[part for name in _PROXY_NAMES for part in ("--env", name + "=")],
                    "--env", "HOME=/work", "--env", "CODEX_HOME=/work",
                    "--env", "NO_PROXY=", "--env", "no_proxy=", image_id,
                    "/opt/codex/bin/codex", "exec-server", "--listen", "ws://0.0.0.0:47001")
            _docker("start", executor)
            _copy_materials(materials, executor)
            address = _docker("inspect", "--format",
                              '{{(index .NetworkSettings.Networks "' + network + '").IPAddress}}', executor)
            instance.exec_server_url = f"ws://{address}:47001"
            instance._containers.insert(0, control)
            proxy_env = {**os.environ, **{name: "" for name in _PROXY_NAMES}}
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                proxy_env[name] = model_http_proxy or ""
            if model_api_key_env is not None and model_api_key is not None:
                proxy_env[model_api_key_env] = model_api_key
            _docker("create", "-i", "--name", control, "--network", "bridge", *common,
                    "--mount", f"type=bind,source={home},target=/control",
                    "--env", "HOME=/control", "--env", "CODEX_HOME=/control",
                    *[part for name in _PROXY_NAMES for part in ("--env", name)],
                    *credential_args,
                    "--env", f"NO_PROXY={address},localhost,127.0.0.1",
                    "--env", f"no_proxy={address},localhost,127.0.0.1", image_id,
                    "/opt/codex/bin/codex",
                    "--disable", "apps", "--disable", "plugins", "--disable", "remote_plugin",
                    "--disable", "browser_use", "--disable", "computer_use", "--disable", "multi_agent",
                    "-c", 'web_search="disabled"',
                    "app-server", "--listen", "stdio://", environment=proxy_env)
            _docker("network", "connect", network, control)
            instance.control_argv = ("docker", "start", "-ia", control)
            return instance
        except BaseException as error:
            try:
                instance.cleanup()
            except Exception as cleanup_error:
                raise BaseExceptionGroup("实验准备及资源清理均失败", [error, cleanup_error]) from None
            raise

    def copy_outputs(self, destination: Path) -> None:
        """有界复制固定 outputs 供查看，不登记资产或承诺并发内容一致。

        :param destination: 尚不存在的目标，成功后包含 outputs 子目录。
        :raises OSError: 目标已存在或不可创建。
        :raises ValueError: 归档超过 32 MiB／128 成员，或含链接、特殊文件和越界路径。
        :raises subprocess.SubprocessError: 原输出不可取得；不自动重启模型或认定 I/O 已停止。
        """
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        executor = f"vet3d-stage-a-{self._owner}-executor"
        args = ("docker", "exec", executor, "tar", "-cf", "-", "-C", "/work", "outputs")
        with TemporaryFile() as archive:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                subprocess.run(("head", "-c", "33554433"), stdin=process.stdout,
                               stdout=archive, check=True, timeout=45)
                if archive.tell() > 32 * 1024 * 1024:
                    raise ValueError("实验输出归档超过 32 MiB")
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
                        raise ValueError("实验输出成员过多，或包含链接、特殊文件")
                    if not (member.name == "outputs" or member.name.startswith("outputs/")):
                        raise ValueError("实验输出必须位于固定 outputs 目录")
                    members.append(member)
                stream.extractall(destination, members=members, filter="data")

    def _owns(self, kind: str, name: str) -> bool:
        """在清理边界确认本次标签，不处理同名但不属于本实验的资源。

        :param kind: Docker 的 container 或 network 资源类别。
        :param name: 本次请求的确切资源名称。
        :returns: 资源仍存在且标签属于本次实验。
        :raises subprocess.SubprocessError: 无法查询真实状态，不能假定资源已删除。
        """
        label = '.Config.Labels' if kind == "container" else '.Labels'
        try:
            owner = _docker(kind, "inspect", "--format", '{{index ' + label + ' "vet3d.stage-a"}}', name)
        except subprocess.CalledProcessError as error:
            if f"No such container: {name}" in error.stderr or f"network {name} not found" in error.stderr:
                return False
            raise
        return owner == self._owner

    def cleanup(self) -> None:
        """依次停止控制面、执行环境并删除网络，保留所有清理失败。

        :raises ExceptionGroup: 任一步骤未完成；不能把等待超时当作实际进程停止。
        """
        errors: list[Exception] = []
        for name in self._containers:
            try:
                if self._owns("container", name):
                    _docker("stop", "--timeout", "10", name)
                    _docker("rm", name)
            except Exception as error:
                errors.append(error)
        network = f"vet3d-stage-a-{self._owner}"
        try:
            if self._network_requested and self._owns("network", network):
                _docker("network", "rm", network)
        except Exception as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup("本次原生 Agent 实验清理未完成", errors)
