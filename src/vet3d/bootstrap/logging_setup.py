# 文件信息：有限演示命令的控制台日志初始化位置。
# 固定短事件默认可见；单记录有界、无队列和日志文件，写入错误不静默吞掉。
# 持久诊断由 L1-05 单独装配；本入口不得替换仍在运行的诊断所有者。
"""配置独立的 Vet3D 控制台日志，不修改根 logger。"""

import logging
import sys
from typing import TextIO

from .diagnostics import is_diagnostics_active

_MAX_RECORD_CHARS = 4096


class _BoundedFormatter(logging.Formatter):
    """限制输出记录体积，同时保留关联前缀和异常末尾。"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化单条记录并限制最终字符数，不转储请求正文。

        :param record: 业务或调用边界产生的日志记录。
        :returns: 最多四千零九十六个字符的可见记录。
        """
        rendered = super().format(record)
        if len(rendered) <= _MAX_RECORD_CHARS:
            return rendered
        marker = "\n[日志已截断]\n"
        tail = 1024
        head = _MAX_RECORD_CHARS - len(marker) - tail
        return rendered[:head] + marker + rendered[-tail:]


class _StderrHandler(logging.Handler):
    """让控制台输出失败成为可观察异常，避免静默丢弃关键记录。"""

    def __init__(self, stream: TextIO) -> None:
        """固定由 Bootstrap 提供的输出流，不创建日志文件。

        :param stream: 当前宿主的标准错误输出流。
        """
        super().__init__()
        self._stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        """输出并刷新一条记录，写入失败直接交给宿主处理。

        :param record: 本次需要交付的关键记录。
        :raises OSError: 控制台日志无法格式化或写入时抛出。
        """
        self._stream.write(self.format(record) + "\n")
        self._stream.flush()


def configure_logging() -> None:
    """初始化或替换本宿主拥有的处理器，避免重复装配导致重复输出。

    :returns: 无返回值；后续关键事件输出到当前 stderr。
    :raises RuntimeError: 已有持久诊断所有者，不能移除其处理器。
    """
    if is_diagnostics_active():
        raise RuntimeError("持久诊断仍在运行，不能替换其日志处理器")
    logger = logging.getLogger("vet3d")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    handler = _StderrHandler(sys.stderr)
    handler.setFormatter(_BoundedFormatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
