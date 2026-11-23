# 文件信息：L1-03 固定资源快照的消费方读取端口。
# 作用：允许消费者读取声明与经过核对的文件字节，不泄露主机路径。
# 边界：不安装资源、不执行脚本，不定义会话持久绑定或业务可用性。
"""声明由 Bootstrap 注入的同步资源读取边界。"""

from typing import Protocol

from .records import ResourceDescription, ResourceKey, ResourcePath


class ResourceReader(Protocol):
    """读取实例固定的快照；具体适配器负责真实文件核对及限额。"""

    def describe(self, key: ResourceKey) -> ResourceDescription | None:
        """从实例固定的清单取得确切声明，不执行 I/O 或证明当前文件可用。

        :param key: 当前固定快照内的逻辑资源键。
        :returns: 关联固定快照的描述；仅未声明时为空。
        """
        ...

    def read_file(self, key: ResourceKey, path: ResourcePath) -> bytes:
        """读取该资源明确声明的文件并核对预期字节，不执行其内容。

        :param key: 当前固定快照内的资源键。
        :param path: 必须属于该资源直接文件声明的路径。
        :returns: 与清单预期指纹相符的实际文件字节。
        :raises ResourceContractError: 资源或文件未声明，或实际内容不符。
        :raises OSError: 文件缺失、访问失败或无法完成读取。
        """
        ...
