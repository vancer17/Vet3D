# 文件信息
# 校验既有发行锁和抽离清单，按人工复核的路径关系派生归档优先级。
# 输出限于清单和复核表，供离线取证与后续归档使用。
"""派生 Hi3D 资源优先级清单及逐批核查表。"""

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from .cli import _json_bytes, _matches_existing, _publish_file
from .extraction import _ExtractionManifest, _derive, _read_release
from .records import InventoryRecord


class _FileScope(TypedDict):
    """记录逐文件复核的纳入依据、直接本地依赖和待验证缺口。"""

    basis: str
    requires: list[str]
    pending: str


class _Group(TypedDict):
    """声明一项基础能力的入口、证据和能力外部前提。"""

    title: str
    entries: list[str]
    evidence: list[str]
    external: list[str]


class _BatchScope(TypedDict):
    """表述每批人工复核的能力与逐文件输入。"""

    schema_version: int
    groups: dict[str, _Group]
    files: dict[str, _FileScope]


class _Scope(_BatchScope):
    """保留已发布的 P0 范围输入与延期说明。"""

    deferred: dict[str, str]


class _SelectedFile(_FileScope):
    """将一条选择记录与其发行字节和来源关联。"""

    kind: Literal["archive", "evidence"]
    size: int
    sha256: str
    source_path: NotRequired[str]


class _Batch(TypedDict):
    """保持派生的能力分组与精确文件表结构。"""

    groups: dict[str, _Group]
    files: dict[str, _SelectedFile]


class _P1(TypedDict):
    """记录顺延至 P1 的既有试点路径。"""

    pilot: list[str]


class _P2(TypedDict):
    """记录待选候选统计及已知触发条件。"""

    remaining_candidates: int
    deferred: dict[str, str]


class _ManifestSource(TypedDict):
    """记录两批优先级清单共同使用的来源身份。"""

    schema_version: int
    source_inventory: dict[str, object]
    extraction_sha256: str
    scope_sha256: str


class _PriorityManifest(_ManifestSource):
    """表述归档前重新核对的原有 P0 优先级清单。"""

    p0: _Batch
    p1: _P1
    p2: _P2


class _P1Manifest(_ManifestSource):
    """表述接续 P0 发行身份的 P1 独立核查清单。"""

    p0_priority_sha256: str
    p1: _Batch


def _closure(roots: Iterable[str], decisions: dict[str, _FileScope], level: Literal["P0", "P1"]) -> set[str]:
    """遍历所选入口的显式直接依赖，解析唯一的交付文件集合。

    :param roots: 已按能力选择的入口或取证路径。
    :param decisions: 以安装交付路径索引的人工复核记录。
    :param level: 诊断使用的归档优先级。
    :return: 根路径及沿依赖可达的所有路径。
    :raises ValueError: 存在缺少逐文件复核记录的入口或依赖。
    """
    waiting = list(roots)
    seen: set[str] = set()
    while waiting:
        path = waiting.pop()
        if path in seen:
            continue
        if path not in decisions:
            raise ValueError(f"{level} entry or dependency has no scope record: {path}")
        seen.add(path)
        waiting.extend(decisions[path]["requires"])
    return seen


def _select_batch(
    scope: _BatchScope, candidates: set[str], inventory: list[InventoryRecord], level: Literal["P0", "P1"]
) -> dict[str, _SelectedFile]:
    """核对一批范围的直接依赖闭包、发行身份及抽离资格。

    :param scope: 人工复核的能力分组和逐文件依据。
    :param candidates: 抽离清单允许选作原件的路径。
    :param inventory: 发行索引中的路径及字节身份。
    :param level: 当前归档优先级，用于定位错误。
    :return: 按实际交付路径排序的文件表。
    :raises ValueError: 范围声明、依赖、发行路径或原件候选资格不一致。
    """
    if scope["schema_version"] != 1:
        raise ValueError("unsupported priority scope version")
    if not scope["groups"] or not scope["files"]:
        raise ValueError(f"priority scope requires {level} groups and file review records")
    groups = scope["groups"].values()
    decisions = scope["files"]
    archive = _closure((path for group in groups for path in group["entries"]), decisions, level)
    evidence = _closure((path for group in groups for path in group["evidence"]), decisions, level)
    selected = archive | evidence
    if orphans := decisions.keys() - selected:
        raise ValueError(f"unreferenced {level} scope records: " + ", ".join(sorted(orphans)))
    index = {record["path"]: record for record in inventory}
    if missing := selected - index.keys():
        raise ValueError(f"{level} paths missing from the release inventory: " + ", ".join(sorted(missing)))
    if excluded := archive - candidates:
        raise ValueError(f"{level} archive paths outside the extraction candidates: " + ", ".join(sorted(excluded)))

    files: dict[str, _SelectedFile] = {}
    for path in sorted(selected):
        decision = decisions[path]
        if not decision["basis"].strip() or not decision["pending"].strip():
            raise ValueError(f"missing {level} basis or pending verification: {path}")
        record = index[path]
        file: _SelectedFile = {
            **decision, "kind": "archive" if path in archive else "evidence",
            "size": record["size"], "sha256": record["sha256"],
        }
        if source := record.get("source_path"):
            file["source_path"] = source
        files[path] = file
    return files


