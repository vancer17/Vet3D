# 文件信息
# 校验发行锚点并独占发布确定性的清单和锁，输出目录与安装目录隔离。
"""合并 Hi3D 磁盘文件和 ASAR 成员的盘点证据。

本模块执行发行锚点校验、确定性序列化和只写独立目录的锁定发布。
"""

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .asar import scan_asar
from .disk import DISK_ANCHORS, scan_disk
from .records import InventoryRecord


INVENTORY_NAME = "inventory.jsonl"
LOCK_NAME = "inventory.lock.json"
ARCHIVE = "app.asar"
BLENDER_SOURCES = {
    "tools/blender-tools/scripts/asset_scene.py",
    "tools/blender-tools/scripts/cycles_device.py",
    "tools/blender-tools/scripts/execute.py",
    "tools/blender-tools/scripts/material_nodes.py",
    "skills/texture-bake/scripts/texture_bake.py",
}
SCRIPT_HINTS = {
    ".py": "python",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".ps1": "powershell",
    ".sh": "shell",
    ".cmd": "cmd",
    ".bat": "cmd",
    ".luau": "luau",
    ".cs": "csharp",
}


@dataclass(frozen=True)
class Inventory:
    """保存待发布文件和仅用于本次运行的诊断信息。"""

    records: bytes
    lock: bytes
    count: int
    sha256: str
    ignored_caches: int


def _annotate(record: InventoryRecord) -> None:
    """为已核实的文件补充资源分类和解释器提示。

    :param record: 已经取得字节身份的文件记录。
    """
    path = PurePosixPath(record["path"])
    suffix = path.suffix.lower()
    hint = None
    if (member_path := record.get("member_path")) is not None:
        kind = "desktop-dependency" if member_path.startswith("node_modules/") else "desktop-member"
    elif record["path"] == ARCHIVE:
        kind = "desktop-archive"
    elif path.parts[:2] in (("runtime", ".runtime-python"), ("runtime", "codex")):
        kind = "runtime-dependency"
    elif path.parts[:2] in (("runtime", "prompts"), ("runtime", "templates")):
        kind = "host-template-or-prompt"
        hint = SCRIPT_HINTS.get(suffix)
    elif path.name in ("SKILL.md", "REFERENCE.md"):
        kind = "entry-document"
    elif path.name in ("prebuilt.json", ".workflow-bundle.json", ".runtime-profile.json"):
        kind = "release-metadata"
    elif suffix in SCRIPT_HINTS:
        kind = "test-script" if "tests" in path.parts or path.name.startswith("test_") else "script-or-module"
        hint = SCRIPT_HINTS[suffix]
    elif suffix == ".md":
        kind = "documentation"
    elif suffix in (".json", ".yaml", ".yml", ".toml", ".ini"):
        kind = "configuration-or-data"
    elif suffix in (".exe", ".dll", ".so", ".pyd", ".wasm"):
        kind = "binary"
    else:
        kind = "asset-or-data"

    record["kind"] = kind
    if (source_path := record.get("source_path")) is not None and source_path in BLENDER_SOURCES:
        hint = "blender-python"
    if hint:
        record["execution_hint"] = hint


def _json_bytes(value: object, *, pretty: bool = False) -> bytes:
    """以固定字段次序生成用于哈希锁定的 UTF-8 字节。

    :param value: 可序列化为 JSON 的记录。
    :param pretty: 是否使用缩进格式。
    :return: 以换行符结束的 JSON 字节。
    """
    if pretty:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    else:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (serialized + "\n").encode("utf-8")


def _regular_file(path: Path) -> os.stat_result:
    """取得仅允许普通文件的元数据。

    :param path: 安装文件或现有输出的路径。
    :return: 未跟随文件链接的状态记录。
    :raises ValueError: 目标是重解析点或其他非普通文件。
    """
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError(f"expected regular file without a symlink or reparse point: {path}")
    return info


def _record_path(record: InventoryRecord) -> str:
    """取得用来稳定排序的交付路径。

    :param record: 待写入清单的一条记录。
    :return: 文件的交付路径。
    """
    return record["path"]


