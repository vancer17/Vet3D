# 文件信息：L0-01 应用契约测试。
# 作用：验证唯一请求／结果、边界拒绝及显式依赖替换。
# 范围：仅验证无外部副作用的演示协议，不代表模型或业务质量验收。
"""通过公开包入口验证演示应用的可观察行为。"""

import unittest
from typing import cast

from vet3d.application import (
    DemoPort,
    DemoReply,
    DemoRequest,
    DemoService,
    InvalidDemoReply,
    InvalidDemoRequest,
)
from vet3d.bootstrap import assemble_application, build_demo_application


class RecordingPort(DemoPort):
    """记录接收请求的机械替身，供装配与拒绝边界检查。"""

    def __init__(self) -> None:
        """初始化本次测试独有的调用记录。"""
        self.requests: list[DemoRequest] = []

    async def execute(self, request: DemoRequest) -> DemoReply:
        """记录已经通过应用校验的请求并原样返回。

        :param request: 应用交付的演示请求。
        :returns: 同文本的演示回执。
        """
        self.requests.append(request)
        return DemoReply(text=request.text)


class InvalidReplyPort(DemoPort):
    """故意违反输出契约的替身，用于检查真实运行时边界。"""

    def __init__(self, reply: object) -> None:
        """固定本次要注入的非法输出。

        :param reply: 故意不受静态类型保证的测试值。
        """
        self.reply = reply

    async def execute(self, request: DemoRequest) -> DemoReply:
        """把非法夹具送到应用边界，不新增另一套结果类型。

        :param request: 本轮有效请求。
        :returns: 经显式类型转换注入的非法测试值。
        """
        return cast(DemoReply, self.reply)


class DemoApplicationTests(unittest.IsolatedAsyncioTestCase):
    """验证装配替换和契约校验，不测试简单数据访问器。"""

    async def test_two_assemblies_preserve_the_same_request(self) -> None:
        """两种依赖实现保持同一应用输入输出，消费方无需修改。"""
        request = DemoRequest(text="  五向照片 🐕\n")
        fake = RecordingPort()
        applications = (build_demo_application(), assemble_application(port=fake))
        for application in applications:
            with self.subTest(application=application):
                self.assertEqual(await application.execute(request), DemoReply(text=request.text))
        self.assertEqual(fake.requests, [request])

    async def test_service_accepts_the_documented_upper_boundary(self) -> None:
        """直接调用应用服务可处理长度上界，不依赖宿主或网络。"""
        request = DemoRequest(text="猫" * 256)
        service = DemoService(RecordingPort())
        self.assertEqual(await service.execute(request), DemoReply(text=request.text))

    async def test_invalid_input_is_rejected_before_the_dependency(self) -> None:
        """拒绝空白、超限、非文本及不可编码输入，且依赖不执行。"""
        fake = RecordingPort()
        service = assemble_application(port=fake)
        invalid_texts: tuple[object, ...] = ("", " \t\n", "a" * 257, None, 3, "\ud800")
        for value in invalid_texts:
            with self.subTest(value=repr(value)):
                request = DemoRequest(text=cast(str, value))
                with self.assertRaises(InvalidDemoRequest):
                    await service.execute(request)
        with self.assertRaises(InvalidDemoRequest):
            await service.execute(cast(DemoRequest, {"text": "合法文本"}))
        self.assertEqual(fake.requests, [])

    async def test_invalid_or_mismatched_reply_cannot_become_success(self) -> None:
        """结构无效、文本无效或不属于本次请求的回执均被拒绝。"""
        request = DemoRequest(text="本次请求")
        replies: tuple[object, ...] = (
            None,
            {"text": request.text},
            DemoReply(text=""),
            DemoReply(text=" " * 4),
            DemoReply(text="x" * 257),
            DemoReply(text="\ud800"),
            DemoReply(text=cast(str, 5)),
            DemoReply(text="另一次请求"),
        )
        for reply in replies:
            with self.subTest(reply=repr(reply)):
                service = assemble_application(port=InvalidReplyPort(reply))
                with self.assertRaises(InvalidDemoReply):
                    await service.execute(request)