def _select(
    scope: _Scope, extraction: _ExtractionManifest, inventory: list[InventoryRecord]
) -> tuple[dict[str, _SelectedFile], list[str], int]:
    """核对 P0 并从既有抽离首批派生顺延至 P1 的试点。

    :param scope: 已发布 P0 说明所用的范围输入。
    :param extraction: 已与同一发行锁核对的抽离清单。
    :param inventory: 发行索引中的路径及字节身份。
    :return: P0 文件表、P1 试点路径、其余候选记录数。
    """
    candidates = {path for paths in extraction["candidates"].values() for path in paths}
    files = _select_batch(scope, candidates, inventory, "P0")
    batch = extraction["batch"]
    pilot = set(batch["entries"])
    pilot.update(path for paths in batch["local_dependencies"].values() for path in paths)
    pilot -= files.keys()
    remaining = candidates - files.keys() - pilot
    if unexpected := scope["deferred"].keys() - remaining:
        raise ValueError("invalid deferred paths: " + ", ".join(sorted(unexpected)))
    return files, sorted(pilot), len(remaining)


def _render_batch(
    groups: dict[str, _Group], files: dict[str, _SelectedFile], level: Literal["P0", "P1"]
) -> list[str]:
    """渲染各批共用的能力及精确文件表。

    :param groups: 已核对的能力入口、证据及外部前提。
    :param files: 带发行身份的逐路径核查表。
    :param level: 用于标题与统计的归档优先级。
    :return: Markdown 能力表和文件表的各行。
    """
    archive_count = sum(file["kind"] == "archive" for file in files.values())
    lines = [
        f"{level} 共 {len(files)} 个交付路径，含 {archive_count} 个原件候选和 "
        f"{len(files) - archive_count} 个证据引用。所有路径相对 `resources/`。",
        "",
        f"## {level} 能力入口",
        "",
        "| 能力 | 原件入口 | 外部前提与宿主边界 |",
        "| --- | --- | --- |",
    ]
    no_entry = "由宿主承载" if level == "P0" else "证据引用"
    for group in groups.values():
        names = "<br>".join(f"`{path}`" for path in group["entries"]) or no_entry
        lines.append(f"| {group['title']} | {names} | {'<br>'.join(group['external'])} |")
    lines.extend((
        "",
        f"## {level} 精确文件表",
        "",
        "直接本地依赖列给出静态核实的文件边。解释器、调用方传入的文件和宿主接口见能力入口表。",
        "",
        "| 交付路径 | 用途 | 直接本地依赖 | 纳入依据 | 待验证或适用范围 |",
        "| --- | --- | --- | --- | --- |",
    ))
    for path, file in files.items():
        dependencies = "<br>".join(f"`{value}`" for value in file["requires"]) or "—"
        usage = "原件候选" if file["kind"] == "archive" else "证据引用"
        lines.append(f"| `{path}` | {usage} | {dependencies} | {file['basis']} | {file['pending']} |")
    return lines


