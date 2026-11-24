# 文件信息：L1-01 的 Debian 本地受管根、固定写入锁和身份目录适配器。
# 作用：管理私有 UUID 目录及根所有权，并交付固定工作区的独立文件 I/O 作用域。
# 边界：仅支持独占管理的本地文件系统；目录与 flock 都不是不可信代码执行沙箱。
"""通过保留的目录描述符访问工作区，不向业务层暴露可任意解析的路径。"""

import fcntl
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Event, get_ident

from vet3d.identity import WorkspaceId
from vet3d.workspaces import WorkspaceDirectories


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _validate_entry(descriptor: int, parent: int, name: str, *, directory: bool) -> None:
    """核对已打开对象与目录项的身份、属主和私有权限。

    :param descriptor: 保持打开的目标描述符。
    :param parent: 目标所在目录的描述符。
    :param name: 单个目录项名称。
    :param directory: 是否要求目录，文件时要求单链接普通文件。
    :raises OSError: 对象缺失、被替换或安全属性不符合受管根约束。
    """
    opened = os.fstat(descriptor)
    linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
        raise OSError(f"受管目录项已被替换：{name}")
    expected_mode = 0o700 if directory else 0o600
    valid_type = stat.S_ISDIR(opened.st_mode) if directory else stat.S_ISREG(opened.st_mode)
    if not valid_type or opened.st_uid != os.getuid() or stat.S_IMODE(opened.st_mode) != expected_mode:
        raise PermissionError(f"受管目录项的类型、属主或权限不符合约束：{name}")
    if not directory and opened.st_nlink != 1:
        raise PermissionError(f"受管控制文件不能有额外硬链接：{name}")


def _open_parent(path: Path) -> int:
    """逐段拒绝符号链接并打开受管根的父目录。

    :param path: 不含相对段的绝对受管根路径。
    :returns: 调用者负责关闭的父目录描述符。
    :raises OSError: 任意父目录不存在、不可访问或包含符号链接。
    """
    descriptor = os.open("/", _DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:-1]:
            next_descriptor = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _file_identity(descriptor: int) -> tuple[int, int]:
    """提取当前描述符的设备与 inode，供固定文件作用域核对原对象。

    :param descriptor: 当前持有的目录或控制文件描述符。
    :returns: 文件系统对象身份，不作为业务身份或访问授权。
    """
    info = os.fstat(descriptor)
    return info.st_dev, info.st_ino


def _require_identity(descriptor: int, expected: tuple[int, int]) -> None:
    """拒绝安全属性相同但已替换原对象的目录或控制文件。

    :param descriptor: 本次操作独立打开的描述符。
    :param expected: 装配时从原根观察并冻结的设备与 inode。
    :raises OSError: 当前对象与原观察身份不一致。
    """
    if _file_identity(descriptor) != expected:
        raise OSError("受管文件作用域内的原对象已被替换")


