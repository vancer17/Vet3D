# 文件信息：L1-03 资源维护源及发布清单的严格 JSON 边界。
# 作用：复用同一资源解析逻辑，确定编码顺序并保留原始清单字节的独立身份。
# 边界：不读取文件、不扫描导入、不计算安装状态，不在清单内重复存放自身摘要。
"""解析维护源和发布清单，并提供确定性的清单编码。"""

from dataclasses import fields
import hashlib
import json
from typing import cast

from vet3d.artifacts import ContentFingerprint

from .records import (
    DocumentResource, InterpreterRequirement, ResourceContractError,
    ResourceDefinition, ResourceFile, ResourceKey, ResourceManifest,
    ResourceMetadata, ResourcePath, ScriptResource, TemplateResource,
    _require_type, _validate_definitions,
)


def fingerprint_bytes(data: bytes) -> ContentFingerprint:
    """取得确切原始字节的指纹，不重新编码或赋予业务身份。

    :param data: 需要绑定的不可变字节。
    :returns: 复用已有类型的实际 SHA-256 与长度。
    :raises TypeError: 输入不是 bytes。
    """
    _require_type(data, bytes)
    return ContentFingerprint(hashlib.sha256(data).hexdigest(), len(data))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """保留 JSON 对象字段并拒绝重复键，避免解析器默默覆盖。

    :param pairs: JSON 解码器按原顺序提供的键值对。
    :returns: 字段唯一的对象。
    :raises ResourceContractError: 对象重复定义同一字段。
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResourceContractError("JSON 对象不得含重复字段")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    """拒绝非标准 JSON 数值，避免 NaN 等扩展进入输入契约。

    :param value: 解码器遇到的非标准常量。
    :raises ResourceContractError: 常量不属于标准 JSON。
    """
    raise ResourceContractError(f"不允许非标准 JSON 常量：{value}")


def _decode_json(data: bytes) -> object:
    """解码无 BOM 的严格 UTF-8 JSON，保留字段类型供具体 Schema 核对。

    :param data: 维护源或发布清单的原始字节。
    :returns: 未进行业务转换的 JSON 值。
    :raises TypeError: 输入不是 bytes。
    :raises ResourceContractError: 编码、JSON 语法或嵌套结构无效。
    """
    _require_type(data, bytes)
    if data.startswith(b"\xef\xbb\xbf"):
        raise ResourceContractError("资源 JSON 不接受 UTF-8 BOM")
    try:
        decoded = data.decode("utf-8")
        result: object = json.loads(
            decoded, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as cause:
        raise ResourceContractError("资源输入必须是严格 UTF-8 JSON") from cause
    return result


def _object(value: object, expected: set[str]) -> dict[str, object]:
    """检查对象字段恰好符合 Schema，不接收未知字段或隐式缺省。

    :param value: 已解码的 JSON 值。
    :param expected: 该对象唯一允许且全部必填的字段。
    :returns: 已核对字段集合的对象。
    :raises ResourceContractError: 输入不是对象或字段集合不符。
    """
    if type(value) is not dict:
        raise ResourceContractError("资源 JSON 字段必须是对象")
    result = cast(dict[str, object], value)
    if set(result) != expected:
        raise ResourceContractError("资源 JSON 字段缺失或含未知字段")
    return result


def _array(value: object) -> list[object]:
    """要求 JSON 数组，不接受字符串或其他可迭代值替代。

    :param value: JSON 字段值。
    :returns: 经过类型核对的数组。
    :raises ResourceContractError: 字段不是数组。
    """
    if type(value) is not list:
        raise ResourceContractError("资源 JSON 字段必须是数组")
    return cast(list[object], value)


def _string(value: object) -> str:
    """读取严格字符串字段，不执行字符串化或裁剪。

    :param value: JSON 字段值。
    :returns: 原始字符串。
    :raises ResourceContractError: 字段不是字符串。
    """
    if type(value) is not str:
        raise ResourceContractError("资源 JSON 字段必须是字符串")
    return value


def _schema_root(data: bytes, expected: set[str]) -> dict[str, object]:
    """核对唯一输入 Schema 版本，不把版本变为运行架构开关。

    :param data: 原始 JSON 字节。
    :param expected: 当前根对象必填字段集合。
    :returns: Schema 为整数一的根对象。
    :raises ResourceContractError: 字段结构或版本不受支持。
    """
    result = _object(_decode_json(data), expected)
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise ResourceContractError("仅支持资源输入 Schema 1")
    return result


def _parse_metadata(value: object) -> ResourceMetadata:
    """按唯一记录字段解析资源说明，不维护第二份元数据 Schema。

    :param value: 资源的 metadata 对象。
    :returns: 明确各项说明的冻结记录。
    :raises ResourceContractError: 字段或文本无效。
    """
    names = {field.name for field in fields(ResourceMetadata)}
    parsed = _object(value, names)
    return ResourceMetadata(**{name: _string(item) for name, item in parsed.items()})


def _parse_resource(value: object) -> ResourceDefinition:
    """解析资源种类及相应字段，使解释器仅存在于脚本定义。

    :param value: 同时适用于维护源和清单的资源 JSON 对象。
    :returns: 文档、脚本或模板的唯一具体记录。
    :raises ResourceContractError: 种类、字段或引用文本无效。
    """
    if type(value) is not dict:
        raise ResourceContractError("资源定义必须是对象")
    raw = cast(dict[str, object], value)
    kind = _string(raw.get("kind"))
    expected = {"kind", "key", "entry", "files", "dependencies", "metadata"}
    if kind == "script":
        expected.add("interpreter")
    elif kind not in ("document", "template"):
        raise ResourceContractError("未知资源种类")
    parsed = _object(raw, expected)
    common = (
        ResourceKey(_string(parsed["key"])),
        ResourcePath(_string(parsed["entry"])),
        tuple(ResourcePath(_string(path)) for path in _array(parsed["files"])),
        tuple(ResourceKey(_string(key)) for key in _array(parsed["dependencies"])),
        _parse_metadata(parsed["metadata"]),
    )
    if kind == "document":
        return DocumentResource(*common)
    if kind == "template":
        return TemplateResource(*common)
    interpreter = _object(parsed["interpreter"], {"runtime", "version", "dependencies"})
    return ScriptResource(
        *common,
        InterpreterRequirement(
            _string(interpreter["runtime"]), _string(interpreter["version"]),
            tuple(_string(item) for item in _array(interpreter["dependencies"])),
        ),
    )


def parse_resource_spec(data: bytes) -> tuple[ResourceDefinition, ...]:
    """解析唯一维护源中的资源声明，不允许作者手写实际文件摘要。

    :param data: 仅含 schema_version 与 resources 的严格 JSON 字节。
    :returns: 完整的同包资源声明闭包；构建器另从实际字节建立文件表。
    :raises TypeError: 输入不是 bytes。
    :raises ResourceContractError: Schema、字段、入口或依赖不符合契约。
    """
    root = _schema_root(data, {"schema_version", "resources"})
    resources = tuple(_parse_resource(item) for item in _array(root["resources"]))
    _validate_definitions(resources)
    return resources


def parse_manifest(data: bytes) -> ResourceManifest:
    """解析安装清单，不把重新编码的内容当作原始快照。

    :param data: 含 schema_version、files 和 resources 的原始 JSON 字节。
    :returns: 校验完整关联的冻结清单，不包含其自身摘要。
    :raises TypeError: 输入不是 bytes。
    :raises ResourceContractError: Schema、字节声明或关联关系无效。
    """
    root = _schema_root(data, {"schema_version", "files", "resources"})
    resource_files: list[ResourceFile] = []
    for item in _array(root["files"]):
        raw = _object(item, {"path", "content"})
        content = _object(raw["content"], {"sha256", "byte_size"})
        if type(content["byte_size"]) is not int:
            raise ResourceContractError("文件长度必须是非布尔整数")
        try:
            fingerprint = ContentFingerprint(
                _string(content["sha256"]), content["byte_size"],
            )
        except ValueError as cause:
            raise ResourceContractError("文件内容指纹无效") from cause
        resource_files.append(ResourceFile(ResourcePath(_string(raw["path"])), fingerprint))
    resources = tuple(_parse_resource(item) for item in _array(root["resources"]))
    return ResourceManifest(tuple(resource_files), resources)


def _encode_resource(resource: ResourceDefinition) -> dict[str, object]:
    """从具体记录单向编码种类及字段，不保存并行的 kind 状态。

    :param resource: 已经通过纯校验的资源记录。
    :returns: 用于确定编码的 JSON 对象。
    """
    metadata = {
        field.name: cast(str, getattr(resource.metadata, field.name))
        for field in fields(ResourceMetadata)
    }
    kind = "document" if isinstance(resource, DocumentResource) else "template"
    result: dict[str, object] = {
        "kind": kind, "key": resource.key.value, "entry": resource.entry.value,
        "files": sorted(path.value for path in resource.files),
        "dependencies": sorted(key.value for key in resource.dependencies),
        "metadata": metadata,
    }
    if isinstance(resource, ScriptResource):
        result["kind"] = "script"
        result["interpreter"] = {
            "runtime": resource.interpreter.runtime,
            "version": resource.interpreter.version,
            "dependencies": sorted(resource.interpreter.dependencies),
        }
    return result


def serialize_manifest(manifest: ResourceManifest) -> bytes:
    """确定性编码清单为 UTF-8、无 BOM、末尾 LF，不写入自身摘要。

    :param manifest: 已完整校验的冻结清单。
    :returns: 按路径、资源键及 JSON 字段排序的发布字节。
    :raises TypeError: 输入不是 ResourceManifest。
    """
    _require_type(manifest, ResourceManifest)
    root: dict[str, object] = {
        "schema_version": 1,
        "files": [
            {
                "path": item.path.value,
                "content": {"sha256": item.content.sha256, "byte_size": item.content.byte_size},
            }
            for item in sorted(manifest.files, key=_file_order)
        ],
        "resources": [
            _encode_resource(resource)
            for resource in sorted(manifest.resources, key=_resource_order)
        ],
    }
    return (json.dumps(root, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _file_order(resource_file: ResourceFile) -> str:
    """提供文件编码的确定排序键。

    :param resource_file: 清单中的文件记录。
    :returns: 规范路径文本。
    """
    return resource_file.path.value


def _resource_order(resource: ResourceDefinition) -> str:
    """提供资源编码的确定排序键。

    :param resource: 清单中的资源记录。
    :returns: 规范逻辑键文本。
    """
    return resource.key.value