def _render(scope: _Scope, files: dict[str, _SelectedFile], pilot: list[str], remaining: int) -> str:
    """呈现已供 P0 归档使用的原有 Markdown 核查表。

    :param scope: 已核对的能力分组与待启用资源。
    :param files: 带发行身份的 P0 文件表。
    :param pilot: 从原抽离试点保留的 P1 路径。
    :param remaining: 此批和试点之外的候选记录数。
    :return: UTF-8 写出前的 Markdown 正文。
    """
    lines = [
        "# Hi3D 1.2.11 资源优先级与 P0 核查表",
        "",
        "本表由[核查范围](priority.scope.json)、[抽离清单](extraction.json)和"
        "[发行锁](../inventory/inventory.lock.json)生成。完整交付路径、字节数、"
        "SHA-256 和源码映射见[机器可读清单](priority.json)。",
        "",
        *_render_batch(scope["groups"], files, "P0"),
    ]
    lines.extend((
        "",
        "## P1 试点",
        "",
        "以下文件从既有抽离试点顺延至建模与验收批次。",
        "",
        *(f"- `{path}`" for path in pilot),
        "",
        "## P2 延期候选",
        "",
        f"其余 {remaining} 个候选等待能力选取或环境触发后再展开依赖。以下是已明确的延期入口。",
        "",
        *(f"- `{path}` — {reason}" for path, reason in scope["deferred"].items()),
        "",
    ))
    return "\n".join(lines)


def _locked_extraction(
    directory: Path, extraction_path: Path
) -> tuple[_ExtractionManifest, list[InventoryRecord], str]:
    """复核供 P0 与 P1 共用的发行索引和现有抽离清单。

    :param directory: 发行锁与文件索引目录。
    :param extraction_path: 现有抽离清单路径。
    :return: 现有抽离范围、锁内文件记录和抽离清单摘要。
    :raises ValueError: 发行锁或抽离清单与来源身份不符。
    """
    identity, inventory = _read_release(directory)
    extraction = _derive(identity, inventory)
    extraction_bytes = extraction_path.read_bytes()
    if extraction_bytes != _json_bytes(extraction, pretty=True):
        raise ValueError("extraction manifest does not match the locked release derivation")
    return extraction, inventory, hashlib.sha256(extraction_bytes).hexdigest()


def _p0_manifest(
    extraction: _ExtractionManifest, inventory: list[InventoryRecord], extraction_digest: str, scope_path: Path
) -> tuple[_PriorityManifest, _Scope]:
    """按已发布契约重建 P0 优先级清单。

    :param extraction: 已核对的抽离清单。
    :param inventory: 同一份发行索引中的文件记录。
    :param extraction_digest: 抽离清单原始字节的 SHA-256。
    :param scope_path: 已用于发布 P0 的人工范围输入。
    :return: 派生清单及用于呈现的 P0 范围输入。
    """
    scope_bytes = scope_path.read_bytes()
    scope: _Scope = json.loads(scope_bytes)
    files, pilot, remaining = _select(scope, extraction, inventory)
    return {
        "schema_version": 1,
        "source_inventory": extraction["source_inventory"],
        "extraction_sha256": extraction_digest,
        "scope_sha256": hashlib.sha256(scope_bytes).hexdigest(),
        "p0": {"groups": scope["groups"], "files": files},
        "p1": {"pilot": pilot},
        "p2": {"remaining_candidates": remaining, "deferred": scope["deferred"]},
    }, scope


def _derive_priority(
    directory: Path, extraction_path: Path, scope_path: Path
) -> tuple[_PriorityManifest, _Scope]:
    """从锁定来源重建 P0 清单，供现有入口与归档核对。

    :param directory: 发行锁与文件索引目录。
    :param extraction_path: 现有抽离清单路径。
    :param scope_path: 人工复核的 P0 输入路径。
    :return: 派生优先级清单及用于呈现的范围输入。
    """
    return _p0_manifest(*_locked_extraction(directory, extraction_path), scope_path)