@dataclass(frozen=True, slots=True)
class _WorkspaceFileScope:
    """让文件 worker 独立打开固定工作区，不共享根句柄或目录观察字典。

    :param path: 装配时确认的绝对受管根路径。
    :param name: 由固定工作区身份派生的目录名。
    :param closed: 唯一根生命周期标记；仅根所有者在排空 I/O 后设置。
    :param identities: 父目录、根、控制目录、集合、锁及工作区的原对象身份。
    """

    path: Path
    name: str
    closed: Event
    identities: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]

    def _open_checked(self, parent: int, name: str, *, directory: bool, index: int) -> int:
        """打开一个原受管对象，同时核对路径、安全属性与冻结身份。

        :param parent: 本次操作独立持有的父目录描述符。
        :param name: 固定布局中的单个目录项名称。
        :param directory: 是否要求私有目录，否则要求私有控制文件。
        :param index: 该对象在冻结身份元组中的位置。
        :returns: 调用方负责关闭的独立描述符。
        :raises OSError: 路径不安全、对象缺失或原身份已经变化。
        """
        flags = _DIRECTORY_FLAGS if directory else os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        descriptor = os.open(name, flags, dir_fd=parent)
        try:
            _validate_entry(descriptor, parent, name, directory=directory)
            _require_identity(descriptor, self.identities[index])
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def open_handle(self) -> int:
        """逐次打开并核对完整布局，只交付本次拥有的工作区描述符。

        文件操作开始和结束都调用此方法；根所有者必须先排空实际文件 I/O，
        再关闭根并释放 flock。本方法不改变根线程或注册库的所有权。

        :returns: 调用方负责关闭的工作区句柄，不共享流游标。
        :raises RuntimeError: 根已经关闭，原作用域不允许继续读写。
        :raises OSError: 任一路径、安全属性或冻结对象身份失效。
        """
        if self.closed.is_set():
            raise RuntimeError("受管根已关闭")
        descriptors: list[int] = []
        try:
            parent = _open_parent(self.path)
            descriptors.append(parent)
            _require_identity(parent, self.identities[0])
            root = self._open_checked(parent, self.path.name, directory=True, index=1)
            descriptors.append(root)
            control = self._open_checked(root, ".control", directory=True, index=2)
            descriptors.append(control)
            workspaces = self._open_checked(root, "workspaces", directory=True, index=3)
            descriptors.append(workspaces)
            lock = self._open_checked(control, "writer.lock", directory=False, index=4)
            descriptors.append(lock)
            workspace = self._open_checked(workspaces, self.name, directory=True, index=5)
            descriptors.append(workspace)
            if self.closed.is_set():
                raise RuntimeError("受管根已关闭")
            return descriptors.pop()
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


