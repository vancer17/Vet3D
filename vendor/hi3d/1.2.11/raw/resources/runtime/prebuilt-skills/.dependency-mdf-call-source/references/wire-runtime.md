# 通信运行时

默认 HTTP 模式通过中控 `/generate_model` 执行 MDF3 `generic-forward`，由中控处理 TaskQueue/TCP；调用端不启动回调服务。`--transport sdk` 才使用完整 SDK `ServiceInvokeSession` 并要求 worker 能回连当前主机。

## 本地依赖与 codec

先运行 `scripts/check_runtime.py`，数组契约添加 `--require-numpy`；SDK 模式添加 `--transport sdk`。检查只做本地 BinaryFile/可选 NumPy 往返，不读取认证、配置或访问网络。HTTP 文件型入口支持 Python 3.7+，使用标准库 HTTP；SDK 模式使用完整 SDK 所支持的 Python 并需要 PyYAML。当前测试解释器为 Python 3.9+。

`mdf_runtime.load_codec` 优先使用已安装且可导入的 `mdf3.mdf_tool`。没有 MDF3 安装时，HTTP 模式加载包内 `scripts/_wire/mdf3/`，其 BinaryFile/dumps/loads 为 [官方 MDF3 3.3.0](http://172.31.0.3:8099/TangPei/mdf3/-/tree/28f0983a99f40cb73a226611c3a04ca55812d4f5) 的协议子集，保留 `mdf3.mdf_tool.BinaryFile` pickle 身份及 protocol 4，不包含 worker、配置或凭据。子集位于单独搜索路径，避免覆盖已安装的完整 SDK。已有 SDK 却缺少其导入依赖时报告运行时失败，不静默替换已安装实现。

SDK 模式不加载通信子集；目标项目需提供完整官方 SDK 及其依赖。源码目录为 `mdf3/` 时把父目录加入 `PYTHONPATH`，不要安装来源不明的同名包。已在进程内加载子集后，不能据此声称拥有完整 SDK；切换到完整 SDK 使用配置正确的新进程。SDK API 来源和回连前提见 [SDK 适配器](mdf3-service-invoke.md)。

## 网络与大小边界

HTTP 地址、SDK 配置及预检方式见 [部署与诊断](deployment-and-probes.md)。HTTP 标准库传输不使用环境代理、重定向或自动重试；响应体默认上限 512 MiB，可通过 Python `post_json(max_response_bytes=...)` 为已知部署设置更小上限。pickle/base64/JSON 会增加峰值内存，不以 GLB 原文件大小估算总内存。

只解码已确认可信的 MDF 部署响应；pickle 不是任意第三方数据解析格式。两种传输保留相同 BinaryFile/NumPy 契约与单次提交语义，不明结果不得自动换通道重提。

## 独立验证

按入口打包约定在仓库外物化完整分发目录，运行 unittest 和代表性 CLI。HTTP 集成测试用仅本机可达的 HTTP 网关与真实 wire 编解码，在 `python -S` 下验证无 SDK/第三方依赖、大于 2 MiB 的文件保存、原 trace 和已有目录拒绝。完整 SDK 可用时另测真实 `ServiceInvokeSession` 的 loopback TCP 往返与模拟队列；缺 SDK 明确跳过。测试不提交线上业务，loopback 成功不证明跨网络回连。
