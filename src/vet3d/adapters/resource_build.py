# 文件信息：L1-03 受管资源唯一维护源的显式构建入口。
# 作用：读取 resource-spec.json 与声明的 payload 原件，单向生成实际摘要和 manifest。
# 边界：仅供受信 Operations 同步调用；不执行脚本、不安装依赖，不生成已安装事实。
# 恢复：输出必须不存在且由本次独占；普通失败核对根 inode 后清理，强退残留拒绝续建。
"""把单一元数据源和实际文件构建为私有资源包，不维护旁路元数据清单。"""

import os
from pathlib import Path
import shutil

from vet3d.artifacts import ContentFingerprint
from vet3d.resources import (
    ResourceContractError, ResourceFile, ResourceManifest, ResourcePath,
    fingerprint_bytes, parse_resource_spec, serialize_manifest,
)

from .artifact_files import _write_all
from .resource_io import (
    ResourceLimits, file_identity, list_payload_paths, open_child_directory, opened_resource_directory,
    read_payload_file, read_regular_bytes, safe_root_path, validate_directory,
)
from .workspace_directories import _DIRECTORY_FLAGS, _open_parent


_SOURCE_DIRECTORY_MODES = (0o700, 0o755)
_SOURCE_FILE_MODES = (0o400, 0o600, 0o644)


def _require_source_layout(directory: int) -> None:
    """要求维护源只包含元数据声明与 payload，不隐式收集其他目录或文件。

    :param directory: 已核对的维护源目录描述符。
    :raises ResourceContractError: 存在额外根条目或缺少必要条目。
    """
    names: set[str] = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in ("resource-spec.json", "payload"):
                raise ResourceContractError("资源维护源只能包含 resource-spec.json 和 payload")
            names.add(entry.name)
    if names != {"resource-spec.json", "payload"}:
        raise ResourceContractError("资源维护源缺少声明文件或 payload")


def _output_parent(payload: int, path: ResourcePath) -> int:
    """只在本次新建的私有输出中准备声明文件的父目录。

    :param payload: 本次输出的 payload 目录描述符。
    :param path: 已通过资源契约校验的文件位置。
    :returns: 由调用方负责关闭的文件父目录描述符。
    :raises OSError: 目录创建、属性检查或同步失败。
    """
    directory = os.dup(payload)
    try:
        for name in path.value.split("/")[:-1]:
            try:
                os.mkdir(name, mode=0o700, dir_fd=directory)
                os.fsync(directory)
            except FileExistsError:
                pass
            child = open_child_directory(directory, name)
            os.close(directory)
            directory = child
        return directory
    except BaseException:
        os.close(directory)
        raise


def _write_new_file(directory: int, name: str, content: bytes) -> None:
    """独占写入一个输出文件，同步原始字节并固定只读权限。

    :param directory: 本次拥有的私有输出父目录描述符。
    :param name: 已由声明或固定布局确定的单段文件名。
    :param content: 按原样保存的完整字节。
    :raises OSError: 创建、写入、权限设置或同步失败。
    """
    descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        mode=0o600, dir_fd=directory,
    )
    try:
        _write_all(descriptor, content)
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory)


def _remove_owned_output(parent: int, name: str, identity: tuple[int, int]) -> None:
    """确认独占输出根仍是原 inode 后清理整棵输出，不提供逐子项归属追踪。

    :param parent: 创建输出时持有的原父目录描述符。
    :param name: 本次创建的输出目录名。
    :param identity: 创建后取得的设备与 inode。
    :raises OSError: 输出已被替换、清理失败或目录同步失败。
    """
    try:
        observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if (observed.st_dev, observed.st_ino) != identity:
        raise OSError("构建输出已被替换，保留现场而不删除未知对象")
    shutil.rmtree(name, dir_fd=parent)
    os.fsync(parent)


