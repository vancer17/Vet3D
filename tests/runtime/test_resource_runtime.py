# 文件信息：L1-03 公开资源装配的真实消费者与异步生命周期验证。
# 作用：验证原快照读取、独立安装准入、有限并发、取消和资源关闭。
# 证据边界：仅安装和读取自研文档夹具，不执行脚本或证明模型已接收内容。
"""以真实构建及资源存储核对固定版本的宿主交接。"""

import asyncio
from collections.abc import Callable
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from vet3d.adapters import ResourceLimits, build_resource_bundle
from vet3d.artifacts import ContentFingerprint
from vet3d.bootstrap import (
    PinnedResources, ResourceBusyError, ResourceClosedError, ResourceTimeoutError,
    initialize_resources, open_resources,
)
from vet3d.resources import (
    ResourceContractError, ResourceDescription, ResourceKey, ResourcePath, ResourceReader, ResourceReference,
)


def _build_fixture(base: Path, bundle_root: Path, name: str, content: bytes) -> ContentFingerprint:
    """由唯一维护源真实构建一个小文档资源包，不手写摘要。

    :param base: 本例维护源所在临时父目录。
    :param bundle_root: 受信资源包来源根。
    :param name: 该版本的独立构建名称。
    :param content: 此版本的文档原始字节。
    :returns: 真实构建所得的清单指纹。
    """
    source = base / ("author-" + name)
    source.mkdir(mode=0o700)
    payload = source / "payload"
    payload.mkdir(mode=0o700)
    (payload / "guide.txt").write_bytes(content)
    (payload / "guide.txt").chmod(0o600)
    spec: dict[str, object] = {
        "schema_version": 1,
        "resources": [{
            "kind": "document", "key": "fixture.guide", "entry": "guide.txt",
            "files": ["guide.txt"], "dependencies": [],
            "metadata": {
                "purpose": "仅用于资源读取验收", "source": "本测试自研夹具",
                "inputs": "不适用", "outputs": "原文档字节", "overwrite": "不覆盖",
                "failure": "没有脚本执行", "adoption": "独立实现", "priority": "首期闭环",
                "evidence": "只验证安装与读取，不验证模型理解",
            },
        }],
    }
    declaration = source / "resource-spec.json"
    declaration.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    declaration.chmod(0o600)
    return build_resource_bundle(source, bundle_root / name, limits=_limits())


def _limits() -> ResourceLimits:
    """给当前小夹具注入有限部署预算，不定义产品能力默认值。

    :returns: 明确的清单、文件数量、单文件及总字节预算。
    """
    return ResourceLimits(max_manifest_bytes=32768, max_files=8, max_file_bytes=4096, max_total_bytes=16384)


async def _wait_event(event: threading.Event) -> None:
    """有限等待实际线程到达读操作，保持事件循环可调度。

    :param event: 工作线程到达通知。
    """
    async with asyncio.timeout(5):
        while not event.is_set():
            await asyncio.sleep(0.001)


def _held_read(
    path: Path, entered: threading.Event, release: threading.Event,
    descriptors: list[int], *, fail: bool = False,
) -> Callable[[int, int, int], bytes]:
    """仅暂停确切普通文件第一次实际读取，不替换其余文件系统行为。

    :param path: 本例目标源文件或已安装文件。
    :param entered: 到达实际 I/O 的通知。
    :param release: 允许真实 I/O 继续的通知。
    :param descriptors: 记录实际打开的描述符供寿命断言。
    :param fail: 放行后是否注入晚期读取故障。
    :returns: 保持 os.pread 签名的测试替代函数。
    """
    info = path.stat()
    identity = info.st_dev, info.st_ino
    original = os.pread

    def read(descriptor: int, length: int, offset: int) -> bytes:
        """在仍持有真实文件句柄时暂停一次，之后回到原读取。

        :param descriptor: 实际打开的普通文件描述符。
        :param length: 适配器的有界读取请求。
        :param offset: 原读取位置。
        :returns: 实际文件字节。
        """
        current = os.fstat(descriptor)
        if (current.st_dev, current.st_ino) == identity and not entered.is_set():
            descriptors.append(descriptor)
            entered.set()
            if not release.wait(5):
                raise TimeoutError("测试未放行实际资源读取")
            if fail:
                raise OSError("受控晚期资源读取故障")
        return original(descriptor, length, offset)

    return read


