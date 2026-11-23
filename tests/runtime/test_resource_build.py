# 文件信息：L1-03 唯一资源维护源与确定性构建的真实文件测试。
# 作用：验证声明驱动的完整复制、实际摘要、源保护和失败输出所有权边界。
# 证据边界：只用本文件创建的自研小夹具，不执行资源脚本或证明实际模型环境就绪。
"""通过公共构建入口验证源声明与实际文件，不为资源建立第二份维护清单。"""

from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vet3d.adapters import ResourceLimits, build_resource_bundle
from vet3d.resources import ResourceContractError, ResourceKey, fingerprint_bytes, parse_manifest, parse_resource_spec


def _specification() -> dict[str, object]:
    """创建唯一的测试元数据来源，不手写任何文件摘要或字节长度。

    :returns: 同时包含文档、模板和带解释器要求脚本的维护源声明。
    """
    metadata = {
        "purpose": "验证资源构建，不提供产品能力",
        "source": "本测试自行创建，无第三方原件",
        "inputs": "不适用，构建只读取原始字节",
        "outputs": "测试包内原始字节",
        "overwrite": "不覆盖已有输出",
        "failure": "构建失败不代表安装完成",
        "adoption": "仅用于自动测试",
        "priority": "本条目验证夹具",
        "evidence": "不证明脚本可执行或动物质量",
    }
    return {
        "schema_version": 1,
        "resources": [
            {
                "kind": "script", "key": "probe", "entry": "scripts/probe.py",
                "files": ["scripts/probe.py"], "dependencies": ["guide"], "metadata": metadata,
                "interpreter": {"runtime": "Python", "version": "未执行", "dependencies": []},
            },
            {
                "kind": "template", "key": "report", "entry": "templates/report.txt",
                "files": ["templates/report.txt"], "dependencies": [], "metadata": metadata,
            },
            {
                "kind": "document", "key": "guide", "entry": "docs/guide.md",
                "files": ["docs/guide.md"], "dependencies": [], "metadata": metadata,
            },
        ],
    }


