# 文件信息：L1-03 受管资源快照安装与固定读取的真实文件系统测试。
# 作用：验证无覆盖目录提交、精确输入树、权限、限额及局部失败清理边界。
# 证据边界：小型自研字节夹具不证明脚本执行安全、解释器就绪或真实建模能力。
"""通过公开适配器验证实际文件、锁和目录发布，不执行资源脚本。"""

from dataclasses import replace
import fcntl
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from vet3d.adapters import LocalResourceStore, ResourceLimits
from vet3d.artifacts import ContentFingerprint
from vet3d.resources import (
    DocumentResource, ResourceContractError, ResourceFile, ResourceKey, ResourceManifest,
    ResourceMetadata, ResourcePath, fingerprint_bytes, serialize_manifest,
)


class ResourceFilesTests(unittest.TestCase):
    """核对只读资源版本的真实 I/O 行为及保留现场的恢复边界。"""

    def setUp(self) -> None:
        """建立互相分离的私有来源和资源根，使用显式单次预算。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self._parent = Path(temporary.name)
        self._incoming = self._parent / "incoming"
        self._incoming.mkdir(mode=0o700)
        self._root = self._parent / "resources"
        self._limits = ResourceLimits(16 * 1024, 8, 4096, 8192)
        self._store = LocalResourceStore.initialize(self._root, self._limits)
        self._snapshot = self._bundle("first")

    def _bundle(self, name: str, *, content: bytes = b"trusted source\n", suffix: bytes = b"") -> ContentFingerprint:
        """从唯一资源记录生成私有测试包，不依赖生产构建器作为安装测试前提。

        :param name: 私有源中的单段包名。
        :param content: 第一份资源的真实字节。
        :param suffix: 合法 JSON 末尾空白，用于证明快照对应原字节。
        :returns: 此包原始清单内容指纹。
        """
        bundle = self._incoming / name
        bundle.mkdir(mode=0o700)
        files = {"docs/guide.md": content, "scripts/extra.py": b"raise RuntimeError('never run')\n"}
        metadata = ResourceMetadata(
            purpose="真实文件测试", source="本测试的自研字节夹具", inputs="无需执行",
            outputs="原始字节", overwrite="拒绝已有版本", failure="只报告实际文件错误",
            adoption="单元验证", priority="当前条目", evidence="不证明任何执行能力",
        )
        guide = ResourcePath("docs/guide.md")
        extra = ResourcePath("scripts/extra.py")
        manifest = ResourceManifest(
            files=tuple(ResourceFile(ResourcePath(path), fingerprint_bytes(data)) for path, data in files.items()),
            resources=(
                DocumentResource(ResourceKey("guide"), guide, (guide,), (), metadata),
                DocumentResource(ResourceKey("extra"), extra, (extra,), (ResourceKey("guide"),), metadata),
            ),
        )
        raw = serialize_manifest(manifest) + suffix
        (bundle / "manifest.json").write_bytes(raw)
        (bundle / "manifest.json").chmod(0o400)
        payload = bundle / "payload"
        payload.mkdir(mode=0o700)
        for path, data in files.items():
            target = payload / path
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o400)
        return fingerprint_bytes(raw)

    def _published(self, snapshot: ContentFingerprint | None = None) -> Path:
        """定位测试需观察的最终目录，不用于产品路径协议。

        :param snapshot: 需要定位的原清单身份，缺省使用第一包。
        :returns: 本夹具资源根下的版本目录。
        """
        selected = self._snapshot if snapshot is None else snapshot
        return self._root / "snapshots" / selected.sha256

    def test_real_directory_commit_preserves_raw_manifest_source_and_readonly_permissions(self) -> None:
        """真实无覆盖提交保留原清单空白与源字节，最终所有文件和目录只读。"""
        snapshot = self._bundle("whitespace", suffix=b" \n")
        original = (self._incoming / "whitespace/manifest.json").read_bytes()
        self.assertEqual(self._store.install(self._incoming, "whitespace", snapshot), snapshot)
        published = self._published(snapshot)
        self.assertEqual((published / "manifest.json").read_bytes(), original)
        self.assertEqual((self._incoming / "whitespace/manifest.json").read_bytes(), original)
        for path in (published, *published.rglob("*")):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o500 if path.is_dir() else 0o400)
        reader = self._store.pin(snapshot)
        description = reader.describe(ResourceKey("guide"))
        assert description is not None
        self.assertEqual(description.reference.snapshot, snapshot)
        self.assertEqual(reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"trusted source\n")
        self.assertEqual(reader.read_file(ResourceKey("extra"), ResourcePath("scripts/extra.py")), b"raise RuntimeError('never run')\n")
        self.assertEqual(list((self._root / ".staging").iterdir()), [])

    def test_open_never_initializes_and_initialize_refuses_existing_nonempty_roots(self) -> None:
        """显式打开不补建缺失布局，初始化不认领已有文件或已初始化根。"""
        absent = self._parent / "absent"
        with self.assertRaises(FileNotFoundError):
            LocalResourceStore.open(absent, self._limits)
        self.assertFalse(absent.exists())
        with self.assertRaises(FileExistsError):
            LocalResourceStore.initialize(self._root, self._limits)
        incomplete = self._parent / "incomplete"
        incomplete.mkdir(mode=0o700)
        (incomplete / "unrelated").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            LocalResourceStore.initialize(incomplete, self._limits)
        self.assertEqual((incomplete / "unrelated").read_bytes(), b"keep")
        (self._root / ".staging").rmdir()
        with self.assertRaises(FileNotFoundError):
            LocalResourceStore.open(self._root, self._limits)
        self.assertFalse((self._root / ".staging").exists())

    def test_root_links_permissions_and_original_layout_replacement_are_rejected(self) -> None:
        """根链接、非私有根和已观察控制目录替换均不被当作原存储继续使用。"""
        link = self._parent / "linked-root"
        link.symlink_to(self._root, target_is_directory=True)
        with self.assertRaises(OSError):
            LocalResourceStore.open(link, self._limits)
        self._root.chmod(0o755)
        with self.assertRaises(PermissionError):
            LocalResourceStore.open(self._root, self._limits)
        self._root.chmod(0o700)
        snapshots = self._root / "snapshots"
        snapshots.rename(self._parent / "old-snapshots")
        snapshots.mkdir(mode=0o700)
        with self.assertRaisesRegex(OSError, "inode"):
            self._store.install(self._incoming, "first", self._snapshot)

    def test_new_version_does_not_change_an_already_pinned_reader(self) -> None:
        """同一逻辑键的新版本独立发布，原读者继续使用原身份和原内容。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        second = self._bundle("second", content=b"new contents\n")
        self._store.install(self._incoming, "second", second)
        self.assertEqual(reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"trusted source\n")
        self.assertEqual(self._store.pin(second).read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"new contents\n")
        with self.assertRaises(FileExistsError):
            self._store.install(self._incoming, "first", self._snapshot)

    def test_reader_requires_direct_file_ownership_and_description_is_metadata_only(self) -> None:
        """依赖声明不扩大文件读取权，描述存在不表示其文件仍然可读。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        self.assertIsNone(reader.describe(ResourceKey("missing")))
        with self.assertRaises(ResourceContractError):
            reader.read_file(ResourceKey("extra"), ResourcePath("docs/guide.md"))
        target = self._published() / "payload/docs/guide.md"
        target.parent.chmod(0o700)
        target.unlink()
        target.parent.chmod(0o500)
        self.assertIsNotNone(reader.describe(ResourceKey("guide")))
        with self.assertRaises(FileNotFoundError):
            reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md"))

    def test_source_tree_must_be_exact_without_extra_files_or_directories(self) -> None:
        """额外文件或目录在复制前拒绝，未声明目录连句柄也不打开。"""
        payload = self._incoming / "first/payload"
        extra = payload / "extra"
        extra.write_bytes(b"unlisted")
        extra.chmod(0o400)
        with self.assertRaises(OSError):
            self._store.install(self._incoming, "first", self._snapshot)
        extra.unlink()
        extra.mkdir(mode=0o700)
        original_open = os.open

        def tracked_open(path: str | bytes | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
            """拒绝测试夹具的未声明目录被实际打开，以验证先判声明再打开。

            :param path: 被调用的系统打开位置。
            :param flags: 原打开标志。
            :param mode: 原创建权限。
            :param dir_fd: 原父目录句柄。
            :returns: 真实系统打开结果。
            """
            if path == "extra":
                raise AssertionError("undeclared directory must not be opened")
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with patch("os.open", tracked_open), self.assertRaises(OSError):
            self._store.install(self._incoming, "first", self._snapshot)
        self.assertFalse(self._published().exists())
        self.assertEqual(list((self._root / ".staging").iterdir()), [])

    def test_source_links_hardlinks_special_objects_and_public_permissions_are_rejected(self) -> None:
        """私有包规则独立于构建源规则，实际拒绝链接、FIFO 与普通公共文件。"""
        target = self._incoming / "first/payload/docs/guide.md"
        data = target.read_bytes()
        outside = self._parent / "outside"
        outside.write_bytes(data)
        outside.chmod(0o400)
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaises(OSError):
            self._store.install(self._incoming, "first", self._snapshot)
        target.unlink()
        os.link(outside, target)
        with self.assertRaises(OSError):
            self._store.install(self._incoming, "first", self._snapshot)
        target.unlink()
        os.mkfifo(target, mode=0o600)
        with self.assertRaises(OSError):
            self._store.install(self._incoming, "first", self._snapshot)
        target.unlink()
        target.write_bytes(data)
        target.chmod(0o644)
        with self.assertRaises(PermissionError):
            self._store.install(self._incoming, "first", self._snapshot)
        target.chmod(0o600)
        self._store.install(self._incoming, "first", self._snapshot)

    def test_manifest_and_actual_payload_digest_mismatch_never_publish(self) -> None:
        """预期清单与实际内容分别核对，复制期内容错误清理本次而保留未知暂存。"""
        with self.assertRaises(ResourceContractError):
            self._store.install(self._incoming, "first", ContentFingerprint("0" * 64, self._snapshot.byte_size))
        unknown = self._root / ".staging/unknown"
        unknown.mkdir(mode=0o700)
        target = self._incoming / "first/payload/docs/guide.md"
        target.chmod(0o600)
        target.write_bytes(b"untrusted data\n")
        target.chmod(0o400)
        with self.assertRaises(ResourceContractError):
            self._store.install(self._incoming, "first", self._snapshot)
        self.assertEqual(list((self._root / ".staging").iterdir()), [unknown])
        self.assertFalse(self._published().exists())

    def test_each_operational_budget_rejects_without_publishing(self) -> None:
        """清单、文件数、单文件及总量均由唯一限额核对，不生成业务能力状态。"""
        cases = (
            replace(self._limits, max_manifest_bytes=8), replace(self._limits, max_files=1),
            replace(self._limits, max_file_bytes=2), replace(self._limits, max_total_bytes=8),
        )
        for limits in cases:
            with self.subTest(limits=limits):
                store = LocalResourceStore.open(self._root, limits)
                with self.assertRaises(OSError):
                    store.install(self._incoming, "first", self._snapshot)
        self.assertFalse(self._published().exists())
        self.assertEqual(list((self._root / ".staging").iterdir()), [])

    def test_source_and_managed_roots_cannot_overlap_and_bundle_name_is_single_segment(self) -> None:
        """资源安装只接受固定私有来源中的单段包名，不能跳入控制根。"""
        with self.assertRaises(ValueError):
            self._store.install(self._root, "first", self._snapshot)
        with self.assertRaises(ResourceContractError):
            self._store.install(self._incoming, "first/payload", self._snapshot)
        with self.assertRaises(ResourceContractError):
            self._store.install(self._incoming, "../first", self._snapshot)
        linked = self._parent / "linked-incoming"
        linked.symlink_to(self._incoming, target_is_directory=True)
        with self.assertRaises(OSError):
            self._store.install(linked, "first", self._snapshot)

    def test_late_existing_directory_is_not_overwritten_by_real_atomic_commit(self) -> None:
        """在预检后出现的空目标仍由真实 RENAME_NOREPLACE 拒绝，不回退覆盖。"""
        original_fsync = os.fsync
        inserted = False

        def fsync_with_late_target(descriptor: int) -> None:
            """在完整暂存同步时注入已有目录，保留系统原语实际冲突行为。

            :param descriptor: 当前待同步的实际句柄。
            """
            nonlocal inserted
            path = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
            if path == self._root / ".staging" and not inserted:
                self._published().mkdir(mode=0o500)
                inserted = True
            original_fsync(descriptor)

        with patch("os.fsync", fsync_with_late_target), self.assertRaises(FileExistsError):
            self._store.install(self._incoming, "first", self._snapshot)
        self.assertTrue(inserted)
        self.assertEqual(list(self._published().iterdir()), [])
        self.assertEqual(list((self._root / ".staging").iterdir()), [])

    def test_sync_failure_after_publish_preserves_final_and_requires_explicit_readback(self) -> None:
        """提交后父目录同步失败报告异常但保留已出现版本，后续按原指纹复核。"""
        original_fsync = os.fsync

        def fail_after_commit(descriptor: int) -> None:
            """仅在目标已可见后的父目录同步点模拟失败。

            :param descriptor: 本次待同步句柄。
            """
            if Path(os.readlink(f"/proc/self/fd/{descriptor}")) == self._root / "snapshots" and self._published().exists():
                raise OSError("injected final parent fsync failure")
            original_fsync(descriptor)

        with patch("os.fsync", fail_after_commit), self.assertRaisesRegex(OSError, "injected"):
            self._store.install(self._incoming, "first", self._snapshot)
        reopened = LocalResourceStore.open(self._root, self._limits)
        self.assertEqual(reopened.pin(self._snapshot).read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"trusted source\n")
        with self.assertRaises(FileExistsError):
            reopened.install(self._incoming, "first", self._snapshot)

    def test_failure_preserves_stage_when_an_unknown_object_appears_inside(self) -> None:
        """暂存出现未由本次创建对象时拒绝清理整树，不删除未知现场。"""
        original_fsync = os.fsync

        def fail_with_unknown_object(descriptor: int) -> None:
            """在本次第一文件同步时放入未知对象并触发失败。

            :param descriptor: 实际同步的文件句柄。
            """
            path = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
            if path.name == "manifest.json" and path.is_relative_to(self._root / ".staging"):
                (path.parent / "unknown").write_bytes(b"keep")
                raise OSError("injected stage failure")
            original_fsync(descriptor)

        with patch("os.fsync", fail_with_unknown_object), self.assertRaisesRegex(OSError, "injected") as caught:
            self._store.install(self._incoming, "first", self._snapshot)
        stages = list((self._root / ".staging").iterdir())
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "unknown").read_bytes(), b"keep")
        self.assertTrue(caught.exception.__notes__)
        self.assertFalse(self._published().exists())

    def test_install_lock_refuses_second_writer_without_blocking_fixed_readers(self) -> None:
        """真实文件锁只管理安装，原快照固定和读取不申请该排他锁。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        second = self._bundle("second", content=b"new content\n")
        lock = os.open(self._root / ".install.lock", os.O_RDWR | os.O_CLOEXEC)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            other = LocalResourceStore.open(self._root, self._limits)
            with self.assertRaises(BlockingIOError):
                other.install(self._incoming, "second", second)
            self.assertIsNotNone(other.pin(self._snapshot).describe(ResourceKey("guide")))
            self.assertEqual(reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"trusted source\n")
        finally:
            os.close(lock)
        self._store.install(self._incoming, "second", second)

    def test_fixed_reader_rejects_same_bytes_inode_replacement(self) -> None:
        """原样文件替换也不能冒充同一读者已经观察的实际对象。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        target = self._published() / "payload/docs/guide.md"
        replacement = self._parent / "replacement"
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(0o400)
        target.parent.chmod(0o700)
        replacement.replace(target)
        target.parent.chmod(0o500)
        with self.assertRaisesRegex(OSError, "inode"):
            reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md"))
        self.assertEqual(self._store.pin(self._snapshot).read_file(ResourceKey("guide"), ResourcePath("docs/guide.md")), b"trusted source\n")

    def test_fixed_reader_rechecks_actual_digest_on_every_read(self) -> None:
        """同一 inode 在读取前被改变后，重新核对真实字节而不沿用旧 hash 成功。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        target = self._published() / "payload/docs/guide.md"
        target.chmod(0o600)
        target.write_bytes(b"changed source\n")
        target.chmod(0o400)
        with self.assertRaises(ResourceContractError):
            reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md"))
        with self.assertRaises((OSError, ResourceContractError)):
            self._store.pin(self._snapshot)

    def test_fixed_reader_rejects_directory_replacement_even_if_file_inode_is_original(self) -> None:
        """中间目录替换无法只凭最终文件同 inode 绕过固定路径观察。"""
        self._store.install(self._incoming, "first", self._snapshot)
        reader = self._store.pin(self._snapshot)
        payload = self._published() / "payload"
        payload.chmod(0o700)
        original = payload / "docs"
        old = self._parent / "old-docs"
        original.chmod(0o700)
        original.rename(old)
        original.mkdir(mode=0o700)
        old.chmod(0o700)
        (old / "guide.md").rename(original / "guide.md")
        original.chmod(0o500)
        payload.chmod(0o500)
        with self.assertRaisesRegex(OSError, "目录 inode"):
            reader.read_file(ResourceKey("guide"), ResourcePath("docs/guide.md"))
