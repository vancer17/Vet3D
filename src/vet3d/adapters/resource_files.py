# 文件信息：L1-03 本地资源版本安装、固定快照与安全读取适配器。
# 作用：校验完整资源包，在私有暂存完成后无覆盖发布，读者只消费确切快照。
# 边界：无数据库、latest 指针、自动修复或代码执行；安装锁不阻塞既有快照读取。
# 恢复：未知残留不认领；发布后同步失败保留最终版本，只清理本次仍属原 inode 的暂存。
"""以操作内目录句柄管理单用户资源存储，不把安装成功解释为执行就绪。"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import logging
import os
from pathlib import Path
import secrets
import stat
import time

from vet3d.artifacts import ContentFingerprint
from vet3d.resources import (
    ResourceContractError, ResourceDescription, ResourceKey, ResourceManifest, ResourcePath,
    ResourceReader, ResourceReference, fingerprint_bytes, parse_manifest,
)

from .artifact_files import _validate_regular, _write_all
from .file_commit import commit_file_no_replace
from .resource_io import (
    ResourceLimits as ResourceLimits, file_identity, list_payload_paths, open_child_directory,
    opened_resource_directory, read_payload_file, read_regular_bytes, safe_root_path,
    validate_directory, validate_manifest_limits, verify_payload,
)
from .workspace_directories import _open_parent


_LOGGER = logging.getLogger("vet3d")
type _Identity = tuple[int, int]


def _require_entries(directory: int, expected: set[str]) -> None:
    """只接受当前层声明的目录项，不扫描额外子树。

    :param directory: 当前目录句柄。
    :param expected: 允许且必须存在的单段名称集合。
    :raises OSError: 出现额外项或缺少必需项。
    """
    remaining = expected.copy()
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in remaining:
                raise OSError(f"资源目录含有未声明项：{entry.name}")
            remaining.remove(entry.name)
    if remaining:
        raise FileNotFoundError("资源目录缺少必需项")


@dataclass(frozen=True, slots=True)
class _Layout:
    """在一次操作内借用完整布局句柄，不作为业务状态或持久身份。

    :param root: 受管根。
    :param staging: 独立安装暂存集合。
    :param snapshots: 已发布版本集合。
    :param lock: 固定安装锁文件。
    """

    root: int
    staging: int
    snapshots: int
    lock: int

    def identities(self) -> tuple[_Identity, ...]:
        """取得本实例已观察的布局身份，供之后的操作检查替换。

        :returns: 根、暂存、版本集合与锁文件的设备及 inode。
        """
        return tuple(file_identity(item) for item in (self.root, self.staging, self.snapshots, self.lock))

    def validate(self) -> None:
        """核对操作内保留句柄仍与受管目录项一致。

        :raises OSError: 布局目录或锁文件被替换或改权。
        """
        _require_entries(self.root, {".install.lock", ".staging", "snapshots"})
        validate_directory(self.staging, self.root, ".staging", modes=(0o700,))
        validate_directory(self.snapshots, self.root, "snapshots", modes=(0o700,))
        info = os.fstat(self.lock)
        _validate_regular(info, modes=(0o600,))
        linked = os.stat(".install.lock", dir_fd=self.root, follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != (info.st_dev, info.st_ino):
            raise OSError("资源安装锁文件已经被替换")


@contextmanager
def _opened_layout(root: Path) -> Iterator[_Layout]:
    """只打开既有完整布局，释放本次句柄而不删除控制文件。

    :param root: 已冻结的受管根位置。
    :yields: 本次操作有效的布局句柄。
    :raises OSError: 根或布局不符合既有存储约束。
    """
    with opened_resource_directory(root) as directory:
        descriptors: list[int] = []
        try:
            staging = open_child_directory(directory, ".staging")
            descriptors.append(staging)
            snapshots = open_child_directory(directory, "snapshots")
            descriptors.append(snapshots)
            lock = os.open(
                ".install.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory,
            )
            descriptors.append(lock)
            layout = _Layout(directory, staging, snapshots, lock)
            layout.validate()
            yield layout
            layout.validate()
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


class _InstallProgress:
    """只为实际安装记录有限频率的字节进度，不复制业务运行状态。"""

    def __init__(self, snapshot: str) -> None:
        """绑定原快照并初始化诊断计数。

        :param snapshot: 原清单 SHA-256，用于日志关联。
        """
        self._snapshot = snapshot
        self._last = time.monotonic()
        self._read_bytes = 0
        self._written_bytes = 0
        self.files = 0

    def read(self, count: int) -> None:
        """记录真实读取进度，长文件读取也定期交付诊断。

        :param count: 当前实际读取的字节数。
        """
        self._read_bytes += count
        self._emit()

    def written(self, count: int) -> None:
        """记录真实暂存写入进度。

        :param count: 当前实际写出的字节数。
        """
        self._written_bytes += count
        self._emit()

    def _emit(self) -> None:
        """最多每五秒记录一次进度，不输出资源内容或大对象。"""
        now = time.monotonic()
        if now - self._last >= 5:
            self._last = now
            _LOGGER.info(
                "resource_install_progress snapshot=%s files=%d read_bytes=%d written_bytes=%d",
                self._snapshot, self.files, self._read_bytes, self._written_bytes,
            )


@contextmanager
def _opened_relative_directory(root: int, path: str, *, modes: tuple[int, ...]) -> Iterator[int]:
    """从保留根逐段打开内部相对目录，校验后关闭所有临时句柄。

    :param root: 原目录根。
    :param path: 内部生成的相对目录，空字符串表示根自身。
    :param modes: 中间及目标目录允许的权限。
    :yields: 当前实际目录句柄。
    """
    descriptors = [os.dup(root)]
    parts = [] if not path else path.split("/")
    try:
        for part in parts:
            descriptors.append(open_child_directory(descriptors[-1], part, modes=modes))
        yield descriptors[-1]
        for index, part in enumerate(parts):
            validate_directory(descriptors[index + 1], descriptors[index], part, modes=modes)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _write_stage_file(
    stage: int, relative: str, data: bytes, owned: dict[str, _Identity], progress: _InstallProgress,
) -> None:
    """在本次独占暂存中建立所需目录及新文件，登记清理所需原 inode。

    :param stage: 本次暂存根句柄。
    :param relative: 清单导出的包内相对位置。
    :param data: 已核对的确切字节。
    :param owned: 仅存本次实际创建对象的设备和 inode。
    :param progress: 本次安装的限频诊断计数。
    :raises OSError: 写入、改权或文件同步失败。
    """
    descriptors = [os.dup(stage)]
    parts = relative.split("/")
    prefix = ""
    try:
        for part in parts[:-1]:
            prefix = f"{prefix}/{part}" if prefix else part
            if prefix not in owned:
                os.mkdir(part, mode=0o700, dir_fd=descriptors[-1])
                child = open_child_directory(descriptors[-1], part)
                owned[prefix] = file_identity(child)
            else:
                child = open_child_directory(descriptors[-1], part)
                if file_identity(child) != owned[prefix]:
                    os.close(child)
                    raise OSError("本次暂存子目录已被替换")
            descriptors.append(child)
        output = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            mode=0o600, dir_fd=descriptors[-1],
        )
        try:
            owned[relative] = file_identity(output)
            for offset in range(0, len(data), 1024 * 1024):
                chunk = data[offset:offset + 1024 * 1024]
                _write_all(output, chunk)
                progress.written(len(chunk))
            os.fchmod(output, 0o400)
            os.fsync(output)
        finally:
            os.close(output)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _capture_objects(snapshot: int, manifest: ResourceManifest) -> dict[str, _Identity]:
    """核对并记录声明快照树各对象的进程内身份。

    :param snapshot: 已发布或待发布完整快照根。
    :param manifest: 控制允许对象集合的唯一清单。
    :returns: 内部相对位置到设备、inode 的观察映射。
    :raises OSError: 声明对象缺失、不安全或打开期间发生替换。
    """
    objects = {"": file_identity(snapshot)}
    paths = ["manifest.json", *("payload/" + item.path.value for item in manifest.files)]
    for path in paths:
        parts = path.split("/")
        descriptors = [os.dup(snapshot)]
        prefix = ""
        try:
            for part in parts[:-1]:
                prefix = f"{prefix}/{part}" if prefix else part
                child = open_child_directory(descriptors[-1], part, modes=(0o500, 0o700))
                descriptors.append(child)
                identity = file_identity(child)
                if prefix in objects and objects[prefix] != identity:
                    raise OSError("资源目录在核对期间被替换")
                objects[prefix] = identity
            info = os.stat(parts[-1], dir_fd=descriptors[-1], follow_symlinks=False)
            _validate_regular(info, modes=(0o400,))
            objects[path] = (info.st_dev, info.st_ino)
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    return objects


def _seal_stage(stage: int, manifest: ResourceManifest, owned: dict[str, _Identity]) -> None:
    """核对本次对象并封存内部目录，根保留跨父重命名所需的写权限。

    :param stage: 完整暂存根。
    :param manifest: 原资源清单。
    :param owned: 本次实际创建的对象身份。
    :raises OSError: 内容布局、对象归属、改权或同步失败。
    """
    if _capture_objects(stage, manifest) != owned:
        raise OSError("暂存树不再完全属于本次安装")
    directories = {"", "payload"}
    for item in manifest.files:
        parts = item.path.value.split("/")
        directories.update("payload/" + "/".join(parts[:index]) for index in range(1, len(parts)))
    ordered = sorted((path.count("/") + bool(path), path) for path in directories)
    for _, path in reversed(ordered):
        with _opened_relative_directory(stage, path, modes=(0o700, 0o500)) as directory:
            if file_identity(directory) != owned[path]:
                raise OSError("暂存目录已被替换")
            if path:
                os.fchmod(directory, 0o500)
            os.fsync(directory)


def _clean_owned_stage(parent: int, name: str, owned: dict[str, _Identity]) -> None:
    """核对整棵暂存仍全属本次后定点删除，未知或替换对象保留现场。

    :param parent: 暂存集合句柄。
    :param name: 本次独占建立的技术目录名。
    :param owned: 每个本次已创建对象的原身份。
    :raises OSError: 现场含未知对象、inode 已变化或清理未完成。
    """
    try:
        stage = open_child_directory(parent, name, modes=(0o700, 0o500))
    except FileNotFoundError:
        return
    try:
        if file_identity(stage) != owned[""]:
            raise OSError("暂存根已被替换，保留现场")
        pending = [(os.dup(stage), "")]
        directories: list[str] = []
        files: list[str] = []
        try:
            while pending:
                current, prefix = pending.pop()
                try:
                    directories.append(prefix)
                    with os.scandir(current) as entries:
                        for entry in entries:
                            path = f"{prefix}/{entry.name}" if prefix else entry.name
                            info = entry.stat(follow_symlinks=False)
                            if owned.get(path) != (info.st_dev, info.st_ino):
                                raise OSError("暂存含未知或已替换对象，保留现场")
                            if stat.S_ISDIR(info.st_mode):
                                pending.append((open_child_directory(current, entry.name, modes=(0o700, 0o500)), path))
                            else:
                                _validate_regular(info, modes=(0o400, 0o600))
                                files.append(path)
                finally:
                    os.close(current)
        finally:
            for descriptor, _ in pending:
                os.close(descriptor)
        for path in directories:
            with _opened_relative_directory(stage, path, modes=(0o500, 0o700)) as directory:
                if file_identity(directory) != owned[path]:
                    raise OSError("暂存目录在清理前被替换")
                os.fchmod(directory, 0o700)
        for path in files:
            parts = path.split("/")
            with _opened_relative_directory(stage, "/".join(parts[:-1]), modes=(0o700,)) as directory:
                info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if owned[path] != (info.st_dev, info.st_ino):
                    raise OSError("暂存文件在清理时被替换")
                os.unlink(parts[-1], dir_fd=directory)
        for _, path in reversed(sorted((path.count("/") + bool(path), path) for path in directories if path)):
            parts = path.split("/")
            with _opened_relative_directory(stage, "/".join(parts[:-1]), modes=(0o700,)) as directory:
                info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if owned[path] != (info.st_dev, info.st_ino):
                    raise OSError("暂存目录在删除前被替换")
                os.rmdir(parts[-1], dir_fd=directory)
        validate_directory(stage, parent, name, modes=(0o700,))
        os.rmdir(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(stage)


class LocalResourceStore:
    """只冻结资源根、限额和原布局身份，实际 I/O 每次独立持有句柄。

    :param root: 既有完整资源根。
    :param limits: 唯一操作限额；不加载环境或设置业务能力。
    """

    def __init__(self, root: Path, limits: ResourceLimits) -> None:
        """核对已存在的资源布局，不隐式初始化或修复。

        :param root: 已完成初始化的受管位置。
        :param limits: 装配注入的实际文件预算。
        """
        if type(limits) is not ResourceLimits:
            raise TypeError("资源存储需要 ResourceLimits")
        self._root = safe_root_path(root)
        self._limits = limits
        with _opened_layout(self._root) as layout:
            self._identities = layout.identities()

    @classmethod
    def initialize(cls, root: Path, limits: ResourceLimits) -> "LocalResourceStore":
        """显式建立安全空根及固定控制布局，失败只关闭句柄并保留现场。

        :param root: 不存在或已确认空白的私有根。
        :param limits: 操作限额。
        :returns: 不持有安装锁的资源存储。
        :raises OSError: 根非空、不安全或初始化同步失败。
        """
        if type(limits) is not ResourceLimits:
            raise TypeError("资源存储需要 ResourceLimits")
        absolute = safe_root_path(root)
        parent = _open_parent(absolute)
        try:
            try:
                os.mkdir(absolute.name, mode=0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
            directory = open_child_directory(parent, absolute.name)
            try:
                with os.scandir(directory) as entries:
                    if next(entries, None) is not None:
                        raise FileExistsError("资源初始化只接受空白根")
                lock = os.open(
                    ".install.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    mode=0o600, dir_fd=directory,
                )
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    os.fsync(lock)
                    for name in (".staging", "snapshots"):
                        os.mkdir(name, mode=0o700, dir_fd=directory)
                        child = open_child_directory(directory, name)
                        try:
                            os.fsync(child)
                        finally:
                            os.close(child)
                    os.fsync(directory)
                finally:
                    os.close(lock)
            finally:
                os.close(directory)
        finally:
            os.close(parent)
        return cls(absolute, limits)

    @classmethod
    def open(cls, root: Path, limits: ResourceLimits) -> "LocalResourceStore":
        """只打开完整布局，不重建缺失目录或控制文件。

        :param root: 已初始化资源根。
        :param limits: 本次装配限额。
        :returns: 不持有常驻句柄或写锁的资源存储。
        """
        return cls(root, limits)

    @contextmanager
    def _layout(self) -> Iterator[_Layout]:
        """打开本次操作布局并拒绝原实例已观察的目录替换。

        :yields: 仅在操作期间有效的布局句柄。
        :raises OSError: 根或控制对象已经改变。
        """
        with _opened_layout(self._root) as layout:
            if layout.identities() != self._identities:
                raise OSError("资源存储原布局 inode 已改变")
            yield layout

    def install(self, source_root: Path, bundle_name: str, expected: ContentFingerprint) -> ContentFingerprint:
        """在本次排他安装内核对完整源包，生成不可覆盖的只读资源快照。

        :param source_root: 可信部署注入的私有资源包来源根。
        :param bundle_name: 该根中的单段资源包名称。
        :param expected: 构建回执中的 manifest 原始字节指纹。
        :returns: 已发布并同步的原始清单指纹，不表示资源可执行。
        :raises OSError: 来源、预算、内容、锁或发布失败；最终目录可能已发布。
        :raises ResourceContractError: 清单或输入名称违反当前契约。
        """
        if type(expected) is not ContentFingerprint or type(bundle_name) is not str:
            raise TypeError("资源安装需要快照指纹和单段包名")
        checked_name = ResourcePath(bundle_name)
        if "/" in checked_name.value:
            raise ResourceContractError("安装包名称只能是单段名称")
        source = safe_root_path(source_root)
        if source.is_relative_to(self._root) or self._root.is_relative_to(source):
            raise ValueError("资源来源与安装根必须分开")
        if expected.byte_size > self._limits.max_manifest_bytes:
            raise OSError("预期资源清单超过预算")
        with self._layout() as layout:
            fcntl.flock(layout.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            layout.validate()
            try:
                os.stat(expected.sha256, dir_fd=layout.snapshots, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("资源快照目标已经存在，不覆盖或认领")
            with opened_resource_directory(source) as incoming:
                bundle = open_child_directory(incoming, bundle_name)
                try:
                    _require_entries(bundle, {"manifest.json", "payload"})
                    raw = read_regular_bytes(bundle, "manifest.json", max_bytes=expected.byte_size)
                    if fingerprint_bytes(raw) != expected:
                        raise ResourceContractError("资源清单与原构建回执不匹配")
                    manifest = parse_manifest(raw)
                    validate_manifest_limits(manifest, self._limits)
                    payload = open_child_directory(bundle, "payload")
                    try:
                        list_payload_paths(
                            payload, self._limits, expected_paths=tuple(item.path for item in manifest.files),
                        )
                        self._install_payload(layout, payload, raw, manifest, expected)
                        validate_directory(payload, bundle, "payload", modes=(0o700,))
                    finally:
                        os.close(payload)
                    _require_entries(bundle, {"manifest.json", "payload"})
                    validate_directory(bundle, incoming, bundle_name, modes=(0o700,))
                finally:
                    os.close(bundle)
            return expected

    def _install_payload(
        self, layout: _Layout, source: int, raw: bytes, manifest: ResourceManifest, expected: ContentFingerprint,
    ) -> None:
        """持锁建立本次暂存、核对全部字节并发布，异常只清理本次对象。

        :param layout: 本次持锁布局。
        :param source: 已核对来源 payload。
        :param raw: 原始清单字节。
        :param manifest: 同一清单的解析记录。
        :param expected: 原快照内容身份。
        """
        name = "install-" + secrets.token_hex(16)
        os.mkdir(name, mode=0o700, dir_fd=layout.staging)
        stage = open_child_directory(layout.staging, name)
        owned = {"": file_identity(stage)}
        progress = _InstallProgress(expected.sha256)
        try:
            _write_stage_file(stage, "manifest.json", raw, owned, progress)
            for item in manifest.files:
                data = read_payload_file(
                    source, item.path, max_bytes=item.content.byte_size,
                    directory_modes=(0o700,), file_modes=(0o400, 0o600), progress=progress.read,
                )
                if fingerprint_bytes(data) != item.content:
                    raise ResourceContractError(f"来源资源内容不符：{item.path.value}")
                _write_stage_file(stage, "payload/" + item.path.value, data, owned, progress)
                progress.files += 1
            _require_entries(stage, {"manifest.json", "payload"})
            payload = open_child_directory(stage, "payload")
            try:
                verify_payload(payload, manifest, self._limits, file_modes=(0o400,), progress=progress.read)
            finally:
                os.close(payload)
            _seal_stage(stage, manifest, owned)
            os.fsync(layout.staging)
            layout.validate()
            validate_directory(stage, layout.staging, name, modes=(0o700,))
            commit_file_no_replace(layout.staging, name, layout.snapshots, expected.sha256)
            os.fchmod(stage, 0o500)
            os.fsync(stage)
            os.fsync(layout.snapshots)
            os.fsync(layout.staging)
            validate_directory(stage, layout.snapshots, expected.sha256, modes=(0o500,))
        except BaseException as cause:
            try:
                _clean_owned_stage(layout.staging, name, owned)
            except OSError as cleanup:
                cause.add_note(f"本次资源暂存清理未确认：{cleanup}")
            raise
        finally:
            os.close(stage)

    def pin(self, snapshot: ContentFingerprint) -> "LocalResourceReader":
        """全量核对确切已发布快照，建立不持安装锁的固定读者。

        :param snapshot: 调用方保留的原始清单指纹。
        :returns: 固定清单、根及已观察对象身份的只读适配器。
        :raises OSError: 快照缺失、不安全、超限或发生可观察替换。
        :raises ResourceContractError: 清单或实际字节与指纹不匹配。
        """
        if type(snapshot) is not ContentFingerprint:
            raise TypeError("资源固定需要 ContentFingerprint")
        with self._layout() as layout:
            directory = open_child_directory(layout.snapshots, snapshot.sha256, modes=(0o500,))
            try:
                _require_entries(directory, {"manifest.json", "payload"})
                raw = read_regular_bytes(
                    directory, "manifest.json", max_bytes=min(snapshot.byte_size, self._limits.max_manifest_bytes),
                    modes=(0o400,),
                )
                if fingerprint_bytes(raw) != snapshot:
                    raise ResourceContractError("已安装清单与固定快照不符")
                manifest = parse_manifest(raw)
                validate_manifest_limits(manifest, self._limits)
                objects = _capture_objects(directory, manifest)
                payload = open_child_directory(directory, "payload", modes=(0o500,))
                try:
                    verify_payload(payload, manifest, self._limits, directory_mode=0o500, file_modes=(0o400,))
                finally:
                    os.close(payload)
                if _capture_objects(directory, manifest) != objects:
                    raise OSError("资源快照在固定期间发生替换")
                final_raw = read_regular_bytes(directory, "manifest.json", max_bytes=len(raw), modes=(0o400,))
                if final_raw != raw:
                    raise ResourceContractError("资源清单在固定期间变化")
                validate_directory(directory, layout.snapshots, snapshot.sha256, modes=(0o500,))
                return LocalResourceReader(self, snapshot, manifest, objects)
            finally:
                os.close(directory)


class LocalResourceReader(ResourceReader):
    """消费一个已经全量核对的资源快照，各次读取独立打开并校验句柄。

    :param store: 不持常驻句柄的受管存储。
    :param snapshot: 固定的清单原始字节指纹。
    :param manifest: 已解析且不可变的唯一资源声明。
    :param objects: pin 时实际观察的目录及文件身份，不作为持久身份协议。
    """

    def __init__(
        self, store: LocalResourceStore, snapshot: ContentFingerprint, manifest: ResourceManifest,
        objects: dict[str, _Identity],
    ) -> None:
        """保存固定读取所需事实，不取得写锁或为调用者切换版本。

        :param store: 原存储实例。
        :param snapshot: 原清单指纹。
        :param manifest: 原不可变清单。
        :param objects: 原进程内对象观察；复制后不再修改。
        """
        self._store = store
        self._snapshot = snapshot
        self._manifest = manifest
        self._objects = objects.copy()

    def describe(self, key: ResourceKey) -> ResourceDescription | None:
        """仅返回固定声明的元数据，不能把描述存在当作当前文件可访问。

        :param key: 原快照中的逻辑键。
        :returns: 已声明资源的描述，或明确未声明时的空值。
        """
        definition = self._manifest.find_resource(key)
        return None if definition is None else ResourceDescription(ResourceReference(self._snapshot, key), definition)

    def read_file(self, key: ResourceKey, path: ResourcePath) -> bytes:
        """只读取该逻辑键直接声明的文件，核对原 inode 和实际内容指纹。

        :param key: 固定快照内已声明的资源键。
        :param path: 该资源直接声明的文件路径。
        :returns: 本次真实取得且匹配原清单的有限字节。
        :raises ResourceContractError: 资源、文件归属或内容与声明不符。
        :raises OSError: 原快照无法访问或对象已经被替换。
        """
        definition = self._manifest.find_resource(key)
        if type(path) is not ResourcePath:
            raise TypeError("资源读取需要 ResourcePath")
        if definition is None or path not in definition.files:
            raise ResourceContractError("资源文件不属于所选逻辑键的直接声明")
        item = self._manifest.find_file(path)
        assert item is not None
        with self._store._layout() as layout:
            snapshot = open_child_directory(layout.snapshots, self._snapshot.sha256, modes=(0o500,))
            descriptors = [snapshot]
            try:
                if file_identity(snapshot) != self._objects[""]:
                    raise OSError("固定快照目录已被替换")
                _require_entries(snapshot, {"manifest.json", "payload"})
                raw = read_regular_bytes(
                    snapshot, "manifest.json", max_bytes=self._snapshot.byte_size, modes=(0o400,),
                    expected_identity=self._objects["manifest.json"],
                )
                if fingerprint_bytes(raw) != self._snapshot:
                    raise ResourceContractError("固定清单内容已改变")
                directory_parts = ["payload", *path.value.split("/")[:-1]]
                prefix = ""
                for part in directory_parts:
                    child = open_child_directory(descriptors[-1], part, modes=(0o500,))
                    descriptors.append(child)
                    prefix = f"{prefix}/{part}" if prefix else part
                    if file_identity(child) != self._objects[prefix]:
                        raise OSError("固定资源路径的目录 inode 已被替换")
                data = read_regular_bytes(
                    descriptors[-1], path.value.split("/")[-1], max_bytes=item.content.byte_size,
                    modes=(0o400,), expected_identity=self._objects["payload/" + path.value],
                )
                if fingerprint_bytes(data) != item.content:
                    raise ResourceContractError("固定资源文件的实际内容不符")
                for index, part in enumerate(directory_parts):
                    validate_directory(descriptors[index + 1], descriptors[index], part, modes=(0o500,))
                validate_directory(snapshot, layout.snapshots, self._snapshot.sha256, modes=(0o500,))
                return data
            finally:
                for descriptor in reversed(descriptors):
                    os.close(descriptor)
