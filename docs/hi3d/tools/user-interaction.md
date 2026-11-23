# `user_interaction`

## 工具名称与注册来源

模型可见名称为 `user_interaction`。核查版本为 Windows x64 版 Hi3D Agent 1.2.11，随包 Codex 0.166.0。Hi3D Runtime 通过 `Vg` 将 `nj` 中的定义合入 `thread/start` 的 `dynamicTools`。Runtime 接收工具调用，桌面宿主根据 `interaction/request` 展示面板，面板响应返回原调用。

## 暴露给 LLM 的描述

以下是 Runtime 工具定义中的 `description` 原文。

```text
Collect user input, preferences, or authorization through a host interaction panel for any task, not just Hi3D or skills. A panel appears only when this tool is called; ordinary chat cannot create one. If arguments are rejected, correct them and retry. Never claim to be waiting for a panel that was not created.
```

此描述与 1.2.11 原包解码后的定义逐字一致。描述长 312 个字符，正文 UTF-8 字节的 SHA-256 为 `2b78cc71e79c8ea6cf6ecb9b80c7ea072d59e183e5b9ecbba5b22ce76a0585b4`，排除围栏及两端换行。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

### 工具调用与宿主协议

`user_interaction` 是模型可调用的工具。`interaction/request` 是 Runtime 向桌面宿主发送面板参数的方法，由 `serverRequest` 携带 `requestId`，宿主以相同 ID 的 `serverResponse` 返回。Runtime 内部也可以为其他工具发起同类面板请求，并复用这里的请求 schema 和响应校验器。显式调用 `user_interaction` 时，校验后的 `status`、`source`、`answers` 和可选 `decision` 返回给原调用。由其他工具发起的请求仍属于该工具，返回格式由发起分支决定。

其他工具的 `waiting_choice` 由发起方解释。以 Hi3D 生成参数面板为例，Runtime 把原生成参数和面板参数一起保存到该 `requestId`，由生成分支接收用户选择并处理续接。显式调用本工具时，确认或取消的结果按 `requestId` 关联回原调用。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

随包 `pcg-view` 的决策视图也使用 `waiting_choice`。Python 视图代码把会话状态和 `routes.yaml` 中的 `choices_example`、`confirm_required` 投影为显示数据。触发本工具面板须有显式调用，其他工具的面板须由相应 Runtime 分支发起请求。在已核查的 Runtime 和桌面 ASAR 内未找到通用接线，把上述路线声明直接转换成 `interaction/request`。 [决策视图实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-pcg-view/scripts/view_ir.py:66>)

渲染器按 `requestId` 去重，仅为当前线程中仍待答复的面板发送结果。Electron 主进程检查 IPC 发送窗口，再经 Runtime 网关转发该 ID 和答复或错误。Runtime 使用该 ID 找到原调用，并按原面板参数再次校验答复。

## 参数与结果

| 参数 | 必填与取值 | 默认值或限制 |
| --- | --- | --- |
| `kind` | 必填。`input`、`preference` 或 `confirmation`。 | 依类型校验问题、消息及超时。 |
| `title` | 必填。面板标题。 | 去掉首尾空白后长 1–2000。 |
| `message` | 可选。`confirmation` 必填，用于说明具体动作。 | 与 `title` 使用相同的字符串校验。 |
| `questions` | 可省略。`input`、`preference` 各需 1–3 题，`confirmation` 需为空。 | 省略时为 `[]`。每题 `id` 和 `question` 必填，`id` 去掉首尾空白后长 1–80，面板内唯一。`question` 使用与 `title` 相同的校验。 |
| `questions[].options` | `input` 可省略，`preference` 每题至少一项。每项有必填 `label` 和可选 `description`。 | 省略时为 `[]`，每题至多 6 项，`label` 在题内唯一。两字段使用与 `title` 相同的校验。 |
| `questions[].defaultAnswer` | 仅 `preference` 可用，且每题必填。 | 使用与 `title` 相同的校验，并须与该题一个选项的 `label` 完全相同。 |
| `timeoutSeconds` | 可选，仅 `preference` 可用，范围为 60–600 的整数。 | Runtime 保留省略值，核查版本的桌面面板初始化为 60 秒。面板只在窗口可见、有焦点且用户尚未编辑时倒计时。 |
| `skillCredit` | 可选对象。`skill` 接受 `hi3d-model-gpt-animation`、`image-to-assembly` 或 `mask-design`，`credits` 为正整数。 | 积分提示相关元数据。通用工具校验后将其随面板请求转发。 |