def _scan_inventory(resources: Path) -> Inventory:
    """校验发行锚点，合并磁盘与 ASAR 记录并生成锁。

    :param resources: 安装包的 resources 目录。
    :return: 可发布的清单、锁定记录及运行诊断。
    :raises ValueError: 发行锚点缺失、摘要不符或盘点期间文件改变。
    """
    records, disk = scan_disk(resources)
    if missing := DISK_ANCHORS - {record["path"] for record in records}:
        raise ValueError("missing release anchors: " + ", ".join(sorted(missing)))

    archive = resources / ARCHIVE
    before = _regular_file(archive)
    members = scan_asar(archive)
    with archive.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    after = _regular_file(archive)
    if (before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev) != (
        after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev
    ):
        raise ValueError("app.asar changed during the scan")

    records.append({"path": ARCHIVE, "size": before.st_size, "sha256": archive_hash, "scope": "resources"})
    for member in members:
        member_path = member["path"]
        records.append({
            **member,
            "path": f"{ARCHIVE}/{member_path}",
            "member_path": member_path,
            "scope": "asar-member",
        })

    records.sort(key=_record_path)
    if len({record["path"].casefold() for record in records}) != len(records):
        raise ValueError("duplicate or case-colliding inventory paths")

    sources: defaultdict[str, set[str]] = defaultdict(set)
    for record in records:
        _annotate(record)
        if source_path := record.get("source_path"):
            sources[source_path].add(record["sha256"])

    inventory = b"".join(_json_bytes(record) for record in records)
    checksum = hashlib.sha256(inventory).hexdigest()
    anchors = DISK_ANCHORS | {ARCHIVE}
    lock = {
        "schema_version": 1,
        "inventory_file": INVENTORY_NAME,
        "inventory_sha256": checksum,
        "records": len(records),
        "records_by_scope": dict(Counter(record["scope"] for record in records)),
        "anchors_sha256": {
            record["path"]: record["sha256"] for record in records if record["path"] in anchors
        },
        "disk": {
            key: value
            for key, value in disk.items()
            if key not in {"excluded_cache_files", "excluded_prebuilt_cache_files"}
        },
        "asar": {
            "members": len(members),
            "verified_integrity": sum(member["integrity_verified"] for member in members),
        },
        "source_mapping": {
            "unique_source_paths": len(sources),
            "source_paths_with_delivery_variants": sum(len(hashes) > 1 for hashes in sources.values()),
        },
        "evidence_defaults": {
            "dependency_or_host_reference": None,
            "isolated_execution": None,
            "observed_in_rollout": None,
        },
    }
    return Inventory(inventory, _json_bytes(lock, pretty=True), len(records), checksum, disk["excluded_cache_files"])


def _matches_existing(target: Path, content: bytes) -> bool:
    """检查现有输出是否可原样复用。

    :param target: 清单或锁定记录的输出路径。
    :param content: 本次生成的字节。
    :return: 文件存在且内容相同则返回 True，未创建则返回 False。
    :raises ValueError: 目标类型不受支持或内容有差异。
    """
    try:
        _regular_file(target)
    except FileNotFoundError:
        return False
    if target.read_bytes() != content:
        raise ValueError(f"locked output differs: {target}; choose a new output directory")
    return True


def _publish_file(target: Path, content: bytes) -> None:
    """独占发布一个完整输出文件，复用并发写入的相同内容。

    :param target: 清单或锁定记录的输出路径。
    :param content: 待发布的全量字节。
    """
    if _matches_existing(target, content):
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".inventory-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if not _matches_existing(target, content):
                raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """执行只读盘点并发布 JSONL 清单及其配套锁。

    :param argv: 命令参数，缺省时采用当前进程参数。
    :return: 成功返回 0，盘点或发布失败返回 1。
    """
    parser = argparse.ArgumentParser(description="只读核对 Hi3D 安装资源并生成盘点清单与锁。")
    parser.add_argument("--resources-root", required=True, type=Path, help="安装包的 resources 目录")
    parser.add_argument("--output-dir", required=True, type=Path, help="独立于安装包的输出目录")
    args = parser.parse_args(argv)

    try:
        resources = args.resources_root.absolute()
        output = args.output_dir.resolve()
        if output.is_relative_to(resources.resolve()):
            raise ValueError("output directory must be outside the read-only resources root")
        inventory = _scan_inventory(resources)
        files = (
            (output / INVENTORY_NAME, inventory.records),
            (output / LOCK_NAME, inventory.lock),
        )
        output.mkdir(parents=True, exist_ok=True)
        for target, content in files:
            _matches_existing(target, content)
        for target, content in files:
            _publish_file(target, content)
    except (OSError, ValueError) as error:
        print(f"inventory: {error}", file=sys.stderr)
        return 1

    print(f"Locked {inventory.count} records in {output}")
    print(f"{INVENTORY_NAME} sha256={inventory.sha256}")
    print(f"Excluded local cache files: {inventory.ignored_caches}")
    return 0
