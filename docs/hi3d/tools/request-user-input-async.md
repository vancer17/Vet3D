# `request_user_input_async`

## 工具名称与注册来源

`request_user_input_async` 是 Hi3D Agent 1.2.11（Windows x64）随包 Codex 0.166.0 的通用函数工具。Codex 在 `experimental_request_user_input_enabled` 生效、会话为根线程，且模型目录声明支持 `request_user_input_async` 或旧能力名 `send_user_message_async` 时注册 `RequestUserInputAsyncHandler`，使用 `DirectModelOnly` 暴露形式。描述与模型可见参数可以由模型目录覆盖。以下契约以本机模型声明和对应版本实现为准。 [注册条件](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1325-L1351) · [参数覆盖与工具定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L35-L86)

当前有效目录提供 `request_user_input_async` 时，通过模型的函数调用入口使用。`DirectModelOnly` 的注册形式要求该入口保持直接可见，Code Mode 的 `tools` 嵌套目录按各工具的暴露形式筛选。 [Code Mode 工具路由](exec.md#嵌套路由与结果交付)

## 暴露给 LLM 的描述

以下为本机两个 rollout 的 `additional_tools` 中一致的 `description` 原文。

```text
Ask the user one or more questions during ongoing work. Use this tool only to request missing information, preferences, constraints, clarification, or approval. The tool returns immediately without ending the turn or waiting for a reply; any reply arrives asynchronously as a new user message. Keep questions concise, self-contained, and easy to understand, using a level of detail appropriate to the user and task. The UI always allows a free-text answer, including when suggested options are provided. A preselected option is not submitted automatically.
```

## 参数与结果

| 参数 | 必填性与约束 |
| --- | --- |
| `questions` | 必填数组。至少一题，按展示顺序提供。当前模型可见 schema 无 `maxItems`。 |
| `questions[].title` | 必填字符串。包含用户作答所需的上下文。处理器拒绝空字符串及纯空白。 |
| `questions[].options` | 可选字符串数组。提供时至少一项，处理器拒绝空字符串及纯空白选项。描述要求把推荐项放在首位，客户端提供自由作答。省略时为仅自由填写的问题。 |

本机模型可见 schema 在顶层及题目层声明 `additionalProperties: false`，工具声明为 `strict: false`。上游处理器和题目类型对未知字段实施拒绝，并检查空题组、空白标题和空选项。参数没有问题 ID。 [处理器与校验](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L29-L85) · [题目类型](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/protocol/src/items.rs#L144-L149)

成功时，处理器先发布一项 `AgentMessage` 的开始和完成事件，再返回函数文本 `{"accepted":true}`。消息项的 `id` 是原函数 `call_id`，带 `delivery: Async` 和原有结构化 `questions`，同时保留由题目和选项拼成的文本。工具回包确认问题消息项已经发出。按声明，用户回答在收到后作为新用户消息进入对话，第一项预选也需要用户提交。调用方依据后续用户消息核对答案；已发布的问题与原调用可用消息项 `id` 对账。公开参数没有等待、查询、撤销或跨进程恢复句柄。Hi3D 桌面端对后续回复的关联及恢复仍待实测。 [消息项与成功回包](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L131-L147) · [上游行为测试](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/tests/suite/request_user_input_async.rs#L447-L620)

非函数负载、解析错误或内容校验失败时，处理器返回函数错误。空题组、空白标题和空选项各有具体错误，均发生在发出消息事件之前。 [错误分支](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L93-L129)

## 实现伪代码

**根据 Codex 处理器重建。** 问题通过所有检查后发布异步消息项。处理器在同次调用返回提交回执，用户答复沿客户端消息路径进入对话。

```text
handle_request_user_input_async(call):
    require_function_payload(call)
    questions = parse_and_require_nonempty_questions(call.arguments)
    require_nonblank_titles_and_options(questions)
    message = agent_message(
        id=call.call_id,
        text=render_titles_and_choices(questions),
        phase="final_answer",
        delivery="async",
        questions=questions,
    )
    await emit_item_started(call.turn, message)
    await emit_item_completed(call.turn, message)
    return successful_text('{"accepted":true}')
```

## 调用示例与核查依据

**根据已核查 schema 重建的参数示例。** 请求报告显示单位的偏好。

```json
{
  "questions": [
    {
      "title": "温度报告采用哪种单位？",
      "options": ["摄氏度", "华氏度"]
    }
  ]
}
```

**按已核查实现重建的即时成功文本负载。** 用户的实际答复随后作为独立消息提交。

```json
{"accepted":true}
```

- **版本固定证据。** 本机 `codex-package.json` 标记 `0.166.0` 和 `x86_64-pc-windows-msvc`。`bin/codex.exe` SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。可在该可执行文件零基字节 `291904783` 找到与会话声明逐字一致的描述，工具名存在于偏移 `292670060`。官方 `rust-v0.166.0` 发布对应固定提交 `6ff1e1ca3b30fc8b914720681fcf5fe62e95f856`。 [本机包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json>) · [官方发行版](https://github.com/openai/codex/releases/tag/rust-v0.166.0)
- **模型声明与实际样本。** 两份 rollout 第 2 行的 `additional_tools` 均含 `functions.request_user_input_async`，未发现该名称的实际调用项或应答。消息发布和即时回包可用固定源码与其测试复核。Hi3D 桌面实际的问题展示、用户答复和回连行为尚缺生产样本。 [活跃会话声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>) · [归档会话声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl:2>) · [上游测试](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/tests/suite/request_user_input_async.rs#L447-L620)