顶层、题目、选项和 `skillCredit` 都使用严格对象校验。`threadId`、`turnId` 和 `callId` 来自工具调用上下文，Runtime 将这些字段附到宿主请求上。

偏好面板按 `requestId` 在草稿中保留剩余时间。渲染器每 250 毫秒检查一次计时状态，暂停时重置计时基点，单次累计最多 1000 毫秒。用户开始编辑后，面板保留答复机会，停止自动采用默认值。

结果包含 `status`、`source`、`answers`，确认型结果另带 `decision`。以下是 Runtime 接受的组合。

| 情况 | `status` / `source` | `answers` 和 `decision` |
| --- | --- | --- |
| 用户回答输入或偏好 | `answered` / `user` | `answers` 的键与原题 ID 完全一致。每项去掉首尾空白后须非空，支持自定义值。省略 `decision`。 |
| 偏好采用超时默认值 | `defaulted` / `assistant_default` | 每个题目的答案都等于其 `defaultAnswer`。省略 `decision`。用户主动点击采用推荐项则仍属于 `answered` / `user`。 |
| 用户接受确认 | `answered` / `user` | `answers: {}`，`decision: "accept"`。 |
| 用户拒绝确认 | `declined` / `user` | `answers: {}`，`decision: "decline"`。 |
| 用户取消 | `cancelled` / `user` | `answers: {}`，省略 `decision`。 |

有效结果由 Runtime 封装成 `success: true` 和一个包含 JSON 文本的 `contentItems` 项，取消或拒绝也以结构化结果返回。参数无效时返回 `success: false`，文本负载包含 `error`、`panelDisplayed: false`、字段级 `issues` 和 `next_action`。调用上下文无效或未关联工作区时返回 `success: false`，负载含 `error` 和 `panelDisplayed: false`。宿主显式返回错误时清理待处理记录并将错误转给原调用。宿主响应形状无效或与原题目不符时只写日志，继续保留该请求。

副作用是创建一条宿主请求并交给桌面尝试展示，记录本次交互，完成时清理关联。参数校验通过后才发出请求，面板实际出现仍取决于宿主处理。确认型请求需要本人同意时，须匹配 `status: "answered"`、`source: "user"` 和 `decision: "accept"`。需要本人提交具体回答时，核对前两项和相应答案。偏好超时的 `assistant_default` 只交付选项默认值。外层 `success: true` 也用于有效的拒绝、取消及偏好超时结果。确认结果表达用户的决定，后续动作由调用方执行。

