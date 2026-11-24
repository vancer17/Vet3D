# 文件信息：L1-04 真实资产目录及文件观察接入 L0-05 生成消费方的集成验证。
# 作用：通过 Bootstrap 保存、登记和观察真实字节，驱动已有生成守卫。
# 证据边界：只有生成器和执行仓储仍为替身；合成字节不证明图像或动物质量。
"""验证字节交接和生成前拒绝，不将五向标签夹具宣称为真实图片方向证据。"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from vet3d.adapters import FiveViewGenerator, FourViewGenerator, MemoryReconstructionRepository
from vet3d.application import ReconstructionRecord, ReconstructionService
from vet3d.artifacts import (
    ArtifactContractError, ContentFingerprint, FileMissing,
    FilePresent, FileReference, LocatedArtifact,
)
from vet3d.bootstrap import initialize_workspaces
from vet3d.execution import AttemptActive, AttemptSucceeded, InputInsufficient
from vet3d.identity import (
    ArtifactId, ArtifactIdentity, AttemptId, AttemptIdentity, JobId, JobIdentity,
    TaskId, TaskIdentity, WorkspaceId,
)
from vet3d.modeling import (
    GenerationPlan, PreparedView, PreparedViews, ReconstructionPort, ReconstructionRequest,
    TaskReferences, ViewDirection,
)


class RealFileGenerationTests(unittest.IsolatedAsyncioTestCase):
    """将真实存储、实际摘要检查和既有生成契约放在同一公开调用链验证。"""

    async def asyncSetUp(self) -> None:
        """真实保存五份不同字节，分别赋予五向标签但不宣称图片可解码。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name)
        self._root = parent / "managed"
        input_root = parent / "received"
        input_root.mkdir(mode=0o700)
        self._workspace_id = WorkspaceId(uuid4())
        self._task = TaskIdentity(TaskId(uuid4()), self._workspace_id)
        runtime = await initialize_workspaces(self._root)
        self.addAsyncCleanup(runtime.aclose)
        await runtime.create(workspace_id=self._workspace_id, display_name="真实文件消费方测试")
        self._files = await runtime.files(
            self._workspace_id, input_root=input_root, max_file_bytes=1024 * 1024
        )
        self._catalog = await runtime.artifacts(self._workspace_id, max_file_bytes=1024 * 1024)
        records: list[LocatedArtifact] = []
        views: list[PreparedView] = []
        for direction in ViewDirection:
            payload = f"L1-04 byte fixture for {direction.value}; not an image\n".encode("utf-8")
            input_name = f"{direction.value}.bin"
            source = input_root / input_name
            source.write_bytes(payload)
            source.chmod(0o600)
            artifact = ArtifactIdentity(ArtifactId(uuid4()), self._workspace_id)
            reference = FileReference(
                artifact.id, ContentFingerprint(hashlib.sha256(payload).hexdigest(), len(payload))
            )
            saved = await self._files.store_new(artifact, reference, input_name)
            records.append(LocatedArtifact(artifact, reference, saved.location))
            views.append(PreparedView(artifact.id, direction))
        self._records = tuple(records)
        self._prepared = PreparedViews(tuple(views), ())
        self._references = TaskReferences(
            task_id=self._task.id, subject_reference_id=self._records[0].artifact.id,
            preserve_features=("测试仅传递必保特征，不判断是否保留",),
            required_preparation_directions=frozenset(ViewDirection),
        )

    def _request(self, *, four_inputs: bool = False) -> ReconstructionRequest:
        """保留完整五向准备集，为独立尝试明确选择四图或五图计划。

        :param four_inputs: 是否只在本次计划中选择前后左右图。
        :returns: 固定原身份、准备要求和真实内容指纹的生成请求。
        """
        job = JobIdentity(JobId(uuid4()), self._task.id)
        attempt = AttemptIdentity(AttemptId(uuid4()), job.id)
        plan = GenerationPlan(tuple(
            view.artifact_id for view in self._prepared.views
            if not four_inputs or view.direction is not ViewDirection.TOP
        ))
        return ReconstructionRequest(
            task=self._task, job=job, attempt=attempt, references=self._references,
            prepared=self._prepared, plan=plan,
            files=tuple(record.reference for record in self._records),
        )

    async def _service(
        self, generator: ReconstructionPort, repository: MemoryReconstructionRepository,
        records: tuple[LocatedArtifact, ...] | None = None,
    ) -> ReconstructionService:
        """逐件完成真实目录登记，再装配既有生成服务。

        :param generator: 既有的五向或四向生成替身。
        :param repository: 当前用例的内存生成仓储。
        :param records: 可选的实际部分登记集合；未登记项仍保留磁盘文件。
        :returns: 真实文件观察已经接通的生成消费方。
        """
        for record in self._records if records is None else records:
            await self._catalog.register(record.artifact, record.reference)
        return ReconstructionService(
            task=self._task, artifacts=self._catalog, generator=generator, repository=repository
        )

    def _path(self, record: LocatedArtifact) -> Path:
        """仅为测试制造磁盘故障，从既有回执定位本例受管文件。

        :param record: 测试已经保存的文件元数据。
        :returns: 本例临时根中的实际文件路径，不作为产品调用接口。
        """
        return self._root / "workspaces" / str(self._workspace_id.value) / record.location.relative_path.value

    async def test_five_input_generation_consumes_real_matching_files(self) -> None:
        """真实字节逐项通过既有匹配守卫后，仅调用一次五向生成替身。"""
        generator = FiveViewGenerator()
        repository = MemoryReconstructionRepository()
        service = await self._service(generator, repository)
        request = self._request()
        result = await service.start(request)
        self.assertIsInstance(result, ReconstructionRecord)
        assert isinstance(result, ReconstructionRecord)
        self.assertIsInstance(result.observation, AttemptSucceeded)
        self.assertEqual(generator.submitted_requests, (request,))
        self.assertEqual(await service.read(request.attempt.id), result)

    async def test_four_input_plan_preserves_five_prepared_files(self) -> None:
        """完整五向真实文件可支持明确四图计划，顶图不被偷偷删除或提交。"""
        generator = FourViewGenerator()
        repository = MemoryReconstructionRepository()
        service = await self._service(generator, repository)
        request = self._request(four_inputs=True)
        started = await service.start(request)
        assert isinstance(started, ReconstructionRecord)
        self.assertIsInstance(started.observation, AttemptActive)
        self.assertEqual(len(generator.submitted_requests), 1)
        self.assertEqual(len(generator.submitted_requests[0].plan.input_ids), 4)
        self.assertEqual(len(generator.submitted_requests[0].prepared.views), 5)
        top = next(record for record in self._records if record.artifact.id == self._prepared.views[-1].artifact_id)
        self.assertNotIn(top.artifact.id, request.plan.input_ids)
        self.assertEqual(
            await self._files.observe(top.artifact, top.location), FilePresent(top.location, top.reference.content)
        )
        await service.query(request.attempt.id)
        completed = await service.query(request.attempt.id)
        self.assertIsInstance(completed.observation, AttemptSucceeded)

    async def test_actual_missing_file_prevents_claim_and_submission(self) -> None:
        """元数据仍在但真实文件已删除时，不登记尝试或调用生成端口。"""
        generator = FiveViewGenerator()
        repository = MemoryReconstructionRepository()
        service = await self._service(generator, repository)
        missing = self._records[0]
        self._path(missing).unlink()
        self.assertEqual(await self._files.observe(missing.artifact, missing.location), FileMissing(missing.location))
        request = self._request()
        with self.assertRaises(ArtifactContractError):
            await service.start(request)
        self.assertEqual(generator.submitted_requests, ())
        self.assertIsNone(await repository.get(request.attempt.id))

    async def test_actual_changed_hash_prevents_claim_and_submission(self) -> None:
        """同长度字节被改写后实际观察保留新摘要，旧引用不能通过生成守卫。"""
        generator = FiveViewGenerator()
        repository = MemoryReconstructionRepository()
        service = await self._service(generator, repository)
        changed = self._records[0]
        path = self._path(changed)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b"X" + original[1:])
        path.chmod(0o400)
        observation = await self._files.observe(changed.artifact, changed.location)
        assert isinstance(observation, FilePresent)
        self.assertEqual(observation.observed.byte_size, changed.reference.content.byte_size)
        self.assertNotEqual(observation.observed.sha256, changed.reference.content.sha256)
        request = self._request()
        with self.assertRaises(ArtifactContractError):
            await service.start(request)
        self.assertEqual(generator.submitted_requests, ())
        self.assertIsNone(await repository.get(request.attempt.id))

    async def test_disk_file_does_not_supply_missing_metadata(self) -> None:
        """真实文件存在仍不能替代元数据解析，不通过扫描目录伪造产品登记。"""
        omitted = self._records[0]
        self.assertEqual(
            await self._files.observe(omitted.artifact, omitted.location),
            FilePresent(omitted.location, omitted.reference.content),
        )
        generator = FiveViewGenerator()
        repository = MemoryReconstructionRepository()
        service = await self._service(generator, repository, self._records[1:])
        request = self._request()
        self.assertIsInstance(await service.start(request), InputInsufficient)
        self.assertEqual(generator.submitted_requests, ())
        self.assertIsNone(await repository.get(request.attempt.id))
