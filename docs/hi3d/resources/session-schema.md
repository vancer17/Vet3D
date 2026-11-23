# `session_schema.py` 包外会话文档

## 资源名称、来源与模型可见性

该 Python 模块随 Hi3D Agent 1.2.11（Windows x64）的 `.dependency-run-tools` 交付，构建来源为 `tools/run-tools/scripts/session_schema.py`。它维护 `pcg.session.v1` 字典。模型可通过受管依赖文档获知能力，由调用方决定何时读取、写盘或加入模型上下文。已核实模块函数与引用文档，未发现独立 CLI 或同名 LLM Tool 注册。以下是模块 docstring 原文。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/session_schema.py) · [安装包受管依赖说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>)

```text
Package-external agent session document. Never write this file into a skill pack.
```

## 参数与结果

模块运行于普通 Python。以下函数接受显式会话对象，通常就地更新并返回同一对象。读取及持久化会话由调用方负责。

| 函数或分组 | 输入与结果 |
| --- | --- |
| `new_session`、`validate_session` | 创建要求 `entry` 和 `task_id`，默认 `route='main'`、`checkpoint=None`、`status='running'`，并初始化列表和流状态。校验要求固定 schema、非空 `task_id`、`entry` 与 `route`、规定的列表及合法状态。状态支持 `running`、`waiting_choice`、`completed`、`failed`、`interrupted`。缺省的 `refs`、`popup_reasons`、`injected`、`stream`、`confirmations` 会原地补齐。 |
| `append_artifact`、`apply_tool_result` | 必须给出产物路径，槽位键 `task/output` 成对。无槽位时按路径找对应记录。新项记 `add`，同槽更新记 `sync` 并保留历史。可选 `href`、`digest`、`tool`、`at`。会拒绝带常见签名标记或脚本协议的 `href`。`apply_tool_result` 检查结果是字典后遍历 `artifacts`，短结果 schema 和 `status` 均不参与回填。隔离夹具已确认，合法的 `failed` 结果也能登记其部分产物。会话检查点、提交选择、完成状态及产物验收由调用方处理。 |
| `mark_purged`、`purge_under_root` | 记录 `purge` 并保留最后一次路径。清理入口要求 `targets` 列表和 `task_root`，遇到 `retain='keep'` 或判定越界时抛出错误。成功时返回实际调用 `unlink()` 移除的路径。 |
| `pending_inject`、`mark_injected`、`clear_injected` | 用计划加载路径和当前列表求差集，登记经校验且未重复的路径，在新窗口清空记录。文件读入和上下文注入发生在调用方。 |
| `mark_stream` | 输入 `idle`、`in_flight`、`incomplete` 或 `settled`，可附响应 ID 和原因。流不完整且会话正在运行时改为 `interrupted`，保留已有记录供调用方恢复。 |
| `mark_popup_reason`、`asked_popup_reasons` 及 `hi3d_*` 辅助函数 | 弹窗原因按检查点与原因去重。Hi3D 辅助函数保存参数选择、等待阶段及一次或会话同意，提供消费和撤销标记，远端提交和用户授权仍由宿主处理。 |

格式或状态不合规通常抛 `ValueError`。产物路径和摘要字段在这个模块中按数据字段处理，实际内容及 SHA-256 须由消费者核实。逐项回填或删除中途失败时，可能保留此前内存更新与删除结果。

## 执行与权限

普通校验与状态记录在内存中执行。`purge_under_root` 调用 `unlink()`，依赖当前用户和执行环境的文件权限。绝对输入分支解析真实路径，相对输入分支拼接后做词法范围检查。隔离夹具用 `../outside-fixture.txt` 指向任务根之外、同一临时目录内的兄弟文件。归档模块通过检查并删除了该夹具文件。使用时由调用方确认最终真实路径边界，文件系统删除错误传播给调用方。宿主用本地执行入口调用此模块时，适用当前命令的权限和前置 Hook。 [本地执行权限与 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 中性示例与核查依据

**Python 导入示例。** 在已能从归档 `scripts/` 导入模块的解释器运行。此例只更新内存。

```python
from session_schema import append_artifact, mark_injected, new_session, pending_inject

session = new_session("demo", task_id="demo-01", checkpoint="prepare")
append_artifact(session, path="exports/preview.png", task="review", output="preview")
mark_injected(session, "references/format.md")
assert pending_inject(session, ["references/format.md", "references/qa.md"]) == [
    "references/qa.md"
]
```

发行索引还记录同源同摘要的 `taubin-smooth/scripts/session_schema.py`。已静态核对原件中的结构校验、记录更新和各类辅助函数，并用归档模块实测内存示例、失败结果回填与上述路径边界。真实宿主的清理前路径预检、部分产物验收、持久化时机和上下文续接仍需对应轨迹复核。 [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
