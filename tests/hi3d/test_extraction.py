# 文件信息
# 本文件通过正式 CLI 验证发行盘点、抽离范围和首批依赖之间的交接。
# 测试输入来自归档的真实发布锁及临时副本，结果写入临时目录。
"""验证 Hi3D 抽离范围推导的命令行契约。

入口从版本目录中的只读清单和锁定记录生成抽离计划。测试使用发行锁定样本及临时篡改副本。
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "hi3d" / "derive-extraction.py"
RELEASE_INVENTORY = REPO / "docs" / "hi3d" / "upstream" / "1.2.11" / "inventory"
INVENTORY = "inventory.jsonl"
LOCK = "inventory.lock.json"
EXTRACTION = "extraction.json"
PREBUILT = "runtime/prebuilt-skills/"
MATERIAL = PREBUILT + ".dependency-blender-tools/scripts/material_nodes.py"
EXECUTE = PREBUILT + ".dependency-blender-tools/scripts/execute.py"
TEXTURE_BAKE = PREBUILT + ".dependency-texture-bake/scripts/texture_bake.py"
CYCLES_DEVICE = PREBUILT + ".dependency-texture-bake/scripts/cycles_device.py"


class ExtractionTests(unittest.TestCase):
    """验证入口以锁定清单为输入，并发布可复用的依赖闭包。"""

    def setUp(self) -> None:
        """创建独立的运行目录与抽离计划输出位置。"""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "extraction"

    def run_extraction(self, inventory_dir: Path) -> subprocess.CompletedProcess[str]:
        """从仓库外的临时目录调用正式 CLI。

        :param inventory_dir: 含锁定记录和全量清单的版本目录。
        :return: 用于核对命令结果与错误诊断的进程回执。
        """
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                "--inventory-dir",
                str(inventory_dir),
                "--output-dir",
                str(self.output),
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_locked_release_emits_repeatable_extraction_plan(self) -> None:
        """验证实际发行记录的分类、首批本地依赖和重跑稳定性。"""
        result = self.run_extraction(RELEASE_INVENTORY)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = self.output / EXTRACTION
        first = output.read_bytes()
        extracted = json.loads(first)

        inventory_bytes = (RELEASE_INVENTORY / INVENTORY).read_bytes()
        lock_bytes = (RELEASE_INVENTORY / LOCK).read_bytes()
        source = extracted["source_inventory"]
        self.assertEqual(source["lock_sha256"], hashlib.sha256(lock_bytes).hexdigest())
        self.assertEqual(source["inventory_sha256"], hashlib.sha256(inventory_bytes).hexdigest())
        self.assertEqual(source["runtime_version"], "1.2.11")
        self.assertEqual(source["profile"], "sparc3d")

        candidates = extracted["candidates"]
        batch = extracted["batch"]
        self.assertLessEqual({MATERIAL, EXECUTE, TEXTURE_BAKE}, set(batch["entries"]))
        self.assertIn(CYCLES_DEVICE, batch["local_dependencies"][TEXTURE_BAKE])
        self.assertLessEqual({MATERIAL, EXECUTE, TEXTURE_BAKE, CYCLES_DEVICE}, set(candidates["prebuilt"]))
        self.assertIn("runtime/support/pcg_yaml.py", candidates["host"])
        self.assertEqual(batch["external_dependencies"], ["blender"])
        self.assertIn("blender", extracted["external_references"])
        locked_sizes = {
            row["path"]: row["size"]
            for row in (json.loads(line) for line in inventory_bytes.splitlines())
        }
        origin_review = extracted["origin_review"]
        self.assertIn(PREBUILT + ".dependency-head-template/assets/taro/manifest.json", origin_review)
        self.assertIn(PREBUILT + "print-kit/assets/viewer/vendor/three.min.js", origin_review)

        references = extracted["reference_only"]
        contract_sizes = [
            size for path, size in locked_sizes.items()
            if path.startswith("app.asar/node_modules/@sparc3d/contracts/")
        ]
        self.assertTrue(contract_sizes)
        self.assertEqual(
            references["desktop-host-contracts"],
            {"records": len(contract_sizes), "bytes": sum(contract_sizes)},
        )

        listed_paths = candidates["prebuilt"] + candidates["host"] + origin_review
        self.assertEqual(len(listed_paths), len(set(listed_paths)))
        self.assertLessEqual(set(listed_paths), locked_sizes.keys())
        self.assertEqual(
            len(listed_paths) + sum(group["records"] for group in references.values()),
            len(locked_sizes),
        )
        self.assertEqual(
            sum(locked_sizes[path] for path in listed_paths)
            + sum(group["bytes"] for group in references.values()),
            sum(locked_sizes.values()),
        )

        required_paths = set(batch["entries"]) | set(batch["upstream_references"])
        for dependent, dependencies in batch["local_dependencies"].items():
            required_paths.add(dependent)
            required_paths.update(dependencies)
        self.assertLessEqual(required_paths, locked_sizes.keys())
        self.assertTrue(required_paths.isdisjoint(origin_review))
        self.assertFalse(
            any(
                "/vendor/" in path
                or path.startswith(("app.asar/node_modules/", "runtime/codex/", "runtime/.runtime-python/"))
                for path in required_paths
            )
        )

        repeated = self.run_extraction(RELEASE_INVENTORY)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual(output.read_bytes(), first)

    def test_tampered_inventory_cannot_publish_extraction_plan(self) -> None:
        """验证只修改清单字节时，摘要不符在发布抽离计划前被拒绝。"""
        inventory_dir = self.root / "tampered-inventory"
        inventory_dir.mkdir()
        shutil.copyfile(RELEASE_INVENTORY / LOCK, inventory_dir / LOCK)
        original = (RELEASE_INVENTORY / INVENTORY).read_bytes()
        (inventory_dir / INVENTORY).write_bytes(original.replace(b"\n", b" \n", 1))

        result = self.run_extraction(inventory_dir)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stderr, r"(?i)sha-?256|摘要|哈希|digest")
        self.assertFalse((self.output / EXTRACTION).exists())
