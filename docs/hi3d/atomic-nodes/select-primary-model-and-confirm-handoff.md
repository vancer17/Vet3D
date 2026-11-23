# 选定主模型并确认交接

本节点根据本轮用途选定一份符合要求的模型，确认工作区中的确切版本，并按交付目标核对所需的完成条件。执行链根据 Hi3D Agent 1.2.11（Windows x64）、随包 Codex 0.166.0 的接口和 Skill 归纳。分支的证据范围见[核查证据](#核查证据)。

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 上游交付一份或多份可读候选，或组合生成回包附有 `registeredModel`。本地修订的可用导出也可进入。 |
| 输入 | 当前工作区、模型家族、本轮用途、必保特征、候选文件及适用性证据。云端产物保留原作业引用，已登记产物保留确切文件名。按交付要求确定是否需展示、本人确认、实际另存或接收回执。 [逐项落盘与清单复验](download-and-persist-artifact-manifest.md) · [候选适用性](check-model-candidate-suitability.md) |
| 输出 | 与所选候选匹配的可读取文件引用、用途与证据范围，以及所需交付条件的确认结果。需要工作区正式版本时一并交付对应的登记结果。Hi3D 以当前 `assetId` 和登记结果的确切 `fileName` 标识版本。 |
| 完成条件 | 核对所选候选与实际交付文件。普通新建模型按 Hi3D 通用 Skill 登记工作区正式版本，核对版本与候选的对应关系。仅交付普通文件或 ZIP 时，用实际相对路径提供可定位的文件。需要展示、用户验收、实际另存或外部接收时，分别取得对应证据。 |
| 下游 | 聊天交付使用实际相对路径。修订、绑定或动画接收固定版本、目标用途与保留项，按各自的接口验证输入。 [Studio 加载](../infrastructure/workspace/load-studio-revision.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

工作区 `AGENTS.md` 提供家族版本、`exports/` 导出登记、按需使用 Studio，以及通过实际文件名与相对路径交付的通用规则。宿主负责路径解析、版本发布及视窗加载。 [目录与登记规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:5>) · [展示与交付规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:37>)

| Skill | 选用条件与执行范围 |
| --- | --- |
| [Hi3D 通用建模](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | 普通图生 3D 使用。取得 `registeredModel` 时核对并复用。只有导出文件时选定 GLB 再显式登记。缺分类时补充后沿用原文件。 |
| [图片到高精度组装模型](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口) | 选用部件重建或装配路线后，按对应阶段的在位、接口、干涉及视觉证据决定能否交给依赖该件的下游。 |
| [骨架适配与重定向](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/SKILL.md:20>) | 需要绑定、重定向或局部权重修复时，按该入口检查已有骨架或准备新绑定输入。该入口取自安装包。 [仓库快照范围](../upstream/1.2.11/README.md) |

## LLM Tools

Runtime 动态工具、Studio 动态工具与随包 Codex 工具分别注册。下表记录业务调用条件。模型可见描述、schema 与实现由独立工具页维护。 [工具索引](../tools/README.md)

| 工具说明 | 用途与触发条件 |
| --- | --- |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`image_classification`](../tools/image-classification.md) | 已选定 GLB 且需发布时显式登记。缺少可用分类或返回 `classificationRequired` 时，根据主体证据补分类，再用原导出恢复登记。 |
| [`studio_load_revision`](../tools/studio-load-revision.md) · [`studio_get_state`](../tools/studio-get-state.md) | 需要展示时用当前 `assetId` 和确切 `fileName` 加载。确认当前视窗或恢复未明加载时读状态。 |
| [`studio_capture_view`](../tools/studio-capture-view.md) · [`view_image`](../tools/view-image.md) | 需要画面证据时按版本和方向取证。取得截图的可信本地路径后可用 `view_image` 读像素。指定方向也可以按确切 GLB 本地渲染。 |
| [`workflow_report`](../tools/workflow-report.md) | 本轮使用 Skill 且有适用工作流图时报告进度。需要补挂归属时，用确切已登记文件名和节点 ID 上报 `artifact`。 |
| [`user_interaction`](../tools/user-interaction.md) · [`request_user_input`](../tools/request-user-input.md) · [`request_user_input_async`](../tools/request-user-input-async.md) | 存在影响交付的候选取舍或要求本人确认时，按任务模式和客户端能力使用相应入口。需要本人接受时，应取得真实用户答复。 |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) · [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | 按需核对实物、大小或摘要。Code Mode 单元用 `cell_id`，本地进程用 `session_id` 续查。 |
| [`hi3d_api`](../tools/hi3d-api.md#已下载-3d-产物与登记) · [`model_retry_prepare`](../tools/model-retry-prepare.md) | 上游生成或作业恢复沿原 `jobPath`。用户明确请求且原版本满足资格时，以 `retryRequestId` 进入免费重试分支。 |
| [`studio_arrange`](../tools/studio-arrange.md) · [`studio_export_3mf`](../tools/studio-export-3mf.md) | 仅打印交付需要时调用。摆盘事件、面板触发、文件落盘和切片器开启分别确认。 |
| [`mdf_api`](../tools/mdf-api.md) · [`skill_capture_suggest`](../tools/skill-capture-suggest.md) | 前者用于下游选定的绑骨、网格或打印专项。后者可在完成后记录可复用流程建议。 |

`workspace/models` 和 `artifact/register` 属宿主 RPC，用户点击普通 GLB 链接走 `file:saveAs` IPC。 [版本目录接口](../infrastructure/workspace/interfaces/model-catalog-rpc.md) · [文件产物登记](../infrastructure/workspace/register-file-artifact.md) · [桌面另存](../infrastructure/workspace/preview-and-deliver-files.md#普通保存与-studio-下载)

## Hi3D 实现

### 决策

| 已知结果 | 下一步 |
| --- | --- |
| `attention` 且 `phase: "register-model"` | 保留原 `jobPath`、`task_id` 和 `files`。先核对正式版本是否已存在。选定可用候选且尚未发布时，走显式登记。 |
| 已有 `registeredModel` 或确切的工作区版本 | 以版本目录定位实际文件，核对其与所选候选及用途证据的对应关系。满足交付要求的版本直接使用。缺证据时按该文件补查。 |
| 已下载或本地导出，存在可用 GLB | 根据用途、已核实的来源角色及验收证据固定一份候选。多个候选有实质取舍时，补证或请用户选择。 |
| 任务仍待完成、受理未明、候选不可读或用途证据不足 | 保留原引用，回到对应的原作业恢复、候选核对或修订，待条件满足后继续。 |

候选依据来自具体文件。大小和声明字段支持对应的文件检查，作业级封面提供作业外观线索。聚合 `artifact` 顶层继承了第一条文件记录的字段。列表顺序用于定位文件，来源角色以能复核的记录为准。主图、补充参考、方向和必保特征通过上游定稿和验收记录交接。补取画面时关联实际视角、文件或版本。 [候选适用性](check-model-candidate-suitability.md) · [整组参考图定稿](review-and-finalize-view-set.md) · [版本视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md)

### 执行

1. **从上游取得发布结果。** 正式 `generate_3d` 带 `registerName` 与显式 `tag4`，或 `retry` 已解析出固定登记计划时，组合调用在进程退出码为 `0` 且下载结果为 `success` 后筛选工作区内的普通 GLB 列表项。恰有一项时尝试发布。重复路径也按项计数。零项、多项或登记异常均可返回 `attention/register-model`。成功回包附 `registeredModel`，候选适用性仍以证据确认。 [自动登记接口](../tools/hi3d-api.md#已下载-3d-产物与登记)
2. **显式发布已选候选。** 向 `workspace_commit_model` 传实际家族名与确切 `exportPath`。可传 `tag4`，其中 `null` 是有效分类。省略时 Runtime 先查当前轮分类，再查同家族最新版本。返回 `classificationRequired` 时按主体证据补分类并重试同一导出。仅在图内归属明确时传 `workflowNodeId`。 [登记工具](../tools/workspace-commit-model.md) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md#执行)
3. **核对发布身份。** 用当前 `assetId` 和 `file.fileName` 或 `registeredModel.fileName` 定位正式文件。登记可能先按同可信任务返回已有版本，再尝试按最新同摘要版本复用。要确认 `unchanged: true` 对应本次所选文件，应核对真实文件、SHA-256 和适用的来源元数据。发现差异时保留原候选并对账。 [复用判据](../tools/workspace-commit-model.md#实现伪代码) · [工作区版本目录](../infrastructure/workspace/query-assets-and-model-versions.md)

**按安装包自动登记分支重建的伪代码。** 以下合并展示登记计划已确定后的调用门槛与方法逻辑。`registration_attention` 保留原作业引用和下载清单，供调用方对账或选件。 [组合回包契约](../tools/hi3d-api.md#已下载-3d-产物与登记)

```python
def finish_automatic_registration(result, plan):
    downloaded = try_read_stdout_object(result)
    if result.exit_code != 0 or downloaded is None or downloaded.result != "success":
        return result

    entries = eligible_workspace_glb_entries(downloaded.files)
    if len(entries) != 1:
        return registration_attention(result, downloaded)

    try:
        version = commit_export(entries[0], plan)
        flush_registry()
        attach_optional_workflow_owner(version, plan)
        notify_new_registration_if_needed(version)
    except Exception as error:
        return registration_attention(result, downloaded, error=error)

    return attach_registered_model(result, downloaded, version)
```

**根据已核实接口重建的中性请求。** 假设已验收 `exports/hi3d-example.glb`，当前尚未登记，且主体无适用分类。 [登记参数](../tools/workspace-commit-model.md#参数与结果)

```javascript
text(await tools.workspace_commit_model({
  name: "example",
  exportPath: "exports/hi3d-example.glb",
  tag4: null,
}));
```

### 验收

| 本轮要求 | 完成判据 |
| --- | --- |
| 提供文件引用 | 工作区内能定位所选文件，交付使用实际文件名与相对路径。需要正式版本时，核对登记回执和实际文件。若要求实际另存，取得 `file:saveAs` 的 `canceled:false` 与保存路径，或适用的下载完成事件。 |
| 在 Studio 展示 | 用当前 `assetId` 和确切 `fileName` 加载。核对回包顶层 `loaded:true`、版本身份，以及 `state.ready:true` 和状态中的版本身份。若已通过状态读取确认目标版本就绪，可复用该证据。 |
| 画面、尺寸或本人确认 | 按要求取得具体版本的图像、方向或测量依据。Studio 尺寸要核对单位来源。需要本人接受时取得针对该版本的真实用户答复。 |
| 交给本地处理、绑定、动画或打印 | 按目标交付固定版本或可追溯的派生文件、用途和保留项，需接收回执时核对回执。绑定、动作及打印产物各有后续验收。 |
| 更新工作流图 | 有相应图时，在当前节点的所需条件满足后报告完成。图回执确认图状态。 |

**根据已核实接口重建的中性请求。** 假设已登记回包确认 `hi3d-example_2.glb`，且本轮需要展示。 [加载与就绪确认](../tools/studio-load-revision.md#参数与结果)

```javascript
text(await tools.studio_load_revision({
  assetId: "asset_demo",
  fileName: "hi3d-example_2.glb",
}));
```

随包人形动画路线接收固定模型、目标动作和帧率、对象及保留项。选用服务绑骨时，可从选定版本派生身体 GLB，再用返回件做回迁、权重及动作验收。 [动画交接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/rigging.md:3>) · [服务绑骨输入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/runtime-service-rig.md:7>)

## 完成与恢复

| 情况 | 恢复和交接条件 |
| --- | --- |
| 上游 `pending` 或受理不明 | 保留原 `jobPath`、计划和诊断。有任务 ID 时续查同一任务，在原绑定目录取件。缺 ID 时先核对受理。外层仍给原 `cell_id` 时续读该单元。 [等待与交接](schedule-wait-and-handoff.md) · [下载来源](confirm-download-source-and-recovery.md) · [逐项恢复](download-and-persist-artifact-manifest.md#完成与恢复) |
| 候选不足、来源存疑或验收失败 | 保留原候选及待查项，按确切文件补证或修订。已有登记时保留旧版供追溯，新候选通过后再发布。 [候选恢复](check-model-candidate-suitability.md#完成与恢复) |
| 分类缺失、登记回执不明或复用结果存疑 | 补分类时沿用原家族和导出。回执不明时先按文件与摘要检查目录和来源。匹配的正式版本可复用，需要恢复时用原导出走显式工具。 [登记恢复](../infrastructure/workspace/import-or-register-model-version.md#完成与恢复) |
| 已登记，Studio 加载未就绪、取消或超时 | 保留正式版本，先读状态以识别迟到结果。仍需展示时用同一确切文件名恢复。直接读文件的接收方按其文件和质量要求接续。 [Studio 恢复](../infrastructure/workspace/load-studio-revision.md#完成与恢复) |
| 仍需本人确认、另存或接收回执 | 保留同一版本和接收方，等所需回执。消息发出可记录引用已提供，实际保存及外部接收分别确认。 [文件交付验收](../infrastructure/workspace/preview-and-deliver-files.md#验收) |

## Vet3D 迁移与核查范围

用供应商无关的记录保存工作区、家族、选定候选及其摘要、可选的正式版本和作业引用、用途、保留项和证据缺口。每项交付证据关联实际文件身份。五视图验收关联实际 `front / back / left / right / top` 与所检版本，并记录不可见或需推断的区域。

**Vet3D 设计伪代码。** 先确认候选和版本身份，再按本轮要求推进交付。各条件的顺序取决于接收方式，例如用户收到引用后再另存。

```python
def confirm_handoff(context, source, assessment):
    if source.needs_recovery:
        return pending_original_job(source.job_ref)

    selected = assessment.selected_candidate
    if selected is None or assessment.required_evidence_missing:
        return retain_for_review(source.candidates, assessment.reasons)

    revision = None
    if context.delivery_requirements.workspace_revision:
        revision = find_registered_match(context.workspace, selected)
        if revision is None:
            publication = register_selected_export(context.family, selected)
            if publication.needs_reconciliation:
                return pending_registration_reconciliation(selected)
            if publication.failed:
                return retain_unpublished_candidate(selected, publication.error)
            revision = publication.revision

        if not verify_revision_identity(revision, selected):
            return pending_registration_reconciliation(selected)

    handoff = advance_required_steps(context.delivery_requirements, selected, revision)
    return record_handoff(selected, revision, assessment.evidence, handoff)
```

## 核查证据

| 证据层 | 核实结果与范围 |
| --- | --- |
| 安装包静态核查 | `runtime.mjs` 的 `registerGeneratedModel`（`3201579`）、`commitExport`（`2695691`）和显式分派（`3197771`）覆盖候选登记。ASAR renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 的 `4711410`、`1585327` 分别对应加载确认和聊天另存调用附近。偏移为原文件或成员的零基 UTF-8 字节位置。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，ASAR 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| 规则与模型可见声明 | 仓库归档的 `hi3d`、`image-to-assembly` Skill 与安装包副本字节一致。活跃会话第 2 行保存 `additional_tools`，第 19 行记录读取通用 Skill。声明证明模型可见范围，实际调用以请求和回包确认。 [Skill 归档](../upstream/1.2.11/README.md) · [会话声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>) · [Skill 读取](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>) |
| 隔离复现 | 使用安装包方法和替身依赖复现单一列表项自动登记、重复项、刷新错误、同可信任务优先复用，以及同工作区加载回包的顶层和快照可能指向不同版本。证据覆盖这些局部控制流。 [自动登记](../tools/hi3d-api.md#核查依据) · [版本复用](../tools/workspace-commit-model.md#核查依据) · [加载回包](../tools/studio-load-revision.md#核查依据) |
| 待端到端实测 | 唯一 GLB 自动登记后的完整交接、真实登记回执丢失、实际视窗竞争、用户选择候选及确认、截图、另存和打印交付。历史样本为静态 GLB，四足绑定、权重和动作输出需用下游样本验证。 |

### 历史运行观测

- **候选与选择。** 三视图猫任务返回两份 GLB 和一份作业 WebP，自动登记回 `attention/register-model`。Agent 查看作业级封面、核对两份 GLB 的声明后，显式登记 `exports/hi3d-cat-multiview/hi3d-result-0/hi3d-api-result-0.glb`。事后才从下载记录确认该文件对应 `model3DGlbUrl`，另一件对应 `model3DPreviewUrl`。具体排序依据与逐件渲染未见历史记录。 [原回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) · [显式登记实录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>) · [候选对账](check-model-candidate-suitability.md#验收)
- **发布、展示及图状态。** 第 148 行取得 `hi3d-猫_1.glb`，所选导出与正式文件的 SHA-256 同为 `b217a0365f827657cabcda90aa427d5830e153cd4a7cf3271831ff1c568fb9f5`。第 154–160 行确认文件存在且 Studio 尚未就绪，第 164–167 行显式加载，第 171–175 行更新同轮图，第 180 行回复文件链接。样本证明已发出引用，用户完成另存尚无回执。 [登记回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:148>) · [文件与状态](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:160>) · [加载回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:167>) · [工作流落盘](<D:/download/.sparc3d-runtime/environments/prod/workflow-graphs/39c03c1881feb41ce45e56a40380876211e366e02a24e8cfca31dd7a3e5f69c5.json>) · [回复实录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:180>)
- **本地修订及条件工具。** 两次修订分别显式登记并加载 `_2`、`_3`，继承家族分类，登记回包无云端 `source`，加载后记录了 Skill 建议。用户指出 `_2` 脸部缺陷后另行修订。首次交付未触发候选选择面板、Studio 截图或外部接收回执。后续修订的用户询问用于澄清 Blender 路径。 [首次修订](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:486>) · [用户反馈](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:519>) · [第二次修订](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>) · [依赖澄清](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:222>)
