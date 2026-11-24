# 文件信息：L2-01 Debian/Linux 受信环境探针适配器。
# 作用：仅执行产品内固定自检，在有限并发、时间和输出预算内观察 Python／Blender CPU 环境。
# 边界：不执行资源脚本或用户代码，不安装依赖，不是执行沙箱或可重启恢复的执行账本。
"""管理有限探针原进程组的启动、排空及清理，不把退出码直接当作环境合格。"""

import asyncio
from collections.abc import Mapping
import json
import logging
import os
from pathlib import Path
import signal
import shutil
import sys
import tempfile
from typing import Never, cast

from vet3d.operations import (
    EnvironmentObservation, EnvironmentProbe, ProbeError, ProbeLimits, supported_dependencies,
)

_PREFIX = "VET3D_ENVIRONMENT_V1="
_LOGGER = logging.getLogger("vet3d")
_PYTHON_PAYLOAD = '''# 文件信息：产品内固定 Python CPU 与 SQLite 自检，无用户输入。
"""在独立受信进程返回本次环境观察，不读写业务资产。"""
import json
import platform
import sys
dependencies = []
try:
    import sqlite3
except ImportError:
    pass
else:
    try:
        with sqlite3.connect(":memory:") as connection:
            if connection.execute("select 6 * 7").fetchone() == (42,):
                dependencies.append("sqlite3")
    except sqlite3.Error:
        pass
print("VET3D_ENVIRONMENT_V1=" + json.dumps({
    "python_version": list(sys.version_info[:3]),
    "blender_version": None,
    "dependencies": dependencies,
    "cpu_check": sum(value * value for value in range(16)) == 1240,
    "platform": platform.system(),
    "machine": platform.machine(),
}), flush=True)
'''
_BLENDER_PAYLOAD = '''# 文件信息：产品内固定 Blender CPU 数据自检，无用户输入或渲染。
"""用临时内存网格和向量运算观察实际 Blender Python 环境。"""
import json
import platform
import sys
import bpy
dependencies = []
mesh = None
cpu_check = False
try:
    mesh = bpy.data.meshes.new("vet3d_environment_probe")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mesh.update()
    cpu_check = len(mesh.vertices) == 3 and len(mesh.polygons) == 1
    if cpu_check:
        dependencies.append("bpy")
except Exception:
    cpu_check = False
finally:
    if mesh is not None:
        bpy.data.meshes.remove(mesh)
try:
    import mathutils
    if mathutils.Vector((3, 4, 0)).length == 5:
        dependencies.append("mathutils")
except (ImportError, ValueError):
    pass
print("VET3D_ENVIRONMENT_V1=" + json.dumps({
    "python_version": list(sys.version_info[:3]),
    "blender_version": list(bpy.app.version),
    "dependencies": dependencies,
    "cpu_check": cpu_check,
    "platform": platform.system(),
    "machine": platform.machine(),
}), flush=True)
'''


def _log(
    event: str, runtime: str, *, reason: str = "none", level: int = logging.INFO, exc_info: bool = False,
) -> None:
    """输出有限事件，诊断接收故障不能改写探针事实或跳过清理。

    :param event: 产品定义的固定事件名。
    :param runtime: 已核对的固定运行环境名称。
    :param reason: 产品定义的有限原因，不包含输出或配置转储。
    :param level: 按实际失败影响选择的日志级别。
    :param exc_info: 非预期边界错误是否保留当前异常堆栈。
    """
    try:
        _LOGGER.log(level, "%s runtime=%s reason=%s", event, runtime, reason, exc_info=True if exc_info else None)
    except Exception:
        try:
            sys.stderr.write("environment_probe_diagnostic_failed\n")
        except (OSError, UnicodeError):
            pass


async def _settle[T](task: asyncio.Task[T]) -> T:
    """沿同一实际操作等待结果，清理所有者不受重复取消破坏。

    :param task: 已经开始的唯一操作，不新建替代操作。
    :returns: 原操作完成的结果。
    """
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


def _group_running(group: int) -> bool:
    """检查 Linux 原进程组中仍可执行的成员，已终止僵尸不作为运行任务。

    :param group: 本探针通过新会话创建的原进程组 ID。
    :returns: 至少一个非僵尸成员仍存在时为真。
    :raises OSError: 无法确认进程状态时拒绝假定排空。
    """
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            stat = (entry / "stat").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        fields = stat[stat.rfind(b")") + 2:].split()
        if len(fields) < 3:
            raise OSError("无法解析进程组观察")
        if int(fields[2]) == group and fields[0] not in (b"Z", b"X"):
            return True
    return False


