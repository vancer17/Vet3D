# 文件信息：L1-03 资源身份、严格清单与依赖闭包的纯契约测试。
# 作用：覆盖单源编码、输入解析、引用关联及非法声明，不以行覆盖率为目标。
# 边界：不使用替身证明文件安装、真实解释器兼容性或执行隔离。
"""通过公开入口验证固定资源快照的高价值规则。"""

from dataclasses import FrozenInstanceError, replace
import json
from typing import cast
import unittest

from vet3d.artifacts import ContentFingerprint
from vet3d.resources import (
    DocumentResource, InterpreterRequirement, ResourceContractError,
    ResourceDefinition, ResourceDescription, ResourceFile, ResourceKey,
    ResourceManifest, ResourceMetadata, ResourcePath, ResourceReference,
    ScriptResource, TemplateResource, fingerprint_bytes, parse_manifest,
    parse_resource_spec, serialize_manifest,
)


def _metadata() -> ResourceMetadata:
    """建立明确未执行的采纳说明，避免夹具伪造实际验证。

    :returns: 用于纯契约测试的资源说明。
    """
    return ResourceMetadata(
        "契约测试资源", "Vet3D 自研测试夹具，无上游版本", "不适用", "不适用",
        "不执行覆盖", "不执行文件副作用", "独立实现", "首期闭环", "只验证清单，未执行脚本",
    )


def _manifest() -> ResourceManifest:
    """构造有共享依赖的三种资源，所有内容均只作为声明。

    :returns: 完整且有效的测试清单。
    """
    document = ResourcePath("docs/说明.md")
    script = ResourcePath("scripts/tool.py")
    template = ResourcePath("templates/input.json")
    return ResourceManifest(
        (
            ResourceFile(document, fingerprint_bytes("说明\n".encode())),
            ResourceFile(script, fingerprint_bytes(b"pass\n")),
            ResourceFile(template, fingerprint_bytes(b"{}\n")),
        ),
        (
            DocumentResource(ResourceKey("docs.guide"), document, (document,), (), _metadata()),
            ScriptResource(
                ResourceKey("tools.preview"), script, (script,), (ResourceKey("docs.guide"),),
                _metadata(), InterpreterRequirement("Python", "3.14", ("标准库",)),
            ),
            TemplateResource(
                ResourceKey("templates.input"), template, (template, document),
                (ResourceKey("docs.guide"),), _metadata(),
            ),
        ),
    )


def _json_manifest() -> dict[str, object]:
    """取得可逐字段破坏的 JSON 样例，形状仍来自唯一编码入口。

    :returns: 尚未修改的 manifest JSON 对象。
    """
    return cast(dict[str, object], json.loads(serialize_manifest(_manifest())))


def _json_bytes(value: object) -> bytes:
    """编码待测 JSON 值，不替代生产解析或序列化。

    :param value: 测试需要提交的 JSON 值。
    :returns: UTF-8 测试输入。
    """
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _resources(raw: dict[str, object]) -> list[dict[str, object]]:
    """取得夹具资源定义，供测试单个错误边界。

    :param raw: 由有效清单生成的测试对象。
    :returns: 可修改的资源对象数组。
    """
    return cast(list[dict[str, object]], raw["resources"])


