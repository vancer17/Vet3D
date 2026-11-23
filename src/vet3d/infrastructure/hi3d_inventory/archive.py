# 文件信息
# 根据锁定的批次范围复核安装副本，发布原始字节和归档收据。
# 证据文件只校验身份。归档命令不加载任何上游脚本或宿主配置。
"""原样归档 Hi3D 1.2.11 的锁定原件。"""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Literal

from .cli import _json_bytes, _matches_existing
from .disk import _measure, _regular_or_directory, _relative_path
from .priority import _Batch, _derive_p1, _derive_priority
from .records import FileFingerprint


RECEIPT = "archive.lock.json"


def _canonical_output(path: Path) -> Path:
    """Reject real links, then normalize an ordinary output path.

    Windows short names and ordinary parent segments can change under resolve()
    without traversing a link. Inspect existing components before resolving so
    those aliases remain usable while symlinks and reparse points stay rejected.
    """
    absolute = path.absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        _regular_or_directory(info, str(component))
        if not component.is_dir():
            raise ValueError(f"archive output path is not a directory: {component}")
    return absolute.resolve()


def _read_originals(
    resources: Path, batch: _Batch
) -> tuple[dict[str, bytes], list[FileFingerprint], list[str]]:
    """核对一批全部来源，只保留其中需要归档的原件字节。

    :param resources: 已解析的安装包 resources 目录。
    :param batch: 重建并与已发布清单对账的批次范围。
    :return: 待归档原件、已测量的文件指纹及证据引用路径。
    :raises ValueError: 路径越界、包含链接或安装文件与锁定身份不符。
    """
    originals: dict[str, bytes] = {}
    fingerprints: list[FileFingerprint] = []
    references: list[str] = []
    for path, selection in batch["files"].items():
        relative = _relative_path(path, "archive path")
        source = resources / relative
        if source.resolve(strict=True) != source:
            raise ValueError(f"linked source path: {relative}")
        retain = selection["kind"] == "archive"
        measured, raw = _measure(source, relative, capture_bytes=retain)
        if measured["size"] != selection["size"] or measured["sha256"] != selection["sha256"]:
            raise ValueError(f"source bytes do not match the release lock: {relative}")
        if retain:
            assert raw is not None
            originals[relative] = raw
            fingerprints.append(measured)
        else:
            references.append(relative)
    return originals, fingerprints, references


def _verify_tree(directory: Path, files: list[FileFingerprint], receipt: bytes) -> None:
    """复核整个归档的准确文件集合及逐件摘要。

    :param directory: 准备发布或已存在的归档根。
    :param files: 核查安装副本取得的原件指纹。
    :param receipt: 对应安装证据和优先级的收据字节。
    :raises ValueError: 目录内容、路径、收据或原件身份有差异。
    """
    expected = {RECEIPT, *(f"resources/{file['path']}" for file in files)}
    actual: set[str] = set()
    for path in directory.rglob("*"):
        relative = path.relative_to(directory).as_posix()
        _regular_or_directory(path.lstat(), relative)
        if path.is_file():
            actual.add(relative)
    if actual != expected:
        raise ValueError(f"archive file set differs: {directory}")
    _matches_existing(directory / RECEIPT, receipt)
    for file in files:
        archived = directory / "resources" / file["path"]
        measured, _ = _measure(archived, file["path"])
        if measured != file:
            raise ValueError(f"archived bytes do not match the release lock: {file['path']}")


def _publish_archive(
    output: Path, originals: dict[str, bytes], files: list[FileFingerprint], receipt: bytes
) -> None:
    """在同一文件系统完整核验暂存副本，再发布整个归档目录。

    :param output: 用户指定的新归档根或需要原样复用的归档根。
    :param originals: 已锁定的原件字节，按安装包相对路径索引。
    :param files: 写出后核查的原件指纹。
    :param receipt: 归档收据的 UTF-8 字节。
    """
    if output.exists():
        _verify_tree(output, files, receipt)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".hi3d-archive-") as temporary:
        staged = Path(temporary) / "archive"
        for relative, raw in originals.items():
            target = staged / "resources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (staged / RECEIPT).write_bytes(receipt)
        _verify_tree(staged, files, receipt)
        try:
            staged.rename(output)
        except OSError:
            if not output.is_dir():
                raise
            _verify_tree(output, files, receipt)


def _locked_batch(release: Path, level: Literal["P0", "P1"]) -> tuple[_Batch, dict[str, object]]:
    """重建目标批次并校验已发布的优先级清单字节。

    :param release: 发行锁与各批优先级所在版本目录。
    :param level: 需要归档的资源优先级。
    :return: 已核实的批次和收据使用的来源身份。
    :raises ValueError: 已发布的优先级清单与重新派生的字节不符。
    """
    inventory = release / "inventory"
    extraction = release / "extraction"
    extraction_path = extraction / "extraction.json"
    prior: dict[str, str] = {}
    if level == "P1":
        priority = extraction / "p1"
        p1 = _derive_p1(
            inventory, extraction_path, priority / "priority.scope.json", extraction / "priority.json"
        )
        batch = p1["p1"]
        identity = p1["source_inventory"]
        prior["p0_priority_sha256"] = p1["p0_priority_sha256"]
        expected = _json_bytes(p1, pretty=True)
    else:
        priority = extraction
        p0, _ = _derive_priority(inventory, extraction_path, priority / "priority.scope.json")
        batch = p0["p0"]
        identity = p0["source_inventory"]
        expected = _json_bytes(p0, pretty=True)
    if (priority / "priority.json").read_bytes() != expected:
        raise ValueError("priority manifest does not match the locked release derivation")
    return batch, {
        "priority_sha256": hashlib.sha256(expected).hexdigest(),
        "source_inventory": identity,
        **prior,
    }


def archive_main(argv: list[str] | None = None, *, level: Literal["P0", "P1"] = "P0") -> int:
    """锁定归档输入，核对安装副本并发布该批原件。

    :param argv: 命令参数，缺省时采用当前进程参数。
    :param level: 由调用脚本指定的已发布优先级批次。
    :return: 归档并通过核查返回 0，校验或发布失败返回 1。
    """
    parser = argparse.ArgumentParser(description=f"按已发布的 Hi3D {level} 清单归档原件。")
    parser.add_argument("--release-dir", required=True, type=Path, help="发行锁、抽离和优先级所在的版本目录")
    parser.add_argument("--resources-root", required=True, type=Path, help="保留的安装包 resources 目录")
    parser.add_argument("--output-dir", required=True, type=Path, help="原件归档目录")
    args = parser.parse_args(argv)

    try:
        release = args.release_dir.resolve(strict=True)
        resources = args.resources_root.resolve(strict=True)
        output = _canonical_output(args.output_dir)
        if output.is_relative_to(resources) or resources.is_relative_to(output):
            raise ValueError("archive must use a separate directory without symlinks")
        for name in ("inventory", "extraction"):
            directory = (release / name).resolve()
            if output.is_relative_to(directory) or directory.is_relative_to(output):
                raise ValueError(f"archive output overlaps a locked release input directory: {name}")
        batch, identity = _locked_batch(release, level)
        originals, files, references = _read_originals(resources, batch)
        receipt = _json_bytes({
            "schema_version": 1,
            **identity,
            "files": files,
            "evidence_references": references,
        }, pretty=True)
        _publish_archive(output, originals, files, receipt)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"{level} archive: {error}", file=sys.stderr)
        return 1

    print(f"Verified {len(files)} archived originals and {len(references)} evidence references in {output}")
    return 0
