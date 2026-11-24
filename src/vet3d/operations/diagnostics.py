# 文件信息：L1-05 运维诊断的有限读取契约与部署预算。
# 作用：保留既有业务身份关联，交付保留窗口中的事件及丢失、损坏信息。
# 边界：诊断不授予访问权限，不是执行账本、业务验收或发布事实。
"""定义诊断消费者的只读端口，不依赖日志框架、路径或存储实现。"""

from dataclasses import dataclass
from typing import Protocol

from vet3d.identity import ArtifactId, AttemptId, TaskId, TaskIdentity, WorkspaceId


@dataclass(frozen=True, slots=True)
class DiagnosticLimits:
    """保存唯一的诊断存储和队列预算；总存储上限由轮转数量派生。

    :param max_record_bytes: 一条完整 JSONL 记录含换行的字节上限。
    :param max_file_bytes: 单个活动或归档文件的字节上限。
    :param archive_count: 保留的归档文件数量，不含活动文件。
    :param queue_capacity: 待写记录及读取请求共享的有限排队数量。
    """

    max_record_bytes: int = 16384
    max_file_bytes: int = 8388608
    archive_count: int = 3
    queue_capacity: int = 512

    def __post_init__(self) -> None:
        """拒绝布尔预算及无法容纳单条记录的文件布局。

        :raises TypeError: 限额不是非布尔整数。
        :raises ValueError: 限额为非正数或文件不能容纳记录。
        """
        for value in (self.max_record_bytes, self.max_file_bytes, self.archive_count, self.queue_capacity):
            if type(value) is not int:
                raise TypeError("诊断限额必须为非布尔整数")
            if value <= 0:
                raise ValueError("诊断限额必须为正数")
        if self.max_record_bytes < 1024 or self.max_file_bytes < self.max_record_bytes:
            raise ValueError("单条诊断至少需要 1024 字节，且不能大于文件预算")


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    """表示一次已存储的有界事件，不反向建立业务关联。

    :param timestamp: 事件记录的 UTC 时间文本。
    :param runtime_id: 不可解析的本次宿主运行关联字符串。
    :param level: Python 日志严重程度名称。
    :param message: 有界消息及必要异常堆栈，不包含配置对象转储。
    :param workspace_id: 生产者实际掌握的工作区身份，可为空。
    :param task_id: 生产者实际掌握的任务身份，可为空。
    :param attempt_id: 已知尝试身份，可为空，不由消息文本推断。
    :param artifact_id: 已知产物身份，可为空，不由路径推断。
    """

    timestamp: str
    runtime_id: str
    level: str
    message: str
    workspace_id: WorkspaceId | None = None
    task_id: TaskId | None = None
    attempt_id: AttemptId | None = None
    artifact_id: ArtifactId | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticStatus:
    """交付当前进程观察到的诊断损失，不表示任务状态。

    :param dropped_records: 队列满、编码或写入失败导致未保存的记录数。
    :param write_error: 首次写入、输出或关闭故障的有限说明；没有观察到时为空。
    """

    dropped_records: int
    write_error: str | None


@dataclass(frozen=True, slots=True)
class DiagnosticRead:
    """返回有限保留窗口，空结果不能证明历史中从未发生某事件。

    :param records: 按文件内写入顺序排列的最近匹配事件。
    :param truncated: 匹配数量超过本次请求上限。
    :param malformed_records: 已扫描窗口内不完整或不符合当前记录契约的行数。
    :param status: 读取时当前进程的诊断输出观察。
    """

    records: tuple[DiagnosticRecord, ...]
    truncated: bool
    malformed_records: int
    status: DiagnosticStatus


class DiagnosticReader(Protocol):
    """供可信宿主读取诊断的替换边界；调用前授权属于接入层。"""

    async def read_workspace(self, workspace_id: WorkspaceId, *, limit: int = 100) -> DiagnosticRead:
        """读取指定工作区在当前保留窗口中的最近事件。

        :param workspace_id: 已由调用方授权的具体工作区。
        :param limit: 返回记录上限，范围为一至一千。
        :returns: 有界事件及损失信息，不补造业务状态。
        """
        ...

    async def read_task(self, task: TaskIdentity, *, limit: int = 100) -> DiagnosticRead:
        """同时按任务和工作区过滤，不仅凭知道任务 ID 放宽范围。

        :param task: 已有权威任务身份及所属工作区。
        :param limit: 返回记录上限，范围为一至一千。
        :returns: 同时满足两个身份的有界事件及损失信息。
        """
        ...