class ResourceContractTests(unittest.TestCase):
    """验证不同事实不合并、非法声明不能进入安装边界。"""

    def test_round_trip_preserves_all_resource_kinds_and_metadata(self) -> None:
        """三种资源可经唯一 JSON 边界读回，解释器仅属于脚本。"""
        original = _manifest()
        encoded = serialize_manifest(original)
        decoded = parse_manifest(encoded)
        self.assertEqual(serialize_manifest(decoded), encoded)
        self.assertIsInstance(decoded.find_resource(ResourceKey("docs.guide")), DocumentResource)
        self.assertIsInstance(decoded.find_resource(ResourceKey("tools.preview")), ScriptResource)
        self.assertIsInstance(decoded.find_resource(ResourceKey("templates.input")), TemplateResource)
        self.assertEqual(decoded.find_resource(ResourceKey("docs.guide")), original.resources[0])
        self.assertIn("说明".encode(), encoded)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertNotIn(b"\r", encoded)

    def test_serialization_order_is_independent_of_declaration_order(self) -> None:
        """文件和资源表的声明顺序不制造另一种构建结果。"""
        original = _manifest()
        reversed_manifest = ResourceManifest(tuple(reversed(original.files)), tuple(reversed(original.resources)))
        self.assertEqual(serialize_manifest(original), serialize_manifest(reversed_manifest))
        template = cast(TemplateResource, original.resources[2])
        changed = replace(template, files=tuple(reversed(template.files)))
        reordered = replace(original, resources=original.resources[:2] + (changed,))
        self.assertEqual(serialize_manifest(original), serialize_manifest(reordered))

    def test_raw_manifest_bytes_define_snapshot_even_when_parsed_records_match(self) -> None:
        """仅改变原始空白也产生新快照，解析不会静默维持旧 pin。"""
        canonical = serialize_manifest(_manifest())
        other = b" \n" + canonical
        self.assertEqual(parse_manifest(canonical), parse_manifest(other))
        self.assertNotEqual(fingerprint_bytes(canonical), fingerprint_bytes(other))
        self.assertNotIn("snapshot", _json_manifest())

    def test_resource_description_rejects_foreign_logical_key(self) -> None:
        """同一快照也不能用其他资源定义响应确切引用。"""
        manifest = _manifest()
        snapshot = fingerprint_bytes(serialize_manifest(manifest))
        correct = ResourceReference(snapshot, manifest.resources[0].key)
        self.assertEqual(ResourceDescription(correct, manifest.resources[0]).reference, correct)
        with self.assertRaises(ResourceContractError):
            ResourceDescription(correct, manifest.resources[1])

    def test_keys_and_paths_reject_aliases_and_traversal(self) -> None:
        """逻辑键与包内路径都保持规范形式，不通过归一化接纳越界输入。"""
        for name in ("A", "a..b", "../a", "a/b", "a-", " a", "猫"):
            with self.subTest(key=name), self.assertRaises(ResourceContractError):
                ResourceKey(name)
        for path in ("", " ", "/a", "a/../b", "./a", "a//b", "a/", "C:a", "a\\b", "a\n"):
            with self.subTest(path=path), self.assertRaises(ResourceContractError):
                ResourcePath(path)

    def test_invalid_json_encoding_constants_and_duplicate_keys_are_rejected(self) -> None:
        """编码和重复字段错误不能由 JSON 默认宽容行为掩盖。"""
        for data in (
            b"\xef\xbb\xbf{}", b"\xff", b"{} trailing", b"NaN", b"Infinity",
            b'{"schema_version":1,"schema_version":1,"files":[],"resources":[]}',
            b'{"schema_version":1,"files":[],"resources":[{"kind":"document","kind":"script"}]}',
        ):
            with self.subTest(data=data), self.assertRaises(ResourceContractError):
                parse_manifest(data)

    def test_schema_version_and_root_fields_are_strict(self) -> None:
        """Schema 是输入契约，布尔值、浮点数及未知字段均不能充当版本。"""
        for version in (True, 1.0, "1", 2, None):
            raw = _json_manifest()
            raw["schema_version"] = version
            with self.subTest(version=version), self.assertRaises(ResourceContractError):
                parse_manifest(_json_bytes(raw))
        raw = _json_manifest()
        raw["latest"] = "current"
        with self.assertRaises(ResourceContractError):
            parse_manifest(_json_bytes(raw))
        del raw["latest"]
        del raw["schema_version"]
        with self.assertRaises(ResourceContractError):
            parse_manifest(_json_bytes(raw))

    def test_interpreter_is_required_only_for_scripts(self) -> None:
        """判别记录消除文档携解释器及脚本缺解释器的非法组合。"""
        raw = _json_manifest()
        document, _, script = _resources(raw)
        document["interpreter"] = script["interpreter"]
        with self.assertRaises(ResourceContractError):
            parse_manifest(_json_bytes(raw))
        raw = _json_manifest()
        del _resources(raw)[2]["interpreter"]
        with self.assertRaises(ResourceContractError):
            parse_manifest(_json_bytes(raw))
        raw = _json_manifest()
        _resources(raw)[0]["kind"] = "executable"
        with self.assertRaises(ResourceContractError):
            parse_manifest(_json_bytes(raw))

    def test_metadata_is_complete_text_without_runtime_status_fields(self) -> None:
        """采纳说明完整保留，但不能夹带 ready 字段或隐式布尔文本。"""
        for name, value in (("purpose", False), ("source", " "), ("evidence", "\ud800"), ("ready", True)):
            raw = _json_manifest()
            metadata = cast(dict[str, object], _resources(raw)[0]["metadata"])
            metadata[name] = value
            data = json.dumps(raw, ensure_ascii=True).encode()
            with self.subTest(field=name), self.assertRaises(ResourceContractError):
                parse_manifest(data)

    def test_file_fingerprint_rejects_wrong_types_and_invalid_values(self) -> None:
        """文件表复用原内容指纹规则，不能接受布尔长度或畸形摘要。"""
        for name, value in (("byte_size", True), ("byte_size", -1), ("byte_size", 1.5), ("sha256", "A" * 64)):
            raw = _json_manifest()
            resource_files = cast(list[dict[str, object]], raw["files"])
            content = cast(dict[str, object], resource_files[0]["content"])
            content[name] = value
            with self.subTest(field=name, value=value), self.assertRaises(ResourceContractError):
                parse_manifest(_json_bytes(raw))

    def test_entry_and_duplicate_local_references_are_rejected(self) -> None:
        """入口必须直接列入自身文件，重复引用不能被静默去重。"""
        document = cast(DocumentResource, _manifest().resources[0])
        for changes in (
            {"entry": ResourcePath("other.md")},
            {"files": (document.entry, document.entry)},
            {"dependencies": (ResourceKey("other"), ResourceKey("other"))},
        ):
            with self.subTest(changes=changes), self.assertRaises(ResourceContractError):
                replace(document, **changes)
        with self.assertRaises(ResourceContractError):
            InterpreterRequirement("Python", "3.14", ("numpy", "numpy"))

    def test_duplicate_resource_keys_and_file_paths_are_rejected(self) -> None:
        """唯一表的重复定义直接拒绝，不靠后续漂移测试选择一个版本。"""
        manifest = _manifest()
        with self.assertRaises(ResourceContractError):
            replace(manifest, resources=manifest.resources + (manifest.resources[0],))
        with self.assertRaises(ResourceContractError):
            replace(manifest, files=manifest.files + (manifest.files[0],))

    def test_file_table_must_equal_declared_union(self) -> None:
        """文件表既不能漏项也不能夹带未声明文件，显式共享引用仍合法。"""
        manifest = _manifest()
        with self.assertRaises(ResourceContractError):
            replace(manifest, files=manifest.files[:-1])
        with self.assertRaises(ResourceContractError):
            replace(manifest, files=manifest.files + (ResourceFile(ResourcePath("hidden"), fingerprint_bytes(b"")),))
        self.assertIsNotNone(manifest.find_file(ResourcePath("docs/说明.md")))
        self.assertIsNone(manifest.find_file(ResourcePath("undeclared")))

    def test_file_path_cannot_also_be_directory_prefix(self) -> None:
        """清单在访问文件系统之前拒绝文件与目录占用同一位置。"""
        parent, child = ResourcePath("data"), ResourcePath("data/item")
        document = DocumentResource(ResourceKey("docs"), parent, (parent, child), (), _metadata())
        with self.assertRaises(ResourceContractError):
            ResourceManifest(
                (ResourceFile(parent, fingerprint_bytes(b"")), ResourceFile(child, fingerprint_bytes(b""))),
                (document,),
            )
        raw = _json_manifest()
        del raw["files"]
        _resources(raw)[0]["entry"] = "data"
        _resources(raw)[0]["files"] = ["data", "data/item"]
        with self.assertRaises(ResourceContractError):
            parse_resource_spec(_json_bytes(raw))

    def test_missing_dependency_and_cycles_are_rejected(self) -> None:
        """依赖闭包必须同包完整且无环，不进行版本求解或网络补齐。"""
        manifest = _manifest()
        document = cast(DocumentResource, manifest.resources[0])
        for dependency in (ResourceKey("missing"), document.key, ResourceKey("tools.preview")):
            changed = replace(document, dependencies=(dependency,))
            with self.subTest(dependency=dependency), self.assertRaises(ResourceContractError):
                replace(manifest, resources=(changed,) + manifest.resources[1:])

    def test_resource_spec_reuses_definitions_and_cannot_supply_hashes(self) -> None:
        """维护源只声明资源与文件名，实际字节指纹必须由构建器计算。"""
        raw = _json_manifest()
        del raw["files"]
        definitions = parse_resource_spec(_json_bytes(raw))
        manifest = _manifest()
        self.assertEqual(serialize_manifest(ResourceManifest(manifest.files, definitions)), serialize_manifest(manifest))
        raw["files"] = []
        with self.assertRaises(ResourceContractError):
            parse_resource_spec(_json_bytes(raw))
        del raw["files"]
        _resources(raw)[0]["dependencies"] = ["missing"]
        with self.assertRaises(ResourceContractError):
            parse_resource_spec(_json_bytes(raw))

    def test_empty_bundle_and_wrong_container_types_are_rejected(self) -> None:
        """空包、可变容器和非声明对象不能构成冻结资源快照。"""
        manifest = _manifest()
        with self.assertRaises(ResourceContractError):
            ResourceManifest((), ())
        with self.assertRaises(TypeError):
            ResourceManifest(cast(tuple[ResourceFile, ...], list(manifest.files)), manifest.resources)
        with self.assertRaises(TypeError):
            ResourceManifest(manifest.files, cast(tuple[ResourceDefinition, ...], ("docs",)))
        with self.assertRaises(TypeError):
            fingerprint_bytes(cast(bytes, bytearray(b"x")))

    def test_frozen_records_do_not_allow_snapshot_or_metadata_mutation(self) -> None:
        """实例固定的引用和清单记录不能通过普通赋值转成另一版本。"""
        manifest = _manifest()
        reference = ResourceReference(fingerprint_bytes(serialize_manifest(manifest)), manifest.resources[0].key)
        with self.assertRaises(FrozenInstanceError):
            setattr(reference, "snapshot", ContentFingerprint("a" * 64, 1))
        with self.assertRaises(FrozenInstanceError):
            setattr(manifest.resources[0].metadata, "evidence", "伪造已实测")


if __name__ == "__main__":
    unittest.main()
