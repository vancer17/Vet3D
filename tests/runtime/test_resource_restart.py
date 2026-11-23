# 文件信息：L1-03 独立进程退出后的资源快照与安装暂存边界验证。
# 作用：真实构建和安装后，以保留的清单指纹重新固定快照，拒绝认领失败残留。
# 证据边界：进程退出不等于断电；脚本只作为文件字节复制和读取，未执行任何资源。
"""通过公开入口和真实独立解释器验证安装回执不明时的有限对账。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Literal, cast
from unittest.mock import patch

from vet3d.adapters import LocalResourceStore, ResourceLimits, build_resource_bundle
from vet3d.artifacts import ContentFingerprint
from vet3d.resources import ResourceKey, ResourcePath, ResourceReference, fingerprint_bytes


type ProcessWindow = Literal["install", "partial", "renamed", "unsealed", "unsealed-read", "read", "missing"]
_PAYLOAD = b"raise RuntimeError('resource fixture must never run')\n" + b"# inert resource fixture\n" * 65536
_LIMITS = ResourceLimits(16 * 1024, 4, 4 * 1024 * 1024, 8 * 1024 * 1024)
_PARTIAL_EXIT = 75
_RENAMED_EXIT = 76
_UNSEALED_EXIT = 77


def _specification() -> dict[str, object]:
    """为本文件创建一个自研脚本声明，解释器要求仅为描述。

    :returns: 不含摘要或长度的唯一资源维护声明。
    """
    return {
        "schema_version": 1,
        "resources": [{
            "kind": "script", "key": "fixture", "entry": "fixture.py", "files": ["fixture.py"],
            "dependencies": [], "interpreter": {"runtime": "Python", "version": "不执行", "dependencies": []},
            "metadata": {
                "purpose": "进程退出边界验证", "source": "本测试自研字节夹具",
                "inputs": "不适用", "outputs": "不适用，禁止执行", "overwrite": "禁止覆盖",
                "failure": "保留未确认安装残留", "adoption": "仅供本地自动测试",
                "priority": "当前条目验证", "evidence": "只证明所测进程退出后的文件事实",
            },
        }],
    }


def _child_operation(
    root: Path, incoming: Path, expected: ContentFingerprint, window: ProcessWindow,
) -> None:
    """在独立解释器中安装或只读固定快照，并在实际落盘点中断。

    :param root: 父进程已经初始化的资源根。
    :param incoming: 父进程构建包所在的私有来源根。
    :param expected: 调用方保留的原始清单指纹。
    :param window: 正常安装、部分写入、发布封口窗口或只读验证。
    """
    store = LocalResourceStore.open(root, _LIMITS)
    if window == "read":
        reader = store.pin(expected)
        description = reader.describe(ResourceKey("fixture"))
        if description is None or description.reference != ResourceReference(expected, ResourceKey("fixture")):
            raise AssertionError("新进程没有固定调用方指定的原快照")
        observed = reader.read_file(ResourceKey("fixture"), ResourcePath("fixture.py"))
        print(fingerprint_bytes(observed).sha256, flush=True)
        return
    if window == "missing":
        try:
            store.pin(expected)
        except FileNotFoundError:
            print("missing", flush=True)
            return
        raise AssertionError("尚未发布的资源不能由暂存目录自动认领")
    if window == "unsealed-read":
        try:
            store.pin(expected)
        except PermissionError:
            print("unsealed", flush=True)
            return
        raise AssertionError("发布后尚未封口的根不能被固定为可用快照")
    original_write = os.write
    original_fsync = os.fsync
    original_fchmod = os.fchmod

    def interrupt_after_payload_chunk(descriptor: int, data: bytes) -> int:
        """先写出真实首块，再直接退出，不运行安装异常清理。

        :param descriptor: 当前实际暂存输出文件。
        :param data: 安装器准备写入的字节块。
        :returns: 未触及中断条件时的实际写入长度。
        """
        written = original_write(descriptor, data)
        if len(data) >= 1024 * 1024:
            os._exit(_PARTIAL_EXIT)
        return written

    def interrupt_after_published_name(descriptor: int) -> None:
        """最终快照目录已出现时在目录同步回执前退出。

        :param descriptor: 安装器当前正在同步的真实对象句柄。
        """
        if (root / "snapshots" / expected.sha256).exists():
            os._exit(_RENAMED_EXIT)
        original_fsync(descriptor)

    def interrupt_before_final_seal(descriptor: int, mode: int) -> None:
        """最终名称已出现且根即将只读封口时退出，保留真实未完成窗口。

        :param descriptor: 安装器正在修改权限的实际目录句柄。
        :param mode: 安装器准备设置的目标权限。
        """
        if mode == 0o500 and (root / "snapshots" / expected.sha256).exists():
            os._exit(_UNSEALED_EXIT)
        original_fchmod(descriptor, mode)

    if window == "partial":
        with patch("os.write", side_effect=interrupt_after_payload_chunk):
            store.install(incoming, "built", expected)
        raise AssertionError("未到达实际 payload 部分写入窗口")
    if window == "renamed":
        with patch("os.fsync", side_effect=interrupt_after_published_name):
            store.install(incoming, "built", expected)
        raise AssertionError("未到达发布后同步窗口")
    if window == "unsealed":
        with patch("os.fchmod", side_effect=interrupt_before_final_seal):
            store.install(incoming, "built", expected)
        raise AssertionError("未到达发布后根目录封口窗口")
    installed = store.install(incoming, "built", expected)
    print(installed.sha256, flush=True)


class ResourceRestartTests(unittest.TestCase):
    """仅依据原清单指纹固定完整快照，不以重新安装冒充未确认操作续接。"""

    def setUp(self) -> None:
        """构建真实私有包并初始化空安装根，尚不执行安装。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self._parent = Path(temporary.name)
        source = self._parent / "source"
        source.mkdir(mode=0o700)
        (source / "payload").mkdir(mode=0o700)
        (source / "resource-spec.json").write_text(
            json.dumps(_specification(), ensure_ascii=False), encoding="utf-8"
        )
        (source / "resource-spec.json").chmod(0o600)
        (source / "payload/fixture.py").write_bytes(_PAYLOAD)
        (source / "payload/fixture.py").chmod(0o600)
        self._incoming = self._parent / "incoming"
        self._incoming.mkdir(mode=0o700)
        self._snapshot = build_resource_bundle(source, self._incoming / "built", limits=_LIMITS)
        self._root = self._parent / "installed"
        LocalResourceStore.initialize(self._root, _LIMITS)

    def _run_child(self, window: ProcessWindow, expected_exit: int = 0) -> str:
        """运行实际独立解释器，核对正常或指定强退退出码。

        :param window: 子进程动作及故障窗口。
        :param expected_exit: 预期的退出码。
        :returns: 子进程刷新的清单或文件指纹文本。
        """
        result = subprocess.run(
            [
                sys.executable, str(Path(__file__).absolute()), "--child", str(self._root),
                str(self._incoming), self._snapshot.sha256, str(self._snapshot.byte_size), window,
            ],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, expected_exit, result.stderr)
        return result.stdout.rstrip("\n")

    def test_complete_install_can_be_pinned_and_read_in_another_process(self) -> None:
        """新进程全量核对调用方保留的清单指纹，并读取同一脚本原始字节。"""
        self.assertEqual(self._run_child("install"), self._snapshot.sha256)
        self.assertEqual(self._run_child("read"), fingerprint_bytes(_PAYLOAD).sha256)
        self.assertEqual(tuple((self._root / ".staging").iterdir()), ())

    def test_partial_process_exit_leaves_stage_without_automatic_adoption(self) -> None:
        """复制中强退后暂存保留，新进程不能把未发布目录当成完整快照。"""
        self._run_child("partial", _PARTIAL_EXIT)
        stages = tuple((self._root / ".staging").iterdir())
        self.assertEqual(len(stages), 1)
        partial = stages[0] / "payload/fixture.py"
        content = partial.read_bytes()
        self.assertGreater(len(content), 0)
        self.assertLess(len(content), len(_PAYLOAD))
        self.assertEqual(content, _PAYLOAD[:len(content)])
        self.assertEqual(tuple((self._root / "snapshots").iterdir()), ())
        self.assertEqual(self._run_child("missing"), "missing")
        self.assertEqual(partial.read_bytes(), content)
        self.assertEqual(tuple((self._root / ".staging").iterdir()), stages)

    def test_exit_after_publish_allows_original_pin_but_reinstall_is_rejected(self) -> None:
        """最终目录封口后同步回执不明时可核对原快照，再次安装仍不覆盖。"""
        self._run_child("renamed", _RENAMED_EXIT)
        self.assertEqual(self._run_child("read"), fingerprint_bytes(_PAYLOAD).sha256)
        store = LocalResourceStore.open(self._root, _LIMITS)
        with self.assertRaises(FileExistsError):
            store.install(self._incoming, "built", self._snapshot)
        self.assertEqual(
            store.pin(self._snapshot).read_file(ResourceKey("fixture"), ResourcePath("fixture.py")), _PAYLOAD
        )

    def test_exit_after_rename_before_seal_is_rejected_without_repair_or_overwrite(self) -> None:
        """跨父移动后尚未封口的强退现场不可读取，不被重装覆盖或自动修复。"""
        self._run_child("unsealed", _UNSEALED_EXIT)
        target = self._root / "snapshots" / self._snapshot.sha256
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual((target / "payload/fixture.py").read_bytes(), _PAYLOAD)
        self.assertEqual(self._run_child("unsealed-read"), "unsealed")
        store = LocalResourceStore.open(self._root, _LIMITS)
        with self.assertRaises(PermissionError):
            store.pin(self._snapshot)
        with self.assertRaises(FileExistsError):
            store.install(self._incoming, "built", self._snapshot)
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual((target / "payload/fixture.py").read_bytes(), _PAYLOAD)

    def test_unknown_stage_is_preserved_during_later_install_and_read(self) -> None:
        """未知安装暂存不被清理或认领，后续独立安装和读取仍能正常完成。"""
        unknown = self._root / ".staging/install-0123456789abcdef0123456789abcdef"
        unknown.mkdir(mode=0o700)
        sentinel = unknown / "unrelated.bin"
        sentinel.write_bytes(b"unknown provenance")
        sentinel.chmod(0o600)
        self.assertEqual(self._run_child("missing"), "missing")
        self.assertEqual(self._run_child("install"), self._snapshot.sha256)
        self.assertEqual(self._run_child("read"), fingerprint_bytes(_PAYLOAD).sha256)
        self.assertEqual(sentinel.read_bytes(), b"unknown provenance")
        self.assertEqual(tuple((self._root / ".staging").iterdir()), (unknown,))


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "--child":
        if sys.argv[6] not in ("install", "partial", "renamed", "unsealed", "unsealed-read", "read", "missing"):
            raise ValueError("未知资源进程故障窗口")
        _child_operation(
            Path(sys.argv[2]), Path(sys.argv[3]), ContentFingerprint(sys.argv[4], int(sys.argv[5])),
            cast(ProcessWindow, sys.argv[6]),
        )
    else:
        unittest.main()
