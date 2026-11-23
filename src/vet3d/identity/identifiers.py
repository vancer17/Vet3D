# 文件信息：L0-02 的业务身份值类型。
# 作用：用完整 UUID4 和具体类型区分各业务对象，提供唯一的文本解析入口。
# 边界：不生成身份、不读取环境、不编码名称、路径、时间排序或部署能力。
"""维护不携带业务状态的不可变身份。"""

from dataclasses import dataclass
from typing import Self, final
from uuid import UUID


@dataclass(frozen=True, slots=True)
class _Identifier:
    """复用身份值的构造校验，不作为业务参数的公共基类。

    :param value: 调用边界提供的完整 UUID4。
    """

    value: UUID

    def __post_init__(self) -> None:
        """拒绝非 UUID 或非第四版值，保证具体身份的基础表示。

        :raises TypeError: 输入不是 UUID 对象。
        :raises ValueError: 输入不是 UUID4。
        """
        if type(self.value) is not UUID:
            raise TypeError("身份值必须是 UUID 对象")
        if self.value.version != 4:
            raise ValueError("业务身份必须使用完整 UUID4")

    @classmethod
    def parse(cls, value: str) -> Self:
        """从规范文本还原同类身份，不猜测类别或修正来路内容。

        :param value: 小写、带连字符的完整 UUID4 文本。
        :returns: 保持原 UUID 的具体身份对象。
        :raises TypeError: 输入不是字符串。
        :raises ValueError: 文本不是规范 UUID4。
        """
        if not isinstance(value, str):
            raise TypeError("身份文本必须是字符串")
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("身份文本必须使用小写且带连字符的规范形式")
        return cls(parsed)


@final
@dataclass(frozen=True, slots=True)
class WorkspaceId(_Identifier):
    """标识业务数据归属范围，不表示目录或当前界面选择。

    :param value: 工作区的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class TaskId(_Identifier):
    """标识一次业务目标，不等于传输请求或聊天会话。

    :param value: 业务任务的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class SessionId(_Identifier):
    """标识任务可选的执行上下文，不绑定具体 Agent SDK。

    :param value: 会话的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class TurnId(_Identifier):
    """标识会话内的受控处理轮次，不等于单次模型采样。

    :param value: 轮次的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class JobId(_Identifier):
    """标识任务内的具体执行意图，不采用供应商任务编号。

    :param value: 本地作业的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class AttemptId(_Identifier):
    """标识作业的一次执行尝试，原尝试续查沿用此身份。

    :param value: 执行尝试的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class ArtifactId(_Identifier):
    """标识原件或派生件，不以文件名、位置或摘要代替身份。

    :param value: 素材或产物的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class ModelFamilyId(_Identifier):
    """标识模型家族，不从显示名称推导身份或派生关系。

    :param value: 模型家族的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class ModelVersionId(_Identifier):
    """标识确切模型版本，不表达最新、发布或质量状态。

    :param value: 模型版本的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class EvidenceId(_Identifier):
    """标识一份观察证据，不把证据存在视为质量合格。

    :param value: 证据的 UUID4。
    """


@final
@dataclass(frozen=True, slots=True)
class AcceptanceId(_Identifier):
    """标识一次验收记录，不携带验收结论。

    :param value: 验收记录的 UUID4。
    """
