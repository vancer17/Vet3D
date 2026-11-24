<!-- 文件信息：L2-01 有限环境探测的架构决定。
作用：保留选择理由及未采用方案；现行契约统一由 L2-01 实施卡维护。
边界：本决定不选择执行隔离后端、模型供应商、Agent SDK 或 BFF 协议。 -->
# ADR 0011：固定资源要求与受信环境探针

- 状态：已采纳，实施验收范围见 [L2-01](../implementation/work-items/L2-01.md)；后续通用执行及账本的职责由 [ADR 0012](0012-native-agent-runtime-integration.md)局部修订。
- 背景：L1-03 已保存描述性解释器要求，L1-05 已定位候选；两者都不能证明实际程序、内嵌 Python 或 CPU 自检成功。Vet3D 面向 BFF 的正常业务链需要可程序化消费的事实，而不是每次人工审核或部署配置定义业务能力。

采用原 `ResourceReference` 与 `InterpreterRequirement`，在 Operations 建立有限消费者语义。只有真实可替换的探针使用 Protocol，规则服务保持具体实现。观察、未取得观察的原因和原声明是事实源，结果与缺口单向派生，不增设 `ready/available/supported` 多份状态或用一致性测试维护它们。

保留 L1-03 既有描述文本而不假设其历史语法：只解释明确的规范版本与有限依赖名，其他声明不可判定。没有真实消费者要求，不加入 pip 求解器、动态 import、旧别名或多协议兼容开关。Blender 程序和内嵌 Python 是不同版本事实，原 `Blender Python` 要求约束内嵌解释器。

有限产品探针与脚本执行器分开：本项只运行产品随包的固定 CPU 自检，资源脚本与上传内容不进入进程。以标准库异步管理原句柄、总输出预算、并发准入与清理，避免过早把 L2-02 通用执行及 L2-03 账本全部引入。借鉴 Hi3D 的预算和进程组机制，但不沿用桌面弹窗、人工预算确认或在保护区外写心跳导致进程遗留的行为。

首期沿既有 Debian/Linux、CPython 3.14 和两套 Docker 装配，新增官方 Blender 4.5.16 LTS Linux x64 固定归档；SHA-256 为 `23432b064977908beb1ab4b7f32f024e7331105c875c187dce002aff84b10c11`。官方来源：[LTS](https://www.blender.org/download/lts/4-5/)、[归档与校验文件](https://download.blender.org/release/Blender4.5/)。选择 LTS 固定制品便于复现实测，不由用户素材或资源声明下载解释器；没有引入供应商网关或第三套编排。

每次检查重新取得证据，同次闭包按 runtime 共享一次观察；没有已存在的持久消费者要求，故不建设缓存有效期、巡检服务、PID 恢复库或兼容投影。SIGKILL 后不能保证裸宿主清理，该边界明确交给部署监督与后续执行设计，不用日志或新进程冒充原尝试恢复。

参考官方进程语义：[Python 3.14 异步子进程](https://docs.python.org/3.14/library/asyncio-subprocess.html)、[Blender 4.5 命令参数](https://docs.blender.org/manual/en/4.5/advanced/command_line/arguments.html)。进程组、关闭 autoexec 和现有应用容器都不等于不可信执行隔离；后续隔离部署必须重新取得对应环境证据。

2026-11-24 的 [ADR 0012](0012-native-agent-runtime-integration.md)将后续 Agent 路线收敛为成熟运行时的完整原生循环接入，不沿本项受信探针扩建通用执行内核或另一套进程账本。本 ADR 的有限自检、资源声明和已有验证继续有效；进入实际任务环境时复用检查语义并按环境变化取得证据，原生工具与反馈的选型验证由 [L2-02](../implementation/work-items/L2-02.md)维护。