等待期间由原调用维持关联。若通过 Code Mode 调用后返回运行中的执行句柄，按原句柄续读该执行单元。`requestId` 是宿主协议关联号，工具参数未提供按该号码查询或跨进程恢复的动作。轮次结束或进程失去关联后，先核对是否已有有效终态，仍需新交互时以当前有效上下文重新收集。 [Code Mode 续查](exec.md#用-wait-续查代码执行单元) · [面板关联与清理](#实现伪代码)

## 调用示例

**根据工具 schema 构造的示例。** 请求填写项目名称。

```json
{
  "kind": "input",
  "title": "填写项目名称",
  "questions": [
    {
      "id": "project_name",
      "question": "这个项目使用什么名称？"
    }
  ]
}
```

**根据响应校验规则构造的结果负载示例。** 用户提交项目名称后，以下对象出现在 `contentItems` 的 JSON 文本中。

```json
{
  "status": "answered",
  "source": "user",
  "answers": {"project_name": "示例项目"}
}
```

**根据偏好型 schema 重建的示例。** 请求选择报告格式。`defaultAnswer` 与第一个选项的标签完全一致，自动采用默认选项时返回 `defaulted` 和 `assistant_default`。

```json
{
  "kind": "preference",
  "title": "选择报告格式",
  "questions": [
    {
      "id": "report_format",
      "question": "报告采用哪种格式？",
      "options": [{"label": "摘要"}, {"label": "详细版"}],
      "defaultAnswer": "摘要"
    }
  ],
  "timeoutSeconds": 60
}
```

**根据确认型 schema 和响应校验规则重建的示例。** 请求用户确认一个明确动作。`questions` 可省略。

```json
{
  "kind": "confirmation",
  "title": "确认复制报告",
  "message": "是否将报告副本写入当前项目的归档目录？"
}
```

用户接受时，工具负载形如以下示例。

```json
{
  "status": "answered",
  "source": "user",
  "answers": {},
  "decision": "accept"
}
```

## 实现伪代码

**根据 Runtime 控制流重建的伪代码。** 以下覆盖显式工具调用。`request_id` 由 Runtime 生成，关联原始工具调用 ID 与经校验的面板参数。面板等待期间保留这一记录。有效响应完成该调用。整轮中断或收到 `turn/completed` 时，Runtime 按 `threadId` 和适用的 `turnId` 清理尚待答复的请求，并发送 `serverRequest/resolved`，渲染器据此移除面板和草稿。该关联表位于运行进程内，工具契约未提供独立的查询或跨进程恢复动作。

```text
handle_user_interaction(call):
    if not valid_call_context(call) or not workspace_registered(call.thread_id):
        return tool_error(panel_displayed=false)

    args = validate_interaction_arguments(call.arguments)
    if args.invalid:
        return tool_error(panel_displayed=false, issues=args.issues, next_action="correct arguments")

    request_id = allocate_request_id()
    pending[request_id] = {call, args}
    send_host_request(
        request_id,
        method="interaction/request",
        params=with_call_context(args, call),
    )

handle_host_response(response):
    entry = pending.get(response.request_id)
    if entry is missing:
        log_unmatched_response(response.request_id)
        return
    if response.has_error:
        remove_pending_and_reply_error(entry, response.error)
        return

    result = validate_response_for_kind(entry.args, response.result)
    if result.invalid:
        log_invalid_response_and_keep_pending(response.request_id)
        return
    remove_pending_and_reply(entry, result)

cancel_interactions(thread_id, turn_id):
    for entry in pending_requests_for(thread_id, turn_id):
        remove_pending_and_reply(entry, {status: "cancelled", source: "user", answers: {}})
        notify_host_request_resolved(entry.request_id)
```

## 核查依据

- 核查使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/` 下的原安装包备份。`runtime/manifest.json` 标记版本 `1.2.11`。`runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。模型描述的定义在 `var nj=[`（UTF-8 零基字节偏移 `2179064`）。参数和处理见 `qx`、`dg`、`Wx`、`fg`、`Vg`、`handleServerResponse` 与 `cancelInteractions`。
- `app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`interaction/request` 在 `out/main/index.js` 成员内的首个 UTF-8 零基字节偏移为 `86598`，在 `out/renderer/assets/index-CDPCug_K.js` 成员内为 `215060`。主进程校验和应答转发见前一成员第 20、29 行。渲染器的答复校验、草稿与计时、待处理请求和面板控件见后一成员第 58、145、148、624 行。 [原始 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- 原始描述与安装包定义及两份本机 rollout 第 2 行 `exec.description` 的嵌套声明逐字一致。宿主协议复用见 `handleRuntimeDynamicTool` 和 `handleServerResponse` 对同一 `serverRequestIds` 关联表及 `dg`、`fg` 校验器的使用。生成参数面板对已解析生成参数的条件检查和 `hi3dArgs` 保存位于 Runtime 零基字节 `3195400` 至 `3196661` 的分派片段。
- **离线复核与待实测。** 使用合成时间戳核对了 `d0e` 的计时累计、暂停和单次上限。窗口焦点、答复转发及清理链路来自安装包静态核查。显式偏好超时、用户主动选择与取消的端到端应答，以及各发起方的实际面板触发仍待桌面验证。
- **实际调用。** 活跃样本第 222 行记录 `exec` 内的工具调用，第 224 行交回 `cell_id`，第 228 行以同一 ID 调用 `wait`，第 230 行仍返回运行中。第 241 行的宿主 `DynamicToolCall` 终态为 `failed`（`success: false`），未产生结构化回答。此后未见对该执行单元的续查，也未确认面板实际展示或失败终态已交付给模型。`hi3d_api` 内部偏好面板的样本回执来自该生成工具的续调协议。 [显式调用](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:222>) · [调用终态](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:241>) · [生成工具的参数选择](hi3d-api.md#参数选择与请求规划)
