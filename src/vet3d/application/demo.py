# 文件信息：L0-01 演示用例及其唯一输入、输出和依赖端口。
# 本模块只验证装配与调用契约，不表示照片处理、模型生成或业务验收能力。
# 环境、日志初始化、超时策略和具体适配器由宿主装配边界负责。
"""定义无外部副作用的短文本回显用例。"""

from dataclasses import dataclass
from typing import Protocol

_MAX_TEXT_LENGTH = 256


class InvalidDemoRequest(ValueError):
    """表示进入演示依赖之前发现的请求契约错误。"""


class InvalidDemoReply(RuntimeError):
    """表示依赖返回值未满足演示回显契约。"""


@dataclass(frozen=True, slots=True)
class DemoRequest:
    """承载单次演示输入，不包含部署事实或正式任务身份。

    :param text: 保持原样传递的短文本，由应用服务校验有效性。
    """

    text: str


@dataclass(frozen=True, slots=True)
class DemoReply:
    """承载依赖返回的演示文本，不表达模型或质量验收状态。

    :param text: 应与本次输入完全一致的短文本。
    """

    text: str


class DemoPort(Protocol):
    """由演示应用拥有的替换端口，只约束一次异步回显。"""

    async def execute(self, request: DemoRequest) -> DemoReply:
        """处理已经过应用校验的演示请求。

        :param request: 本次不可变输入。
        :returns: 对应输入的回显结果，仍由应用核对。
        """
        ...


def _valid_text(value: object) -> bool:
    """核对演示链路允许的文本边界，不修改原始内容。

    :param value: 请求或依赖回包中的待核对值。
    :returns: 值为一至二百五十六个字符、非全空白且可编码为 UTF-8 时为真。
    """
    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_TEXT_LENGTH:
        return False
    if not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


class DemoService:
    """通过注入端口执行演示用例，不创建具体适配器或全局状态。"""

    def __init__(self, port: DemoPort) -> None:
        """固定本服务使用的依赖，实现选择由装配方负责。

        :param port: 必需的演示能力端口。
        :raises TypeError: 装配未提供依赖时抛出。
        """
        if port is None:
            raise TypeError("演示依赖不能为空")
        self._port = port

    async def execute(self, request: DemoRequest) -> DemoReply:
        """校验输入、调用依赖并核对本次回显结果。

        :param request: 单次演示输入，不携带宿主运行配置。
        :returns: 与输入文本完全一致的有效回显。
        :raises InvalidDemoRequest: 输入结构或文本不符合契约。
        :raises InvalidDemoReply: 依赖回包结构、文本或对应关系不符合契约。
        """
        if not isinstance(request, DemoRequest) or not _valid_text(request.text):
            raise InvalidDemoRequest("需要一至二百五十六个字符的非空白 UTF-8 文本")
        reply = await self._port.execute(request)
        if (
            not isinstance(reply, DemoReply)
            or not _valid_text(reply.text)
            or reply.text != request.text
        ):
            raise InvalidDemoReply("演示回包必须完整保留本次输入文本")
        return reply
