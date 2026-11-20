# 账号 Runtime 免费重试：本包入口与 desktop 改动清单

本包提供 3D 免费重试 CLI 与宿主调用契约。桌面入口需要宿主同时放行路由、注册工具 schema、持久化意图并校验模型来源；不能仅更新本包就假定旧宿主具备这些能力。

## 本仓库已经外露什么

账号模式 CLI（物化后的 `hi3d/scripts/hi3d_api.py`）：

| 命令 | 作用 |
| --- | --- |
| `retry-quota --task-id <原任务>` 或 `--job <原 job>` | 复用 `GET /model3d/result?jobId=` 的 `data.retryCount`，归一化为 `remaining` / `eligible` / `can_retry` |
| `retry --parent-job` 或 `--parent-task-id` + 新的 `--job` `--out` | `POST /model3d/retry`，代理转正式账号接口 `/aigc/api/generate/img2model3d-url`，正文只有 `{"parentGenerateId":"<原任务根ID>"}`，再走等待和下载 |

CLI 的 `--job`/`--parent-job` 先验证原 job 账号环境，重试 job 使用 `parent_task_id`，普通 job 使用有效 `parentId`，没有时使用 `task_id` 作为根任务。新任务 ID 落盘后立即通过 stderr JSONL 输出并 flush `event=submitted`，再开始首次结果查询。明确额度/原任务/并发拒绝保留 `submission_has_task_id` 并区分拒绝与受理不确定。

次数只认服务端 `retryCount`，Runtime 输出的 remaining 是归一化字段。提交或查询结果返回有效次数时直接覆盖缓存，不额外请求；缺字段或失败时才校准，不把未知展示为 0。`retryType`、`tier`、`amount` 仍然禁止由客户端填写。原任务 job 不会被覆盖。

Agent 侧契约以当前宿主工具 schema 为准：`action="retry_quota"` 传注册 `fileName`；`action="retry"` 只传 `retryRequestId` 和可选 targetName。卡片注入请求 ID；只有文件名时调用 `model_retry_prepare(fileName)`。Runtime 保存意图、分配新路径并自动登记。旧宿主尚未暴露这些动作时，不调用未提供的工具。

路由与字段见 [桌面参数](desktop-parameters.md)；调用示例见 [调用参考](calling.md)。

## desktop 仓库需要改的清单

1. **代理放行。** `packages/desktop/src/main/tool-api-proxy.ts` 的 `validToolRoute` 增加内部 `POST /v1/model3d/retry` 并映射到正式账号接口；次数复用已有 GET result 路由。测试夹具一起改。

2. **Runtime 工具 schema。** `packages/runtime/src/hi3d-tool.ts`：`action` 增加 `retry_quota`、`retry`。`retry_quota` 接受准确 fileName，retry 接受 retryRequestId；根任务、kind、新 jobPath、outputDir 与登记字段由 Runtime 从持久化意图解析，不让 Agent 填写。`hi3dEstimatedPoints` 对 `retry` 记 0。

3. **执行适配。** `packages/runtime/src/desktop-hi3d-tool.ts` 将 retry 转到独立 CLI 分支，不走 `generate-3d`；retry_quota 由 Runtime 直接查询 loopback tool proxy，避免每张卡片启动 Python。

4. **可信模型来源。** Runtime 根据已知下载 job、规范 GLB 路径和实际 SHA-256 建立来源，登记时核对哈希再写入 ModelFile.source。记录 taskId、retryRootId、jobPath、kind、账号与环境，不接受 Agent 自填来源；编辑版、导入版和无法验证的历史模型不显示重试。

5. **卡片 UI。** `ChatWorkspace.vue` 的 `model-result__actions`：在「打印」左侧加「重试」，角标为 `remaining`（主站 `X10` 那种）。`remaining <= 0`、未登录、账号/环境和 job 不一致时不渲染。文案进 i18n。

6. **次数怎么读。** 卡片不要让 Agent 每轮查。Runtime 经现有 tool proxy 查询，代理使用现有 Cookie；缓存按账号、环境、根任务分组。字段兼容与 Python 相同，失败标为未知。受理或新鲜结果已有次数时直接使用；缺字段及异常后的账本核对才触发结果接口校准。

7. **点击之后。** 走 Runtime `hi3d_api(action="retry")`，沿用进度卡、下载与 Runtime 自动登记，registeredModel 返回后不重复登记。不要在 Main 里单独 POST 再自己下 GLB。`10030105` / `10030107` 后重新读次数并收起按钮。

8. **workflows gitlink。** 本仓库推送含上述入口的提交后，desktop 把 `workflows` 指到该提交并重启 Runtime，宿主才能装到带 `retry` 的 `hi3d/SKILL.md`。

`scripts/runtime/hi3d_client.py` 中 RETRY 仅指 loopback 内部路由，不是远端 API。Main 使用正式账号接口和 parentGenerateId；次数读取既有结果接口，不能再为次数构造新的 HTTP 路径。
