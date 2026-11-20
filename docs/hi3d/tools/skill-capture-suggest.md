# `skill_capture_suggest`

## 工具名称与注册来源

模型可见名称为 `skill_capture_suggest`。核查版本为 Windows x64 版 Hi3D Agent 1.2.11。Hi3D Runtime 将 `UL` 中的定义经 `Vg` 合入创建对话线程时的动态工具列表。Runtime 使用调用上下文的 `threadId` 和 `turnId` 关联候选。

## 暴露给 LLM 的描述

下文是注册时的 `description` 原文。

```text
Record a reusable completed workflow suggestion. Host decides whether to display it after this turn completes. Never claim the card is displayed.
```

## 参数与结果

| 参数 | 必填 | 约束 |
| --- | --- | --- |
| `title` | 是 | 1–80 字符的字符串。 |
| `summary` | 是 | 1–400 字符的字符串，概括可复用流程。 |
| `reason` | 是 | 1–400 字符的字符串，说明复用理由。 |
| `steps` | 否 | 2–4 个字符串。每项去掉首尾空白后需为 1–24 字符。省略时不创建步骤列表。 |

Runtime 拒绝额外字段。`threadId` 与 `turnId` 取自工具调用上下文。参数无默认值。

成功返回 `success: true`，其 `contentItems` 中的 `inputText` 含 JSON 负载 `{"recorded":true}`。候选暂存在 Runtime 内存。同轮多次提交有效候选时保留第一条，每次均可得到相同的回执。参数校验失败或线程未注册时返回 `success: false`，负载为 `{"error":"Invalid capture suggestion"}`。

回执确认本轮已有候选进入待处理记录。轮次结束时，Runtime 移除这条暂存记录。发布要求轮次已完成、捕获功能启用、当前线程的 Runtime 工具版本至少为 1，且该线程没有已有建议、Skill 创建记录或草稿。符合条件时，宿主保存 `threadId`、`turnId`、候选内容、`state: "shown"` 及时间戳，并通过 `skills/captureEvaluated` 报告 `outcome: "shown"`。如果发布条件满足，近期已完成轮次有产物记录但本轮没有候选，评估事件可报告 `outcome: "gate-missed"`。卡片实际渲染仍需桌面端核查。

## 实现伪代码

**根据 Runtime 控制流重建的伪代码。** 提交和轮末评估使用同一对话与轮次的组合标识。评估只处理状态为 `completed` 的轮次，使用最近 32 条已评估轮次记录去重。未发布的候选依赖当前 Runtime 进程的内存。已发布的候选可由宿主通过 `skills/captureSuggestions` 按 `threadId` 读取，并通过 `skills/resolveSuggestion` 以原 `threadId` 与 `turnId` 接受或关闭。找不到对应建议时，宿主返回 `DRAFT_NOT_FOUND`。

```python
def skill_capture_suggest(call):
    candidate = parse_suggestion(call.arguments)
    if candidate is None or not registered_thread(call.thread_id):
        return tool_result(False, {"error": "Invalid capture suggestion"})

    key = (call.thread_id, call.turn_id)
    pending.setdefault(key, candidate)
    return tool_result(True, {"recorded": True})


def evaluate_when_turn_ends(thread_id, turn_id, status):
    key = (thread_id, turn_id)
    candidate = pending.pop(key, None)
    if status != "completed" or recently_evaluated(key):
        return

    record_completed_and_evaluated(key)
    event = None
    if capture_allowed(thread_id):
        if candidate is not None:
            save_suggestion_in_thread_state(key, candidate, state="shown")
            event = "shown"
        elif has_recent_completed_artifact(thread_id):
            event = "gate-missed"

    persist_thread_state(thread_id)
    if event is not None:
        emit_capture_evaluated(key, outcome=event)
```

## 中性调用示例与核查依据

**根据已核实的参数约束构造的示例。** 调用参数记录可复用的资产命名检查流程。

```json
{
  "title": "检查资产命名",
  "summary": "校验目录中的文件名并输出问题清单。",
  "reason": "规则和检查步骤可在其他目录复用。",
  "steps": ["列出目标文件", "校验命名规则", "汇总异常"]
}
```

- 安装包证据位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs`，SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。零基 UTF-8 字节 `2142157` 为注册表 `UL`，`2142482` 为本工具名及描述，`2141775` 为入参 schema `Yu`，`2671153` 为合并表 `Vg`。执行和轮末发布见 `handleRuntimeDynamicTool` 及捕获控制器 `Eg` 的 `suggest`、`complete` 和 `allowed`。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [1.2.11 归档](../upstream/1.2.11/README.md)
- **样本实际调用。** 安装包注册原文与留存会话的模型可见目录一致。该会话的两个不同轮次分别调用本工具，均收到 `{"recorded":true}`。持久记录的 `suggestion.turnId` 对应第一轮，状态为 `shown`。第二轮也在该线程的已评估记录中。回执、宿主持久状态和卡片画面具有各自的证据，桌面渲染与用户交互仍待实测。 [第一次调用与回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:504>) · [第二次调用与回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:953>) · [线程持久记录](<D:/download/.sparc3d-runtime/environments/prod/skill-capture/threads.json>)
