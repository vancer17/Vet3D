# `skill_draft_submit`

## 工具名称与注册来源

模型可见名称为 `skill_draft_submit`。核查版本为 Windows x64 版 Hi3D Agent 1.2.11。Hi3D Runtime 将 `UL` 中的定义经 `Vg` 合入创建对话线程时的动态工具列表。Runtime 使用调用上下文查找当前对话的工作区，并将草稿版本关联到提交轮次。

## 暴露给 LLM 的描述

下文是注册时的 `description` 原文。

```text
Validate and freeze a Skill draft from skill-drafts/<name> in this conversation workspace. Does not install or execute it. Fix returned issues before resubmitting.
```

## 参数与结果

| 参数 | 必填 | 约束与默认值 |
| --- | --- | --- |
| `path` | 是 | 字符串最长 1024，须匹配 `^skill-drafts/[a-zA-Z0-9][a-zA-Z0-9_-]*$`。路径相对于当前对话工作区，指向 `skill-drafts` 下的单层目录。 |
| `summary` | 否 | 字符串最长 4000。省略时取 `SKILL.md` frontmatter 中的 `description`。 |
| `exampleTask` | 否 | 字符串最长 4000。省略时不记录示例任务。 |
| `mergedInstalledRevisionId` | 否 | 长 1–512 的字符串。在已把当前安装版本合并到草稿目录后，传入当前绑定的同名已安装 Skill 的有效 `revisionId`。 |

Runtime 拒绝额外字段。工作区、`threadId` 和 `turnId` 由调用上下文确定。

成功返回 `success: true`，其 `contentItems` 中的 `inputText` 含 JSON 负载 `draftId`、`draftRevisionId`、`revisionNumber`、`installAs`，可能另有 `notice`。`installAs` 的值为 `new` 或 `update`。成功冻结会在 Runtime 草稿存储中保存校验后的文件快照和版本元数据。新版本会把同一草稿链下旧的未安装版本标记为 `superseded`，并触发回收。Runtime 还会尝试取消指向旧版本且仍在等待选择、分析授权或确认的安装操作。

失败返回 `success: false`，JSON 负载含 `error`、`issues`、`next_action`。`issues` 项含 `file`、`code`、`message`，可能另有 `line`。异常处理还可能附带 `systemCode`。参数无效或找不到线程对应的工作区时可得到 `INVALID_ARGUMENT`。绑定的安装版本需要合并时返回 `MERGE_REQUIRED`，并提供当前版本的信息供合并。传入的版本标识与当前绑定版本不匹配时返回 `STALE_REVISION`。冻结期间发现内容变化可得到 `DRAFT_STALE`，超出草稿存储配额可得到 `DRAFT_QUOTA_EXCEEDED`。

## 实现伪代码

**根据 Runtime 控制流重建的伪代码。** Runtime 校验草稿目录、`SKILL.md` 元数据和包内文件，检查名称保留与冲突、文件链接、路径越界、凭据、签名 URL 及最终 3D 产物等。提交同名已绑定草稿时还需核对已安装版本。若安装后的变更尚未写回工作区，或草稿基线的包哈希与当前已安装版本不同，需先按诊断合并工作区文件，再用返回的当前版本标识提交。Runtime 核对标识并重新验证包内容，具体合并由调用方完成。改名时，Runtime 将草稿作为新 Skill 处理，并在成功回执中给出 `notice`。

冻结时 Runtime 将文件复制到临时目录，并校验读取和复制后的文件哈希。文件版本与元数据写入成功后返回同一草稿链及新修订的标识。写入失败时清理本次暂存文件和未完成登记的版本。此调用在本地同步返回冻结结果。若回执中断，可先通过宿主的 `skills/drafts` 按原 `threadId` 查阅记录，再通过 `skills/draftDetail` 用 `draftId` 和 `draftRevisionId` 读取仍保留的快照。重新提交会创建新版本。

```python
def skill_draft_submit(call):
    try:
        args = validate_arguments(call.arguments)
        workspace = require_workspace(call.thread_id)
        draft = find_thread_draft(call.thread_id)
        candidate = validate_package(workspace, args.path, draft)
        binding = resolve_installed_binding(draft, candidate.name)

        if args.mergedInstalledRevisionId is not None:
            require_current_installed_revision(binding, args.mergedInstalledRevisionId)
        elif merge_required(binding, draft):
            return tool_result(False, merge_diagnostics(binding))

        revision = freeze_verified_package(
            candidate, draft, call.thread_id, call.turn_id, args, binding
        )
        cancel_superseded_pending_installations(revision)
        return tool_result(True, summarize_revision(revision))
    except DraftError as error:
        return tool_result(False, draft_diagnostics(error))
```

## 中性调用示例与核查依据

**根据已核实的参数约束构造的示例。** 调用前，当前工作区内已准备好 `skill-drafts/check-asset-names/SKILL.md` 及其引用的包内文件。

```json
{
  "path": "skill-drafts/check-asset-names",
  "summary": "检查目录中的资产命名规则。",
  "exampleTask": "检查 inputs 目录并列出不符合约定的文件。"
}
```

- 1.2.11 Windows x64 留存包 `runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。定位符为注册表 `UL`、合并表 `Vg`、入参 schema `Dx`、分派函数 `handleRuntimeDynamicTool`、包校验函数 `a8`、草稿控制器 `Vv.submit` 与草稿存储 `qv.freeze`。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [1.2.11 归档](../upstream/1.2.11/README.md)
- 已静态核查注册原文、目录校验、合并条件和冻结流程。草稿的实际冻结及桌面确认未做端到端调用。
