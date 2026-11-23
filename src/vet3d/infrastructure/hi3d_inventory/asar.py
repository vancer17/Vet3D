# 文件信息
# 模块负责只读解析 Hi3D 桌面 ASAR 的归档头，定位内嵌文件并核对声明摘要。
# 盘点协调器使用成员路径、绝对偏移和摘要生成发行锁定记录。
"""解析已打包的 ASAR 成员。"""

import hashlib
import json
import os
import re
import stat
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from .records import FileFingerprint


class AsarMember(FileFingerprint):
    """一项已从 ASAR 原件读取并计算摘要的成员信息。"""

    offset: int
    integrity_verified: bool


@dataclass(frozen=True)
class _Integrity:
    """归档头声明的文件与数据块校验信息。"""

    sha256: str
    block_size: int
    blocks: tuple[str, ...] | None


_PREFIX = struct.Struct("<4I")
_CHUNK_SIZE = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_DECIMAL = re.compile(r"[0-9]+")
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "AUX",
    "CON",
    "CONIN$",
    "CONOUT$",
    "NUL",
    "PRN",
    *(f"{prefix}{suffix}" for prefix in ("COM", "LPT") for suffix in "123456789¹²³"),
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """构造拒绝重复字段的 JSON 对象，避免归档头歧义。

    :param pairs: JSON 解码器提取的字段和值。
    :return: 通过唯一性检查的对象。
    :raises ValueError: 出现重复字段。
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field {key!r}")
        result[key] = value
    return result


def _read_header(source: BinaryIO, archive_size: int) -> tuple[dict[str, object], int]:
    """从 Chromium Pickle 归档头读取成员树与数据起点。

    :param source: 位于归档起点的二进制流。
    :param archive_size: 原始归档字节数。
    :return: 成员树和数据区的绝对偏移。
    :raises ValueError: 归档头损坏、截断或成员树无效。
    """
    prefix = source.read(_PREFIX.size)
    if len(prefix) != _PREFIX.size:
        raise ValueError("truncated ASAR header")

    # ASAR packs the header size and the JSON string in two Chromium Pickles.
    size_payload, header_size, header_payload, json_size = _PREFIX.unpack(prefix)
    content_start = 8 + header_size
    if (
        size_payload != 4
        or header_size != header_payload + 4
        or header_payload % 4
        or not 0 <= header_payload - 4 - json_size <= 3
        or content_start > archive_size
    ):
        raise ValueError("invalid ASAR header size or padding")

    raw = source.read(json_size)
    if len(raw) != json_size:
        raise ValueError("truncated ASAR JSON header")
    try:
        header = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"invalid ASAR JSON header: {error}") from error
    if not isinstance(header, dict) or not isinstance(header.get("files"), dict):
        raise ValueError("ASAR header has no files tree")
    return cast(dict[str, object], header["files"]), content_start


def _validate_name(name: str, parent: str) -> None:
    """检查成员名称在盘点相对路径中的可移植性。

    :param name: 单个成员的文件名或目录名。
    :param parent: 父成员路径，仅用于定位失败位置。
    :raises ValueError: 名称包含危险字符或使用 Windows 保留名。
    """
    stem = name.partition(".")[0].rstrip(" ").upper()
    if (
        not name
        or name.endswith((".", " "))
        or _UNSAFE_NAME.search(name)
        or stem in _RESERVED_NAMES
        or any(0xD800 <= ord(char) <= 0xDFFF for char in name)
    ):
        raise ValueError(f"unsafe ASAR member name {name!r} in {parent or '/'}")


def _file_members(files: dict[str, object]) -> Iterator[tuple[str, dict[str, object]]]:
    """遍历文件树，交付可从归档内部直接读取的成员。

    :param files: 归档头中的文件树。
    :return: 成员相对路径和归档元数据的迭代器。
    :raises ValueError: 存在路径冲突、链接、外置成员或异常元数据。
    """
    directories = [("", files)]
    while directories:
        parent, children = directories.pop()
        seen: set[str] = set()
        for name, entry in children.items():
            _validate_name(name, parent)
            if name.casefold() in seen:
                raise ValueError(f"case-insensitive ASAR member collision: {parent}/{name}")
            seen.add(name.casefold())
            path = f"{parent}/{name}" if parent else name
            if not isinstance(entry, dict):
                raise ValueError(f"invalid ASAR member metadata: {path}")
            if "link" in entry:
                raise ValueError(f"ASAR links are unsupported: {path}")
            if "unpacked" in entry and entry["unpacked"] is not False:
                raise ValueError(f"ASAR unpacked members are unsupported: {path}")
            if "files" not in entry:
                yield path, entry
                continue
            nested = entry["files"]
            if not isinstance(nested, dict) or "offset" in entry or "size" in entry:
                raise ValueError(f"invalid ASAR directory metadata: {path}")
            directories.append((path, cast(dict[str, object], nested)))


def _member_extent(
    entry: dict[str, object], path: str, content_start: int, limit: int
) -> tuple[int, int]:
    """将成员在数据区中的区间转换成实际读取位置。

    :param entry: 当前成员的归档头记录。
    :param path: 当前成员路径。
    :param content_start: 数据区的绝对偏移。
    :param limit: 归档文件末端偏移。
    :return: 成员绝对偏移及字节数。
    :raises ValueError: 数据区间无效或越过归档边界。
    """
    size = entry.get("size")
    offset = entry.get("offset")
    if type(size) is not int or size < 0 or not isinstance(offset, str) or not _DECIMAL.fullmatch(offset):
        raise ValueError(f"invalid ASAR member size or offset: {path}")
    try:
        start = content_start + int(offset)
    except ValueError as error:
        raise ValueError(f"invalid ASAR member offset: {path}") from error
    if start > limit or size > limit - start:
        raise ValueError(f"ASAR member exceeds archive bounds: {path}")
    return start, size


def _declared_integrity(entry: dict[str, object], path: str, size: int) -> _Integrity | None:
    """解析成员声明的 SHA-256 元数据并校验数据块数量。

    :param entry: 当前成员的归档头记录。
    :param path: 当前成员路径。
    :param size: 当前成员的字节数。
    :return: 校验声明，或者成员未声明完整性时返回空值。
    :raises ValueError: 算法、摘要、分块大小或数量无效。
    """
    if "integrity" not in entry:
        return None
    integrity = entry["integrity"]
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "SHA256":
        raise ValueError(f"unsupported ASAR integrity metadata: {path}")
    expected = integrity.get("hash")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError(f"invalid ASAR member SHA-256: {path}")
    if "blockSize" not in integrity and "blocks" not in integrity:
        return _Integrity(expected.lower(), max(1, size), None)

    block_size = integrity.get("blockSize")
    blocks = integrity.get("blocks")
    if type(block_size) is not int or block_size <= 0 or not isinstance(blocks, list):
        raise ValueError(f"invalid ASAR integrity blocks: {path}")
    if len(blocks) not in ({0, 1} if size == 0 else {(size + block_size - 1) // block_size}):
        raise ValueError(f"invalid ASAR integrity block count: {path}")
    checked: list[str] = []
    for value in blocks:
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError(f"invalid ASAR block SHA-256: {path}")
        checked.append(value.lower())
    return _Integrity(expected.lower(), block_size, tuple(checked))


def _hash_member(
    source: BinaryIO, start: int, size: int, path: str, integrity: _Integrity | None
) -> str:
    """流式计算成员摘要并核对已声明的数据块。

    :param source: 已打开的只读归档流。
    :param start: 成员的绝对偏移。
    :param size: 成员的字节数。
    :param path: 成员路径，用于定位读取或校验错误。
    :param integrity: 要核对的成员和数据块摘要声明。
    :return: 实际读取内容的 SHA-256。
    :raises ValueError: 内容截断，或者成员或数据块摘要不匹配。
    """
    source.seek(start)
    remaining = size
    digest = hashlib.sha256()
    block_size = integrity.block_size if integrity is not None else max(1, size)
    blocks = integrity.blocks if integrity is not None else None
    block_count = len(blocks) if blocks is not None else 1
    for index in range(block_count):
        block_remaining = min(remaining, block_size)
        remaining -= block_remaining
        block_digest = hashlib.sha256() if blocks is not None else None
        while block_remaining:
            chunk = source.read(min(block_remaining, _CHUNK_SIZE))
            if not chunk:
                raise ValueError(f"truncated ASAR member: {path}")
            digest.update(chunk)
            if block_digest is not None:
                block_digest.update(chunk)
            block_remaining -= len(chunk)
        if (
            blocks is not None
            and block_digest is not None
            and block_digest.hexdigest() != blocks[index]
        ):
            raise ValueError(f"ASAR block SHA-256 mismatch: {path} block {index}")
    actual = digest.hexdigest()
    if integrity is not None and actual != integrity.sha256:
        raise ValueError(f"ASAR member SHA-256 mismatch: {path}")
    return actual


def _archive_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """提取盘点期间用于对照归档身份的文件元数据。

    :param info: 通过文件路径或打开的句柄取得的文件状态。
    :return: 设备号、节点号、类型、字节数及修改时间。
    """
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns)


def scan_asar(archive: Path) -> list[AsarMember]:
    """只读盘点正常打包的 ASAR，按成员路径返回结果。

    :param archive: 留存安装包中的 ASAR 路径。
    :return: 逐项核对后的内嵌成员清单。
    :raises ValueError: 输入类型异常，归档变化，或成员校验失败。
    """
    original = archive.lstat()
    if (
        not stat.S_ISREG(original.st_mode)
        or getattr(original, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError("app.asar must be a regular file without reparse points")
    with archive.open("rb") as source:
        before = os.fstat(source.fileno())
        if _archive_identity(before) != _archive_identity(original):
            raise ValueError("ASAR archive changed before inventory")
        files, content_start = _read_header(source, before.st_size)
        located: list[tuple[int, int, str, _Integrity | None]] = []
        for path, entry in _file_members(files):
            offset, size = _member_extent(entry, path, content_start, before.st_size)
            located.append((offset, size, path, _declared_integrity(entry, path, size)))

        result: list[AsarMember] = []
        previous_end = content_start
        for offset, size, path, integrity in sorted(located):
            if size and offset < previous_end:
                raise ValueError(f"overlapping ASAR member: {path}")
            if size:
                previous_end = offset + size
            actual = _hash_member(source, offset, size, path, integrity)
            result.append(
                AsarMember(
                    path=path,
                    size=size,
                    sha256=actual,
                    offset=offset,
                    integrity_verified=integrity is not None,
                )
            )
        after = os.fstat(source.fileno())
        if not (
            _archive_identity(before)
            == _archive_identity(after)
            == _archive_identity(archive.lstat())
        ):
            raise ValueError("ASAR archive changed during inventory")
    return sorted(result, key=lambda member: member["path"])
