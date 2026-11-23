# 文件信息
# 按安装包目录读取磁盘文件并核对清单，向盘点命令提供可验证的记录。
"""Hi3D 安装目录盘点。

以只读方式度量磁盘文件并对账随包清单，输出安装包相对路径、内容摘要、
部署归属及来源映射。ASAR 成员由归档读取模块单独核查。
"""

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import TypedDict

from .records import FileFingerprint, InventoryRecord


_PREBUILT = "runtime/prebuilt-skills/"
_PREBUILT_MANIFEST = _PREBUILT + "prebuilt.json"
_WORKFLOW_MANIFEST = _PREBUILT + ".workflow-bundle.json"
_RUNTIME_MANIFEST = "runtime/manifest.json"
_METADATA = {_PREBUILT_MANIFEST, _WORKFLOW_MANIFEST, _RUNTIME_MANIFEST}
DISK_ANCHORS = _METADATA | {"runtime/dist/runtime.mjs"}
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_WINDOWS_DEVICES = {"aux", "con", "conin$", "conout$", "nul", "prn"} | {
    prefix + numeral for prefix in ("com", "lpt") for numeral in "123456789¹²³"
}

_JsonObject = dict[str, object]


class DiskSummary(TypedDict):
    """磁盘对账结果及本机扫描诊断。"""

    runtime_version: str
    platform: str
    arch: str
    profile: str
    prebuilt_entries: int
    public_entries: int
    hidden_entries: int
    prebuilt_files: int
    workflow_mappings: int
    prebuilt_declared_only_files: int
    unlisted_prebuilt_paths: list[str]
    excluded_cache_files: int
    excluded_prebuilt_cache_files: int


class _CacheCounts(TypedDict):
    """本次扫描跳过的 Python 缓存统计。"""

    all: int
    prebuilt: int


