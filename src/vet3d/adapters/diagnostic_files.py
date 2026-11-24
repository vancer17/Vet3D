# 文件信息：L1-05 私有 JSONL 诊断文件适配器。
# 作用：由唯一后台线程持有目录锁、轮转固定文件并有界读取现存诊断。
# 边界：本地单写入者，不承诺断电零丢失，不是数据库或业务恢复账本。
"""实现有界诊断文件存储；所有方法由同一个所有者线程调用。"""

from collections import deque
import fcntl
import json
import os
from pathlib import Path
from threading import get_ident

from vet3d.identity import ArtifactId, AttemptId, TaskId, WorkspaceId
from vet3d.operations import DiagnosticLimits, DiagnosticRecord

from .workspace_directories import _DIRECTORY_FLAGS, _open_parent, _validate_entry

_ACTIVE = "events.jsonl"
_LOCK = "writer.lock"
_FIELDS = {"schema", "timestamp", "runtime_id", "level", "message", "workspace_id", "task_id", "attempt_id", "artifact_id"}


def _decode_record(data: bytes) -> DiagnosticRecord:
    """将当前存储 Schema 的一行解析为既有身份关联，拒绝未知结构。

    :param data: 已经有字节上限的一条完整 JSONL 记录。
    :returns: 不含可变容器的诊断记录。
    :raises ValueError: JSON、字段或规范身份文本不符合契约。
    """
    value: object = json.loads(data)
    if not isinstance(value, dict) or set(value) != _FIELDS or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError("诊断记录 Schema 无效")
    for name in ("timestamp", "runtime_id", "level", "message"):
        if type(value[name]) is not str:
            raise ValueError("诊断文本字段无效")
    for name in ("workspace_id", "task_id", "attempt_id", "artifact_id"):
        if value[name] is not None and type(value[name]) is not str:
            raise ValueError("诊断身份字段无效")
    workspace = WorkspaceId.parse(value["workspace_id"]) if value["workspace_id"] is not None else None
    task = TaskId.parse(value["task_id"]) if value["task_id"] is not None else None
    if task is not None and workspace is None:
        raise ValueError("任务诊断缺少已知工作区关联")
    return DiagnosticRecord(
        timestamp=value["timestamp"], runtime_id=value["runtime_id"], level=value["level"], message=value["message"],
        workspace_id=workspace, task_id=task,
        attempt_id=AttemptId.parse(value["attempt_id"]) if value["attempt_id"] is not None else None,
        artifact_id=ArtifactId.parse(value["artifact_id"]) if value["artifact_id"] is not None else None,
    )


