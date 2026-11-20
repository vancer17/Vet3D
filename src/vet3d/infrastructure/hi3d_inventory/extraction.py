# 文件信息
# 从已锁定的 Hi3D 发行清单派生候选、引用边界和首批抽离文件。
# 本模块服务离线取证，不加载安装原件或注册运行时能力。
"""派生 Hi3D 1.2.11 的抽离清单。"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypedDict

from .cli import ARCHIVE, INVENTORY_NAME, LOCK_NAME, _json_bytes, _publish_file
from .disk import DISK_ANCHORS
from .records import InventoryRecord


EXTRACTION_NAME = "extraction.json"
RELEASE = {
    "runtime_version": "1.2.11",
    "platform": "win32",
    "arch": "x64",
    "profile": "sparc3d",
}
PREBUILT = "runtime/prebuilt-skills/"
BLENDER_TOOLS = PREBUILT + ".dependency-blender-tools/"
TEXTURE_BAKE = PREBUILT + ".dependency-texture-bake/"

# Runtime 安装包中可单独定位的宿主脚本、配置和模板。
HOST_CANDIDATES = frozenset({
    "runtime/prompts/skill-install-review.md",
    "runtime/support/pcg_yaml.py",
    "runtime/templates/AGENTS.md",
    "runtime/templates/config.toml",
    "runtime/templates/hooks/skill-credit.cjs",
    "runtime/templates/store-python.ps1",
})

# 已找到上游授权、供应方或官方资料来源的独立资产，逐路径保留。
ORIGIN_REVIEW_PREFIXES = (
    PREBUILT + "lamp-design/assets/experience/vendor/",
    PREBUILT + "print-kit/assets/viewer/vendor/",
    PREBUILT + "rhino-control/references/official/",
)
ORIGIN_REVIEW_FILES = frozenset({
    PREBUILT + ".dependency-head-hair-split/assets/viewer/LICENSE-three.txt",
    PREBUILT + ".dependency-head-hair-split/assets/viewer/OrbitControls.js",
    PREBUILT + ".dependency-head-hair-split/assets/viewer/three.min.js",
    PREBUILT + "rhino-control/references/catalog.zip",
    PREBUILT + "roblox-api/references/hi3d-roblox-official-docs.zip",
})


class _ExtractionBatch(TypedDict):
    """表述抽离清单中已核对的入口、依赖和参考文件。"""

    entries: list[str]
    local_dependencies: dict[str, list[str]]
    upstream_references: list[str]
    external_dependencies: list[str]


class _ExtractionManifest(TypedDict):
    """表述发行索引派生的抽离清单，保持与既有 JSON 字段一致。"""

    schema_version: int
    source_inventory: dict[str, object]
    candidates: dict[str, list[str]]
    origin_review: list[str]
    reference_only: dict[str, dict[str, int]]
    batch: _ExtractionBatch
    external_references: dict[str, dict[str, list[str] | str]]


def _read_release(directory: Path) -> tuple[dict[str, object], list[InventoryRecord]]:
    """复核发行锁和索引，返回派生用的来源身份与路径记录。

    :param directory: 发行锁及其 JSONL 索引所在目录。
    :return: 本次来源的字节身份与盘点记录。
    :raises ValueError: 锁格式、发行身份、索引摘要或分区身份不符。
    """
    lock_bytes = (directory / LOCK_NAME).read_bytes()
    lock: dict[str, object] = json.loads(lock_bytes)
    if not isinstance(lock, dict) or lock.get("schema_version") != 1 or lock.get("inventory_file") != INVENTORY_NAME:
        raise ValueError("unsupported inventory lock format")
    indexed_bytes = (directory / INVENTORY_NAME).read_bytes()
    indexed_digest = hashlib.sha256(indexed_bytes).hexdigest()
    if lock.get("inventory_sha256") != indexed_digest:
        raise ValueError("inventory SHA-256 does not match the release lock")
    disk = lock.get("disk")
    if not isinstance(disk, dict) or any(disk.get(key) != value for key, value in RELEASE.items()):
        raise ValueError("extraction scope requires Hi3D 1.2.11 win32 x64 sparc3d")

    records: list[InventoryRecord] = [json.loads(line) for line in indexed_bytes.splitlines()]
    by_path = {record["path"]: record for record in records}
    if len({path.casefold() for path in by_path}) != len(records):
        raise ValueError("inventory contains duplicate or case-colliding paths")
    if len(records) != lock.get("records") or Counter(record["scope"] for record in records) != lock.get(
        "records_by_scope"
    ):
        raise ValueError("inventory counts do not match the release lock")
    anchors = lock.get("anchors_sha256")
    if not isinstance(anchors, dict) or anchors.keys() != DISK_ANCHORS | {ARCHIVE} or any(
        path not in by_path or by_path[path]["sha256"] != digest for path, digest in anchors.items()
    ):
        raise ValueError("inventory anchors do not match the release lock")
    return {
        **RELEASE,
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "inventory_sha256": indexed_digest,
        "records": len(records),
    }, records


def _group(record: InventoryRecord) -> str:
    """以交付来源和已核实的例外给一个物理路径归组。

    :param record: 发行锁覆盖的一条物理路径记录。
    :return: 候选、来源复核或只读引用的组名。
    """
    path = record["path"]
    if record["scope"] == "prebuilt-skill":
        if "/assets/taro/" in path or path.startswith(ORIGIN_REVIEW_PREFIXES) or path in ORIGIN_REVIEW_FILES:
            return "origin-review"
        if record.get("kind") == "release-metadata":
            return "release-metadata"
        if record.get("kind") == "test-script" or "/tests/" in path:
            return "upstream-verification"
        return "prebuilt" if record.get("source_path") else "unmapped-prebuilt"
    if path in HOST_CANDIDATES:
        return "host"
    if path.startswith("runtime/codex/"):
        return "codex"
    if path.startswith("runtime/.runtime-python/"):
        return "bundled-python"
    if path.startswith("app.asar/node_modules/@sparc3d/contracts/"):
        return "desktop-host-contracts"
    if path.startswith("app.asar/node_modules/"):
        return "desktop-dependencies"
    if path == ARCHIVE or record["scope"] == "asar-member":
        return "desktop-bundle"
    return "host-bundle-and-release-resources"


def _first_batch(available: set[str], prebuilt: set[str]) -> _ExtractionBatch:
    """列出首批原件、已核实的本地导入及上游参考文档。

    :param available: 发行锁中存在的全部交付路径。
    :param prebuilt: 通过候选归类的 Skill 交付路径。
    :return: 首批入口、依赖关系、证据路径和外部环境依赖。
    :raises ValueError: 入口、本地依赖或引用路径缺失。
    """
    bake = TEXTURE_BAKE + "scripts/texture_bake.py"
    entries = [BLENDER_TOOLS + "scripts/execute.py", BLENDER_TOOLS + "scripts/material_nodes.py", bake]
    cycles = TEXTURE_BAKE + "scripts/cycles_device.py"
    references = [
        BLENDER_TOOLS + "REFERENCE.md",
        BLENDER_TOOLS + "references/cycles-device.md",
        BLENDER_TOOLS + "references/material-nodes.md",
        TEXTURE_BAKE + "references/contract.md",
    ]
    if missing := (set(entries) | {cycles}) - prebuilt:
        raise ValueError("first-batch resource not found among candidates: " + ", ".join(sorted(missing)))
    if missing := set(references) - available:
        raise ValueError("first-batch upstream reference missing: " + ", ".join(sorted(missing)))
    return {
        "entries": entries,
        "local_dependencies": {bake: [cycles]},
        "upstream_references": references,
        "external_dependencies": ["blender"],
    }


def _derive(identity: dict[str, object], records: list[InventoryRecord]) -> _ExtractionManifest:
    """生成只引用发行锁路径的离线抽离清单。

    :param identity: 已核对的发行锁与 JSONL 身份。
    :param records: 发行锁对应的全部文件记录。
    :return: 可稳定序列化的抽离范围及首批文件。
    """
    paths: defaultdict[str, list[str]] = defaultdict(list)
    bytes_by_group: Counter[str] = Counter()
    for record in records:
        group = _group(record)
        paths[group].append(record["path"])
        bytes_by_group[group] += record["size"]

    candidates = {group: sorted(paths.pop(group)) for group in ("prebuilt", "host")}
    if missing := HOST_CANDIDATES - set(candidates["host"]):
        raise ValueError("host candidate missing from the release inventory: " + ", ".join(sorted(missing)))
    origin_review = sorted(paths.pop("origin-review", []))
    return {
        "schema_version": 1,
        "source_inventory": identity,
        "candidates": candidates,
        "origin_review": origin_review,
        "reference_only": {
            group: {"records": len(members), "bytes": bytes_by_group[group]}
            for group, members in paths.items()
        },
        "batch": _first_batch({record["path"] for record in records}, set(candidates["prebuilt"])),
        "external_references": {
            "blender": {"provides": ["bpy", "cycles"], "source": "external-installation"},
        },
    }


def extraction_main(argv: list[str] | None = None) -> int:
    """从已锁定的发行证据发布抽离清单。

    :param argv: 命令参数，缺省时采用当前进程参数。
    :return: 成功返回 0，输入校验或发布失败返回 1。
    """
    parser = argparse.ArgumentParser(description="根据现有 Hi3D 发行锁派生抽离清单。")
    parser.add_argument("--inventory-dir", required=True, type=Path, help="已锁定的发行清单目录")
    parser.add_argument("--output-dir", required=True, type=Path, help="独立的抽离清单输出目录")
    args = parser.parse_args(argv)

    try:
        directory = args.inventory_dir.resolve()
        output = args.output_dir.resolve()
        if output.is_relative_to(directory):
            raise ValueError("output directory must be outside the read-only inventory directory")
        manifest = _json_bytes(_derive(*_read_release(directory)), pretty=True)
        output.mkdir(parents=True, exist_ok=True)
        target = output / EXTRACTION_NAME
        _publish_file(target, manifest)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"extraction: {error}", file=sys.stderr)
        return 1

    print(f"{target} sha256={hashlib.sha256(manifest).hexdigest()}")
    return 0