def _relative_path(value: object, label: str) -> str:
    """校验外部文件标识可作为安全的安装包相对路径。

    :param value: 清单或磁盘枚举提供的斜杠分隔路径。
    :param label: 用于定位错误的清单或数据来源。
    :return: 校验通过的原始相对路径。
    :raises ValueError: 路径为空、越界或包含 Windows 保留名称。
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: expected a nonempty relative path")
    for part in value.split("/"):
        if (
            not part
            or part in {".", ".."}
            or part.endswith((" ", "."))
            or part.split(".")[0].rstrip(" ").casefold() in _WINDOWS_DEVICES
            or any(
                character in '<>:"\\|?*' or ord(character) < 32
                or 0xD800 <= ord(character) <= 0xDFFF
                for character in part
            )
        ):
            raise ValueError(f"{label}: unsafe relative path {value!r}")
    return value


def _unique(key: str, seen: set[str], label: str) -> None:
    """登记一个名称，避免大小写不敏感文件系统中的歧义。

    :param key: 当前待登记的路径或入口名。
    :param seen: 本组已登记的折叠名称。
    :param label: 用于定位冲突的清单或数据来源。
    :raises ValueError: 已存在同名或仅大小写不同的记录。
    """
    folded = key.casefold()
    if folded in seen:
        raise ValueError(f"{label}: duplicate or case-conflicting path {key!r}")
    seen.add(folded)


def _regular_or_directory(info: os.stat_result, relative: str) -> None:
    """限制扫描范围内的条目为实际目录或常规文件。

    :param info: 未跟随链接取得的文件状态。
    :param relative: 用于错误定位的路径。
    :raises ValueError: 条目为链接、重解析点或特殊文件。
    """
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"reparse point or symlink: {relative}")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f"unsupported file type: {relative}")


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """提取用于核对一次读取前后身份的文件系统属性。

    :param info: 路径或文件句柄提供的状态。
    :return: 设备、节点、类型、字节数和修改时间。
    """
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns)


def _measure(path: Path, relative: str, *, capture_bytes: bool = False) -> tuple[FileFingerprint, bytes | None]:
    """读取一个文件的摘要并核对读取前后的身份。

    :param path: 安装目录中的实际文件路径。
    :param relative: 用于清单和元数据识别的相对路径。
    :param capture_bytes: 同时保留校验过的原始字节，供小型资源归档。
    :return: 文件度量和在请求时或对指定清单保留的原始字节。
    :raises ValueError: 条目类型不符或文件在读取时发生变化。
    """
    # Windows 上 DirEntry.stat() 不提供用于比对的设备号和节点号。
    info = path.lstat()
    _regular_or_directory(info, relative)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"expected a regular file: {relative}")
    original = _file_identity(info)
    with path.open("rb") as stream:
        if _file_identity(os.fstat(stream.fileno())) != original:
            raise ValueError(f"file changed before hashing: {relative}")
        if capture_bytes or relative in _METADATA:
            data = stream.read()
            digest = hashlib.sha256(data)
        else:
            data = None
            digest = hashlib.file_digest(stream, "sha256")
        if not (
            _file_identity(os.fstat(stream.fileno()))
            == _file_identity(path.lstat())
            == original
        ):
            raise ValueError(f"file changed while hashing: {relative}")
    return {"path": relative, "size": info.st_size, "sha256": digest.hexdigest()}, data


def _collect(
    resources: Path,
) -> tuple[dict[str, FileFingerprint], dict[str, bytes], _CacheCounts]:
    """枚举安装包目录并取得后续清单对账所需的文件字节身份。

    :param resources: 已校验和规范化的安装资源根。
    :return: 按相对路径索引的文件度量、元数据字节及跳过的缓存计数。
    :raises ValueError: 路径冲突、目录变化或条目类型不受支持。
    """
    files: dict[str, FileFingerprint] = {}
    metadata: dict[str, bytes] = {}
    seen: set[str] = set()
    excluded_caches: _CacheCounts = {"all": 0, "prebuilt": 0}
    directories = [(resources, "", False)]
    while directories:
        directory, prefix, in_cache = directories.pop()
        info = directory.lstat()
        _regular_or_directory(info, prefix)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"expected a directory: {prefix}")
        original = _file_identity(info)
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = prefix + entry.name
                _relative_path(relative, "filesystem")
                _unique(relative, seen, "filesystem")
                info = entry.stat(follow_symlinks=False)
                _regular_or_directory(info, relative)
                if relative == "app.asar":
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError("app.asar must be a regular file")
                    continue
                path = Path(entry.path)
                if stat.S_ISDIR(info.st_mode):
                    directories.append((
                        path, relative + "/", in_cache or entry.name.casefold() == "__pycache__"
                    ))
                elif in_cache or entry.name.casefold().endswith(".pyc"):
                    excluded_caches["all"] += 1
                    if relative.startswith(_PREBUILT):
                        excluded_caches["prebuilt"] += 1
                else:
                    files[relative], data = _measure(path, relative)
                    if data is not None:
                        metadata[relative] = data
        if _file_identity(directory.lstat()) != original:
            raise ValueError(f"directory changed while enumerating: {prefix}")
    return files, metadata, excluded_caches


def _read_metadata(raw: dict[str, bytes], name: str) -> _JsonObject:
    """解析与磁盘度量使用相同原件字节的清单。

    :param raw: 以安装包相对路径索引的原件字节。
    :param name: 需解析的清单路径。
    :return: 供各清单校验器读取的 JSON 对象。
    :raises ValueError: 清单缺失、结构无效或包含重复字段。
    """
    if name not in raw:
        raise ValueError(f"missing manifest: {name}")

    def unique_object(items: list[tuple[str, object]]) -> _JsonObject:
        """构造 JSON 对象并明确拒绝含义不确定的重复字段。

        :param items: 当前对象按原始顺序析出的字段对。
        :return: 仅含唯一字段的对象。
        :raises ValueError: 字段在同一对象内重复出现。
        """
        result: _JsonObject = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON field {key!r}")
            result[key] = value
        return result

    try:
        result: object = json.loads(raw[name], object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"{name}: {error}") from error
    if not isinstance(result, dict):
        raise ValueError(f"{name}: expected a JSON object")
    return result


def _rows(data: _JsonObject, key: str, label: str) -> list[object]:
    """读取后续需要逐项验证的清单数组。

    :param data: 已解析的清单对象。
    :param key: 声明的数组字段。
    :param label: 用于定位错误的清单名称。
    :return: 元素尚待检查的数组。
    :raises ValueError: 字段缺失或不是数组。
    """
    rows = data.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"{label}: {key} must be an array")
    return rows


def _digest(value: object, path: str) -> str:
    """规范化清单声明的文件摘要以供字节证据对账。

    :param value: 尚未校验的摘要字段。
    :param path: 对应的清单路径。
    :return: 小写十六进制 SHA-256。
    :raises ValueError: 值不符合 SHA-256 格式。
    """
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"invalid declared SHA-256: {path}")
    return value.lower()


def _deploy_entries(manifest: _JsonObject) -> dict[str, str]:
    """建立部署入口与其声明来源之间的映射。

    :param manifest: 预构建部署清单。
    :return: 由公开入口和隐藏依赖名称索引的来源路径。
    :raises ValueError: 入口记录缺失、重复或路径无效。
    """
    entries: dict[str, str] = {}
    seen: set[str] = set()
    for entry in _rows(manifest, "entries", "prebuilt.json"):
        if not isinstance(entry, dict):
            raise ValueError("prebuilt.json: expected an entry object")
        name = _relative_path(entry.get("name"), "prebuilt.json entry")
        if "/" in name:
            raise ValueError(f"prebuilt.json: nested entry name {name!r}")
        _unique(name, seen, "prebuilt.json entries")
        entries[name] = _relative_path(entry.get("source"), "prebuilt.json entry source")
    return entries


def _deploy_files(
    manifest: _JsonObject, files: dict[str, FileFingerprint]
) -> set[str]:
    """核对每个部署文件的实际摘要并固定已声明路径集合。

    :param manifest: 预构建部署清单。
    :param files: 盘点取得的实际文件度量。
    :return: 相对预构建目录的已核实部署路径。
    :raises ValueError: 存在缺失、重复、无效或摘要不同的条目。
    """
    deployed: set[str] = set()
    seen: set[str] = set()
    for entry in _rows(manifest, "files", "prebuilt.json"):
        if not isinstance(entry, dict):
            raise ValueError("prebuilt.json: expected a file object")
        relative = _relative_path(entry.get("path"), "prebuilt.json file")
        _unique(relative, seen, "prebuilt.json files")
        expected = _digest(entry.get("sha256"), relative)
        path = _PREBUILT + relative
        record = files.get(path)
        if record is None:
            raise ValueError(f"prebuilt.json: declared file missing or excluded: {relative}")
        if record["sha256"] != expected:
            raise ValueError(f"prebuilt.json: SHA-256 mismatch: {relative}")
        deployed.add(relative)
    if ".workflow-bundle.json" not in deployed:
        raise ValueError("prebuilt.json: workflow manifest is not locked by the deployment")
    return deployed


def _workflow_files(
    manifest: _JsonObject, files: dict[str, FileFingerprint], deployed: set[str]
) -> dict[str, str]:
    """对账工作流来源映射，并保留每条记录的实际部署路径。

    :param manifest: 随包工作流构建清单。
    :param files: 盘点取得的实际文件度量。
    :param deployed: 已通过部署清单核验的路径。
    :return: 从部署相对路径到构建来源路径的映射。
    :raises ValueError: 映射无效或与部署记录不一致。
    """
    mapped: dict[str, str] = {}
    seen: set[str] = set()
    for entry in _rows(manifest, "files", "workflow manifest"):
        if not isinstance(entry, list) or len(entry) != 3:
            raise ValueError("workflow manifest: expected [target, source, sha256]")
        target = _relative_path(entry[0], "workflow target")
        _unique(target, seen, "workflow targets")
        source = _relative_path(entry[1], "workflow source")
        expected = _digest(entry[2], target)
        if target not in deployed or files[_PREBUILT + target]["sha256"] != expected:
            raise ValueError(f"workflow manifest: target or SHA-256 disagrees with deployment: {target}")
        mapped[target] = source
    return mapped


def _release_text(data: _JsonObject, key: str, label: str) -> str:
    """读取用于版本锁定的已声明非空文字。

    :param data: 已解析的清单对象。
    :param key: 发行信息字段名。
    :param label: 用于定位错误的清单名称。
    :return: 清单中的原始文字。
    :raises ValueError: 字段缺失或为空白。
    """
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: invalid {key}")
    return value


def scan_disk(resources: Path) -> tuple[list[InventoryRecord], DiskSummary]:
    """盘点安装包磁盘文件，并在输出前对账三份发行元数据。

    :param resources: 原安装包的资源根。
    :return: 按相对路径排序的文件记录，以及发行汇总和本次诊断。
    :raises ValueError: 安装目录无效或发行清单、文件内容无法互相核实。
    """
    attributes = resources.lstat()
    _regular_or_directory(attributes, str(resources))
    if not stat.S_ISDIR(attributes.st_mode):
        raise ValueError("resources must be a directory")
    files, raw, excluded_caches = _collect(resources.resolve(strict=True))
    runtime = _read_metadata(raw, _RUNTIME_MANIFEST)
    deploy = _read_metadata(raw, _PREBUILT_MANIFEST)
    workflow = _read_metadata(raw, _WORKFLOW_MANIFEST)
    runtime_version = _release_text(runtime, "runtimeVersion", _RUNTIME_MANIFEST)
    platform = _release_text(runtime, "platform", _RUNTIME_MANIFEST)
    arch = _release_text(runtime, "arch", _RUNTIME_MANIFEST)
    if type(deploy.get("version")) is not int or deploy["version"] != 1:
        raise ValueError("prebuilt.json: expected schema version 1")
    if type(workflow.get("schema")) is not int or workflow["schema"] != 1:
        raise ValueError("workflow manifest: expected schema version 1")
    profile = _release_text(workflow, "profile", _WORKFLOW_MANIFEST)

    entries = _deploy_entries(deploy)
    declared = _deploy_files(deploy, files)
    for path in declared:
        owner = path.split("/")[0]
        if owner not in entries and path != ".workflow-bundle.json":
            raise ValueError(f"prebuilt.json: declared file has no package owner: {path}")
    public = {name for name in entries if not name.startswith(".dependency-")}
    for name in entries:
        entrypoint = "SKILL.md" if name in public else "REFERENCE.md"
        if f"{name}/{entrypoint}" not in declared:
            raise ValueError(f"prebuilt.json: missing package entry point: {name}/{entrypoint}")
    workflow_entries: set[str] = set()
    for item in _rows(workflow, "entries", "workflow manifest"):
        name = _relative_path(item, "workflow entry")
        _unique(name, workflow_entries, "workflow entries")
        if name not in public:
            raise ValueError(f"workflow manifest: unknown public entry: {name}")
    if len(workflow_entries) != len(public):
        raise ValueError("workflow public entries disagree with deployment")

    counts = runtime.get("prebuiltSkills")
    if not isinstance(counts, dict) or any(
        type(counts.get(key)) is not int or counts[key] != expected
        for key, expected in (("entries", len(entries)), ("files", len(declared)))
    ):
        raise ValueError("runtime/manifest.json: prebuiltSkills counts disagree with deployment")
    mapped = _workflow_files(workflow, files, declared)

    unlisted: list[str] = []
    records: list[InventoryRecord] = []
    for path, measured in sorted(files.items()):
        if path.startswith(_PREBUILT):
            relative = path.removeprefix(_PREBUILT)
            owner = relative.split("/")[0]
            record = InventoryRecord(**measured, scope="prebuilt-skill", declared_digest=relative in declared)
            if relative in mapped:
                record["source_path"] = mapped[relative]
            if owner in entries:
                record["package"] = owner
                record["package_source"] = entries[owner]
            if relative not in declared and path != _PREBUILT_MANIFEST:
                unlisted.append(relative)
        else:
            record = InventoryRecord(**measured, scope="runtime" if path.startswith("runtime/") else "resources")
        records.append(record)

    stats: DiskSummary = {
        "runtime_version": runtime_version,
        "platform": platform,
        "arch": arch,
        "profile": profile,
        "prebuilt_entries": len(entries),
        "public_entries": len(public),
        "hidden_entries": len(entries) - len(public),
        "prebuilt_files": len(declared),
        "workflow_mappings": len(mapped),
        "prebuilt_declared_only_files": len(declared) - len(mapped),
        "unlisted_prebuilt_paths": sorted(unlisted),
        "excluded_cache_files": excluded_caches["all"],
        "excluded_prebuilt_cache_files": excluded_caches["prebuilt"],
    }
    return records, stats