def build_resource_bundle(source_root: Path, output: Path, *, limits: ResourceLimits) -> ContentFingerprint:
    """从唯一受信声明构建独立资源包，摘要只从本次实际读取的字节派生。

    维护源可使用当前用户所有的普通 Git 只读权限；输出始终为私有目录和
    只读文件。元数据通过领域的同一解析器读取，构建不推断脚本依赖，也不
    执行任何 payload。返回的清单指纹不是安装、执行或业务验收事实。

    :param source_root: 仅含 resource-spec.json 与 payload 的维护源目录。
    :param output: 必须不存在且与维护源不重叠的输出目录。
    :param limits: 由 Operations 注入的文件数、单文件、总量及清单字节预算。
    :returns: 构建完成的 manifest 原始字节指纹，用于随后显式安装时固定输入。
    :raises ValueError: 输入根重叠或资源声明不符合契约。
    :raises OSError: 目标存在、路径不安全、源文件变化或实际 I/O 失败。
    """
    if type(limits) is not ResourceLimits:
        raise TypeError("资源构建需要明确的 ResourceLimits")
    source_path = safe_root_path(source_root)
    output_path = safe_root_path(output)
    if source_path.is_relative_to(output_path) or output_path.is_relative_to(source_path):
        raise ValueError("资源构建源与输出不能重叠")
    with opened_resource_directory(source_path, modes=_SOURCE_DIRECTORY_MODES) as source:
        _require_source_layout(source)
        specification = read_regular_bytes(
            source, "resource-spec.json", max_bytes=limits.max_manifest_bytes, modes=_SOURCE_FILE_MODES
        )
        definitions = parse_resource_spec(specification)
        declared = {path for definition in definitions for path in definition.files}
        if len(declared) > limits.max_files:
            raise ResourceContractError("资源声明超过构建文件数预算")
        declared_paths = tuple(sorted(declared, key=_path_text))
        source_payload = open_child_directory(source, "payload", modes=_SOURCE_DIRECTORY_MODES)
        try:
            list_payload_paths(
                source_payload, limits, expected_paths=declared_paths,
                directory_modes=_SOURCE_DIRECTORY_MODES, file_modes=_SOURCE_FILE_MODES,
            )
            parent = _open_parent(output_path)
            try:
                os.mkdir(output_path.name, mode=0o700, dir_fd=parent)
                opened = os.open(output_path.name, _DIRECTORY_FLAGS, dir_fd=parent)
                output_info = os.fstat(opened)
                identity = output_info.st_dev, output_info.st_ino
                try:
                    os.mkdir("payload", mode=0o700, dir_fd=opened)
                    payload = open_child_directory(opened, "payload")
                    try:
                        files: list[ResourceFile] = []
                        total_bytes = 0
                        for path in declared_paths:
                            content = read_payload_file(
                                source_payload, path,
                                max_bytes=min(limits.max_file_bytes, limits.max_total_bytes - total_bytes),
                                directory_modes=_SOURCE_DIRECTORY_MODES, file_modes=_SOURCE_FILE_MODES,
                            )
                            fingerprint = fingerprint_bytes(content)
                            destination = _output_parent(payload, path)
                            try:
                                _write_new_file(destination, path.value.split("/")[-1], content)
                            finally:
                                os.close(destination)
                            files.append(ResourceFile(path, fingerprint))
                            total_bytes += len(content)
                        manifest = ResourceManifest(tuple(files), definitions)
                        _require_source_layout(source)
                        if read_regular_bytes(
                            source, "resource-spec.json", max_bytes=limits.max_manifest_bytes,
                            modes=_SOURCE_FILE_MODES,
                        ) != specification:
                            raise OSError("资源声明在构建期间改变")
                        list_payload_paths(
                            source_payload, limits, expected_paths=declared_paths,
                            directory_modes=_SOURCE_DIRECTORY_MODES,
                            file_modes=_SOURCE_FILE_MODES,
                        )
                        for resource_file in manifest.files:
                            observed_bytes = read_payload_file(
                                source_payload, resource_file.path, max_bytes=resource_file.content.byte_size,
                                directory_modes=_SOURCE_DIRECTORY_MODES, file_modes=_SOURCE_FILE_MODES,
                            )
                            if fingerprint_bytes(observed_bytes) != resource_file.content:
                                raise OSError("资源源文件内容在构建期间改变")
                        validate_directory(source_payload, source, "payload", modes=_SOURCE_DIRECTORY_MODES)
                        manifest_bytes = serialize_manifest(manifest)
                        if len(manifest_bytes) > limits.max_manifest_bytes:
                            raise ResourceContractError("实际构建清单超过字节预算")
                        _write_new_file(opened, "manifest.json", manifest_bytes)
                        os.fsync(payload)
                        os.fsync(opened)
                        os.fsync(parent)
                        validate_directory(opened, parent, output_path.name, modes=(0o700,))
                        current_parent = _open_parent(output_path)
                        try:
                            if file_identity(current_parent) != file_identity(parent):
                                raise OSError("构建输出的父路径已经改变")
                        finally:
                            os.close(current_parent)
                    finally:
                        os.close(payload)
                except BaseException as cause:
                    try:
                        _remove_owned_output(parent, output_path.name, identity)
                    except OSError as cleanup_error:
                        cause.add_note(f"本次构建输出清理未确认：{cleanup_error}")
                    raise
                finally:
                    os.close(opened)
            finally:
                os.close(parent)
        finally:
            os.close(source_payload)
    return fingerprint_bytes(manifest_bytes)


def _path_text(path: ResourcePath) -> str:
    """提供确定性的文件排序键，不把清单顺序绑定到磁盘枚举顺序。

    :param path: 声明中的规范相对路径。
    :returns: 未修改的路径文本。
    """
    return path.value