class ManagedWorkspaceRoot:
    """持有受管根的目录描述符与写入所有权，供 Bootstrap 封闭于单线程。

    :param path: 已校验的绝对根路径。
    :param descriptors: 父目录、根、控制目录、工作区集合及锁文件描述符。
    """

    def __init__(self, path: Path, descriptors: tuple[int, int, int, int, int]) -> None:
        """接管已成功建立的描述符，不提供隐式初始化副作用。

        :param path: 受管根的绝对路径。
        :param descriptors: 已按固定顺序建立的五个描述符。
        """
        self._path = path
        self._parent, self._root, self._control, self._workspaces, self._lock = descriptors
        self._thread = get_ident()
        self._closed = Event()
        self._directories = LocalWorkspaceDirectories(self)

    @classmethod
    def initialize(cls, root: Path) -> "ManagedWorkspaceRoot":
        """显式初始化不存在或已确认空白的私有根，保留失败现场。

        :param root: 运维注入的本地绝对或相对根位置。
        :returns: 持有独占写入锁的根对象；数据库仍由仓储初始化。
        :raises OSError: 路径不安全、根非空、目录同步或锁定失败。
        """
        return cls._build(root, initialize=True)

    @classmethod
    def open(cls, root: Path) -> "ManagedWorkspaceRoot":
        """重新打开完整的既有布局，拒绝通过补建结构伪装恢复。

        :param root: 运维注入的既有受管根位置。
        :returns: 持有独占写入锁的根对象。
        :raises OSError: 结构、注册库或固定锁缺失、不安全或被其他写入者占用。
        """
        return cls._build(root, initialize=False)

    @classmethod
    def _build(cls, root: Path, *, initialize: bool) -> "ManagedWorkspaceRoot":
        """按初始化或重开语义装配描述符，异常只释放资源。

        :param root: 待装配的根位置。
        :param initialize: 是否执行首次空根初始化。
        :returns: 资源所有权完整转移后的根对象。
        :raises OSError: 任一步骤失败，磁盘残留由后续显式对账处理。
        """
        if ".." in root.parts:
            raise ValueError("受管根路径不能包含上级目录跳转")
        path = Path(os.path.abspath(root))
        if path == Path("/"):
            raise ValueError("受管根不能是文件系统根目录")
        descriptors: list[int] = []
        try:
            parent = _open_parent(path)
            descriptors.append(parent)
            if initialize:
                try:
                    os.mkdir(path.name, mode=0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            root_fd = os.open(path.name, _DIRECTORY_FLAGS, dir_fd=parent)
            descriptors.append(root_fd)
            _validate_entry(root_fd, parent, path.name, directory=True)
            if initialize and os.listdir(root_fd):
                raise FileExistsError("首次初始化仅接受空白受管根")
            directory_fds: list[int] = []
            for name in (".control", "workspaces"):
                if initialize:
                    os.mkdir(name, mode=0o700, dir_fd=root_fd)
                descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=root_fd)
                descriptors.append(descriptor)
                directory_fds.append(descriptor)
                _validate_entry(descriptor, root_fd, name, directory=True)
                if initialize:
                    os.fsync(descriptor)
                    os.fsync(root_fd)
            control, workspaces = directory_fds
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if initialize:
                flags |= os.O_CREAT | os.O_EXCL
            lock = os.open("writer.lock", flags, mode=0o600, dir_fd=control)
            descriptors.append(lock)
            _validate_entry(lock, control, "writer.lock", directory=False)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if initialize:
                os.fsync(lock)
                os.fsync(control)
            else:
                database = os.open(
                    "registry.sqlite3", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=control
                )
                try:
                    _validate_entry(database, control, "registry.sqlite3", directory=False)
                finally:
                    os.close(database)
            instance = cls(path, (parent, root_fd, control, workspaces, lock))
            instance._check()
            return instance
        except BaseException:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            raise

    def _check_thread(self) -> None:
        """拒绝跨线程使用，使根与仓储可以由同一执行工作线程持有。

        :raises RuntimeError: 调用线程不是建立资源的线程。
        """
        if get_ident() != self._thread:
            raise RuntimeError("受管根必须由创建它的线程使用和关闭")

    def _check(self) -> None:
        """在每次路径访问前检查资源存活与持有对象的可观察替换。

        :raises RuntimeError: 根已关闭或跨线程访问。
        :raises OSError: 原目录或固定锁被删除、替换、改权或改属主。
        """
        self._check_thread()
        if self._closed.is_set():
            raise RuntimeError("受管根已关闭")
        current_parent = _open_parent(self._path)
        try:
            original = os.fstat(self._parent)
            current = os.fstat(current_parent)
            if (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
                raise OSError("受管根的父目录已被替换")
        finally:
            os.close(current_parent)
        _validate_entry(self._root, self._parent, self._path.name, directory=True)
        _validate_entry(self._control, self._root, ".control", directory=True)
        _validate_entry(self._workspaces, self._root, "workspaces", directory=True)
        _validate_entry(self._lock, self._control, "writer.lock", directory=False)

    def validate(self) -> None:
        """让装配层在仓储读写前校验受管根对象仍与原路径一致。

        :raises RuntimeError: 根已关闭或被跨线程使用。
        :raises OSError: 根、父路径、控制目录、工作区集合或锁对象异常。
        """
        self._check()

    @property
    def database_path(self) -> Path:
        """仅向受信装配层提供控制库位置，不将路径作为业务访问授权。

        :returns: 由固定布局单向派生的注册库路径。
        :raises OSError: 根结构已失效。
        """
        self._check()
        return self._path / ".control" / "registry.sqlite3"

    @property
    def directories(self) -> "LocalWorkspaceDirectories":
        """向装配层提供目录端口的具体实现。

        :returns: 与本根共享生命周期和线程边界的目录适配器。
        """
        self._check()
        return self._directories

    def close(self) -> None:
        """在所有实际 I/O 完成后释放描述符和锁，保留锁文件及磁盘现场。

        :raises RuntimeError: 跨线程关闭。
        """
        self._check_thread()
        if self._closed.is_set():
            return
        self._closed.set()
        for descriptor in (self._lock, self._workspaces, self._control, self._root, self._parent):
            os.close(descriptor)

    def file_scope(self, workspace_id: WorkspaceId) -> _WorkspaceFileScope:
        """在控制线程冻结固定工作区作用域，供已核对登记的文件适配器使用。

        :param workspace_id: 装配已经核对持久登记的唯一工作区身份。
        :returns: 可供多个文件 worker 使用、没有长期目录句柄的具体作用域。
        :raises RuntimeError: 根已关闭或构造调用不在根所属线程。
        :raises OSError: 根或工作区不安全、缺失或已观察原对象被替换。
        """
        workspace = self._directories.open_handle(workspace_id)
        try:
            self._check()
            _validate_entry(workspace, self._workspaces, str(workspace_id.value), directory=True)
            return _WorkspaceFileScope(
                self._path, str(workspace_id.value), self._closed,
                (
                    _file_identity(self._parent), _file_identity(self._root),
                    _file_identity(self._control), _file_identity(self._workspaces),
                    _file_identity(self._lock), _file_identity(workspace),
                ),
            )
        finally:
            os.close(workspace)


class LocalWorkspaceDirectories(WorkspaceDirectories):
    """实现身份目录端口；调用者负责先验证持久意图和业务归属。

    :param root: 由 Bootstrap 持有生命周期的私有根对象。
    """

    def __init__(self, root: ManagedWorkspaceRoot) -> None:
        """绑定具体根并记录本实例已观察目录的设备与 inode。

        :param root: 同线程的受管根。
        """
        self._root = root
        self._observed: dict[str, tuple[int, int]] = {}

    def _name(self, workspace_id: WorkspaceId) -> str:
        """只从唯一身份类型导出目录名，拒绝名称或其他身份投影。

        :param workspace_id: 已构造的工作区身份。
        :returns: 规范 UUID4 目录名。
        :raises TypeError: 输入不是工作区身份。
        """
        self._root._check()
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("目录操作需要 WorkspaceId")
        return str(workspace_id.value)

    def check_absent(self, workspace_id: WorkspaceId) -> None:
        """在登记新意图之前拒绝任何已有同名对象，包括悬空链接。

        :param workspace_id: 即将登记创建意图的身份。
        :raises FileExistsError: 同名目录项已经存在。
        """
        name = self._name(workspace_id)
        try:
            os.stat(name, dir_fd=self._root._workspaces, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise FileExistsError(f"新工作区身份已有同名对象：{name}")

    def _open_workspace(self, name: str) -> int:
        """核对身份目录并记住本进程已观察的对象，返回短期描述符。

        :param name: 由工作区身份派生的单个目录名。
        :returns: 调用者负责关闭的安全目录描述符。
        :raises OSError: 目录缺失、不安全或已观察对象被替换。
        """
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=self._root._workspaces)
        try:
            _validate_entry(descriptor, self._root._workspaces, name, directory=True)
            opened = os.fstat(descriptor)
            identity = (opened.st_dev, opened.st_ino)
            previous = self._observed.get(name)
            if previous is not None and previous != identity:
                raise OSError(f"工作区目录已被替换：{name}")
            self._observed[name] = identity
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def prepare(self, workspace_id: WorkspaceId) -> None:
        """为原待确认意图建立并同步空目录，复用可信空残留。

        :param workspace_id: 仓储已登记且尚未确认的原创建意图身份。
        :raises OSError: 同名对象不安全、含未知内容、被替换或目录同步失败。
        """
        name = self._name(workspace_id)
        try:
            os.mkdir(name, mode=0o700, dir_fd=self._root._workspaces)
        except FileExistsError:
            pass
        descriptor = self._open_workspace(name)
        try:
            if os.listdir(descriptor):
                raise FileExistsError(f"待确认目录含有陌生内容：{name}")
            os.fsync(descriptor)
            os.fsync(self._root._workspaces)
        finally:
            os.close(descriptor)

    def require_existing(self, workspace_id: WorkspaceId) -> None:
        """校验已登记工作区仍存在，不补建、不遍历或解释合法素材。

        :param workspace_id: 仓储已经确认登记的工作区身份。
        :raises OSError: 原目录缺失、类型或权限异常，或发现进程内替换。
        """
        descriptor = self._open_workspace(self._name(workspace_id))
        os.close(descriptor)

    def open_handle(self, workspace_id: WorkspaceId) -> int:
        """向同线程受信文件适配器交付经核对的目录句柄，不授予执行权限。

        调用装配必须已经核对该工作区完成持久注册；本方法不读取注册库。

        :param workspace_id: 原已登记工作区身份。
        :returns: 由调用方负责关闭的目录描述符。
        :raises OSError: 目录缺失、不安全或本实例已观察的对象被替换。
        """
        return self._open_workspace(self._name(workspace_id))
