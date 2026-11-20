# 调用参考

所有调用都使用 Runtime dynamic tool `hi3d_api`。路径相对当前工作区。

`images` / `mesh` 接受工作区内的文件路径；上传由工具完成，无需 Agent 手动构造请求。

图片生成与编辑的调用方式见 [图片生成参考](image-generation.md)。图片 action 在同一调用内等待并下载 PNG；正常 pending 继续查询原任务，任何失败按图片入口规则停止并报告，用户明确要求后才恢复。

## 图生 3D

- 单图 dry run：`{"action":"submit","kind":"model","images":["inputs/front.png"],"jobPath":"hi3d/model.json","dryRun":true}`
- 正式提交：完成参数选择后，保持完全相同的计划并把 `dryRun` 改为 `false`。用户已明确要求生成时不再另行询问计费授权；参数不完整时仍返回 `waiting_choice`，不 POST。
- 多视图：`images` 与 `views` 一一对应，例如 `images=["inputs/front.png","inputs/left.png"]`、`views=["front","left"]`。Runtime 客户端会按前、后、左、右重排。
- 纯几何：`settings={"request_type":1}`。
- 为已有 GLB 贴纹理：提供参考图和 `mesh`，设置 `request_type=2`；部分旧模型版本不支持。

## 其他能力

- 浮雕：`kind="relief"`，单个本地图片放在 `images`，也可使用 `imageUrl`。
- 拆件：`kind="split"`，提供工作区内 `mesh` 或 HTTPS `meshUrl`。
- 多色：`kind="multicolor"`，输入必须是带纹理 GLB。
- 接管旧任务：`{"action":"adopt","kind":"model","taskId":"...","jobPath":"hi3d/adopted.json"}`；不会创建新任务。
- 免费重试次数：`{"action":"retry_quota","fileName":"hi3d-model_1.glb"}`。Runtime 从注册表解析原任务根 ID；查询失败是未知次数，不显示为 0。
- 免费重试提交：卡片提供请求 ID 时调用 `{"action":"retry","retryRequestId":"..."}`。没有请求 ID 时先调用 `model_retry_prepare(fileName)`，会复用同一对话中的进行中意图。Runtime 分配计划、调用免费接口、等待下载并自动登记；返回 registeredModel 后继续原工作流，不重复 workspace_commit_model。不要自动创建下一次重试，也不要使用 generate_3d 代替。详细边界见 [desktop 清单](desktop-free-retry.md)。
- 等待：`{"action":"wait","jobPath":"hi3d/model.json","seconds":1800,"interval":30}`。正式提交后在同一调用内等待，`pending` 后继续恢复原任务，直到成功或失败。Runtime 会把状态进度发送到客户端状态卡；Agent 不在对话中重复播报未变化的等待状态。查询接口没有数值百分比时进度值为 `null`。
- 下载：`{"action":"download","jobPath":"hi3d/model.json","outputDir":"exports/hi3d-model"}`。

每条 `submit` 都应先 dry run。相同 `jobPath` 与相同输入会复用原任务；参数变化时不能覆盖原 job。返回 `submission_uncertain` 时先核对任务历史，不要通过换 job 重提。

下载和文件校验由工具完成；使用返回的产物路径。下载或校验失败时报告具体原因，保留原任务和已有文件，不把不完整产物当作成功结果。

## 查询错误

以工具返回的结果和具体原因决定下一步，不自行解析服务错误码或修改任务记录。组合调用和 `wait` 返回 `result`，`query` 返回任务摘要；查询相关信息可能位于顶层摘要，也可能位于 `job` 中。

| 查询结果 | Agent 操作 |
| --- | --- |
| 查询未成功 | 只报告查询失败及工具给出的原因，结束当前轮次；不据此判定任务失败，不继续下载或自动重试。 |
| 查询成功，任务仍在处理中 | 按既有等待流程继续同一任务；等待预算结束的 `pending` 不是失败。 |
| 查询成功，任务成功 | 组合调用已下载时使用返回的文件；分阶段调用则继续下载、登记或处理产物。 |
| 查询成功，明确返回失败 | 说明具体失败原因并结束当前轮次，不自动重提。按工具说明区分请求被拒绝和生成失败，不把额度、参数等错误说成生成引擎已终止。 |

读取错误原因时，优先使用本次 `last_query_error.reason` / `last_query_error.message`；没有查询错误时读取 `error.reason` / `error.message` 或工具顶层说明。`progress.stale=true` 表示显示的是上次已知结果，不能用其中的 `state` 或进度断言当前任务状态。默认用用户的语言说明原因，不展示数字错误码；没有具体原因时说明未知。`next_action` 中的后续建议不授权在当前轮次继续调用。

用户明确要求继续后，用原 `jobPath` 调用 `query` / `wait`；查询成功后按新结果处理。查询失败后也可用相同参数恢复原生成调用，不更换任务或路径重提。若工具提示登录失效或账号、环境不匹配，按提示恢复原账号和环境后再查询。提交结果不确定且没有 task ID 时先核对任务历史，不按普通查询失败处理。
