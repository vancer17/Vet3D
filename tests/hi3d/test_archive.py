# 文件信息
# 本文件验证 P0 与 P1 原件归档命令对发行输入和输出目录的隔离。
# 测试只创建临时目录，无需安装包文件。
"""验证 Hi3D 归档输出的路径边界。"""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "hi3d"


class ArchiveTests(unittest.TestCase):
    """通过命令行验证输出目录与锁定发行输入的交界。"""

    def setUp(self) -> None:
        """建立空的发行输入和安装资源目录，以验证路径拒绝先于取证。"""
        working = TemporaryDirectory()
        self.addCleanup(working.cleanup)
        self.root = Path(working.name)
        self.release = self.root / "release"
        self.inventory = self.release / "inventory"
        self.extraction = self.release / "extraction"
        self.resources = self.root / "installation" / "resources"
        for directory in (self.inventory, self.extraction, self.resources):
            directory.mkdir(parents=True)

    def run_archive(self, output: Path, *, level: str) -> subprocess.CompletedProcess[str]:
        """从临时目录启动指定批次的正式归档命令。

        :param output: 本次核对的归档输出目录。
        :param level: 命令对应的归档批次。
        :return: 命令退出码和诊断输出。
        """
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPTS / f"archive-{level}.py"),
                "--release-dir",
                str(self.release),
                "--resources-root",
                str(self.resources),
                "--output-dir",
                str(output),
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_output_cannot_overlap_locked_release_inputs(self) -> None:
        """验证相同、子目录和包含发行输入的上层目录均在读锁前被拒绝。"""
        inputs = set(self.release.iterdir())
        cases = (
            (self.inventory, {"inventory"}),
            (self.inventory / "candidate", {"inventory"}),
            (self.extraction, {"extraction"}),
            (self.extraction / "candidate", {"extraction"}),
            (self.release, {"inventory", "extraction"}),
        )
        diagnostic = "archive output overlaps a locked release input directory: "
        for level in ("p0", "p1"):
            for output, expected in cases:
                with self.subTest(level=level, output=output.relative_to(self.release)):
                    result = self.run_archive(output, level=level)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertTrue(
                        any(diagnostic + name in result.stderr for name in expected),
                        result.stderr,
                    )
                    self.assertEqual(set(self.release.rglob("*")), inputs)

    def test_sibling_archive_directory_reaches_inventory_read(self) -> None:
        """验证同级归档目标通过路径预检并进入发行锁读取。"""
        for level in ("p0", "p1"):
            with self.subTest(level=level):
                output = self.release / f"archived-{level}"
                result = self.run_archive(output, level=level)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("inventory.lock.json", result.stderr)
                self.assertNotIn("archive output overlaps", result.stderr)
                self.assertFalse(output.exists())