class LocalDiagnosticFiles:
    """持有唯一诊断目录和锁；文件总预算由固定归档数量派生。"""

    def __init__(self, root: Path, limits: DiagnosticLimits) -> None:
        """创建或重开私有诊断根，不修复宽松权限或不明目录内容。

        :param root: Bootstrap 已解析的绝对目录，其父目录必须存在。
        :param limits: 唯一的存储预算对象。
        :raises OSError: 路径、权限、文件布局或所有者锁不满足要求。
        :raises ValueError: 根不是安全绝对路径或现存文件超过当前预算。
        """
        if not root.is_absolute() or ".." in root.parts or root == Path("/"):
            raise ValueError("诊断根必须是无上级跳转的非根绝对路径")
        self._thread = get_ident()
        self._path = root
        self._limits = limits
        self._parent = -1
        self._root = -1
        self._lock = -1
        self._file = -1
        try:
            self._parent = _open_parent(root)
            try:
                os.mkdir(root.name, mode=0o700, dir_fd=self._parent)
                os.fsync(self._parent)
            except FileExistsError:
                pass
            self._root = os.open(root.name, _DIRECTORY_FLAGS, dir_fd=self._parent)
            _validate_entry(self._root, self._parent, root.name, directory=True)
            entries = set(os.listdir(self._root))
            allowed = {_LOCK, _ACTIVE, *(self._archive(index) for index in range(1, limits.archive_count + 1))}
            if entries - allowed or (entries and _LOCK not in entries):
                raise ValueError("诊断根包含未认领内容或缺少原写入锁")
            flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
            self._lock = os.open(_LOCK, flags | (os.O_CREAT | os.O_EXCL if not entries else 0), 0o600, dir_fd=self._root)
            _validate_entry(self._lock, self._root, _LOCK, directory=False)
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for name in entries - {_LOCK}:
                descriptor = self._open_file(name, os.O_RDONLY)
                os.close(descriptor)
            # 重启不继续拼接可能被截断的旧尾行，旧活动文件进入有界归档。
            if _ACTIVE in entries and os.stat(_ACTIVE, dir_fd=self._root).st_size:
                self._rotate()
            self._file = self._open_file(_ACTIVE, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
            os.fsync(self._root)
        except BaseException:
            self.close()
            raise

    def _archive(self, index: int) -> str:
        """由固定序号派生归档名，不接受用户提供的路径。

        :param index: 一至归档数量的整数。
        :returns: 单段受管文件名。
        """
        return f"{_ACTIVE}.{index}"

    def _check(self) -> None:
        """核对线程、根和锁仍对应原对象，拒绝关闭后或替换后的操作。

        :raises RuntimeError: 生命周期或线程不符合约束。
        :raises OSError: 原对象被替换或权限变化。
        """
        if get_ident() != self._thread or self._root < 0:
            raise RuntimeError("诊断文件只能在所有者线程和有效生命周期使用")
        _validate_entry(self._root, self._parent, self._path.name, directory=True)
        _validate_entry(self._lock, self._root, _LOCK, directory=False)

    def _open_file(self, name: str, flags: int) -> int:
        """打开固定布局普通文件，拒绝链接、权限不符和超预算文件。

        :param name: 由本适配器产生的固定单段名称。
        :param flags: 本次只读或活动追加模式。
        :returns: 调用方负责关闭的文件描述符。
        :raises OSError: 文件不安全或不能打开。
        :raises ValueError: 现存字节超过本次部署限额。
        """
        descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600, dir_fd=self._root)
        try:
            _validate_entry(descriptor, self._root, name, directory=False)
            if os.fstat(descriptor).st_size > self._limits.max_file_bytes:
                raise ValueError("已有诊断文件超过当前单文件预算")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _rotate(self) -> None:
        """只轮转已经验证的固定文件，不删除目录内的未知内容。

        :raises OSError: 轮转失败，现有文件保留其实际部分结果。
        """
        self._check()
        for index in range(self._limits.archive_count, 0, -1):
            source = _ACTIVE if index == 1 else self._archive(index - 1)
            target = self._archive(index)
            try:
                descriptor = self._open_file(source, os.O_RDONLY)
            except FileNotFoundError:
                continue
            os.close(descriptor)
            try:
                descriptor = self._open_file(target, os.O_RDONLY)
            except FileNotFoundError:
                pass
            else:
                os.close(descriptor)
            os.rename(source, target, src_dir_fd=self._root, dst_dir_fd=self._root)
        os.fsync(self._root)

    def append(self, data: bytes) -> None:
        """写出一条完整且有界的记录，需要时先轮转；不做业务提交。

        :param data: 已编码且以换行结束的完整 JSONL 字节。
        :raises OSError: 写入或轮转失败，调用方须暴露诊断丢失。
        :raises ValueError: 记录超出预算或不是完整行。
        """
        self._check()
        if len(data) > self._limits.max_record_bytes or not data.endswith(b"\n"):
            raise ValueError("诊断写入只接受预算内的完整记录")
        _validate_entry(self._file, self._root, _ACTIVE, directory=False)
        if os.fstat(self._file).st_size + len(data) > self._limits.max_file_bytes:
            os.fsync(self._file)
            os.close(self._file)
            self._file = -1
            self._rotate()
            self._file = self._open_file(_ACTIVE, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL)
        remaining = memoryview(data)
        while remaining:
            written = os.write(self._file, remaining)
            if written <= 0:
                raise OSError("诊断记录未完整写出")
            remaining = remaining[written:]

    def read(
        self, workspace_id: WorkspaceId, task_id: TaskId | None, limit: int,
    ) -> tuple[tuple[DiagnosticRecord, ...], bool, int]:
        """在固定保留预算内扫描日志，返回最近匹配记录和损坏计数。

        :param workspace_id: 已授权工作区过滤条件。
        :param task_id: 可选任务过滤条件，与工作区同时应用。
        :param limit: 已校验的最大返回数量。
        :returns: 记录、是否存在更多匹配记录、损坏行数。
        :raises OSError: 文件无法安全读取；不能把故障伪装成空结果。
        """
        self._check()
        if self._file >= 0:
            _validate_entry(self._file, self._root, _ACTIVE, directory=False)
        matches: deque[DiagnosticRecord] = deque(maxlen=limit)
        count = 0
        malformed = 0
        names = [self._archive(index) for index in range(self._limits.archive_count, 0, -1)] + [_ACTIVE]
        for name in names:
            try:
                descriptor = self._open_file(name, os.O_RDONLY)
            except FileNotFoundError:
                if name == _ACTIVE:
                    raise
                continue
            with os.fdopen(descriptor, "rb") as stream:
                remaining = self._limits.max_file_bytes
                while data := stream.readline(min(self._limits.max_record_bytes, remaining) + 1):
                    remaining -= len(data)
                    if remaining < 0:
                        raise OSError("诊断文件在读取期间增长超过预算")
                    if len(data) > self._limits.max_record_bytes or not data.endswith(b"\n"):
                        malformed += 1
                        while data and not data.endswith(b"\n"):
                            data = stream.readline(min(self._limits.max_record_bytes, remaining) + 1)
                            remaining -= len(data)
                            if remaining < 0:
                                raise OSError("诊断文件在读取期间增长超过预算")
                        continue
                    try:
                        record = _decode_record(data)
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        malformed += 1
                        continue
                    if record.workspace_id == workspace_id and (task_id is None or record.task_id == task_id):
                        count += 1
                        matches.append(record)
        self._check()
        if self._file >= 0:
            _validate_entry(self._file, self._root, _ACTIVE, directory=False)
        return tuple(matches), count > limit, malformed

    def close(self) -> None:
        """同步现存活动文件并释放句柄；关闭失败仍释放锁且向所有者报告。

        :raises OSError: 最后的同步失败，不能宣称诊断完整持久化。
        """
        error: OSError | None = None
        if self._file >= 0:
            try:
                os.fsync(self._file)
            except OSError as caught:
                error = caught
        for name in ("_file", "_lock", "_root", "_parent"):
            descriptor: int = getattr(self, name)
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError as caught:
                    if error is None:
                        error = caught
                finally:
                    setattr(self, name, -1)
        if error is not None:
            raise error
