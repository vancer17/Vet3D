# 文件信息：L1-04 单资产目录的独立进程重启验证。
# 作用：在真实文件保存及目录提交后强退子进程，再通过新宿主核对事实。
# 证据边界：覆盖普通进程退出和原引用重开，不代表断电、设备故障或执行恢复。
"""用实际 SQLite 与文件字节验证已提交记录及未登记文件的不同恢复范围。"""

import asyncio
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from vet3d.artifacts import ContentFingerprint, FilePresent, FileReference
from vet3d.bootstrap import open_workspaces
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId

_CHILD = r'''
import asyncio
import hashlib
import os
from pathlib import Path
import sys
from vet3d.artifacts import ContentFingerprint, FileReference, ImportOrigin
from vet3d.bootstrap import initialize_workspaces
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId

async def main() -> None:
    """真实保存候选，在指定边界强退，不进行宿主正常关闭。"""
    root, inputs = Path(sys.argv[1]), Path(sys.argv[2])
    workspace_id = WorkspaceId.parse(sys.argv[3])
    artifact = ArtifactIdentity(ArtifactId.parse(sys.argv[4]), workspace_id)
    payload = b"L1-04 process restart fixture"
    reference = FileReference(artifact.id, ContentFingerprint(hashlib.sha256(payload).hexdigest(), len(payload)))
    runtime = await initialize_workspaces(root)
    await runtime.create(workspace_id=workspace_id, display_name="进程恢复验证")
    files = await runtime.files(workspace_id, input_root=inputs, max_file_bytes=1024)
    await files.store_new(artifact, reference, "source")
    if sys.argv[5] == "registered":
        catalog = await runtime.artifacts(workspace_id, max_file_bytes=1024)
        await catalog.register(artifact, reference, origin=ImportOrigin(artifact.id, "已知测试出处"))
    os._exit(0)

asyncio.run(main())
'''


class ArtifactRestartTests(unittest.IsolatedAsyncioTestCase):
    """重开消费者完全来自新进程之外保留的原身份，不扫描或猜测目标。"""

    def setUp(self) -> None:
        """建立独立临时输入根并保留原身份、内容引用与部署位置。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "managed"
        self.inputs = self.base / "inputs"
        self.inputs.mkdir(mode=0o700)
        self.payload = b"L1-04 process restart fixture"
        source = self.inputs / "source"
        source.write_bytes(self.payload)
        source.chmod(0o600)
        self.workspace_id = WorkspaceId(uuid4())
        self.artifact = ArtifactIdentity(ArtifactId(uuid4()), self.workspace_id)
        self.reference = FileReference(self.artifact.id, ContentFingerprint(
            hashlib.sha256(self.payload).hexdigest(), len(self.payload),
        ))

    def _exit_at(self, phase: str) -> None:
        """运行真实子进程并在完成指定副作用后强退，要求没有超时或异常。

        :param phase: 保存文件后退出，或登记提交后退出。
        """
        result = subprocess.run(
            [sys.executable, "-c", _CHILD, str(self.root), str(self.inputs),
             str(self.workspace_id.value), str(self.artifact.id.value), phase],
            capture_output=True, text=True, timeout=15, env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    async def test_committed_asset_and_origin_survive_abrupt_process_exit(self) -> None:
        """登记提交后的强退不丢失原字段，新宿主仍须独立观察真实文件。"""
        await asyncio.to_thread(self._exit_at, "registered")
        async with await open_workspaces(self.root) as runtime:
            catalog = await runtime.artifacts(self.workspace_id, max_file_bytes=1024)
            record = await catalog.resolve(self.artifact.id)
            assert record is not None
            self.assertEqual(record.artifact, self.artifact)
            self.assertEqual(record.reference, self.reference)
            origin = await catalog.get_origin(self.artifact.id)
            assert origin is not None
            self.assertEqual(origin.source_label, "已知测试出处")
            self.assertEqual(await catalog.observe(record.location), FilePresent(record.location, self.reference.content))

    async def test_saved_file_is_not_adopted_until_explicit_original_registration(self) -> None:
        """文件落盘后的强退不产生目录记录，原引用可显式核对后登记。"""
        await asyncio.to_thread(self._exit_at, "saved")
        async with await open_workspaces(self.root) as runtime:
            catalog = await runtime.artifacts(self.workspace_id, max_file_bytes=1024)
            self.assertIsNone(await catalog.resolve(self.artifact.id))
            record = await catalog.register(self.artifact, self.reference)
            self.assertEqual(record.reference, self.reference)
            self.assertEqual(await catalog.resolve(self.artifact.id), record)