def _derive_p1(directory: Path, extraction_path: Path, scope_path: Path, p0_path: Path) -> _P1Manifest:
    """验证前序清单并在同一发行证据下派生 P1。

    :param directory: 发行锁与文件索引目录。
    :param extraction_path: 已发布抽离清单路径。
    :param scope_path: 人工复核的 P1 输入路径。
    :param p0_path: 已发布 P0 清单，P0 范围输入位于同目录。
    :return: 独立的 P1 优先级清单。
    :raises ValueError: P0 清单不符、试点遗漏或重复选取已有原件。
    """
    extraction, inventory, extraction_digest = _locked_extraction(directory, extraction_path)
    p0, _ = _p0_manifest(extraction, inventory, extraction_digest, p0_path.with_name("priority.scope.json"))
    p0_bytes = p0_path.read_bytes()
    if p0_bytes != _json_bytes(p0, pretty=True):
        raise ValueError("P0 priority manifest does not match the locked release derivation")

    scope_bytes = scope_path.read_bytes()
    scope: _BatchScope = json.loads(scope_bytes)
    candidates = {path for paths in extraction["candidates"].values() for path in paths}
    files = _select_batch(scope, candidates, inventory, "P1")
    p0_archived = {path for path, file in p0["p0"]["files"].items() if file["kind"] == "archive"}
    p1_archives = {path for path, file in files.items() if file["kind"] == "archive"}
    if repeated := p1_archives & p0_archived:
        raise ValueError("P1 archive paths already selected in P0: " + ", ".join(sorted(repeated)))
    if missing := set(p0["p1"]["pilot"]) - p1_archives:
        raise ValueError("P1 archive is missing locked pilot paths: " + ", ".join(sorted(missing)))
    return {
        "schema_version": 1,
        "source_inventory": extraction["source_inventory"],
        "extraction_sha256": extraction_digest,
        "scope_sha256": hashlib.sha256(scope_bytes).hexdigest(),
        "p0_priority_sha256": hashlib.sha256(p0_bytes).hexdigest(),
        "p1": {"groups": scope["groups"], "files": files},
    }


def _render_p1(batch: _Batch) -> str:
    """呈现 P1 文件、外部前提和边界，沿用 P0 的表结构。

    :param batch: 派生的能力分组与待抽离文件。
    :return: UTF-8 写出前的 Markdown 正文。
    """
    return "\n".join((
        "# Hi3D 1.2.11 资源优先级与 P1 核查表",
        "",
        "本表由[P1 核查范围](priority.scope.json)、[抽离清单](../extraction.json)、"
        "[发行锁](../../inventory/inventory.lock.json)及[已发布 P0 清单](../priority.json)生成。"
        "文件大小、SHA-256、源码映射及 P0 清单摘要见[机器可读清单](priority.json)。",
        "",
        "直接依赖闭包覆盖选中的原件候选及已核对的条件导入。"
        "证据行记录版本固定的实现切片、契约和复核样本。供应商客户端及人形流程以原安装环境作为核查前提。",
        "",
        *_render_batch(batch["groups"], batch["files"], "P1"),
        "",
    ))


def priority_main(argv: list[str] | None = None) -> int:
    """读取版本锁、抽离清单和人工核查范围，发布优先级派生结果。

    :param argv: 命令参数，缺省时采用当前进程参数。
    :return: 成功返回 0，校验或发布失败返回 1。
    """
    parser = argparse.ArgumentParser(description="从锁定的 Hi3D 抽离清单派生资源优先级。")
    parser.add_argument("--inventory-dir", required=True, type=Path, help="发行锁与清单目录")
    parser.add_argument("--extraction", required=True, type=Path, help="已派生的抽离清单文件")
    parser.add_argument("--scope", required=True, type=Path, help="人工复核的能力和文件选取依据")
    parser.add_argument("--p0-priority", type=Path, help="派生 P1 时指定先前发布的 P0 优先级清单")
    parser.add_argument("--output-dir", required=True, type=Path, help="优先级清单与核查表输出目录")
    args = parser.parse_args(argv)

    try:
        directory = args.inventory_dir.resolve()
        output = args.output_dir.resolve()
        if output.is_relative_to(directory):
            raise ValueError("output directory must be outside the read-only inventory directory")
        if args.p0_priority is None:
            manifest, scope = _derive_priority(directory, args.extraction, args.scope)
            files = manifest["p0"]["files"]
            markdown = _render(scope, files, manifest["p1"]["pilot"], manifest["p2"]["remaining_candidates"])
            manifest_bytes = _json_bytes(manifest, pretty=True)
            level = "P0"
        else:
            next_manifest = _derive_p1(directory, args.extraction, args.scope, args.p0_priority)
            files = next_manifest["p1"]["files"]
            markdown = _render_p1(next_manifest["p1"])
            manifest_bytes = _json_bytes(next_manifest, pretty=True)
            level = "P1"
        artifacts = (
            (output / "priority.json", manifest_bytes),
            (output / "priority.md", markdown.encode("utf-8")),
        )
        output.mkdir(parents=True, exist_ok=True)
        for target, content in artifacts:
            _matches_existing(target, content)
        for target, content in artifacts:
            _publish_file(target, content)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"priority: {error}", file=sys.stderr)
        return 1

    print(f"Prepared {len(files)} {level} paths in {output}")
    return 0
