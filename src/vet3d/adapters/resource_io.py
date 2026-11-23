# 文件信息：L1-03 资源构建、安装和读取共用的真实文件检查。
# 作用：集中定义唯一运维限额，以目录句柄校验单用户受管文件树与实际字节。
# 边界：不定义业务能力、不执行资源代码，不把私有权限解释为执行沙箱。
"""提供同包资源适配器所需的窄文件系统原语。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import os
from pathlib import Path
import stat

from vet3d.resources import ResourceManifest, ResourcePath, fingerprint_bytes

from .artifact_files import _require_unchanged, _validate_regular
from .workspace_directories import _DIRECTORY_FLAGS, _open_parent


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """保存装配注入的单次资源 I/O 预算，不形成资源或业务状态。

    :param max_manifest_bytes: 清单原始字节上限。
    :param max_files: payload 普通文件数量上限。
    :param max_file_bytes: 单个 payload 文件字节上限。
    :param max_total_bytes: 全部 payload 文件字节总上限，不含清单。
    """

    max_manifest_bytes: int
    max_files: int
    max_file_bytes: int
    max_total_bytes: int

    def __post_init__(self) -> None:
        """拒绝布尔、非整数和非正预算，保持唯一限额表示。

        :raises TypeError: 任一上限不是整数。
        :raises ValueError: 任一上限不是正数。
        """
        for value in (self.max_manifest_bytes, self.max_files, self.max_file_bytes, self.max_total_bytes):
            if type(value) is not int:
                raise TypeError("资源限额必须是非布尔整数")
            if value <= 0:
                raise ValueError("资源限额必须为正数")


def safe_root_path(root: Path) -> Path:
    """一次性冻结配置根的绝对位置，拒绝上级跳转和文件系统根。

    :param root: 可信装配提供的目录位置。
    :returns: 不跟随符号链接的绝对路径。
    :raises TypeError: 输入不是 Path。
    :raises ValueError: 路径包含上级段或指向文件系统根。
    """
    if not isinstance(root, Path):
        raise TypeError("资源根必须是 Path")
    if ".." in root.parts:
        raise ValueError("资源根不能包含上级路径段")
    result = Path(os.path.abspath(root))
    if result == Path("/"):
        raise ValueError("资源根不能是文件系统根")
    return result


def file_identity(descriptor: int) -> tuple[int, int]:
    """取得本进程核对使用的设备和 inode，不写入业务契约。

    :param descriptor: 当前持有的真实句柄。
    :returns: 设备与 inode 二元组。
    """
    info = os.fstat(descriptor)
    return info.st_dev, info.st_ino


def validate_directory(descriptor: int, parent: int, name: str, *, modes: tuple[int, ...]) -> None:
    """核对已打开目录与其父目录项一致，且属于当前用户和许可权限。

    :param descriptor: 实际目录句柄。
    :param parent: 原父目录句柄。
    :param name: 单段目录名称。
    :param modes: 该边界明确允许的权限。
    :raises OSError: 目录被替换、缺失或安全属性不符。
    """
    opened = os.fstat(descriptor)
    linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (
        not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.getuid()
        or stat.S_IMODE(opened.st_mode) not in modes
        or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
    ):
        raise PermissionError("资源目录的身份、类型、属主或权限不符合要求")


def open_child_directory(parent: int, name: str, *, modes: tuple[int, ...] = (0o700,)) -> int:
    """打开一个受管子目录并拒绝链接，句柄所有权交给调用者。

    :param parent: 已经核对的父目录句柄。
    :param name: 单段子目录名。
    :param modes: 此目录允许的精确权限集合。
    :returns: 调用方负责关闭的目录句柄。
    :raises OSError: 目录不能安全打开。
    """
    if not name or name in (".", "..") or "/" in name or "\x00" in name:
        raise ValueError("资源目录访问仅接受单段名称")
    descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    try:
        validate_directory(descriptor, parent, name, modes=modes)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


@contextmanager
def opened_resource_directory(root: Path, *, modes: tuple[int, ...] = (0o700,)) -> Iterator[int]:
    """逐段拒绝父路径链接，在上下文结束后释放安全根句柄。

    :param root: 已配置的资源或构建源根。
    :param modes: 根目录允许的精确权限集合。
    :yields: 仅在上下文中有效的目录描述符。
    :raises OSError: 根或父路径不安全、缺失或在访问中被替换。
    """
    absolute = safe_root_path(root)
    parent = _open_parent(absolute)
    try:
        descriptor = open_child_directory(parent, absolute.name, modes=modes)
        try:
            yield descriptor
            validate_directory(descriptor, parent, absolute.name, modes=modes)
            current_parent = _open_parent(absolute)
            try:
                if file_identity(current_parent) != file_identity(parent):
                    raise OSError("资源根的父路径已经被替换")
            finally:
                os.close(current_parent)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def read_regular_bytes(
    parent: int, name: str, *, max_bytes: int, modes: tuple[int, ...] = (0o400, 0o600),
    expected_identity: tuple[int, int] | None = None, progress: Callable[[int], None] | None = None,
) -> bytes:
    """从实际单链接普通文件有界读取，并核对读取中的属性及目录项。

    :param parent: 经过校验的直接父目录。
    :param name: 单段文件名。
    :param max_bytes: 实际读取上限；零只允许空文件。
    :param modes: 文件允许的精确权限集合。
    :param expected_identity: 已固定读者观察过的文件身份，提供时必须仍一致。
    :param progress: 可选的实际读取字节进度回调，由安装器限频记录。
    :returns: 本次取得的完整字节。
    :raises OSError: 文件不安全、超限、读取失败或发生可观察变化。
    """
    if not name or name in (".", "..") or "/" in name or "\x00" in name:
        raise ValueError("资源文件访问仅接受单段名称")
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("读取上限必须是非负整数")
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
    try:
        before = os.fstat(descriptor)
        _validate_regular(before, modes=modes)
        if expected_identity is not None and (before.st_dev, before.st_ino) != expected_identity:
            raise OSError("固定资源文件的 inode 已被替换")
        if before.st_size > max_bytes:
            raise OSError(errno.EFBIG, "资源文件超过字节上限")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.pread(descriptor, min(1024 * 1024, before.st_size + 1 - total), total)
            if not chunk:
                break
            total += len(chunk)
            if total > before.st_size:
                raise OSError("资源文件在读取期间增长")
            chunks.append(chunk)
            if progress is not None:
                progress(len(chunk))
        _require_unchanged(before, os.fstat(descriptor))
        if total != before.st_size:
            raise OSError("资源文件未能完整读取")
        linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != (before.st_dev, before.st_ino):
            raise OSError("资源文件位置在读取期间被替换")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def list_payload_paths(
    directory: int, limits: ResourceLimits, *, expected_paths: tuple[ResourcePath, ...],
    directory_modes: tuple[int, ...] = (0o700,),
    file_modes: tuple[int, ...] = (0o400, 0o600),
) -> tuple[ResourcePath, ...]:
    """只读盘点精确 payload 树，拒绝链接、特殊文件、空子目录和超额内容。

    :param directory: payload 根句柄。
    :param limits: 装配提供的唯一限额记录。
    :param expected_paths: 从唯一清单或构建声明派生的完整文件集合。
    :param directory_modes: 子目录允许的权限。
    :param file_modes: 普通文件允许的权限。
    :returns: 排序后的实际普通文件路径。
    :raises OSError: 树包含不支持对象、空目录或资源预算耗尽。
    """
    expected = {path.value for path in expected_paths}
    if len(expected) > limits.max_files:
        raise OSError(errno.EFBIG, "声明的资源文件集合超过预算")
    directories = {
        "/".join(path.split("/")[:index])
        for path in expected for index in range(1, len(path.split("/")))
    }
    pending: list[tuple[int, str]] = [(os.dup(directory), "")]
    paths: list[ResourcePath] = []
    total_bytes = 0
    try:
        while pending:
            current, prefix = pending.pop()
            try:
                found = False
                with os.scandir(current) as entries:
                    for entry in entries:
                        found = True
                        path = ResourcePath(prefix + entry.name)
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            if path.value not in directories:
                                raise OSError("资源 payload 含有未声明目录")
                            child = open_child_directory(current, entry.name, modes=directory_modes)
                            pending.append((child, path.value + "/"))
                        else:
                            if path.value not in expected:
                                raise OSError("资源 payload 含有未声明文件")
                            _validate_regular(info, modes=file_modes)
                            paths.append(path)
                            total_bytes += info.st_size
                            if (
                                len(paths) > limits.max_files or info.st_size > limits.max_file_bytes
                                or total_bytes > limits.max_total_bytes
                            ):
                                raise OSError(errno.EFBIG, "资源文件集合超过预算")
                if prefix and not found:
                    raise OSError("资源 payload 不接受未声明的空子目录")
            finally:
                os.close(current)
        if {path.value for path in paths} != expected:
            raise OSError("资源 payload 缺少声明文件")
        return tuple(ResourcePath(value) for value in sorted(path.value for path in paths))
    finally:
        for descriptor, _ in pending:
            os.close(descriptor)


def read_payload_file(
    directory: int, path: ResourcePath, *, max_bytes: int, directory_modes: tuple[int, ...],
    file_modes: tuple[int, ...],
    expected_identity: tuple[int, int] | None = None, progress: Callable[[int], None] | None = None,
) -> bytes:
    """按已解析的资源相对路径逐段打开，并读取同一文件句柄。

    :param directory: payload 根目录。
    :param path: 资源契约已经校验的相对文件路径。
    :param max_bytes: 本次读取的字节上限。
    :param directory_modes: 中间目录允许的权限。
    :param file_modes: 最终文件允许的权限。
    :param expected_identity: 可选的原文件 inode 观察。
    :param progress: 可选的读取进度回调。
    :returns: 实际完整字节。
    :raises OSError: 路径或内容读取不符合安全边界。
    """
    opened = [os.dup(directory)]
    parts = path.value.split("/")
    try:
        for part in parts[:-1]:
            opened.append(open_child_directory(opened[-1], part, modes=directory_modes))
        result = read_regular_bytes(
            opened[-1], parts[-1], max_bytes=max_bytes, modes=file_modes,
            expected_identity=expected_identity, progress=progress,
        )
        for index, part in enumerate(parts[:-1]):
            validate_directory(opened[index + 1], opened[index], part, modes=directory_modes)
        return result
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def validate_manifest_limits(manifest: ResourceManifest, limits: ResourceLimits) -> None:
    """在复制前核对声明文件数与大小，实际 I/O 仍独立验证。

    :param manifest: 通过纯契约解析的资源清单。
    :param limits: 唯一运维限额。
    :raises OSError: 声明内容超过本次安装或读取预算。
    """
    if (
        len(manifest.files) > limits.max_files
        or any(item.content.byte_size > limits.max_file_bytes for item in manifest.files)
        or sum(item.content.byte_size for item in manifest.files) > limits.max_total_bytes
    ):
        raise OSError(errno.EFBIG, "资源清单超过文件数量或字节预算")


def verify_payload(
    directory: int, manifest: ResourceManifest, limits: ResourceLimits, *, directory_mode: int = 0o700,
    file_modes: tuple[int, ...] = (0o400, 0o600),
    progress: Callable[[int], None] | None = None,
) -> None:
    """将实际树和每个文件摘要与同一清单核对，不认可额外内容。

    :param directory: 待核对 payload 根句柄。
    :param manifest: 唯一文件及资源声明。
    :param limits: 单次实际 I/O 预算。
    :param directory_mode: 当前源或已发布树的目录权限。
    :param file_modes: 当前树的普通文件权限。
    :param progress: 可选的实际字节读取进度，仅由安装器用于限频日志。
    :raises OSError: 文件集合、大小或实际摘要不匹配。
    """
    validate_manifest_limits(manifest, limits)
    observed = list_payload_paths(
        directory, limits, expected_paths=tuple(item.path for item in manifest.files),
        directory_modes=(directory_mode,), file_modes=file_modes,
    )
    if set(observed) != {item.path for item in manifest.files}:
        raise OSError("资源 payload 与清单的文件集合不一致")
    for item in manifest.files:
        data = read_payload_file(
            directory, item.path, max_bytes=item.content.byte_size,
            directory_modes=(directory_mode,), file_modes=file_modes, progress=progress,
        )
        if fingerprint_bytes(data) != item.content:
            raise OSError(f"资源内容指纹不匹配：{item.path.value}")