def _signal_group(group: int, action: signal.Signals) -> None:
    """只向本探针原会话的进程组发出终止信号。

    :param group: 原 create_subprocess_exec 返回的 PID 及独立组 ID。
    :param action: TERM 或 KILL；信号发出不等于实际停止。
    """
    try:
        os.killpg(group, action)
    except ProcessLookupError:
        pass


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """拒绝协议中重复 JSON 字段，不能用最后一个值覆盖先前证据。

    :param pairs: JSON 解码器按原顺序提供的字段。
    :returns: 没有重复键的原字段映射。
    :raises ValueError: 同一个对象中重复声明字段。
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("观察字段重复")
        result[key] = value
    return result


def _reject_constant(value: str) -> Never:
    """拒绝不属于标准 JSON 的非有限数值。

    :param value: 解码器遇到的 NaN 或 Infinity 文本。
    :raises ValueError: 固定协议不接受非标准常量。
    """
    raise ValueError("观察包含非标准 JSON 常量")


class LocalEnvironmentProbe(EnvironmentProbe):
    """持有固定候选和实例预算的 Linux 受信探针，实际替换边界由 Operations 拥有。"""

    def __init__(self, candidates: Mapping[str, Path], *, limits: ProbeLimits) -> None:
        """固定部署位置和资源预算，不搜索 PATH、不启动程序或推断业务能力。

        :param candidates: 精确环境名到绝对候选路径的映射。
        :param limits: 唯一的实例级并发、时间及输出预算。
        :raises ValueError: 候选不是绝对路径。
        """
        if type(limits) is not ProbeLimits:
            raise TypeError("探针预算必须为 ProbeLimits")
        for runtime, path in candidates.items():
            if not isinstance(runtime, str) or not isinstance(path, Path) or not path.is_absolute():
                raise ValueError("解释器候选必须是名称与绝对路径")
        self._candidates = dict(candidates)
        self._limits = limits
        self._loop = asyncio.get_running_loop()
        self._active: set[asyncio.Task[EnvironmentObservation]] = set()
        self._closing: asyncio.Task[None] | None = None
        self._cleanup_failed = False
        # 清理失败时保留临时目录及原进程，不能用局部对象析构宣称现场已释放。
        self._retained: list[tuple[Path, asyncio.subprocess.Process | None]] = []

    @staticmethod
    def _payload(runtime: str) -> str:
        """取得固定产品自检；没有用户脚本、模块名或资源入口参数。

        :param runtime: 已确认支持的精确运行环境名称。
        :returns: 产品维护的固定脚本源文本。
        """
        return _PYTHON_PAYLOAD if runtime == "Python" else _BLENDER_PAYLOAD

    async def observe(self, runtime: str) -> EnvironmentObservation:
        """启动一次有界自检并返回真实观察，取消等待必须先清理原进程。

        :param runtime: Python 或 Blender Python；候选属于实例配置。
        :returns: 协议完整且进程组已停止后的环境观察。
        :raises ProbeError: 未配置、未支持、预算、输出、协议或进程故障。
        :raises asyncio.CancelledError: 调用者取消且原进程实际清理完成。
        """
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("探针必须在原事件循环使用")
        if self._closing is not None or self._cleanup_failed:
            raise ProbeError("closed")
        if supported_dependencies(runtime) is None:
            raise ProbeError("unsupported_runtime")
        if sys.platform != "linux":
            raise ProbeError("unsupported_platform")
        candidate = self._candidates.get(runtime)
        if candidate is None:
            raise ProbeError("not_configured")
        if len(self._active) >= self._limits.max_concurrency:
            raise ProbeError("busy")
        task = self._loop.create_task(self._execute(runtime, candidate))
        self._active.add(task)
        task.add_done_callback(self._completed)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            task.cancel()
            try:
                await _settle(task)
            except asyncio.CancelledError:
                pass
            raise

    def _completed(self, task: asyncio.Task[EnvironmentObservation]) -> None:
        """实际任务完成后才移除准入记录，并取得无人等待时的异常。

        :param task: 本实例创建的原探针任务。
        """
        self._active.discard(task)
        if not task.cancelled():
            task.exception()

    async def _execute(self, runtime: str, candidate: Path) -> EnvironmentObservation:
        """创建独立临时目录和原进程，任何退出路径均沿原句柄清理。

        :param runtime: 固定产品自检名称。
        :param candidate: 明确配置的解释器候选，不替换其他环境。
        :returns: 真实进程和输出完成后的冻结观察。
        """
        try:
            directory = Path(tempfile.mkdtemp(prefix="vet3d-environment-"))
        except OSError as cause:
            _log("environment_probe_failed", runtime, reason="preparation_failed", level=logging.ERROR, exc_info=True)
            raise ProbeError("preparation_failed") from cause
        process: asyncio.subprocess.Process | None = None
        started: asyncio.Task[asyncio.subprocess.Process] | None = None
        readers: list[asyncio.Task[bytes]] = []
        try:
            payload = directory / "probe.py"
            payload.write_text(self._payload(runtime), encoding="utf-8", newline="\n")
            arguments: tuple[str, ...]
            if runtime == "Python":
                arguments = (str(candidate), "-I", "-B", str(payload))
            else:
                arguments = (
                    str(candidate), "--background", "--factory-startup", "--disable-autoexec", "--threads", "1",
                    "--python-exit-code", "1", "--python", str(payload),
                )
            _log("environment_probe_started", runtime)
            total = [0]
            async with asyncio.timeout(self._limits.timeout_seconds):
                started = self._loop.create_task(asyncio.create_subprocess_exec(
                    *arguments, cwd=directory, env={
                        "HOME": str(directory), "TMPDIR": str(directory), "LC_ALL": "C.UTF-8",
                        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                    }, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, start_new_session=True, limit=8192,
                ))
                process = await asyncio.shield(started)
                assert process.stdout is not None and process.stderr is not None
                readers = [
                    self._loop.create_task(self._read(process.stdout, total)),
                    self._loop.create_task(self._read(process.stderr, total)),
                ]
                # asyncio.wait 不把期限取消扩散到读取者，finally 继续排空同一管道。
                await asyncio.wait(readers, return_when=asyncio.FIRST_EXCEPTION)
                for reader in readers:
                    if reader.done():
                        reader.result()
                output, _ = await asyncio.gather(*(asyncio.shield(reader) for reader in readers))
                code = await process.wait()
                if code != 0:
                    raise ProbeError("nonzero_exit")
                observation = self._parse(output, runtime, candidate)
            _log("environment_probe_output_observed", runtime)
            return observation
        except TimeoutError as cause:
            _log("environment_probe_failed", runtime, reason="timeout", level=logging.WARNING)
            raise ProbeError("timeout") from cause
        except ProbeError as cause:
            _log("environment_probe_failed", runtime, reason=cause.reason, level=logging.WARNING)
            raise
        except OSError as cause:
            _log("environment_probe_failed", runtime, reason="start_failed", level=logging.ERROR, exc_info=True)
            raise ProbeError("start_failed") from cause
        except asyncio.CancelledError:
            _log("environment_probe_cancelled", runtime)
            raise
        except Exception:
            _log("environment_probe_failed", runtime, reason="unexpected", level=logging.ERROR, exc_info=True)
            raise
        finally:
            try:
                if process is None and started is not None:
                    try:
                        process = await _settle(started)
                    except OSError:
                        pass
                if process is not None:
                    cleanup = self._loop.create_task(self._cleanup(process, readers))
                    await _settle(cleanup)
                shutil.rmtree(directory)
            except BaseException as cause:
                self._cleanup_failed = True
                self._retained.append((directory, process))
                _log("environment_probe_failed", runtime, reason="cleanup_failed", level=logging.ERROR, exc_info=True)
                raise ProbeError("cleanup_failed") from cause
            _log("environment_probe_drained", runtime)

    async def _read(self, stream: asyncio.StreamReader, total: list[int]) -> bytes:
        """并行读取一条管道，两条管道共享总字节预算。

        :param stream: 原进程 stdout 或 stderr。
        :param total: 本次进程两条管道共享的单一字节计数。
        :returns: 预算内的实际原始输出；不转储到日志。
        :raises ProbeError: 任一管道使累计输出超出预算。
        """
        chunks: list[bytes] = []
        while chunk := await stream.read(8192):
            total[0] += len(chunk)
            if total[0] > self._limits.max_output_bytes:
                raise ProbeError("output_limit")
            chunks.append(chunk)
        return b"".join(chunks)

    async def _cleanup(
        self, process: asyncio.subprocess.Process, readers: list[asyncio.Task[bytes]],
    ) -> None:
        """终止原进程组并排空管道；清理不成功时不能释放临时目录或接收新工作。

        :param process: 已经取得的原进程句柄。
        :param readers: 原输出读取任务，可能已经达到输出限额。
        :raises ProbeError: KILL 后仍无法确认原进程组停止或管道排空。
        """
        grace = self._limits.terminate_grace_seconds
        _signal_group(process.pid, signal.SIGTERM)
        deadline = self._loop.time() + grace
        while _group_running(process.pid) and self._loop.time() < deadline:
            await asyncio.sleep(0.01)
        if _group_running(process.pid):
            _signal_group(process.pid, signal.SIGKILL)
        deadline = self._loop.time() + grace
        while _group_running(process.pid):
            if self._loop.time() >= deadline:
                raise ProbeError("cleanup_failed")
            await asyncio.sleep(0.01)
        # 先让原读取者完成或报告超限，再排空剩余字节，最后等待进程管道关闭。
        async with asyncio.timeout(grace):
            await asyncio.gather(*readers, return_exceptions=True)
            drains = [
                self._loop.create_task(self._discard(stream))
                for stream in (process.stdout, process.stderr) if stream is not None
            ]
            await asyncio.gather(*drains)
            await process.wait()

    @staticmethod
    async def _discard(stream: asyncio.StreamReader) -> None:
        """在进程已停止后排空预算超限管道，不再保存其内容。

        :param stream: 原进程尚未到 EOF 的输出管道。
        """
        while await stream.read(8192):
            pass

    @staticmethod
    def _parse(output: bytes, runtime: str, candidate: Path) -> EnvironmentObservation:
        """严格解析唯一协议行，Blender 普通启动提示不作为观察字段。

        :param output: 预算内且原进程已正常退出的 stdout。
        :param runtime: 当前固定探针运行环境。
        :param candidate: 原实际启动的绝对候选位置，不从输出信任该关联。
        :returns: 字段完整、运行环境关联相符的唯一观察。
        :raises ProbeError: 记录缺失、重复、结构不合法或环境不匹配。
        """
        try:
            lines = output.decode("utf-8").splitlines()
            records = [line[len(_PREFIX):] for line in lines if line.startswith(_PREFIX)]
            if len(records) != 1:
                raise ValueError("需要一条实际观察")
            value: object = json.loads(
                records[0], object_pairs_hook=_unique_fields, parse_constant=_reject_constant,
            )
            keys = {"python_version", "blender_version", "dependencies", "cpu_check", "platform", "machine"}
            if not isinstance(value, dict) or set(value) != keys:
                raise ValueError("观察字段不完整")
            python = value["python_version"]
            blender = value["blender_version"]
            dependencies = value["dependencies"]
            if not isinstance(python, list) or not isinstance(dependencies, list):
                raise ValueError("观察字段形状无效")
            if blender is not None and not isinstance(blender, list):
                raise ValueError("Blender 版本形状无效")
            observation = EnvironmentObservation(
                python_version=cast(tuple[int, int, int], tuple(python)),
                blender_version=None if blender is None else cast(tuple[int, int, int], tuple(blender)),
                dependencies=tuple(dependencies), cpu_check=value["cpu_check"],
                platform=value["platform"], machine=value["machine"], executable=str(candidate),
            )
            supported = supported_dependencies(runtime)
            assert supported is not None
            if any(dependency not in supported for dependency in observation.dependencies):
                raise ValueError("观察依赖不属于原环境")
            if (observation.blender_version is not None) != (runtime == "Blender Python"):
                raise ValueError("观察不属于原环境")
            return observation
        except (TypeError, ValueError, UnicodeError) as cause:
            raise ProbeError("invalid_output") from cause

    async def _finish_close(self) -> None:
        """停止所有原探针并等待实际清理，不复用旧观察或重新提交。"""
        active = tuple(self._active)
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        if self._cleanup_failed:
            raise ProbeError("cleanup_failed")

    async def aclose(self) -> None:
        """停止准入并排空原进程；取消等待不会取消实际关闭。

        :raises ProbeError: 实际清理失败，原现场保留且实例拒绝新探针。
        """
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("探针必须在原事件循环关闭")
        if self._closing is None:
            self._closing = self._loop.create_task(self._finish_close())
            self._closing.add_done_callback(self._observe_close)
        await asyncio.shield(self._closing)

    @staticmethod
    def _observe_close(task: asyncio.Task[None]) -> None:
        """取得原关闭异常，避免等待取消后出现无人观察的异常。

        :param task: 唯一的实际关闭任务。
        """
        if not task.cancelled():
            task.exception()
