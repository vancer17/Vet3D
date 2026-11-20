# 导入或登记模型版本

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。宿主或 Agent 交付选定的 GLB，Runtime 将它发布为工作区模型家族的一个版本，或在支持复用的入口返回已有版本。目录更新、工作流产物挂接和 Studio 加载分别确认。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 用户发送 GLB 附件，宿主提交已登记的 GLB 产物，Agent 提交选定的导出文件，正式生成满足自动登记条件，或用户明确要求对已登记版本发起或继续免费重试。 |
| 上游与输入 | [参考素材接入](import-reference-materials.md)提供 `inputs/` 下的 GLB 和 `assetId`。[文件产物登记](register-file-artifact.md)提供 `assetId + artifactId`。显式登记接收选定 GLB 的实际 `exportPath`、家族名及适用的分类和工作流归属。本地修订交接已通过当前要求验收的导出，文件摘要和验收记录供调用方对账。免费重试入口使用准确的已登记版本文件名或已有的 `retryRequestId`，并由 Runtime 核对原版本的可信作业来源。 |
| 输出 | 工作区根目录下的 `hi3d-<家族名>_<序号>.glb` 及版本记录，或可复用的已有版本。记录含 `name`、`index`、`fileName`、相对 `path`、字节数和文件修改时间，可带分类、轮次、备注和来源。 |
| 完成条件 | 新版本已发布、元数据刷新成功并返回版本记录。复用时以入口返回的既有版本为准，显式工具会标记 `unchanged: true`。工作流完成、模型几何验收和 Studio 就绪各有独立条件。 |
| 下游交接 | [模型目录 RPC](interfaces/model-catalog-rpc.md)按工作区提供可选版本。[工作流图状态](workflow-graph-state.md)保存可选节点归属。[加载指定版本并确认](load-studio-revision.md#验收)用具体版本文件名确认 Studio 已加载它。 |

## Skill 绑定

工作区范围校验、文件校验和版本写入属于通用宿主能力。选择建模 Skill 后，Agent 按该 Skill 选择候选、提供分类及处理作业续查。归档的 `hi3d` Skill 要求复用已返回的 `registeredModel`。下载成功且回包只有文件时，从中选定 GLB 再登记。该 Skill 同时指导免费重试使用卡片注入的意图 ID，或在用户明确要求且只给出文件时准备意图。`image-to-assembly` 只在采用部件重建及装配流程时提供各部件下载和在位审查要求。 [Hi3D 通用建模 Skill](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) · [免费重试参考](../../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md) · [装配领域 Skill](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口)

## LLM Tools

| 工具 | 来源及在本节点的调用条件 |
| --- | --- |
| [`workspace_commit_model`](../../tools/workspace-commit-model.md) | Runtime 动态工具。有一个已选导出 GLB，且尚需发布成版本时使用。可带分类和本轮工作流节点 ID。 |
| [`hi3d_api`](../../tools/hi3d-api.md#已下载-3d-产物与登记) | Runtime 动态工具。正式 `generate_3d` 同时提供 `registerName` 和 `tag4` 时启用自动登记。普通作业独立调用 `query`、`wait`、`download` 时续查或取得文件，之后按需显式登记。已有 `retryRequestId` 时使用 `retry` 执行或续跑免费重试。用户只问次数时使用 `retry_quota`。 |
| [`model_retry_prepare`](../../tools/model-retry-prepare.md) | Runtime 动态工具。用户明确要求免费重试、工具在当前会话可用、只有确切版本文件名时，创建或取回本地意图。卡片已注入 `retryRequestId` 时直接使用该 ID。 |
| [`image_classification`](../../tools/image-classification.md) | Runtime 动态工具。按所选 Skill 记录新主体类别，或在显式登记返回 `classificationRequired` 时补分类并重试原导出。同轮重调也会更新该轮已登记版本的标签。 |

模型可见描述及通用参数由各工具页维护。安装包核实了上述工具的注册和分派。归档 Skill 说明 Agent 的调用条件。本机样本观察到多候选提示、显式版本登记和分类调用，免费重试方面观察到宿主额度查询。

## 宿主接口

| 名称 | 参数及结果 |
| --- | --- |
| `workspace/import` | Runtime 宿主 RPC。必填 `{assetId, name, sourcePath}`，成功返回 `{workspace, file}`。桌面入口要求已暂存在工作区 `inputs/` 的绝对路径。 |
| `workspace/commit` | Runtime 宿主 RPC。必填 `{assetId, artifactId, name}`，可带 `threadId`、`turnId`、`note`，成功返回 `{workspace, file}`。已核查的主进程白名单开放它，包内未定位到普通 renderer 的直接调用。 |
| `workspace/modelUpdated` | Runtime 通知。含 `assetId`、`name`、`file`、`workspace`，可带 `threadId`、`turnId` 和 `note`。新版本发布或已有版本元数据变化时可收到。 |
| `workspace/models` | Runtime 宿主 RPC。按 `assetId` 重新扫描模型目录，供版本查询及结果不明时对账。 |
| `model/retry.request` | Runtime 宿主 RPC。接收 `{assetId, fileName, clientRequestId, locale?}`，其中 `clientRequestId` 为客户端 UUID。返回重试记录，记录的 `requestId` 即后续使用的 `retryRequestId`。 |
| `model/retry.list`、`model/retry.cancelPending` | 前者按 `assetId` 对账后返回 `{retries}`。后者接收 `{assetId, requestId}`，只有消息交付仍为 `pending` 时才标为 `cancelled`。 |
| `model/retryQuota.read`、`model/retryChanged`、`model/retryQuotaChanged` | 额度 RPC 接收 `{assetId, fileName, refresh?}`。两类通知分别更新重试记录和额度。未知额度用 `remaining: null` 表达。 |

**根据安装包协议重建的宿主请求。** 示例假设源文件已暂存到项目对应的工作区。

```jsonl
{"type":"request","requestId":"import-model-demo","method":"workspace/import","params":{"assetId":"asset_demo","name":"sample","sourcePath":"D:/example/workspaces/asset_demo/inputs/sample-upload.glb"}}
```

**根据已核实 schema 重建的显式工具参数。** `exportPath` 指向本轮选定的导出文件。`tag4: null` 表示已判断没有适用的命名类别。

```json
{
  "name": "sample",
  "exportPath": "exports/hi3d-sample.glb",
  "tag4": null
}
```

## Hi3D 实现

### 决策

| 入口 | 源文件如何确定 | 版本策略 |
| --- | --- | --- |
| 聊天 GLB 附件 | `Wa` 将 GLB 标为待导入，`QI` 在发送时把已暂存的实际路径交给 `workspace/import`。 | 直接分配新序号。 |
| 已登记产物 | `workspace/commit` 用 `assetId + artifactId` 读取产物记录及路径。 | 直接分配新序号。 |
| 已选导出 GLB | `workspace_commit_model` 从调用线程解析工作区，使用明确给出的 `exportPath`。 | 先按作业来源及最后版本检查复用，再按需分配。 |
| 生成后的单个候选 | `hi3d_api` 从下载成功结果的 `files` 筛选工作区内可解析为普通文件的 GLB。候选恰为一个时才尝试自动登记。 | 与显式导出登记共用 `commitExport`。 |
| 已登记版本的免费重试 | 从意图取得原模型来源、新作业和固定输出目录；下载成功后筛选 GLB。 | 使用原家族和计划分类走自动登记，支持按重试记录查回已经发布的版本。 |

### 执行

**用户导入。** renderer 从附件显示名去掉 `.glb` 并清理文件名保留字符，取得家族名。Electron 主进程要求绝对源路径，分别取得工作区 `inputs/` 和源文件的真实路径，要求源文件是该真实目录的严格子项且为普通文件。Runtime 再检查工作区、源文件和 GLB 首部，然后调用 `Jg.importGlb`。成功后，renderer 将附件更新为登记版本的名称及其绝对路径，并作为 `mention` 交给会话。独立的 Studio 本地文件入口在已核查分支中直接读取网格。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

**按产物提交。** Runtime 接受角色为 `studio-save`、`blender-output` 或 `export-glb` 的 `.glb` 产物。`verifyArtifact` 重验受管路径、普通文件、字节数和 SHA-256。之后检查 GLB 首部，并把产物摘要传给 `importGlb`，供复制后复核。未知产物返回 `INVALID_ARGUMENT`。角色、后缀或 `verifyArtifact` 失败返回 `VALIDATION_FAILED`。GLB 首部无效、复制后摘要不符等写入阶段的异常经 `wrap` 返回 `INVALID_ARGUMENT`。 [文件产物登记与复核](register-file-artifact.md#验收)

**显式导出登记。** `workspace_commit_model` 先确认线程归属以及可选 `workflowNodeId` 是否属于当前线程、轮次的图。分类依次取显式 `tag4`、当前轮已有分类、严格同名家族的最新版本分类。显式 `null` 有效。缺分类返回 `classificationRequired: true`。随后 `commitExport` 检查导出路径是否位于 `exports/` 的词法范围以及 `realpath(exports)` 下，要求文件名以小写 `hi3d-` 开头，文件自身为非符号链接的普通文件。这条真实路径检查以解析后的 `exports` 为界。 [源代码与工具契约](../../tools/workspace-commit-model.md)

**本地修订交接。** 调用方用验收时选定的文件路径登记，候选摘要和几何检查结果由调用方保存并对账。`source` 由本次导出的实际路径和 SHA-256 命中原下载记录时附加。同家族分类和修订时引用的母版属于各自的记录，本地修订可按本地导出完成登记。后续需要展示或继续处理时，以登记回包中的确切版本为引用。 [导出路径与来源](../../tools/workspace-commit-model.md#文件身份与复用)

**下载与自动登记。** 正式 `generate_3d` 同时带 `registerName` 和 `tag4` 时启用自动登记。提供 `workflowNodeId` 时，Runtime 在执行生成前验证该节点属于本轮。得到下载结果后，Runtime 尝试从成功作业的 `jobPath` 和 GLB 摘要记录下载来源。命令成功且下载负载为 `success` 时，登记器筛选真实工作区内的普通 GLB。只有一个候选时，继续应用 `commitExport` 的导出约束。零个、多个候选或登记异常返回 `attention` 与 `phase: "register-model"`，保留原任务和文件清单。登记成功时附加 `registeredModel`。普通作业恢复时，可沿用原参数和路径重新调用组合 `generate_3d` 进入这条登记分支。独立调用 `query`、`wait` 或 `download` 只续查或取得原任务文件，取得 GLB 后再按需显式登记。`mdf_api` 或本地编辑产出的 GLB 同样可作为显式登记的候选。 [自动登记与续查](../../tools/hi3d-api.md#已下载-3d-产物与登记) · [MDF 工具](../../tools/mdf-api.md#参数与结果)

**分类更新。** `image_classification` 以 `threadId + turnId` 保存标签。同一轮再次调用会覆盖本轮记录，并更新工作区内归属于同一线程、同一轮次的现有版本 `tags`。刷新注册表之后，Runtime 发出 `runtime/imageClassification`，再对受影响的版本发 `workspace/modelUpdated`。这些目录通知没有顶层线程及轮次 ID，已有 GLB 文件和版本编号保持原样，renderer 不会由此触发新版本自动展示。 [分类工具](../../tools/image-classification.md#参数与结果)

#### 已登记版本的免费重试

1. **确定资格和意图。** Runtime 用准确的 `fileName` 查已登记版本。新建意图需要可验证的 Hi3D 来源、`kind: "model"`、原会话的兼容工具版本，以及当前账号与环境的有效额度。模型卡读取 `model/retryQuota.read`，按工作区刷新记录，点击时用客户端 UUID 发 `model/retry.request`，或复用已受理但中断的意图。纯文字请求由模型按已提供的工具调用 `model_retry_prepare`。管理器按环境、账号与 `retryRootId` 串行处理重试链，把意图保存在 `dataDir/model-retries.json`，固定新的 `.hi3d/retries/<ID>.json`、`exports/hi3d-retry-<ID>`、原家族和分类。原版本缺标签时，计划保存 `tag4: null`。 [免费重试准备](../../tools/model-retry-prepare.md)
2. **把意图交给原会话。** 模型卡通过后台发送携带原会话 ID 和 `retryRequestId`。Runtime 分别记录消息交付状态和作业执行状态。新建轮次时向 Codex 注入准确文件名、意图 ID、来源任务 ID 和重试链根 ID。模型只需把意图 ID 交给 `hi3d_api(action="retry")`，由 Runtime 校验归属并读取固定计划。 [会话中的重试上下文](llm-context.md#校验后转发给-codex)
3. **提交、续查并登记。** 脚本校验原作业和账号环境。首次执行由脚本独占建立子作业文件，再走免费重试接口，POST 请求用根任务 ID 填 `parentGenerateId`。服务返回的子任务 ID 先写入子作业，再查询和下载。已有子任务 ID 时，原 `retryRequestId` 进入同一个子作业续查。下载成功尝试自动登记，返回 `registeredModel` 后可将该版本交给后续验收。若模型已发布而重试回执丢失，Runtime 可按家族、子任务 ID、子作业路径、重试链根 ID、账号、环境及原线程对账，并返回已有版本。显式登记成功或复用已有版本时也会触发该工作区的重试对账。 [重试工具契约](../../tools/hi3d-api.md#参数与结果)

**按安装包协议重建的宿主请求。** 模型卡发送前已取得准确的登记文件名。

```jsonl
{"type":"request","requestId":"retry-intent-demo","method":"model/retry.request","params":{"assetId":"asset_demo","fileName":"hi3d-sample_2.glb","clientRequestId":"24344314-d77b-4b06-9413-5c42fa0c38a1","locale":"zh"}}
```

**按已核实 schema 重建的工具参数。** 此处的 UUID 来自宿主记录的 `requestId`，也可来自 `model_retry_prepare` 的 `retryRequestId`。

```json
{"action":"retry","retryRequestId":"66dd624b-f618-4da0-b991-dda7a2d1a7bb"}
```

**根据安装包重建的实现伪代码。** 从 LLM 调用进入 Runtime 开始，展示对账、同意图恢复和发布。工具响应封装、消息交付状态及异常分派已省略。

```javascript
async function executeRetry(threadId, turnId, retryRequestId) {
  const record = retries.getForThread(retryRequestId, threadId);
  retries.reconcileRegistered(record.assetId);
  const registered = retries.completedResult(retryRequestId);
  if (registered) return registered;

  const plan = retries.loadExecutionPlan(retryRequestId, threadId);
  retries.bindTurn(retryRequestId, turnId);
  const jobResult = await runRetryCli(plan);
  rememberVerifiedDownloads(record.assetId, jobResult);
  const result = jobResult.exitCode === 0
    ? await registerGeneratedModel(record.assetId, threadId, turnId, plan, jobResult)
    : jobResult;
  retries.complete(retryRequestId, result);
  return result;
}
```

**导出复用。** `commitExport` 按实际导出路径和当前 SHA-256 匹配已记录的下载来源，命中才给版本附加 `source`。来源缺失或不符时，仍可按本地导出处理。同一家族按大小写折叠比较，先找同 `taskId`、`ownerId`、`environment` 的版本。此分支核对的是本次导出与下载摘要，以及旧版本的来源标识。若未命中，再比较最大序号版的大小和 SHA-256。候选带下载来源时，这一步还要求最大序号版的任务 ID 一致。复用保留原版本元数据。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

**共用版本发布。** `Jg.importGlb` 校验工作区，规范化家族名并去掉已有 Hi3D 前缀。扫描根目录匹配 `^(.+)_(\d+)\.glb$` 的条目名，按忽略大小写的家族名找最大数字序号，再加一。旧版无前缀文件也参与编号。复制到同目录的 `.model-<UUID>.glb` 后，检查扩展名、至少 12 字节首部、`glTF` 魔数、版本 2 及声明长度是否等于实际长度。有预期摘要时，再计算临时文件的 SHA-256。同步改名发布正式版本，`EPERM` 或 `EBUSY` 最多尝试三次。退出时清理未改名的临时文件，源文件保留。改名成功后更新内存的工作区时间戳和版本元数据，安排注册表写入。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

**根据安装包重建的实现伪代码。** 入口已完成工作区、候选路径、角色和适用分类的判断。代码展开复用顺序和共用写入器。刷新及通知由各入口处理。

```javascript
function commitExport(workspace, family, exportPath, metadata) {
  const download = findDownloadRecord(workspace, exportPath);
  const source = download && sha256(exportPath) === download.sha256
    ? download.source : undefined;
  const versions = findFamilyVersionsIgnoringCase(workspace, family);
  const bySource = source && versions.find(version =>
    version.source?.taskId === source.taskId
    && version.source.ownerId === source.ownerId
    && version.source.environment === source.environment
  );
  if (bySource) return bySource;

  const latest = highestIndex(versions);
  if (latest && latest.size === stat(exportPath).size
      && (!source || latest.source?.taskId === source.taskId)
      && sha256(join(workspace.cwd, latest.path)) === sha256(exportPath)) {
    return latest;
  }
  return importGlb(workspace, family, exportPath, { ...metadata, source },
    source ? download.sha256 : undefined);
}

function importGlb(workspace, family, sourcePath, metadata, expectedSha256) {
  const name = normalizeFamily(family);
  requireGlbExtension(sourcePath);
  const index = nextIndexFromRootNames(workspace.cwd, name);
  const fileName = `hi3d-${name}_${index}.glb`;
  const temporary = join(workspace.cwd, `.model-${uuid()}.glb`);
  const target = join(workspace.cwd, fileName);

  try {
    copyFile(sourcePath, temporary);
    validateGlbHeader(temporary);
    if (expectedSha256) requireHash(temporary, expectedSha256);
    renameWithBusyRetry(temporary, target);
  } finally {
    if (exists(temporary)) removeFile(temporary);
  }
  saveVersionMetadata(workspace, fileName, metadata);
  return versionFromFile(workspace, name, index, fileName, metadata);
}
```

### 验收

1. **确认正式文件和元数据。** 新版本已改名落盘，入口等待注册表刷新后发布 `workspace/modelUpdated` 并返回版本。目录扫描本身能发现符合命名规则的根目录文件，即使部分元数据尚未持久化。文件头通过也只覆盖容器首部。隔离验证中的 12 字节合成文件可以通过，模型解码、几何和外观各自验收。调用方需要将候选验收依据附于正式版本时，可用回包路径复验该版本与验收件的摘要。按原作业复用若返回不同字节的版本，按回包指定的文件核对下游用途。 [模型目录 RPC](interfaces/model-catalog-rpc.md) · [文件身份与复用](../../tools/workspace-commit-model.md#文件身份与复用)
2. **确认工作流归属。** 显式工具带 `workflowNodeId` 时，可在刷新之前挂接模型。复用分支也可挂接，随后直接返回 `unchanged: true`，没有本次版本刷新或新通知。自动登记在刷新之后做显式挂接，复用时同样等待刷新。带线程和轮次的模型通知还可为已有图补归属。已有显式归属会保留，新产物可默认归通用图的 `execute` 节点，或唯一运行中的叶节点，其余保持未分配。挂接产物与节点完成分别记录。 [工作流状态发布与续接](workflow-graph-state.md)
3. **确认展示状态。** renderer 只向当前资产的模型目录合并版本。普通附件导入通知和分类更新通知只更新目录。带线程和轮次且属于当前资产的通知可选中版本并排队自动展示。App 还核对会话、轮次、导航和窗口状态。实际就绪以与本次加载匹配的 `modelLoaded` 或加载确认回执为准。 [加载指定版本并确认](load-studio-revision.md#验收)

## 完成与恢复

| 情形 | 已核查处理 |
| --- | --- |
| 普通生成仍为 `pending` 或提交状态不明 | 保存原 `jobPath` 和已知任务 ID。沿原作业查询、等待或下载。需要继续自动登记时，沿用带登记参数的组合调用。取得文件后单独核对有无版本回执。 [作业持久化与恢复](../../tools/hi3d-api.md#作业持久化与恢复) |
| 模型卡创建意图的回执不明，或消息尚未送达 | renderer 重新查 `model/retry.list`，用原 `clientRequestId` 找回记录。首次刷新某工作区时，会对尚处于消息交付 `pending` 的旧记录调用 `model/retry.cancelPending`。该动作只将这些意图的交付状态标为 `cancelled`。 |
| 免费重试 `pending`、中断或回执丢失 | 组合调用返回 `pending` 时，重试记录的执行状态可为 `interrupted`，保留原 `retryRequestId` 和子作业供续跑。Runtime 先对账已登记结果，再按原意图恢复。提交受理不明且没有子任务 ID 时返回 `attention` 和 `submission_uncertain_without_task_id`，记录进入 `submission_uncertain`。保留原意图和作业。归档 Skill 要求停止重复提交，也禁止改走付费生成。 |
| 多候选、无候选或自动登记失败 | 保留返回的任务和文件清单。多候选时由调用方选定 GLB。路径或摘要失效时先核对原下载记录与文件，再向显式登记交付。免费重试取到候选时，沿用原意图、导出和计划家族名，符合来源条件的显式登记可让 Runtime 对账到原重试。 |
| `classificationRequired` | 补齐主体分类后沿用原 `name` 和 `exportPath`，继续登记同一导出文件。 |
| 本地修订导出在登记前发生变化 | 调用方根据实际路径和摘要核对候选。按变更复查受影响的验收项，再交当前选定文件登记。 |
| 产物校验失败 | 按原 `artifactId` 核对文件及摘要。文件内容发生变化时，按新内容登记产物，再提交相符版本。 |
| 正式文件已发布，注册表刷新失败或回执不明 | 先检查根目录、`workspace/models`、注册表和来源记录。模型文件或显式工作流挂接可能已经发生。按原文件重试显式登记可走复用判断，收到 `unchanged` 时仍需核对原元数据是否已落盘。直接重送 `workspace/import` 或 `workspace/commit` 可能分配另一个序号。 |
| 版本已登记，候选不合格或 Studio 加载失败 | 保留原版本和来源。需要修订时将修改后的导出作为新候选，再按相应入口审核和登记。同一版本的加载失败可由 Studio 单独重试。 [加载失败与恢复](load-studio-revision.md#完成与恢复) |

## Vet3D 迁移与核查范围

Vet3D 可定义独立于 LLM、生图及 3D 供应商的版本记录，包含工作区 ID、家族 ID、版本 ID、原件引用、内容摘要、可选来源作业与分类、工作流归属。宿主在受管路径内选定文件，可按具体格式验证容器和内容。版本 ID 用于交接和重试，文件名用于展示及读取。主动导入、按内容复用、按作业复用分别定义语义。

对于并发编号和结果不明，可在宿主中用版本发布意图 ID 记录选定源、编号分配、文件发布及元数据提交阶段。由同一个意图续查或补齐已有结果。模型重试可持久化原版本引用、独立的重试意图、服务受理标识、候选和已发布版本之间的关系。供应商的费用、额度和任务 ID 由适配器翻译，消息交付、远端作业、文件下载和版本发布各自验收。文件和元数据均已确认时再发送版本事件。图的归属、版本被用户选择和 Studio 已加载由对应组件单独确认。这些意图持久化、编号约束及对账规则属于 Vet3D 设计。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与摘要 | 核查使用安装事务备份中的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Renderer 与 main | `out/renderer/assets/index-CDPCug_K.js` 内 `1105284` 为家族名处理，`1590687` 为发送时导入，`1108479` 和 `1108969` 为目录通知处理及合并，`4735895` 为自动展示门禁，`4711410` 为 Studio 就绪确认。`out/main/index.js` 内 `183286` 为导入真实路径检查，`82454` 和 `182881` 为 `workspace/commit` 契约与白名单。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime | `runtime/dist/runtime.mjs` 内 `2722874` 为用户导入，`2723655` 为产物提交，`3197771` 为显式工具分派，`3201579` 为自动登记，`2693701` 为下载来源记录，`2695691` 为导出复用，`2691512` 是共用写入器参数锚点，`2703260` 为取号，`2713155` 为 GLB 校验，`3207748` 为版本通知挂接，`3072936` 是图产物挂接的参数锚点。偏移均为原始文件或解开 ASAR 成员内的零基字节位置。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 免费重试与分类的安装包静态核查 | renderer 成员 `1155033` 为记录刷新，`1156331` 为后台发送，`1157206` 为请求和失败对账，`1157523` 为通知处理。Runtime `2714088` 为重试 RPC 分派，`2557748` 为已登记版本对账，`3192199` 为重试前对账，`3200505` 为显式登记后对账，`2678199` 和 `3187990` 为分类元数据更新及工具调用。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 已验证 | 以替身执行从安装包提取的实现，复现了编号、重复导入、两层复用、摘要和 GLB 首部检查、临时文件清理、单候选及多候选分支、图归属和就绪门禁。本机 rollout 记录多候选返回登记阶段提示，随后显式登记选中 GLB，并另行加载至 Studio。 [多候选返回](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) · [显式登记](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:148>) · [Studio 加载](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:167>) |
| 本地修订运行与留存文件 | 两次修订提交选定导出后，分别返回 `hi3d-猫_2.glb`、`hi3d-猫_3.glb`，两个回包均为 `tags.tag4: null`。事后复算，两份留存导出的 SHA-256 各自与对应的正式版本一致。两版通过独立调用按确切 `fileName` 加载，回包确认 `state.ready: true`。 [第一次登记与加载](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:486>) · [第二次登记与加载](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>) |
| 本机实际观察 | 桌面日志记录了宿主 `model/retryQuota.read`。当前抽查样本未观察到卡片提交或模型调用免费重试。 [额度查询日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261113T083555Z-17988.log:68>) |
| 待实测 | 完整桌面中的用户 GLB 导入、宿主 `workspace/commit`、唯一候选自动登记成功、真实磁盘刷新故障及自动展示通知时序。免费重试的卡片送达、远端受理、同一意图续查、登记对账及最终版本质量也待端到端实测。 |
