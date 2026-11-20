---
name: run-tools
description: "为各原子能力和工作流提供显式输出路径、阶段 CLI、耗时记录、恢复统计、包外会话产物留痕、本地预算心跳杀进程与心跳弹窗分类、load 注入去重、流中断续跑，以及对话产物 @name 引用。"
---

# 执行记录工具

为各原子能力和工作流提供显式输出路径、阶段 CLI、耗时记录和恢复统计的通用运行工具。

## 输入与完成结果

- 输入：显式任务/阶段/尝试标识、输出根目录及真实时间或上下文管理器。
- 输出：timing.py 的 StageRecorder / record_external_stage 写任务目录；path_safety、config_runtime、stage_cli 提供路径和调用适配；profiles 保存不同既有记录格式的适配；[本地运行核心](references/local-runtime.md) 提供内容校验、阶段事件和中断子进程清理；[预算与心跳](references/budget-run.md) 为无界本地 CPU 提供墙钟上限、心跳 JSON 与超时杀进程；[session_schema.py](scripts/session_schema.py) / [tool_result.py](scripts/tool_result.py) 约束包外会话、产物留痕、load 注入去重、流中断续跑与短工具回写；[artifact_refs.py](scripts/artifact_refs.py) 为会话产物打 `@name` 对话别名并解析进后续指令。

## 调用与边界

纯 Python，输入路径不得指向凭据。计时规范唯一维护于 references/stage-records.md；存储格式不同的 profile 不直接混用。无网络、无模型生成，日志不写回包。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

多输入/输出根预检与显式环境的单次子进程执行见 [本地运行核心](references/local-runtime.md)；日志捕获和流式输出接口分别保持自己的失败类型，阶段图由工作流提供。本地可能无产物的长 CPU 必须走 [预算与心跳](references/budget-run.md)；心跳只分类 `timeout` / `stall` / `exhausting`，全部决策时刻由宿主 `waiting_choice` 弹窗，不自动续跑。

宿主提供账号工具时，先读 [Desktop Runtime 执行约定](references/desktop-runtime.md)，据实际能力选择生成、登记、预览与恢复边界。

对话里要把「上次的裁切 / 上一轮 GLB」当成下一句指令的输入时，读 [对话产物引用](references/artifact-refs.md)：在任务目录 session 上标记 `@name`，后续文本用 `rewrite` 换成路径。这不是独立 skill；画板槽位仍由 `append_artifact` 维护。

本地软件编辑任务需要版本探测、输入保护和成功产物复用时，读取 [显式编辑任务](references/hi3d-edit-job.md)。

<!-- managed-by: sparc3d-runtime -->