class ResourceBuildTests(unittest.TestCase):
    """验证受信普通维护源到私有资源包的可追溯构建，不安装或执行资源。"""

    def setUp(self) -> None:
        """创建独立源根和明确预算，文件采用正常 Git 的可读权限。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self._parent = Path(temporary.name)
        self._source = self._create_source("source")
        self._output = self._parent / "bundle"
        self._limits = ResourceLimits(
            max_manifest_bytes=16 * 1024, max_files=8, max_file_bytes=1024, max_total_bytes=4096
        )

    def _create_source(self, name: str) -> Path:
        """写入小型自研维护源，元数据只位于一个 resource-spec.json。

        :param name: 本例临时父目录下的源根名称。
        :returns: 受信且无链接的维护源目录。
        """
        root = self._parent / name
        root.mkdir(mode=0o755)
        root.chmod(0o755)
        specification = (json.dumps(_specification(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (root / "resource-spec.json").write_bytes(specification)
        (root / "resource-spec.json").chmod(0o644)
        payload = {
            "docs/guide.md": "# 自研验收夹具\n仅作为原始字节读取。\n".encode("utf-8"),
            "scripts/probe.py": b"raise RuntimeError('resource builder must never execute me')\n",
            "templates/report.txt": b"result: {{ unresolved }}\n",
        }
        for name, content in payload.items():
            target = root / "payload" / name
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            target.parent.chmod(0o755)
            target.write_bytes(content)
            target.chmod(0o644)
        (root / "payload").chmod(0o755)
        return root

    def test_deterministic_bundle_preserves_source_and_derives_actual_fingerprints(self) -> None:
        """相同源独立构建得到相同清单字节，源内容权限不变，输出全部私有只读。"""
        originals = {
            path.relative_to(self._source): (path.read_bytes(), path.stat().st_mode & 0o777)
            for path in self._source.rglob("*") if path.is_file()
        }
        first = build_resource_bundle(self._source, self._output, limits=self._limits)
        second_output = self._parent / "second-bundle"
        second = build_resource_bundle(self._source, second_output, limits=self._limits)
        manifest_bytes = (self._output / "manifest.json").read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(first, fingerprint_bytes(manifest_bytes))
        self.assertEqual(manifest_bytes, (second_output / "manifest.json").read_bytes())
        manifest = parse_manifest(manifest_bytes)
        declared = parse_resource_spec((self._source / "resource-spec.json").read_bytes())
        for definition in declared:
            self.assertEqual(manifest.find_resource(definition.key), definition)
        for resource_file in manifest.files:
            copied = self._output / "payload" / resource_file.path.value
            original = self._source / "payload" / resource_file.path.value
            self.assertEqual(copied.read_bytes(), original.read_bytes())
            self.assertEqual(resource_file.content, fingerprint_bytes(copied.read_bytes()))
        for relative, expected in originals.items():
            path = self._source / relative
            self.assertEqual((path.read_bytes(), path.stat().st_mode & 0o777), expected)
        for path in (self._output, *self._output.rglob("*")):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o400)

    def test_changed_bytes_update_manifest_without_manual_metadata_edits(self) -> None:
        """源文件变化只需重新构建，摘要单向更新，资源元数据仍由原声明提供。"""
        original_spec = (self._source / "resource-spec.json").read_bytes()
        first = build_resource_bundle(self._source, self._output, limits=self._limits)
        (self._source / "payload/docs/guide.md").write_bytes(b"new source content\n")
        second_output = self._parent / "changed-bundle"
        second = build_resource_bundle(self._source, second_output, limits=self._limits)
        self.assertNotEqual(first, second)
        self.assertEqual((self._source / "resource-spec.json").read_bytes(), original_spec)
        first_manifest = parse_manifest((self._output / "manifest.json").read_bytes())
        second_manifest = parse_manifest((second_output / "manifest.json").read_bytes())
        self.assertEqual(first_manifest.resources, second_manifest.resources)
        self.assertEqual(second_manifest.find_resource(ResourceKey("guide")), first_manifest.find_resource(ResourceKey("guide")))

    def test_source_cannot_supply_a_second_file_fingerprint_table(self) -> None:
        """维护源夹带手写文件表时严格拒绝，不能形成与自动摘要并列的权威。"""
        specification = _specification()
        specification["files"] = [{"path": "docs/guide.md", "content": {"sha256": "0" * 64, "byte_size": 0}}]
        (self._source / "resource-spec.json").write_text(json.dumps(specification), encoding="utf-8")
        with self.assertRaises(ResourceContractError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertFalse(self._output.exists())

    def test_missing_extra_and_empty_payload_entries_are_rejected(self) -> None:
        """实际树必须完全对应声明，缺文件、多文件及未声明空目录均不被忽略。"""
        missing = self._source / "payload/docs/guide.md"
        content = missing.read_bytes()
        missing.unlink()
        with self.assertRaises((OSError, ResourceContractError)):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        missing.write_bytes(content)
        missing.chmod(0o644)
        extra = self._source / "payload/undeclared.bin"
        extra.write_bytes(b"undeclared")
        with self.assertRaises((OSError, ResourceContractError)):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        extra.unlink()
        (self._source / "payload/empty").mkdir(mode=0o755)
        with self.assertRaises(OSError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertFalse(self._output.exists())

    def test_links_and_group_writable_sources_are_rejected_without_copying(self) -> None:
        """受信源仍拒绝符号链接、共享硬链接和其他用户可写的文件。"""
        path = self._source / "payload/docs/guide.md"
        content = path.read_bytes()
        external = self._parent / "external.txt"
        external.write_bytes(content)
        external.chmod(0o644)
        path.unlink()
        path.symlink_to(external)
        with self.assertRaises(OSError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        path.unlink()
        os.link(external, path)
        with self.assertRaises(OSError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        path.unlink()
        path.write_bytes(content)
        path.chmod(0o664)
        with self.assertRaises(OSError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertFalse(self._output.exists())

    def test_overlapping_roots_and_existing_output_never_overwrite(self) -> None:
        """同址、嵌套源和既有输出都不能作为本次构建目标。"""
        for output in (self._source, self._source / "built", self._parent):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    build_resource_bundle(self._source, output, limits=self._limits)
        self._output.mkdir(mode=0o700)
        sentinel = self._output / "owned-by-another-operation"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_each_resource_budget_rejects_before_success(self) -> None:
        """清单、数量、单文件和总量预算分别约束实际构建，不产生成功输出。"""
        total = sum(path.stat().st_size for path in (self._source / "payload").rglob("*") if path.is_file())
        limits = (
            replace(self._limits, max_manifest_bytes=1),
            replace(self._limits, max_files=2),
            replace(self._limits, max_file_bytes=1),
            replace(self._limits, max_total_bytes=total - 1),
        )
        for current in limits:
            with self.subTest(limits=current):
                with self.assertRaises((OSError, ResourceContractError)):
                    build_resource_bundle(self._source, self._output, limits=current)
                self.assertFalse(self._output.exists())

    def test_generated_manifest_limit_cleans_only_owned_partial_output(self) -> None:
        """源声明可读但生成清单超限时，已经复制的本次输出被清理。"""
        source_size = (self._source / "resource-spec.json").stat().st_size
        with self.assertRaises(ResourceContractError):
            build_resource_bundle(
                self._source, self._output, limits=replace(self._limits, max_manifest_bytes=source_size)
            )
        self.assertFalse(self._output.exists())
        self.assertTrue((self._source / "payload/docs/guide.md").is_file())

    def test_source_change_during_build_rejects_and_cleans_owned_output(self) -> None:
        """复制后源内容发生变化时构建失败，原件新内容保留且不返回旧快照成功。"""
        original_write = os.write
        changed = False
        source_file = self._source / "payload/docs/guide.md"

        def change_source_after_output_write(descriptor: int, data: bytes) -> int:
            """在一次真实输出写入后修改源，构造跨文件构建期间的实际变化。

            :param descriptor: 本次实际输出文件描述符。
            :param data: 构建器当前写入的字节。
            :returns: 实际完成的写入长度。
            """
            nonlocal changed
            result = original_write(descriptor, data)
            if not changed:
                changed = True
                source_file.write_bytes(b"changed during build\n")
            return result

        with patch("os.write", side_effect=change_source_after_output_write):
            with self.assertRaises(OSError):
                build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertEqual(source_file.read_bytes(), b"changed during build\n")
        self.assertFalse(self._output.exists())

    def test_script_payload_is_not_decoded_compiled_or_executed(self) -> None:
        """带 Python 扩展名的任意字节仍只复制，不导入、编译或执行脚本。"""
        opaque = b"\x00\xffnot Python source\r\n"
        script = self._source / "payload/scripts/probe.py"
        script.write_bytes(opaque)
        build_resource_bundle(self._source, self._output, limits=self._limits)
        self.assertEqual((self._output / "payload/scripts/probe.py").read_bytes(), opaque)
