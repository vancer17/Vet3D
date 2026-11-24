# 文件信息：L2-01 环境要求、原资源关联与观察派生的高价值契约测试。
# 作用：覆盖版本解释、依赖闭包、未知声明、失败与有限观察复用边界。
# 边界：本文件替身只验证机械协议，不证明真实解释器、设备或隔离可用。
"""从公共入口检查环境事实不会被资源声明或部署配置替代。"""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import cast
import unittest

from vet3d.operations import (
    EnvironmentCheckService, EnvironmentObservation, EnvironmentProbe, EnvironmentReport,
    ProbeError, ProbeFailure, ProbeLimits, RequirementStatus,
)
from vet3d.resources import (
    DocumentResource, InterpreterRequirement, ResourceContractError, ResourceDescription,
    ResourceKey, ResourceMetadata, ResourcePath, ResourceReference, ScriptResource, fingerprint_bytes,
)


def _description(
    key: str = "scripts.first", *, version: str = "3.14", runtime: str = "Python",
    dependencies: tuple[str, ...] = (), resources: tuple[str, ...] = (),
) -> ResourceDescription:
    """构造不执行任何脚本的原资源声明。

    :param key: 当前资源逻辑键。
    :param version: 原版本声明文本。
    :param runtime: 原运行环境名称。
    :param dependencies: 解释器依赖要求。
    :param resources: 同快照的资源依赖键。
    :returns: 仅用于契约测试的固定资源描述。
    """
    path = ResourcePath("probe.py")
    definition = ScriptResource(
        ResourceKey(key), path, (path,), tuple(ResourceKey(item) for item in resources),
        ResourceMetadata(
            "环境契约夹具", "Vet3D 测试源", "无文件输入", "无文件输出", "不覆盖", "无执行",
            "独立实现", "首期闭环", "仅机械协议，不证明真实环境",
        ),
        InterpreterRequirement(runtime, version, dependencies),
    )
    return ResourceDescription(ResourceReference(fingerprint_bytes(b"contract snapshot"), definition.key), definition)


def _observation() -> EnvironmentObservation:
    """提供明确为替身的 CPU 与版本观察。

    :returns: 仅用于机械协议核对的结构化观察。
    """
    return EnvironmentObservation((3, 14, 6), None, ("sqlite3",), True, "Linux", "x86_64", "/synthetic/python")