class _ForeignReader(ResourceReader):
    """仅模拟替换端口返回其他快照，不证明实际文件或执行能力。"""

    def __init__(self, description: ResourceDescription) -> None:
        """保存一份故意关联错误的回包。

        :param description: 其他快照的资源声明。
        """
        self.description = description
        self.read_calls = 0

    def describe(self, key: ResourceKey) -> ResourceDescription | None:
        """返回其他快照，要求消费者在交接前拒绝。

        :param key: 原请求键，不会修正错误夹具。
        :returns: 故意错误的描述。
        """
        return self.description

    def read_file(self, key: ResourceKey, path: ResourcePath) -> bytes:
        """记录不应发生的读取。

        :param key: 原请求键。
        :param path: 原请求文件。
        :returns: 不能成为正确交接的测试字节。
        """
        self.read_calls += 1
        return b"wrong snapshot"


class ResourceRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """以真实资源根检验固定版本与服务端并发资源归属。"""

    async def asyncSetUp(self) -> None:
        """建立一个已经安装且可读取的原版本，所有资源在测试结束关闭。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "managed-resources"
        self.bundles = self.base / "bundles"
        self.bundles.mkdir(mode=0o700)
        self.original_bytes = b"original resource bytes"
        self.first = _build_fixture(self.base, self.bundles, "first", self.original_bytes)
        self.runtime = await initialize_resources(
            self.root, source_root=self.bundles, limits=_limits(), max_readers=2,
        )
        self.addAsyncCleanup(self.runtime.aclose)
        await self.runtime.install("first", self.first)
        self.reader = await self.runtime.pin(self.first)
        self.key = ResourceKey("fixture.guide")
        self.path = ResourcePath("guide.txt")

    async def test_public_versions_stay_fixed_and_reopen_uses_original_snapshot(self) -> None:
        """新版发布不改旧实例，独立重开必须明确提供原指纹且不能自动选择最新。"""
        second = _build_fixture(self.base, self.bundles, "second", b"new bytes")
        await self.runtime.install("second", second)
        new_reader = await self.runtime.pin(second)
        self.assertEqual(await self.reader.read_file(self.key, self.path), self.original_bytes)
        self.assertEqual(await new_reader.read_file(self.key, self.path), b"new bytes")
        description = self.reader.describe(self.key)
        assert description is not None
        self.assertEqual(description.reference.snapshot, self.first)
        self.assertIsNone(self.reader.describe(ResourceKey("unknown")))
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(FileExistsError):
            await self.runtime.install("first", self.first)
        await self.runtime.aclose()
        with self.assertRaises(ResourceClosedError):
            await self.reader.read_file(self.key, self.path)
        async with await open_resources(
            self.root, source_root=self.bundles, limits=_limits(), max_readers=1,
        ) as reopened:
            pinned = await reopened.pin(self.first)
            self.assertEqual(await pinned.read_file(self.key, self.path), self.original_bytes)

    async def test_cancelled_install_keeps_source_owned_and_old_readers_available(self) -> None:
        """取消安装等待后保留实际源句柄，新安装被拒绝，旧版本读取仍能推进。"""
        second = _build_fixture(self.base, self.bundles, "second", b"new bytes")
        entered, release = threading.Event(), threading.Event()
        descriptors: list[int] = []
        source = self.bundles / "second" / "payload" / "guide.txt"
        with patch("os.pread", _held_read(source, entered, release, descriptors)):
            operation = asyncio.create_task(self.runtime.install("second", second))
            try:
                await _wait_event(entered)
                operation.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await operation
                self.assertEqual(os.fstat(descriptors[0]).st_size, len(b"new bytes"))
                with self.assertRaises(ResourceBusyError):
                    await self.runtime.install("second", second)
                self.assertEqual(await self.reader.read_file(self.key, self.path), self.original_bytes)
                closing = asyncio.create_task(self.runtime.aclose())
                await asyncio.sleep(0)
                self.assertFalse(closing.done())
                with self.assertRaises(ResourceClosedError):
                    await self.reader.read_file(self.key, self.path)
            finally:
                release.set()
            await self.runtime.aclose()
            await closing
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        async with await open_resources(
            self.root, source_root=self.bundles, limits=_limits(), max_readers=1,
        ) as reopened:
            pinned = await reopened.pin(second)
            self.assertEqual(await pinned.read_file(self.key, self.path), b"new bytes")

    async def test_timeout_retains_one_late_error_and_closes_source(self) -> None:
        """等待超时不吞掉实际故障，晚期异常只记录一次并在终结后关闭原句柄。"""
        second = _build_fixture(self.base, self.bundles, "second", b"new bytes")
        entered, release = threading.Event(), threading.Event()
        descriptors: list[int] = []
        source = self.bundles / "second" / "payload" / "guide.txt"
        with self.assertLogs("vet3d", level="INFO") as captured:
            with patch("os.pread", _held_read(source, entered, release, descriptors, fail=True)):
                operation = asyncio.create_task(self.runtime.install("second", second, timeout_seconds=0.05))
                try:
                    await _wait_event(entered)
                    with self.assertRaises(ResourceTimeoutError):
                        await operation
                    os.fstat(descriptors[0])
                finally:
                    release.set()
                await self.runtime.aclose()
        failures = [record for record in captured.records if record.levelname == "ERROR"]
        self.assertEqual(len(failures), 1)
        self.assertIsNotNone(failures[0].exc_info)
        self.assertIn(second.sha256, failures[0].getMessage())
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    async def test_read_budget_has_no_queue_and_release_occurs_after_actual_read(self) -> None:
        """单读预算占满时新读取直接拒绝；取消等待不会提前返还真实名额。"""
        await self.runtime.aclose()
        async with await open_resources(
            self.root, source_root=self.bundles, limits=_limits(), max_readers=1,
        ) as runtime:
            pinned = await runtime.pin(self.first)
            installed = self.root / "snapshots" / self.first.sha256 / "payload" / "guide.txt"
            entered, release = threading.Event(), threading.Event()
            descriptors: list[int] = []
            with patch("os.pread", _held_read(installed, entered, release, descriptors)):
                operation = asyncio.create_task(pinned.read_file(self.key, self.path))
                try:
                    await _wait_event(entered)
                    operation.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await operation
                    with self.assertRaises(ResourceBusyError):
                        await pinned.read_file(self.key, self.path)
                finally:
                    release.set()
                await runtime.aclose()

    async def test_two_readers_can_progress_independently_within_budget(self) -> None:
        """读取一个固定文件被暂停时，第二个读取名额可以完成相同版本的核对。"""
        installed = self.root / "snapshots" / self.first.sha256 / "payload" / "guide.txt"
        entered, release = threading.Event(), threading.Event()
        descriptors: list[int] = []
        with patch("os.pread", _held_read(installed, entered, release, descriptors)):
            operation = asyncio.create_task(self.reader.read_file(self.key, self.path))
            try:
                await _wait_event(entered)
                self.assertEqual(await self.reader.read_file(self.key, self.path), self.original_bytes)
                self.assertFalse(operation.done())
            finally:
                release.set()
            self.assertEqual(await operation, self.original_bytes)

    async def test_wrong_snapshot_from_injected_reader_is_rejected_before_file_access(self) -> None:
        """替换端口回包不能改变实例已固定的快照，错误关联不会触发读取。"""
        description = self.reader.describe(self.key)
        assert description is not None
        wrong = ResourceDescription(
            ResourceReference(ContentFingerprint("0" * 64, 0), self.key), description.definition,
        )
        dependency = _ForeignReader(wrong)
        pinned = PinnedResources(self.runtime, self.first, dependency)
        with self.assertRaises(ResourceContractError):
            pinned.describe(self.key)
        with self.assertRaises(ResourceContractError):
            await pinned.read_file(self.key, self.path)
        self.assertEqual(dependency.read_calls, 0)

    async def test_configuration_and_request_paths_do_not_escape_fixed_roots(self) -> None:
        """配置根不重叠，请求不能通过路径或 URL 选择任意安装源。"""
        for root in (self.bundles, self.bundles / "nested", self.base, self.base / ".." / "elsewhere"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                await initialize_resources(root, source_root=self.bundles, limits=_limits(), max_readers=1)
        for name in ("../first", str(self.bundles / "first"), "first/child", "file://first"):
            with self.subTest(name=name), self.assertLogs("vet3d", level="WARNING"), self.assertRaises(ValueError):
                await self.runtime.install(name, self.first)
        for seconds in (0.0, -1.0, float("inf"), float("nan"), True):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                await self.reader.read_file(self.key, self.path, timeout_seconds=seconds)
