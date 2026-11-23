# 文件信息：L0-01 正常骨架装配使用的演示适配器。
# 它实际执行内存回显，但不代表模型、Blender、文件存储或 BFF 已接通。
"""实现消费方拥有的演示端口。"""

from vet3d.application import DemoPort, DemoReply, DemoRequest


class DemoAdapter(DemoPort):
    """以无副作用的内存回显提供可启动的演示依赖。"""

    async def execute(self, request: DemoRequest) -> DemoReply:
        """返回同一文本，让外层应用验证调用交接。

        :param request: 应用已校验的单次输入。
        :returns: 保留原文本的演示结果。
        """
        return DemoReply(text=request.text)
