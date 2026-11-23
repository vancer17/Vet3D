# exec

## 工具名称与注册来源

`exec` 是 Hi3D Agent 1.2.11（Windows x64）随包 Codex 0.166.0 的 Code Mode 自由格式工具。本轮有效工具模式为 `CodeMode` 或 `CodeModeOnly` 时，Codex 注册 `exec` 和配套函数 `wait`。本机两份样本的工具声明记录在 `functions` 命名空间中。Codex 从本轮工具路由准备可嵌套调用的定义，实际调用仍经原工具处理器和策略。 [注册与嵌套目录生成](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1018-L1105) · [自由格式工具定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_spec.rs#L5-L25)

## 暴露给 LLM 的描述

以下为两份本机样本 `additional_tools` 记录中的完整 `exec.description`，逐字保留。Codex 根据有效工具模式、本轮可用工具、延迟发现策略、模型设置及生效的等待配置构造该字段。`CodeModeOnly` 可将当前启用工具的命名空间说明与声明附入正文，因此不同轮次或环境的目录可能变化。 [描述生成源码](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-protocol/src/description.rs#L279-L386)

````text
Run JavaScript code to orchestrate/compose tool calls
- Evaluates the provided JavaScript code in a fresh V8 isolate as an async module.
- All nested tools are available on the global `tools` object, for example `await tools.exec_command(...)`. Tool names are exposed as normalized JavaScript identifiers, for example `await tools.mcp__ologs__get_profile(...)`.
- Nested tool methods take either a string or an object as their input argument.
- Nested tools return either an object or a string, based on the description.
- Runs raw JavaScript -- no Node, no file system, no network access, no console.
- Accepts raw JavaScript source text, not JSON, quoted strings, or markdown code fences.
- You may optionally start the tool input with a first-line pragma like `// @exec: {"yield_time_ms": 10000, "max_output_tokens": 1000}`.
- `yield_time_ms` asks `exec` to yield early if the script is still running. Defaults to 30000 ms.
- `max_output_tokens` sets the token budget for direct `exec` results. Defaults to 10000 tokens.
- When the JS code is fully evaluated, the isolate's lifetime ends and unawaited promises are silently discarded.

- Global helpers:
- `exit()`: Immediately ends the current script successfully (like an early return from the top level).
- `text(value: string | number | boolean | undefined | null)`: Appends a text item. Non-string values are stringified with `JSON.stringify(...)` when possible.
- `image(imageUrlOrItem: string | { image_url: string; detail?: "auto" | "low" | "high" | "original" | null } | ImageContent, detail?: "auto" | "low" | "high" | "original" | null)`: Appends an image item. `image_url` should be a base64-encoded `data:` URL. To forward an MCP tool image, pass an individual `ImageContent` block from `result.content`, for example `image(result.content[0])`. MCP image blocks may request detail with `_meta: { "codex/imageDetail": "original" }`. When provided, the second `detail` argument overrides any detail embedded in the first argument.
- `audio(audioUrlOrItem: string | { audio_url: string } | AudioContent)`: Appends an audio item. `audio_url` should be a base64-encoded `data:` URL. To forward an MCP tool audio block, pass an individual `AudioContent` block from `result.content`, for example `audio(result.content[0])`.
- `generatedImage(result: { image_url: string; output_hint?: string })`: Appends an image-generation result and its optional output hint. HTTP(S) URLs are not supported.
- `store(key: string, value: any)`: stores a serializable value under a string key for later `exec` calls in the same session.
- `load(key: string)`: returns the stored value for a string key, or `undefined` if it is missing.
- `notify(value: string | number | boolean | undefined | null)`: immediately injects an extra `custom_tool_call_output` for the current `exec` call. Values are stringified like `text(...)`.
- `setTimeout(callback: () => void, delayMs?: number)`: schedules a callback to run later and returns a timeout id. Pending timeouts do not keep `exec` alive by themselves; await an explicit promise if you need to wait for one.
- `clearTimeout(timeoutId?: number)`: cancels a timeout created by `setTimeout`.
- `ALL_TOOLS`: metadata for the enabled nested tools as `{ name, description }` entries.
- `yield_control()`: yields the accumulated output to the model immediately while the script keeps running.

Some deferred nested tools may be omitted from this description. They are still available on the global `tools` object and listed in `ALL_TOOLS`.
To find one, filter `ALL_TOOLS` by `name` and `description`.

Tool availability can change between calls.

Shared MCP Types:
```ts
type Role = "user" | "assistant";
type MetaObject = Record<string, unknown>;
type Annotations = {
  audience?: Role[];
  priority?: number;
  lastModified?: string;
};
type Icon = {
  src: string;
  mimeType?: string;
  sizes?: string[];
  theme?: "light" | "dark";
};
type TextResourceContents = {
  uri: string;
  mimeType?: string;
  _meta?: MetaObject;
  text: string;
};
type BlobResourceContents = {
  uri: string;
  mimeType?: string;
  _meta?: MetaObject;
  blob: string;
};
type TextContent = {
  type: "text";
  text: string;
  annotations?: Annotations;
  _meta?: MetaObject;
};
type ImageContent = {
  type: "image";
  data: string;
  mimeType: string;
  annotations?: Annotations;
  _meta?: MetaObject;
};
type AudioContent = {
  type: "audio";
  data: string;
  mimeType: string;
  annotations?: Annotations;
  _meta?: MetaObject;
};
type ResourceLink = {
  icons?: Icon[];
  name: string;
  title?: string;
  uri: string;
  description?: string;
  mimeType?: string;
  annotations?: Annotations;
  size?: number;
  _meta?: MetaObject;
  type: "resource_link";
};
type EmbeddedResource = {
  type: "resource";
  resource: TextResourceContents | BlobResourceContents;
  annotations?: Annotations;
  _meta?: MetaObject;
};
type ContentBlock =
  | TextContent
  | ImageContent
  | AudioContent
  | ResourceLink
  | EmbeddedResource;
type CallToolResult<TStructured = { [key: string]: unknown }> = {
  _meta?: MetaObject;
  content: ContentBlock[];
  isError?: boolean;
  structuredContent?: TStructured;
  [key: string]: unknown;
};
```

### `apply_patch`
The `apply_patch` tool can be used to edit files. This is a FREEFORM tool, so do not wrap the patch in JSON.

exec tool declaration:
```ts
declare const tools: { apply_patch(input: string): Promise<unknown>; };
```

### `create_goal`
Create a goal only when explicitly requested by the user or system/developer instructions; do not infer goals from ordinary tasks.
Set token_budget only when an explicit token budget is requested. Fails if an unfinished goal exists; use update_goal only for status.

exec tool declaration:
```ts
declare const tools: { create_goal(args: {
  // Required. The concrete objective to start pursuing. This starts a new active goal when no goal exists or replaces the current goal when it is complete.
  objective: string;
  // Positive token budget for the new goal. Omit unless explicitly requested.
  token_budget?: number;
}): Promise<unknown>; };
```

### `exec_command`
Runs a command in a PTY, returning output or a session ID for ongoing interaction.

Windows safety rules:
- Do not compose destructive filesystem commands across shells. Do not enumerate paths in PowerShell and then pass them to `cmd /c`, batch builtins, or another shell for deletion or moving. Use one shell end-to-end, prefer native PowerShell cmdlets such as `Remove-Item` / `Move-Item` with `-LiteralPath`, and avoid string-built shell commands for file operations.
- Before any recursive delete or move on Windows, verify the resolved absolute target paths stay within the intended workspace or explicitly named target directory. Never issue a recursive delete or move against a computed path if the final target has not been checked.
- When using `Start-Process` to launch a background helper or service, pass `-WindowStyle Hidden` unless the user explicitly asked for a visible interactive window. Use visible windows only for interactive tools the user needs to see or control.

exec tool declaration:
```ts
declare const tools: { exec_command(args: {
  // Shell command to execute.
  cmd: string;
  // User-facing approval question for `require_escalated`; omit otherwise.
  justification?: string;
  // True runs the shell with -l/-i semantics; false disables them. Defaults to true.
  login?: boolean;
  // Output token budget. Defaults to 10000 tokens; larger requests may be capped by policy.
  max_output_tokens?: number;
  // Reusable approval prefix for `cmd`, only with `sandbox_permissions: "require_escalated"`; for example ["git", "pull"].
  prefix_rule?: Array<string>;
  // Per-command sandbox override. Defaults to `use_default`; use `require_escalated` for unsandboxed execution.
  sandbox_permissions?: "use_default" | "require_escalated";
  // Shell binary to launch. Defaults to the user's default shell.
  shell?: string;
  // True allocates a PTY for the command; false or omitted uses plain pipes.
  tty?: boolean;
  // Working directory for the command. Defaults to the turn cwd.
  workdir?: string;
  // Maximum time to wait before returning a session ID for a still-running command. Commands that finish sooner return immediately. For ordinary commands, omit this parameter to use the 10000 ms default. Effective range on Windows is 10000-30000 ms.
  yield_time_ms?: number;
}): Promise<{
  // Chunk identifier included when the response reports one.
  chunk_id?: string;
  // Process exit code when the command finished during this call.
  exit_code?: number;
  // Approximate token count before output truncation.
  original_token_count?: number;
  // Command output text, possibly truncated.
  output: string;
  // Session identifier to pass to write_stdin when the process is still running.
  session_id?: number;
  // Elapsed wall time spent waiting for output in seconds.
  wall_time_seconds: number;
}>; };
```

### `get_goal`
Get the current goal for this thread, including status, budgets, token and elapsed-time usage, and remaining token budget.

exec tool declaration:
```ts
declare const tools: { get_goal(args: {}): Promise<unknown>; };
```

### `hi3d_api`
Use the Runtime-managed Hi3D entry point for text-to-image, single- or multi-image editing, image-to-3D, texturing, relief, part splitting, and multicolor processing. On desktop, prefer generate_image or generate_3d to validate, submit, wait, and download with the current account in one call; a separate dryRun is optional. Runtime opens missing parameter panels. On parameters_selected, call hi3d_api with next_call; on cancelled, stop. For a single GLB generated in the formal generate_3d call, provide registerName and tag4 (null is valid) to register it automatically after download; provide workflowNodeId to assign the model to its responsible workflow node. Registration does not complete the node; report completion through workflow_report after all work for that node is finished. For every image or 3D generation, set targetName to the concise target/object name only, preserving the chosen language and casing; do not include words such as image generation, model generation, progress, or a percentage. Reuse the exact targetName when the same object continues from image generation to 3D or resumes from a saved job. Every newly generated file name must start with hi3d-. For pending work, keep the same job and resume with the same generate_3d arguments or wait/download without submitting again. If a query reports an error, explain its specific reason in the user's language and end the current turn; do not repeat query/wait or resubmit unless the user explicitly asks. Keep numeric error codes in the job diagnostics; show them only if requested. The client status card shows generation progress; do not repeat unchanged status in chat while waiting. Every local path must remain inside the current workspace.

exec tool declaration:
```ts
declare const tools: { hi3d_api(args: {
  // Image and 3D actions use the desktop account proxy. Legacy action names remain available for compatibility.
  action: "defaults" | "balance" | "generate_image" | "generate_3d" | "text_to_image" | "image_to_image" | "submit" | "adopt" | "query" | "wait" | "download" | "retry_quota" | "retry";
  aspectRatio?: "1:1" | "16:9" | "9:16" | "4:3" | "3:4";
  // Validate parameters without authentication, network access, or charges. The current API does not provide price estimates.
  dryRun?: boolean;
  // Exact registered model file for retry_quota; Runtime verifies its source.
  fileName?: string;
  // Image-to-image mode: edit uses the first image as primary; reference uses every image as a reference
  imageMode?: "edit" | "reference";
  // Model name or alias passed to the bundled Hi3D tool. Read the installed Hi3D skill for model selection and defaults. Native request.modelName takes precedence.
  imageModel?: string;
  imageSlots?: Array<number>;
  // Public HTTPS image URL for relief generation
  imageUrl?: string;
  // Image paths inside the workspace. The current API accepts at most four. For 3D, pair with views. For image editing, use the first as the primary image or all as references.
  images?: Array<string>;
  interval?: number;
  // Durable job-record path inside the workspace, such as hi3d/model.json
  jobPath?: string;
  // generate_3d defaults to model and accepts only the first four values. Required for submit and adopt.
  kind?: "model" | "relief" | "split" | "multicolor" | "text-to-image" | "image-edit";
  // Model path inside the workspace
  mesh?: string;
  // Public HTTPS model URL
  meshUrl?: string;
  // Output directory for generate_3d or download; use a new directory under exports/
  outputDir?: string;
  // New PNG path inside the workspace, such as exports/hi3d-concept.png. The file name must start with hi3d- and existing files are not overwritten.
  outputPath?: string;
  // Natural-language prompt for image generation. Read the installed Hi3D skill for the prompt budget; the bundled tool validates the final request.
  prompt?: string;
  // Optional model family name for generate_3d. Together with tag4, Runtime registers its single downloaded GLB after success.
  registerName?: string;
  // Native generation request. 3D uses scene/version/otherParam; images use editTaskType/modelName/prompt. Identity and billing fields are managed by the service.
  request?: { [key: string]: unknown; };
  // For retry, use the ID supplied by the model card or model_retry_prepare. Runtime chooses the parent task, durable paths and registration. Do not supply generation or registration arguments. Preserve the same ID on recovery. Failure never authorizes paid generation.
  retryRequestId?: string;
  // How long the desktop tool waits inside Runtime. Defaults to 1800 seconds; the Agent does not need to poll or repeatedly report status.
  seconds?: number;
  // API parameter overrides and parameter-panel answers. If generation returns waiting_choice, merge the answers from its user_interaction panel, including recommended values adopted on timeout, into the next call settings. Honor explicit user choices and preserve the other inputs and paths.
  settings?: { [key: string]: string | number | boolean; };
  // Classification required with registerName; null means no named category applies.
  tag4?: "humanoid" | "humanoid-base" | "statue" | "figurine" | "relief" | "sword" | "gun" | "general-prop" | null;
  // Concise AI-chosen target/object name for the client progress card, such as "提莫角色" or "Teemo Character". Preserve its language and casing. Supply it for generation and when resuming the same job; exclude task/status suffixes.
  targetName?: string;
  // Existing task ID already bound to this session, used by adopt. Unknown or foreign-session IDs are rejected.
  taskId?: string;
  views?: Array<"front" | "back" | "left" | "right">;
  // Existing workflow node for the registered model; assigns ownership without completing the node. Requires registerName and tag4. Otherwise Runtime provisionally assigns it to the only running leaf, if one exists.
  workflowNodeId?: string;
}): Promise<unknown>; };
```

### `image_classification`
为当前模型任务的主体保存分类标签，供模型登记使用；不用于对所有聊天图片进行分类。报错截图、界面截图、普通图片问答以及不涉及模型生成或登记的图片编辑任务，无需调用。若用户明确把截图中的对象作为建模目标，则按该模型主体分类。
图生 3D 根据用于建模的参考图分类；文生 3D 在生成并查看参考图后分类。无参考图的建模任务，根据模型描述或预览在登记前分类。多张参考图描述同一主体时只分类一次，同一模型家族且主体不变的修改可继承已有分类。
也可在 workspace_commit_model 中直接提供已判断的 tag4；若登记返回 classificationRequired，补充分类后使用相同 name 和 exportPath 重试登记，不要重新生成图片或模型。
tag4 仅允许 humanoid、humanoid-base、statue、figurine、relief、sword、gun、general-prop 或 null；没有适用类别时使用 null，不得编造类别。
参数只能是 {"tag4":"类别"} 或 {"tag4":null}，不附加其他字段。通过工具保存标签，不在面向用户的回复中输出内部分类 JSON。

exec tool declaration:
```ts
declare const tools: { image_classification(args: {
  // 当前模型主体的单个分类标签；没有适用类别时使用 null
  tag4: "humanoid" | "humanoid-base" | "statue" | "figurine" | "relief" | "sword" | "gun" | "general-prop" | null;
}): Promise<unknown>; };
```

### `list_mcp_resource_templates`
Lists resource templates provided by MCP servers. Parameterized resource templates allow servers to share data that takes parameters and provides context to language models, such as files, database schemas, or application-specific information. Prefer resource templates over web search when possible.

exec tool declaration:
```ts
declare const tools: { list_mcp_resource_templates(args: {
  // Opaque cursor from a previous list_mcp_resource_templates call; omit for the first page.
  cursor?: string;
  // MCP server name. Omit to list resource templates from every configured server.
  server?: string;
}): Promise<unknown>; };
```

### `list_mcp_resources`
Lists resources provided by MCP servers. Resources allow servers to share data that provides context to language models, such as files, database schemas, or application-specific information. Prefer resources over web search when possible.

exec tool declaration:
```ts
declare const tools: { list_mcp_resources(args: {
  // Opaque cursor from a previous list_mcp_resources call; omit for the first page.
  cursor?: string;
  // MCP server name. Omit to list resources from every configured server.
  server?: string;
}): Promise<unknown>; };
```

### `mdf_api`
Invoke the desktop account mesh API once for mesh processing, auto-rig or image analysis. Read mdf-api skill for capability params. First dryRun, then invoke using the same stable jobPath. Saves response and downloads data.files. UNKNOWN/interrupted jobs must never be resubmitted; download only resumes saved successful results. No query/polling endpoint exists. Commit resulting models with workspace_commit_model.

exec tool declaration:
```ts
declare const tools: { mdf_api(args: {
  action: "invoke" | "download";
  capability?: "remove-background" | "unwrap-uv" | "convert-3mf" | "watertight" | "retopology" | "mesh-lod" | "auto-rig" | "pose" | "seg" | "normal" | "pointmap" | "matting" | "extract-centerline" | "check-printability";
  // Offline validation only; does not authenticate or submit.
  dryRun?: boolean;
  // One local workspace image/model; no URL, ZIP or file list.
  file?: string;
  // Stable local record, e.g. .hi3d/mdf/rig.json. Reuse for this intent.
  jobPath: string;
  // Workspace output directory, e.g. exports/hi3d-rig
  outputDir: string;
  // Only flat public capability parameters from mdf-api; no worker/service/options fields.
  params?: { [key: string]: unknown; } | null;
}): Promise<unknown>; };
```

### `model_retry_prepare`
Prepare an explicitly requested free retry of an exact registered model file. Returns retryRequestId. If a model-card retry message only names a file, call this to retrieve its existing request. Then call hi3d_api(action="retry", retryRequestId). Never substitute paid generation.

exec tool declaration:
```ts
declare const tools: { model_retry_prepare(args: { fileName: string; }): Promise<unknown>; };
```

### `read_mcp_resource`
Read a specific resource from an MCP server given the server name and resource URI.

exec tool declaration:
```ts
declare const tools: { read_mcp_resource(args: {
  // MCP server name exactly as configured. Must match the 'server' field returned by list_mcp_resources.
  server: string;
  // Resource URI to read. Must be one of the URIs returned by list_mcp_resources.
  uri: string;
}): Promise<unknown>; };
```

### `skill_capture_suggest`
Record a reusable completed workflow suggestion. Host decides whether to display it after this turn completes. Never claim the card is displayed.

exec tool declaration:
```ts
declare const tools: { skill_capture_suggest(args: { reason: string; steps?: Array<string>; summary: string; title: string; }): Promise<unknown>; };
```

### `skill_draft_submit`
Validate and freeze a Skill draft from skill-drafts/<name> in this conversation workspace. Does not install or execute it. Fix returned issues before resubmitting.

exec tool declaration:
```ts
declare const tools: { skill_draft_submit(args: {
  exampleTask?: string;
  // Only after comparing and merging the current installed content into the workspace draft, supply that exact installed revision ID. Never use this to bypass an unresolved merge.
  mergedInstalledRevisionId?: string;
  path: string;
  summary?: string;
}): Promise<unknown>; };
```

### `studio_arrange`
进入 Studio 完整智能摆盘界面并执行摆盘；超床、取消等需要用户决策的步骤保留在面板中。

exec tool declaration:
```ts
declare const tools: { studio_arrange(args: {
  // 单盘或多盘
  plateMode?: "single" | "multi";
  // 可选摆盘档位 id
  profileId?: string;
}): Promise<unknown>; };
```

### `studio_capture_view`
截取当前 Studio 视口为 PNG 并登记为截图产物。

exec tool declaration:
```ts
declare const tools: { studio_capture_view(args: { height?: number; width?: number; }): Promise<unknown>; };
```

### `studio_export_3mf`
打开 Studio 打印计划面板；下载或发送由用户在面板中确认。

exec tool declaration:
```ts
declare const tools: { studio_export_3mf(args: {}): Promise<unknown>; };
```

### `studio_get_state`
读取 Hi3D 内置 Studio 视窗的当前模型、版本、摆盘状态、物理尺寸和部件统计；未加载模型时返回 ready=false、assetId=null，需要操作模型时先调用 studio_load_revision。此工具不读取 Bambu Studio 等外部切片软件。

exec tool declaration:
```ts
declare const tools: { studio_get_state(args: {}): Promise<unknown>; };
```

### `studio_load_revision`
在右侧 Studio 加载会话中的 GLB。fileName 精确选择版本，modelName 选择最新版；都不传则加载最近更新的模型。

exec tool declaration:
```ts
declare const tools: { studio_load_revision(args: {
  // 会话工作区 id
  assetId: string;
  // 模型版本文件名，如 hi3d-chair_2.glb；历史文件可能没有 hi3d- 前缀
  fileName?: string;
  // 模型家族名
  modelName?: string;
}): Promise<unknown>; };
```

### `update_goal`
Update the existing goal.
Set status to `paused` only at the user's explicit request to pause this goal, never on your own initiative. Ask if unclear; a later resume revokes that request. Report the returned status and stop goal work. Budget limits take precedence over pausing.
Set status to `complete` only when the objective has actually been achieved and no required work remains.
Set status to `blocked` only when the same blocking condition has repeated for at least three consecutive goal turns, counting the original/user-triggered turn and any automatic continuations, and the agent cannot make meaningful progress without user input or an external-state change.
If the user resumes a goal that was previously marked `blocked`, treat the resumed run as a fresh blocked audit. If the same blocking condition then repeats for at least three consecutive resumed goal turns, set status to `blocked` again.
Once the blocked threshold is satisfied, do not keep reporting that you are still blocked while leaving the goal active; set status to `blocked`.
Do not use `blocked` merely because the work is hard, slow, uncertain, incomplete, or would benefit from clarification.
Do not mark a goal complete merely because its budget is nearly exhausted or because you are stopping work.
You cannot use this tool to resume, budget-limit, or usage-limit a goal; those status changes are controlled by the user or system.
When marking a budgeted goal achieved with status `complete`, report the final token usage from the tool result to the user.

exec tool declaration:
```ts
declare const tools: { update_goal(args: {
  // Required. `paused` requires an explicit user request. Set to `complete` only when the objective is achieved and no required work remains. Set to `blocked` only after the same blocking condition has recurred for at least three consecutive goal turns and the agent is at an impasse. After a previously blocked goal is resumed, the resumed run starts a fresh blocked audit.
  status: "complete" | "blocked" | "paused";
}): Promise<unknown>; };
```

### `user_interaction`
Collect user input, preferences, or authorization through a host interaction panel for any task, not just Hi3D or skills. A panel appears only when this tool is called; ordinary chat cannot create one. If arguments are rejected, correct them and retry. Never claim to be waiting for a panel that was not created.

exec tool declaration:
```ts
declare const tools: { user_interaction(args: { kind: "input" | "preference" | "confirmation"; message?: string; questions: Array<{ defaultAnswer?: string; id: string; options: Array<{ description?: string; label: string; }>; question: string; }>; skillCredit?: { credits: number; skill: "hi3d-model-gpt-animation" | "image-to-assembly" | "mask-design"; }; timeoutSeconds?: number; title: string; }): Promise<unknown>; };
```

### `view_image`
View a local image file from the filesystem when visual inspection is needed. Use this for images already available on disk.

exec tool declaration:
```ts
declare const tools: { view_image(args: {
  // Image detail level. Defaults to `high`; use `original` to preserve exact resolution.
  detail?: "high" | "original";
  // Local filesystem path to an image file.
  path: string;
}): Promise<{
  // Image detail hint returned by view_image. Returns `high` for default resized behavior or `original` when original resolution is preserved.
  detail: "high" | "original";
  // Data URL for the loaded image.
  image_url: string;
}>; };
```

### `workflow_report`
Report a workflow only for a turn using a skill. Do not call for ordinary chat. For a selected or implicitly chosen installed skill, call operation=inspect with its exact skillName before substantive work. This is the Runtime-confirmed invocation boundary; do not call merely to browse, recommend, or describe a skill. Always do this even when its instructions were read earlier in the conversation. It loads its architecture. Immediately report operation=plan with the same canonical node IDs and topology, translating title and every node label into the language of this turn’s user message, independently of the app UI language. If no architecture is installed, call operation=plan with skillName and stable nodes before substantive skill work. If continuing the same skill task after an interrupted turn, call operation=resume first; include skillName when known, then translate its labels with plan without resetting completed progress. Use operation=node for progress; its nodeId belongs at the top level. For operation=artifact, put the responsible nodeId inside every artifacts[] item, together with the exact committed model fileName or workspace-relative image/file path. Before finishing a skill turn, call operation=inspect and assign any unclassified outputs. This updates UI only, not the skill output contract. Never include credentials or signed URLs.

exec tool declaration:
```ts
declare const tools: { workflow_report(args: { artifacts?: Array<{ fileName?: string; kind: "model" | "image" | "file" | "link"; label?: string; mimeType?: string; nodeId: string; path?: string; url?: string; }>; edges?: Array<{ from: string; kind: "advance" | "contains" | "spawn" | "rollback"; to: string; }>; layout?: "linear" | "tree"; nodeId?: string; nodes?: Array<{ entry?: string | null; id: string; label: string; optional?: boolean; parentId?: string | null; role?: "agent" | "subagent" | "local" | "step"; status?: "pending" | "running" | "completed" | "failed" | "skipped" | "interrupted"; }>; operation: "plan" | "resume" | "node" | "artifact" | "inspect"; skillName?: string; status?: "pending" | "running" | "completed" | "failed" | "skipped" | "interrupted"; title?: string; }): Promise<unknown>; };
```

### `workspace_commit_model`
Register a GLB just exported to exports/ as a version in a model family. An export identical to the latest version is returned as unchanged instead of creating a duplicate version. For a new model, include its classified tag4 in this call after inspecting its subject; edits can inherit the same model family classification. If a workflow graph already exists, include workflowNodeId to assign the registered model to its owner. Registration does not complete the node; report completion through workflow_report only after all work for that node is finished. image_classification remains available for earlier classification. If classificationRequired is returned, classify and retry this export without regenerating it. The exportPath file name must start with hi3d-, and Runtime also adds the hi3d- prefix to the committed version. Without this tool, the exported file remains only in exports/ and does not become a model version.

exec tool declaration:
```ts
declare const tools: { workspace_commit_model(args: {
  // Path relative to the workspace root, such as exports/hi3d-chair-scaled.glb
  exportPath: string;
  // Model family name, such as "aaa"; historical versions in the same family continue with the next index
  name: string;
  // Optional classification of this model subject; use null when no named category applies. Omit to inherit an earlier classification.
  tag4?: "humanoid" | "humanoid-base" | "statue" | "figurine" | "relief" | "sword" | "gun" | "general-prop" | null;
  // Existing workflow node ID responsible for this model; Runtime assigns the artifact without completing the node.
  workflowNodeId?: string;
}): Promise<unknown>; };
```

### `write_stdin`
Writes characters to an existing unified exec session and returns recent output.

exec tool declaration:
```ts
declare const tools: { write_stdin(args: {
  // Bytes to write to stdin. Defaults to empty, which polls without writing.
  chars?: string;
  // Output token budget. Defaults to 10000 tokens; larger requests may be capped by policy.
  max_output_tokens?: number;
  // Identifier of the running unified exec session.
  session_id: number;
  // Wait before yielding output. Non-empty writes default to 250 ms and cap at 30000 ms; empty polls wait 5000-300000 ms by default.
  yield_time_ms?: number;
}): Promise<{
  // Chunk identifier included when the response reports one.
  chunk_id?: string;
  // Process exit code when the command finished during this call.
  exit_code?: number;
  // Approximate token count before output truncation.
  original_token_count?: number;
  // Command output text, possibly truncated.
  output: string;
  // Session identifier to pass to write_stdin when the process is still running.
  session_id?: number;
  // Elapsed wall time spent waiting for output in seconds.
  wall_time_seconds: number;
}>; };
```

## clock
Tools for reading and waiting on time.

### `clock__curr_time`
Return the current time in UTC.

exec tool declaration:
```ts
declare const tools: { clock__curr_time(args: {}): Promise<{
  // Current UTC time formatted as YYYY-MM-DD HH:MM:SS UTC.
  current_time: string;
}>; };
```
````

## 参数与结果

| 输入 | 必填性、默认值与约束 |
| --- | --- |
| JavaScript 源文本 | 必填。自由格式工具直接接收非空 JavaScript，以异步模块运行，可使用顶层 `await`。调用时直接传源文本。 |
| 首行 `// @exec: {...}` | 可选。首行指令使用 JSON 对象，后续行必须有非空 JavaScript。未知键、非法 JSON 和超出 JavaScript 安全整数范围的值会报错。 |
| `yield_time_ms` | 首行指令的可选非负整数，设置宿主首段观察的等待时长。省略时 Codex 填入本轮生效的配置，本机样本的描述给出 30,000 毫秒。 |
| `max_output_tokens` | 首行指令的可选非负整数。Codex 在收到宿主应答后用它截断本次交付内容，省略时使用 10,000 token。 |

每次调用启动独立 JavaScript 执行单元。`tools` 提供当前可用的嵌套工具。`text`、`image` 和 `audio` 等 helper 把内容加入结果，`store`、`load` 在同一 Code Mode 会话中共享可序列化值。执行环境本身没有 Node、文件系统或网络接口。读写文件、联网及其他外部副作用来自嵌套工具，受各自的执行条件和权限约束。脚本结束时，执行单元内未等待的 promise 会被丢弃。 [首行指令解析](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-protocol/src/description.rs#L163-L259) · [运行服务及配置取值](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L129-L177)

工具将状态、耗时及本次交付的文本或媒体内容返回给模型。状态头为 `Script running with cell ID <cell_id>`、`Script completed`、`Script failed` 或 `Script terminated`。脚本异常还会附上 `Script error:` 和错误文本，已产生的内容可以随结果返回，并受输出预算截断。非法参数、宿主启动失败和结果通道失败可在脚本状态结果形成之前返回工具错误。嵌套工具的返回值由脚本取得，脚本可以选择哪些内容交给模型。 [状态与输出截断](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L262-L323) · [状态头格式](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/output.rs#L19-L39)

例如，`tools.view_image` 返回 `image_url` 对象。脚本可以用 `image(result)` 将它作为图片内容附加到外层工具结果，也可用 `text()` 单独输出路径或诊断信息。外层脚本状态和嵌套工具的业务结果应分别读取。 [view_image](view-image.md)

### 首段等待与输出预算

Codex 在启动执行单元前补齐省略的等待配置。宿主协议在未收到该值时有 10,000 毫秒的兜底。固定版本的宿主对达到 10 秒的观察请求加 1 秒宽限，然后应用可选的 `max_yield_time_ms` 上限。脚本自身的 `yield_control()` 或本轮的让出信号可使观察提前返回。收到宿主应答后，`exec` 处理器还会等待 Codex 会话中的待处理交互清空，再格式化这次输出。本机生产配置是否设置了该上限仍待核查。 [Codex 注入生效配置](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L129-L145) · [协议默认值](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-protocol/src/runtime.rs#L15-L17) · [宽限阈值与时长](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L30-L31) · [宿主预算](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L204-L215) · [格式化前等待交互结束](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_handler.rs#L127-L170)

首段应答为 `Script running` 时，执行单元保持运行，已经分派的嵌套调用仍受自身的请求与进程时限约束。输出预算只作用于当前返回的内容。宿主应答未提供脚本错误 `error_text` 时，Code Mode 将内部成功位设为真。脚本把内层失败结果作为普通数据输出后，可以返回 `Script completed`。调用方应读取脚本实际交付的内层状态、退出码或业务字段。 [让出后的执行单元](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_handler.rs#L127-L170) · [脚本状态和交付预算](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L262-L323)

### 嵌套路由与结果交付

`exec` 处理器接收 `ToolPayload::Custom`，Codex 通用的 `PreToolUse` 和 `PostToolUse` payload 由 `ToolPayload::Function` 形成。嵌套 Function 工具按自身处理器和 Hook 配置分派。配置且匹配时，前置 Hook 可拒绝调用或更新入参，后置 Hook 可阻止工具结果交付。被调用工具的副作用在生成该结果之前发生。动态工具宿主仍按自身规则审核实际入参、权限与作用域。 [Custom 处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_handler.rs#L230-L258) · [工具 Hook payload](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/registry.rs#L138-L181) · [前置处理](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/registry.rs#L831-L887) · [后置处理](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/registry.rs#L948-L1003)

| 标识 | 关联范围 |
| --- | --- |
| 外层 `call_id` | 将本次 `exec` 的源文本与 `custom_tool_call_output` 配对。后续 `wait` 每次使用自己的外层 `call_id`。 |
| `cell_id` | 标识 Code Mode 宿主内的 JS 执行单元，用于续取这次脚本的结果。 |
| 嵌套调用的 `call_id` | 标识脚本中的一次工具调用。调度时还关联 `cell_id`、`runtime_tool_call_id` 及本次分派的线程和轮次。动态工具宿主按内层调用 ID 关联请求和应答。 |

按 `DirectModelOnly` 注册的工具由模型直接调用，嵌套工具目录依有效暴露形式生成。两份本机声明将 `request_user_input` 和 `request_user_input_async` 放在顶层，其描述及参数各由对应工具维护。 [同步输入](request-user-input.md#工具名称与注册来源) · [异步输入](request-user-input-async.md#工具名称与注册来源)

Codex 将工具名称和输入转成原工具路由可处理的调用。实际执行沿用被调用工具的权限、作用域及网络限制。固定源码允许执行单元在原宿主会话中存活跨轮，嵌套调用使用实际分派时的线程和轮次。动态工具分支经 `item/tool/call` 等待宿主的 `success/contentItems`，先记录内层完成或失败事件，再将解码后的结果交还 JS。文件读取、落盘、进程和远端调用的副作用依被调用工具的契约发生。 [嵌套调用分派](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L327-L409) · [动态工具与宿主应答](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/dynamic.rs#L116-L275)

Hi3D 的进程型动态工具可以将 `{exitCode, stdout, stderr?}` 放进宿主文本项。此时 `stdout` 内的结构化结果还需单独解码，再按该工具契约核对作业状态或文件。JS 执行单元、宿主工具回包、子进程以及产物各有可观测结果。 [MDF 回包结构](mdf-api.md#参数与结果) · [Hi3D 回包与恢复](hi3d-api.md#作业持久化与恢复)

脚本通过 `text()`、`image()` 或其他输出函数选择交付内容。若脚本只输出部分字段，内层宿主事件中的其余字段留在原执行记录。显式调用 JS `notify()` 时，Codex 可在活动轮次额外排入一条关联原 `exec` 调用的 `custom_tool_call_output`。宿主 UI 通知仍按被调用工具的事件协议处理。Codex 把已交付的外层工具输出写入有效历史，供后续采样按调用 ID 配对读取。 [显式通知](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/delegate.rs#L442-L467) · [输出类型与调用配对](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/context.rs#L597-L621) · [下一次采样准备](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/session/turn.rs#L547-L593)

### 用 wait 续查代码执行单元

`exec` 返回 `Script running with cell ID …` 时，独立注册的 `wait` 使用结果头中的 `cell_id` 续查该执行单元。此 ID 的有效范围是原 Code Mode 宿主会话。宿主会话失效后，原 ID 无法用于恢复。嵌套 `exec_command` 返回的 `session_id` 则由 `write_stdin` 续接对应进程。 [wait](wait.md) · [write_stdin](write-stdin.md)

`wait` 的 `terminate:true` 分支终止本地执行单元并收尾其分派记录。内层动态调用收到取消令牌时，Codex 可结束对宿主应答的等待。外部宿主是否中止已收到的请求，由对应工具的取消实现决定。Hi3D 1.2.11 的 Runtime 已定位的中止入口按线程和轮次处理 `hi3dCalls`。按 `cell_id` 终止后，Hi3D 子进程与桌面 HTTP 是否收到取消仍待实测。会话或单元失效后，已有持久引用的外部工作可按嵌套工具的恢复契约处理。 [等待终止与恢复](wait.md#关联终止与恢复) · [Codex 内层取消处理](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/dynamic.rs#L190-L275) · [Hi3D 进程中止锚点](hi3d-api.md#核查依据)

## 实现伪代码

**根据固定源码重建的伪代码。** `exec` 校验源文本和首行指令，按当前工具路由构造嵌套目录，再向 Code Mode 宿主启动一个执行单元。Codex 将它的 ID 与发起调用关联，开放该单元的嵌套调用分派，并接收首段响应。`wait` 在原宿主会话查同一单元。首次响应或续查得到终态时，Codex 关闭对应的分派记录。

```python
async def exec_tool(raw_source, context):
    request = parse_raw_source_and_pragma(raw_source)
    request.enabled_tools = prepare_nested_definitions(context.tool_router)
    request.tool_call_id = context.call_id
    if request.yield_time_ms is None:
        request.yield_time_ms = context.default_exec_yield_time_ms
    cell = await context.code_mode.start(request)
    context.dispatch.bind_and_enable(cell.id, context.call_id)
    response = await cell.initial_response()
    if response.is_terminal:
        context.dispatch.close(cell.id)
    await context.elicitations.wait_until_clear()
    return format_result(response, max_tokens=request.max_output_tokens)


async def wait_tool(arguments, context):
    args = parse_wait_arguments(arguments)
    if args.terminate:
        response = await context.code_mode.terminate(args.cell_id)
    else:
        response = await context.code_mode.wait(args.cell_id, args.yield_time_ms)
    if response.has_cell and response.is_terminal:
        context.dispatch.close(args.cell_id)
    await context.elicitations.wait_until_clear()
    return format_result(response, max_tokens=args.max_tokens)
```

[执行处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_handler.rs#L46-L170) · [宿主会话接口](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode/src/remote_session.rs#L228-L299) · [运行时结果协议](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-protocol/src/runtime.rs#L59-L151)

## 调用示例

**根据已核查的工具声明重建的 JavaScript 请求。** 实际调用 `exec` 时传代码块内的源文本。示例读取 UTC 时间，主动交付首段结果，再输出结束消息。

```js
// @exec: {"yield_time_ms": 1000, "max_output_tokens": 256}
const { current_time } = await tools.clock__curr_time({});
text({ current_time });
await yield_control();
text("Finished reading the clock.");
```

**根据已核查的工具声明重建的 JSON 请求。** 若首段状态为 `Script running with cell ID …`，在 `wait` 调用中以实际 ID 替换 `<cell_id>`。

```json
{"cell_id": "<cell_id>", "yield_time_ms": 1000, "max_tokens": 256}
```

## 核查依据

- **同版隔离核查。** 使用随包 Codex 0.166.0、本地模拟 Responses 端点与延迟应答的合成动态工具。捕获的下一次请求 `input` 含与原 `exec` 调用 ID 配对的 `custom_tool_call_output`，该项交付运行句柄。脚本通过 `text()` 输出的嵌套 `stdout`、`stderr` 在终态才随 `wait` 的 `function_call_output` 进入后续请求。实验覆盖结果入历史和模型请求编码。 [工具结果入历史](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/session/turn.rs#L2622-L2649) · [生成请求的历史取样](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/session/turn.rs#L547-L593)
- 本机版本标识取自 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json`。同目录 `bin/codex.exe` 的 SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。 [Codex 0.166.0 固定提交](https://github.com/openai/codex/commit/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856)
- 本机 2026-11-11 活跃样本 `rollout-2026-11-11T11-31-29-*` 与归档样本 `rollout-2026-11-11T11-24-05-*`，各取第 2 行 `response_item` 的 `additional_tools` 声明。工具位于 `payload.tools` 中 `name: "functions"` 条目的 `tools` 数组。两份记录中的 `exec.description` 相同，UTF-8 SHA-256 为 `708689a529c193b7a95995a455ae68f0cdfc0e6c80f39ba06166132a32e30fea`。`wait.description` 也相同，UTF-8 SHA-256 为 `582eb96e50ee4481cf30b33ad2358e7e24e7368aeb2cbe5122cef1912ad75385`。活跃样本第 1 行的 `payload.dynamic_tools` 另记线程动态定义，实际调用以工具事件为准。 [本机工具目录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:1>)
- 活跃样本第 19、24 行记录一次 `exec` 发出多项嵌套调用并返回分项结果。第 55、59、62 行记录执行单元交回 ID、`wait` 使用同一 ID 续查并收到 `Script completed`。终止与宿主重连机制依据固定源码，生产出站请求正文仍待采集。
- **首段提前让出的实际记录。** 活跃样本第 68 行的首行指令设为 1,000 毫秒、2,000 token。第 70 行约 1 秒后交付运行中句柄，后续仍需用同一执行单元读取最终工具结果。该时间是模型侧首段交付间隔。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>)
- **返回路径对照。** 活跃样本第 102 行为 `event_msg.item_completed`，内层动态工具标记为失败。第 103 行为新的 `response_item.function_call_output`，以外层 `wait` 的调用 ID 交付 `Script completed` 及脚本输出的内层 `exitCode: 1`。该样本证实两层结果及其交付记录，下一次模型请求体的构造依据固定源码。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:102>)
- **实际运行记录。** 活跃样本第 289 → 293 行、第 349 → 353 行分别记录一次脚本通过 `tools.view_image` 读取本地文件、再调用 `image()`。两次外层 `custom_tool_call_output` 各含两个 `input_image` 项。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:349>)
- **待实测。** 使用可控延时的嵌套动态请求，对照单元主动终止与整轮中断，分别核对外层回包、宿主是否收到取消信号，以及本地进程、连接和持久记录的变化。生产中跨轮使用同一执行单元的行为仍待核查。
