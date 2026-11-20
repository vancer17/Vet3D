# `request_user_input`

## 工具名称与注册来源

`request_user_input` 是 Hi3D Agent 1.2.11（Windows x64）随包 Codex 0.166.0 的通用函数工具。Codex 在 `experimental_request_user_input_enabled` 生效时注册 `RequestUserInputHandler`，使用 `DirectModelOnly` 暴露形式。处理器限制为根线程，并校验当前模式是否在可用列表内。本机模型声明的可用模式是 Plan。固定版本的 App Server 测试另覆盖启用了 `default_mode_request_user_input` 的 Default 模式配置。 [注册来源](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1316-L1323) · [模式校验](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input.rs#L53-L87) · [App Server 测试](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/app-server/tests/suite/v2/request_user_input.rs#L48-L98)

当前有效目录提供 `request_user_input` 时，通过模型的函数调用入口使用。`DirectModelOnly` 的注册形式要求该入口保持直接可见，Code Mode 的 `tools` 嵌套目录按各工具的暴露形式筛选。 [Code Mode 工具路由](exec.md#嵌套路由与结果交付)

## 暴露给 LLM 的描述

以下为本机两个 rollout 的 `additional_tools` 中一致的 `description` 原文。

```text
Request user input for one to three short questions and wait for the response. This tool is only available in Plan mode.
```

## 参数与结果

| 参数 | 必填性与约束 |
| --- | --- |
| `questions` | 必填数组，无默认值。描述建议优先一题，最多三题。 |
| `questions[].id` · `header` · `question` | 均为必填字符串。`id` 用于映射答案，描述建议使用 `snake_case`。`header` 是显示用短标题，描述要求不超过 12 字符。`question` 描述要求为一个完整句子。 |
| `questions[].options` | 必填数组，每题至少提供一个实际选项。模型可见描述要求 2–3 个互斥选项，把推荐项放在首位并给其 `label` 加 `(Recommended)` 后缀。客户端可提供自由填写项。 |
| `questions[].options[].label` · `description` | 均为必填字符串。描述要求标签 1–5 个词，并用一句话解释影响或取舍。 |

模型可见 schema 在顶层和各对象层声明 `additionalProperties: false`、工具声明为 `strict: false`。问题和选项的数量建议、命名及长度说明写在描述中。已核实的参数归一化检查每题 `options` 非空，并为每题置 `is_other = true`。 [参数 schema 与归一化](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_spec.rs#L16-L120)

在 Plan 模式，请求带 `isBlocking: true`，`autoResolutionMs` 未设置。App Server 以 `item/tool/requestUserInput` 向宿主发请求，将原工具 `call_id` 作为 `itemId`，关联 `threadId` 和 `turnId`。宿主使用同一个 RPC 请求 ID 回应，Codex 返回成功的函数文本结果。文本为序列化的 `{ "answers": { "<questionId>": { "answers": ["答案"] } } }`。该形状由 `RequestUserInputResponse` 定义。宿主应答和 `serverRequest/resolved` 通知可用于复核该次请求。 [请求往返测试](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/app-server/tests/suite/v2/request_user_input.rs#L125-L173) · [响应类型](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/protocol/src/request_user_input.rs)

错误分支包括非函数负载、非根线程、模式不可用、JSON 参数解析失败和某题缺少非空选项。等待被取消时，处理器返回取消错误。处理器会等待原调用的回应，当前模型可见 schema 未提供独立查询参数或重启后恢复参数。启用 `GuardianApproval` 时，处理器可把收到的非空答案写入已验证上下文记录。 [处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input.rs#L53-L141)

## 实现伪代码

**根据 Codex 处理器及 App Server 往返测试重建。** 校验发生在发起原问题之前。应答由宿主交回同一个待处理 RPC，并完成原函数调用。

```text
handle_request_user_input(call):
    require_function_payload(call)
    require_root_thread(call)
    require_available_mode(call.mode)
    questions = parse_questions(call.arguments)
    for question in questions:
        require_nonempty_options(question)
        question.is_other = true

    response = await request_user_input(
        thread_id=call.thread_id,
        turn_id=call.turn_id,
        item_id=call.call_id,
        questions=questions,
        is_blocking=(call.mode == "Plan"),
        auto_resolution_ms=None,
    )
    if response is cancelled:
        return tool_error("cancelled before receiving a response")
    return successful_text(json_serialize(response))
```

## 调用示例与核查依据

**根据已核查 schema 重建的参数示例。** 在允许的模式下询问报告篇幅。

```json
{
  "questions": [
    {
      "id": "report_length",
      "header": "Length",
      "question": "报告采用哪种篇幅？",
      "options": [
        {"label": "Brief (Recommended)", "description": "只保留要点。"},
        {"label": "Detailed", "description": "加入背景和检查细节。"}
      ]
    }
  ]
}
```

**根据响应类型重建的成功文本负载。** 此处用题目 ID 定位用户实际提交的选项。

```json
{"answers":{"report_length":{"answers":["Brief (Recommended)"]}}}
```

- **版本固定证据。** 本机 `codex-package.json` 标记 `0.166.0` 和 `x86_64-pc-windows-msvc`。`bin/codex.exe` SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。描述模板的固定前缀起于该可执行文件的零基字节 `291844794`，模式名由 Codex 运行时填入。官方 `rust-v0.166.0` 发布对应固定提交 `6ff1e1ca3b30fc8b914720681fcf5fe62e95f856`。 [本机包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json>) · [官方发行版](https://github.com/openai/codex/releases/tag/rust-v0.166.0) · [描述模板](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/request_user_input_spec.rs#L123-L141)
- **模型声明与实际样本。** 两份 rollout 第 2 行的 `additional_tools` 均含 `functions.request_user_input`，未发现该名称的实际调用项或应答。安装包 Runtime 中 `item/tool/requestUserInput` 字符串位于零基字节 `2107523`。桌面 ASAR 成员 `out/renderer/assets/index-CDPCug_K.js` 的 `ER` 在成员零基字节 `1085130` 识别同名请求。当前生产样本未覆盖屏幕实际展示、应答或恢复。 [活跃会话声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>) · [归档会话声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl:2>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
