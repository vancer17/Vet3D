# 文件信息：L2-01 固定资源要求与真实环境观察的唯一运维契约。
# 作用：关联原资源快照、当前运行和有限探针证据，单向计算需求核对结果。
# 边界：不读取 Settings、不执行资源脚本，不授予业务能力、隔离资格或发布资格。
"""定义有限环境探针端口和无需 LLM 的具体需求核对服务。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Protocol

from vet3d.resources import (
    InterpreterRequirement, ResourceContractError, ResourceDescription, ResourceKey,
    ResourceReference, ScriptResource,
)


@dataclass(frozen=True, slots=True)
class ProbeLimits:
    """保存部署实例唯一的进程预算，不在每次检查中重复定义。

    :param timeout_seconds: 一次探针自开始创建进程到完成输出读取的期限。
    :param terminate_grace_seconds: 发出终止信号后的有限排空宽限。
    :param max_output_bytes: 标准输出与标准错误共同的累计字节上限。
    :param max_concurrency: 同一所有者允许同时进行的实际探针数量。
    """

    timeout_seconds: int = 30
    terminate_grace_seconds: int = 2
    max_output_bytes: int = 65536
    max_concurrency: int = 2

    def __post_init__(self) -> None:
        """拒绝布尔、非正数及隐式预算转换。

        :raises ValueError: 任一预算不是非布尔正整数。
        """
        for value in (
            self.timeout_seconds, self.terminate_grace_seconds,
            self.max_output_bytes, self.max_concurrency,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("探针预算必须为非布尔正整数")


def _text(value: str) -> None:
    """核对不可解析关联文本及有限证据文本的基本形状。

    :param value: 不做大小写转换或别名解释的原始值。
    :raises ValueError: 文本为空白、含控制字符或不能编码为 UTF-8。
    """
    if type(value) is not str or not value.strip() or any(ord(item) < 32 for item in value):
        raise ValueError("环境证据文本必须非空且不含控制字符")
    value.encode("utf-8")


def _version(value: tuple[int, int, int]) -> None:
    """核对来自实际解释器的三段版本，不接受布尔和字符串转换。

    :param value: 已解析的主、次、补丁版本。
    :raises ValueError: 版本不是三个非负整数。
    """
    if type(value) is not tuple or len(value) != 3 or any(type(item) is not int or item < 0 for item in value):
        raise ValueError("环境版本必须是三个非负整数")


@dataclass(frozen=True, slots=True)
class EnvironmentObservation:
    """保留一次固定探针的实际观察，不额外存储 ready 或可发布状态。

    :param python_version: 被探测 Python 或 Blender 内嵌 Python 的实际版本。
    :param blender_version: Blender 程序实际版本；普通 Python 探针为空。
    :param dependencies: 固定依赖检查实际成功的名称，不证明未检查的依赖。
    :param cpu_check: 固定微型 CPU 计算是否完成并得到预期值。
    :param platform: 探针进程实际报告的系统名称。
    :param machine: 探针进程实际报告的体系结构。
    :param executable: 本次实际启动的绝对候选路径，不表示其字节不可变。
    """

    python_version: tuple[int, int, int]
    blender_version: tuple[int, int, int] | None
    dependencies: tuple[str, ...]
    cpu_check: bool
    platform: str
    machine: str
    executable: str

    def __post_init__(self) -> None:
        """校验实际观察形状，运行环境与观察的关联由消费服务核对。"""
        _version(self.python_version)
        if self.blender_version is not None:
            _version(self.blender_version)
        if type(self.dependencies) is not tuple or len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("实际依赖名称必须是无重复的元组")
        for dependency in self.dependencies:
            _text(dependency)
        if type(self.cpu_check) is not bool:
            raise ValueError("CPU 检查必须是布尔观察")
        _text(self.platform)
        _text(self.machine)
        _text(self.executable)
        if not self.executable.startswith("/"):
            raise ValueError("本期 Linux 探针必须记录实际启动的绝对路径")


class ProbeError(RuntimeError):
    """表示未取得可信环境观察，不借用业务执行状态或尝试身份。"""

    def __init__(self, reason: str) -> None:
        """保存具体失败原因，不携带配置转储或任意进程输出。

        :param reason: 适配器定义的有限机器原因。
        """
        _text(reason)
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class ProbeFailure:
    """保存本次探针失败依据，不能与有效观察同时出现。

    :param reason: 原适配器报告的具体机器原因。
    """

    reason: str

    def __post_init__(self) -> None:
        """拒绝没有具体原因的失败占位。"""
        _text(self.reason)


class EnvironmentProbe(Protocol):
    """定义真实可替换的有限环境观察边界，实例固定候选和进程预算。"""

    async def observe(self, runtime: str) -> EnvironmentObservation:
        """执行产品内置的可信探针，绝不接收资源脚本或任意命令。

        :param runtime: 原 InterpreterRequirement 的精确运行环境名称。
        :returns: 实际进程完成后取得的结构化观察。
        :raises ProbeError: 未取得可信观察，具体原因保留在异常中。
        """
        ...


def supported_dependencies(runtime: str) -> tuple[str, ...] | None:
    """返回本期明确实现的检查名，未知名称不产生别名或动态导入。

    :param runtime: 原资源要求中的精确运行环境名称。
    :returns: 本期固定依赖检查名；未支持的运行环境返回空值。
    """
    if runtime == "Python":
        return ("sqlite3",)
    if runtime == "Blender Python":
        return ("bpy", "mathutils")
    return None


class RequirementStatus(StrEnum):
    """表达声明与证据的核对结论，由原事实单向计算。"""

    SATISFIED = "satisfied"  # 已检查的本期要求与实际证据一致。
    MISMATCH = "mismatch"  # 有效观察证明至少一项本期要求不满足。
    INDETERMINATE = "indeterminate"  # 声明无法解释或缺少可信观察。


def _unsupported(requirement: InterpreterRequirement) -> tuple[str, ...]:
    """识别本期无法解释的声明，不猜测历史自然语言版本或依赖。

    :param requirement: L1-03 唯一解释器要求实例。
    :returns: 无法核对的具体原因，空元组表示全部可解释。
    """
    issues: list[str] = []
    supported = supported_dependencies(requirement.runtime)
    if supported is None:
        issues.append("unsupported_runtime")
    if re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?", requirement.version) is None:
        issues.append("unsupported_version")
    for dependency in requirement.dependencies:
        if supported is None or dependency not in supported:
            issues.append(f"unsupported_dependency:{dependency}")
    return tuple(issues)


@dataclass(frozen=True, slots=True)
class ResourceEnvironmentCheck:
    """关联原资源与本次证据，核对状态和缺口始终由这些事实计算。

    :param resource: 原固定快照中的脚本描述，不复制要求、快照或资源键。
    :param evidence: 实际观察或失败原因；声明不受支持时没有执行证据。
    """

    resource: ResourceDescription
    evidence: EnvironmentObservation | ProbeFailure | None

    def __post_init__(self) -> None:
        """拒绝非脚本和与本期声明不关联的观察，避免非法组合。"""
        if type(self.resource) is not ResourceDescription or type(self.resource.definition) is not ScriptResource:
            raise ValueError("环境要求核对只关联原脚本资源")
        if self.evidence is not None and type(self.evidence) not in (EnvironmentObservation, ProbeFailure):
            raise TypeError("环境证据必须是实际观察或失败原因")
        requirement = self.resource.definition.interpreter
        if _unsupported(requirement):
            if self.evidence is not None:
                raise ValueError("无法解释的声明不能附加执行证据")
        elif self.evidence is None:
            raise ValueError("可解释声明必须记录实际观察或失败原因")
        if isinstance(self.evidence, EnvironmentObservation):
            supported = supported_dependencies(requirement.runtime)
            assert supported is not None
            if any(item not in supported for item in self.evidence.dependencies):
                raise ValueError("观察包含当前运行环境未实现的依赖检查")
            if (requirement.runtime == "Blender Python") != (self.evidence.blender_version is not None):
                raise ValueError("观察的程序类型与原运行环境要求不符")

    @property
    def issues(self) -> tuple[str, ...]:
        """从原要求和证据计算当前缺口，不读取外部环境或日志。

        :returns: 有序机器原因；空元组只说明本期固定检查满足要求。
        """
        assert isinstance(self.resource.definition, ScriptResource)
        requirement = self.resource.definition.interpreter
        unsupported = _unsupported(requirement)
        if unsupported:
            return unsupported
        if isinstance(self.evidence, ProbeFailure):
            return (self.evidence.reason,)
        assert isinstance(self.evidence, EnvironmentObservation)
        expected_parts = requirement.version.split(".")
        issues: list[str] = []
        observed_version = ".".join(str(part) for part in self.evidence.python_version[:len(expected_parts)])
        if observed_version != requirement.version:
            issues.append("python_version_mismatch")
        for dependency in requirement.dependencies:
            if dependency not in self.evidence.dependencies:
                issues.append(f"dependency_missing:{dependency}")
        if not self.evidence.cpu_check:
            issues.append("cpu_check_failed")
        return tuple(issues)

    @property
    def status(self) -> RequirementStatus:
        """计算唯一核对结论，失败和未支持声明不能产生通过。

        :returns: 由当前原始证据派生的满足、不满足或不可判定。
        """
        if not isinstance(self.evidence, EnvironmentObservation):
            return RequirementStatus.INDETERMINATE
        return RequirementStatus.MISMATCH if self.issues else RequirementStatus.SATISFIED


@dataclass(frozen=True, slots=True)
class EnvironmentReport:
    """保存单次检查的关联，不形成持久就绪缓存或执行恢复账本。

    :param root: 调用方要求检查的原固定资源引用。
    :param runtime_id: 诊断所有者提供的不可解析当前运行关联。
    :param observed_at: 本次检查结束时的 UTC 时间，不是有效期或授权凭证。
    :param checks: 依赖闭包中脚本要求的实际检查结果。
    """

    root: ResourceReference
    runtime_id: str
    observed_at: datetime
    checks: tuple[ResourceEnvironmentCheck, ...]

    def __post_init__(self) -> None:
        """拒绝空检查、混合快照及错误时间，不给无证据报告补造通过。"""
        if type(self.root) is not ResourceReference:
            raise TypeError("检查报告必须保留原资源引用")
        _text(self.runtime_id)
        if not isinstance(self.observed_at, datetime) or self.observed_at.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError("观察时间必须明确使用 UTC")
        if type(self.checks) is not tuple or not self.checks:
            raise ValueError("检查报告必须包含至少一个脚本要求")
        if any(type(item) is not ResourceEnvironmentCheck for item in self.checks):
            raise TypeError("检查结果必须使用唯一契约类型")
        if any(item.resource.reference.snapshot != self.root.snapshot for item in self.checks):
            raise ValueError("检查结果必须关联同一原始资源快照")
        if len({item.resource.reference.key for item in self.checks}) != len(self.checks):
            raise ValueError("检查报告不得重复同一资源")

    @property
    def status(self) -> RequirementStatus:
        """汇总本次检查，已知不满足优先，其次保留不可判定缺口。

        :returns: 从逐项原始证据计算的结论，不缓存副本。
        """
        statuses = {item.status for item in self.checks}
        if RequirementStatus.MISMATCH in statuses:
            return RequirementStatus.MISMATCH
        if RequirementStatus.INDETERMINATE in statuses:
            return RequirementStatus.INDETERMINATE
        return RequirementStatus.SATISFIED


def _validate_closure(root: ResourceReference, descriptions: tuple[ResourceDescription, ...]) -> None:
    """检查输入恰是同一固定快照的根可达闭包，启动进程前拒绝错误关联。

    :param root: 本次明确选择的原资源引用。
    :param descriptions: 装配入口从同一固定读取实例收集的资源描述。
    :raises ResourceContractError: 重复、跨快照、缺失、成环或包含无关资源。
    """
    if type(root) is not ResourceReference or type(descriptions) is not tuple:
        raise TypeError("环境检查需要原资源引用和冻结描述元组")
    if any(type(item) is not ResourceDescription for item in descriptions):
        raise TypeError("依赖闭包必须由原资源描述组成")
    by_key = {item.reference.key: item for item in descriptions}
    if len(by_key) != len(descriptions) or any(item.reference.snapshot != root.snapshot for item in descriptions):
        raise ResourceContractError("环境检查的资源重复或来自其他快照")
    visited: set[ResourceKey] = set()
    visiting: set[ResourceKey] = set()

    def visit(key: ResourceKey) -> None:
        """沿明确的资源依赖检查闭包，不读取入口脚本。

        :param key: 当前访问的原逻辑资源键。
        :raises ResourceContractError: 依赖缺失或形成环。
        """
        if key in visiting:
            raise ResourceContractError("环境检查的资源依赖成环")
        if key in visited:
            return
        if key not in by_key:
            raise ResourceContractError("环境检查缺少根资源或声明依赖")
        visiting.add(key)
        for dependency in by_key[key].definition.dependencies:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    visit(root.key)
    if visited != set(by_key):
        raise ResourceContractError("环境检查包含根资源不可达的其他资源")
    if not any(isinstance(item.definition, ScriptResource) for item in descriptions):
        raise ResourceContractError("资源闭包没有脚本要求，不能推断环境通过")


class EnvironmentCheckService:
    """具体实现固定资源的需求核对；只有实际探针是可替换边界。"""

    def __init__(self, probe: EnvironmentProbe, *, runtime_id: str) -> None:
        """显式接收有限探针和原运行关联，不接收配置或基础设施容器。

        :param probe: Bootstrap 注入的真实或机械协议替身。
        :param runtime_id: 当前诊断所有者已有的不可解析运行身份。
        """
        _text(runtime_id)
        self._probe = probe
        self._runtime_id = runtime_id

    async def check(
        self, root: ResourceReference, descriptions: tuple[ResourceDescription, ...],
    ) -> EnvironmentReport:
        """核对完整关联后观察环境，同一次检查共享观察，下一次重新取得证据。

        :param root: 本次固定的根资源引用。
        :param descriptions: 与根同快照且恰好覆盖可达闭包的原描述。
        :returns: 关联原资源和当前运行的有限报告；取消直接传播。
        :raises ResourceContractError: 依赖闭包或身份不正确，尚未启动探针。
        """
        _validate_closure(root, descriptions)
        observed: dict[str, EnvironmentObservation | ProbeFailure] = {}
        checks: list[ResourceEnvironmentCheck] = []
        for description in descriptions:
            if not isinstance(description.definition, ScriptResource):
                continue
            requirement = description.definition.interpreter
            if _unsupported(requirement):
                checks.append(ResourceEnvironmentCheck(description, None))
                continue
            if requirement.runtime not in observed:
                try:
                    evidence = await self._probe.observe(requirement.runtime)
                except ProbeError as error:
                    observed[requirement.runtime] = ProbeFailure(error.reason)
                else:
                    try:
                        # 回包必须与原环境类别关联；替身也不能绕过结果边界。
                        ResourceEnvironmentCheck(description, evidence)
                    except (TypeError, ValueError):
                        observed[requirement.runtime] = ProbeFailure("invalid_observation")
                    else:
                        observed[requirement.runtime] = evidence
            checks.append(ResourceEnvironmentCheck(description, observed[requirement.runtime]))
        return EnvironmentReport(root, self._runtime_id, datetime.now(timezone.utc), tuple(checks))
