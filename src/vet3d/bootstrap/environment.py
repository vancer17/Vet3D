# 文件信息：L2-01 固定资源与有限环境观察的装配入口。
# 作用：沿原快照收集依赖声明，向检查服务注入受信本地探针。
# 边界：不执行资源脚本，不登记作业，不把环境结果变成业务资格。
"""把资源宿主、部署候选和环境检查显式连接，保持业务层不读取配置。"""

import logging

from vet3d.adapters import LocalEnvironmentProbe
from vet3d.operations import EnvironmentCheckService, EnvironmentReport, RequirementStatus
from vet3d.resources import ResourceContractError, ResourceDescription, ResourceKey, ResourceReference

from .resources import PinnedResources, ResourceRuntime
from .settings import Settings

_LOGGER = logging.getLogger("vet3d")


def _collect(pinned: PinnedResources, root: ResourceReference) -> tuple[ResourceDescription, ...]:
    """沿固定声明收集根资源的精确依赖闭包，不读取或运行脚本字节。

    :param pinned: 已核对安装快照的只读资源实例。
    :param root: 可信调用方明确指定的原快照及资源键。
    :returns: 根在前、按声明顺序遍历并去重的原描述。
    :raises ResourceContractError: 缺失声明或回包不是原快照。
    """
    found: dict[ResourceKey, ResourceDescription] = {}
    pending = [root.key]
    while pending:
        key = pending.pop()
        if key in found:
            continue
        description = pinned.describe(key)
        if description is None or description.reference.snapshot != root.snapshot:
            raise ResourceContractError("环境检查需要原固定快照中的完整资源依赖声明")
        found[key] = description
        pending.extend(reversed(description.definition.dependencies))
    return tuple(found.values())


class EnvironmentRuntime:
    """拥有本进程的真实探针，不维护跨检查缓存或持久就绪记录。"""

    def __init__(self, settings: Settings, resources: ResourceRuntime, *, runtime_id: str) -> None:
        """从已冻结的部署配置装配实际适配器和消费方。

        :param settings: 仅在装配边界消费的唯一环境配置。
        :param resources: 已成功打开的固定资源宿主。
        :param runtime_id: 诊断所有者提供的不可解析运行关联。
        """
        self._resources = resources
        self._probe = LocalEnvironmentProbe(
            {entry.runtime: entry.path for entry in settings.interpreters}, limits=settings.environment_probe,
        )
        self._service = EnvironmentCheckService(self._probe, runtime_id=runtime_id)

    async def check(self, reference: ResourceReference) -> EnvironmentReport:
        """核对指定资源的解释器要求，每次取得新的实际环境观察。

        :param reference: 原资源身份，不能用 latest 或宿主路径替代。
        :returns: 原资源闭包关联的观察与单向派生结论。
        :raises ResourceContractError: 资源未安装、原快照不符或声明闭包无效。
        """
        if type(reference) is not ResourceReference:
            raise TypeError("环境检查必须使用 ResourceReference")
        _LOGGER.info("environment_check_started snapshot=%s key=%s", reference.snapshot.sha256, reference.key.value)
        pinned = await self._resources.pin(reference.snapshot)
        result = await self._service.check(reference, _collect(pinned, reference))
        _LOGGER.log(
            logging.INFO if result.status is RequirementStatus.SATISFIED else logging.WARNING,
            "environment_check_completed snapshot=%s key=%s status=%s",
            reference.snapshot.sha256, reference.key.value, result.status.value,
        )
        return result

    async def aclose(self) -> None:
        """停止新探针并排空原进程；失败不伪造资源已经释放。"""
        await self._probe.aclose()