class _Probe(EnvironmentProbe):
    """记录探针调用，允许逐测试提供成功、具体失败或取消。"""

    def __init__(self, result: EnvironmentObservation | BaseException) -> None:
        """固定本测试的回包，不实现真实进程行为。

        :param result: 唯一观察或要传播的原异常。
        """
        self.result = result
        self.calls: list[str] = []

    async def observe(self, runtime: str) -> EnvironmentObservation:
        """记录原运行环境名称并返回本测试的机械回包。

        :param runtime: 消费者原样传来的运行环境名称。
        :returns: 测试明确提供的观察。
        :raises BaseException: 测试明确指定的错误或取消。
        """
        self.calls.append(runtime)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class EnvironmentContractTests(unittest.IsolatedAsyncioTestCase):
    """核对资源身份与事实派生，不以一致性测试维护重复状态。"""

    async def test_major_minor_and_exact_patch_follow_original_requirement(self) -> None:
        """两段要求允许补丁差异，三段要求严格匹配，资源原对象保持关联。"""
        probe = _Probe(_observation())
        service = EnvironmentCheckService(probe, runtime_id="opaque-runtime")
        for version, expected in (
            ("3.14", RequirementStatus.SATISFIED), ("3.14.6", RequirementStatus.SATISFIED),
            ("3.14.5", RequirementStatus.MISMATCH), ("3.13", RequirementStatus.MISMATCH),
        ):
            with self.subTest(version=version):
                resource = _description(version=version, dependencies=("sqlite3",))
                report = await service.check(resource.reference, (resource,))
                self.assertEqual(report.status, expected)
                self.assertIs(report.checks[0].resource, resource)
                self.assertIs(report.root, resource.reference)
                self.assertEqual(report.runtime_id, "opaque-runtime")
                self.assertEqual(report.observed_at.utcoffset(), timezone.utc.utcoffset(None))
                self.assertIs(report.checks[0].evidence, probe.result)

    async def test_unknown_declarations_do_not_execute_or_become_satisfied(self) -> None:
        """历史说明、非规范版本和运行环境别名均保持不可判定。"""
        probe = _Probe(_observation())
        service = EnvironmentCheckService(probe, runtime_id="opaque")
        resources = (
            _description(version="未执行"), _description(version=">=3.14"),
            _description(version="03.14"), _description(version="3.14 "),
            _description(runtime="python"), _description(dependencies=("标准库",)),
            _description(dependencies=("os; run command",)),
        )
        for resource in resources:
            with self.subTest(requirement=resource.definition):
                report = await service.check(resource.reference, (resource,))
                self.assertEqual(report.status, RequirementStatus.INDETERMINATE)
                self.assertIsNone(report.checks[0].evidence)
                self.assertTrue(report.checks[0].issues)
        self.assertEqual(probe.calls, [])

    async def test_known_dependencies_and_cpu_are_checked_from_evidence(self) -> None:
        """实际缺少已支持依赖和 CPU 自检失败返回具体不满足原因。"""
        probe = _Probe(replace(_observation(), dependencies=(), cpu_check=False))
        resource = _description(dependencies=("sqlite3",))
        report = await EnvironmentCheckService(probe, runtime_id="opaque").check(resource.reference, (resource,))
        self.assertEqual(report.status, RequirementStatus.MISMATCH)
        self.assertEqual(report.checks[0].issues, ("dependency_missing:sqlite3", "cpu_check_failed"))

    async def test_large_canonical_version_is_compared_without_integer_conversion(self) -> None:
        """合法但巨大的版本段只产生不匹配，不触发整数解析限制或额外计算。"""
        resource = _description(version="9" * 5000 + ".14")
        report = await EnvironmentCheckService(_Probe(_observation()), runtime_id="opaque").check(
            resource.reference, (resource,),
        )
        self.assertEqual(report.status, RequirementStatus.MISMATCH)
        self.assertEqual(report.checks[0].issues, ("python_version_mismatch",))

    async def test_blender_requirement_compares_embedded_python_not_program_version(self) -> None:
        """Blender 程序版本单独保留，原声明 version 明确核对内嵌 Python。"""
        probe = _Probe(replace(_observation(), blender_version=(4, 5, 16), dependencies=("bpy", "mathutils")))
        resource = _description(runtime="Blender Python", version="3.14", dependencies=("bpy",))
        report = await EnvironmentCheckService(probe, runtime_id="opaque").check(resource.reference, (resource,))
        self.assertEqual(report.status, RequirementStatus.SATISFIED)
        changed = replace(resource, definition=replace(
            cast(ScriptResource, resource.definition), interpreter=InterpreterRequirement("Blender Python", "4.5", ()),
        ))
        report = await EnvironmentCheckService(probe, runtime_id="opaque").check(changed.reference, (changed,))
        self.assertEqual(report.checks[0].issues, ("python_version_mismatch",))

    async def test_probe_failure_is_not_a_version_mismatch_or_empty_success(self) -> None:
        """没有可信观察时保留适配器原因，不编造实际版本或匹配结论。"""
        resource = _description()
        probe = _Probe(ProbeError("not_configured"))
        report = await EnvironmentCheckService(probe, runtime_id="opaque").check(resource.reference, (resource,))
        self.assertEqual(report.status, RequirementStatus.INDETERMINATE)
        self.assertEqual(report.checks[0].evidence, ProbeFailure("not_configured"))
        self.assertEqual(report.checks[0].issues, ("not_configured",))

    async def test_cancel_propagates_without_creating_report(self) -> None:
        """调用取消直接传播，核对服务不把取消转换成可复用的观察。"""
        resource = _description()
        service = EnvironmentCheckService(_Probe(asyncio.CancelledError()), runtime_id="opaque")
        with self.assertRaises(asyncio.CancelledError):
            await service.check(resource.reference, (resource,))

    async def test_only_one_check_call_shares_same_runtime_observation(self) -> None:
        """同次闭包复用一次观察，重新检查必定取得新观察，不维护就绪缓存。"""
        root = _description(resources=("scripts.second",))
        second = _description("scripts.second", version="3.14.6")
        probe = _Probe(_observation())
        service = EnvironmentCheckService(probe, runtime_id="opaque")
        first_report = await service.check(root.reference, (root, second))
        self.assertEqual(probe.calls, ["Python"])
        self.assertEqual(len(first_report.checks), 2)
        probe.result = replace(_observation(), python_version=(3, 13, 0))
        second_report = await service.check(root.reference, (root, second))
        self.assertEqual(probe.calls, ["Python", "Python"])
        self.assertEqual(first_report.status, RequirementStatus.SATISFIED)
        self.assertEqual(second_report.status, RequirementStatus.MISMATCH)

    async def test_foreign_duplicate_missing_and_unreachable_resources_reject_before_probe(self) -> None:
        """身份不一致或闭包多缺资源时，在真实进程边界前拒绝。"""
        root = _description(resources=("scripts.second",))
        second = _description("scripts.second")
        foreign = replace(second, reference=replace(second.reference, snapshot=fingerprint_bytes(b"other snapshot")))
        probe = _Probe(_observation())
        service = EnvironmentCheckService(probe, runtime_id="opaque")
        for descriptions in (
            (), (root,), (second,), (root, root, second), (root, foreign),
            (root, second, _description("scripts.unrelated")),
        ):
            with self.subTest(descriptions=descriptions), self.assertRaises(ResourceContractError):
                await service.check(root.reference, descriptions)
        self.assertEqual(probe.calls, [])

    async def test_dependency_cycle_and_document_only_closure_are_not_environment_success(self) -> None:
        """单个资源记录的合法形状不能掩盖成环或没有任何运行要求的闭包。"""
        root = _description(resources=("scripts.second",))
        second = _description("scripts.second", resources=("scripts.first",))
        probe = _Probe(_observation())
        service = EnvironmentCheckService(probe, runtime_id="opaque")
        with self.assertRaises(ResourceContractError):
            await service.check(root.reference, (root, second))
        definition = root.definition
        document = ResourceDescription(root.reference, DocumentResource(
            definition.key, definition.entry, definition.files, (), definition.metadata,
        ))
        with self.assertRaises(ResourceContractError):
            await service.check(document.reference, (document,))
        self.assertEqual(probe.calls, [])

    async def test_wrong_environment_observation_is_rejected_as_untrusted_response(self) -> None:
        """普通 Python 不能用 Blender 或未知依赖的回包冒充实际观察。"""
        resource = _description()
        for observation in (
            replace(_observation(), blender_version=(4, 5, 16)),
            replace(_observation(), dependencies=("invented",)),
        ):
            with self.subTest(observation=observation):
                report = await EnvironmentCheckService(_Probe(observation), runtime_id="opaque").check(
                    resource.reference, (resource,),
                )
                self.assertEqual(report.checks[0].evidence, ProbeFailure("invalid_observation"))
                self.assertEqual(report.status, RequirementStatus.INDETERMINATE)

    async def test_mixed_unknown_and_mismatch_retains_each_gap(self) -> None:
        """汇总不满足不丢弃另一项不可判定的原证据。"""
        root = _description(version="3.13", resources=("scripts.second",))
        second = _description("scripts.second", version="unknown")
        report = await EnvironmentCheckService(_Probe(_observation()), runtime_id="opaque").check(
            root.reference, (root, second),
        )
        self.assertEqual(report.status, RequirementStatus.MISMATCH)
        self.assertEqual(report.checks[1].status, RequirementStatus.INDETERMINATE)
        self.assertEqual(report.checks[1].issues, ("unsupported_version",))

    def test_malformed_observation_and_budget_inputs_reject(self) -> None:
        """结构化协议拒绝隐式布尔、重复检查名、相对候选和零预算。"""
        for version in ((True, 14, 6), (3, -1, 6), (3, 14)):
            with self.subTest(version=version), self.assertRaises(ValueError):
                replace(_observation(), python_version=cast(tuple[int, int, int], version))
        for dependencies in (("sqlite3", "sqlite3"), ("",)):
            with self.subTest(dependencies=dependencies), self.assertRaises(ValueError):
                replace(_observation(), dependencies=dependencies)
        with self.assertRaises(ValueError):
            replace(_observation(), executable="python")
        for value in (0, -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ProbeLimits(timeout_seconds=value)

    def test_report_requires_real_checks_and_aware_utc_time(self) -> None:
        """空检查和没有时区的报告不能成为一次通过证据。"""
        resource = _description()
        with self.assertRaises(ValueError):
            EnvironmentReport(resource.reference, "opaque", datetime.now(timezone.utc), ())
        with self.assertRaises(ValueError):
            EnvironmentReport(resource.reference, "opaque", datetime.now(), ())
