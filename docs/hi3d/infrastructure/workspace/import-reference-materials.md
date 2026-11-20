# 接收并导入参考素材

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。桌面接收用户附件、解析工作区归属、保留原件并按需生成会话预览。已准备的附件引用由会话宿主组装进本轮输入。图片的主体、视角和建模角色由下游结合用户指令判定。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 用户用选择器选取文件、在聊天输入区拖放文件或粘贴文件。宿主也可把已暂存的文件与实际路径交回编辑器，例如首页示例发送失败后的回填。 |
| 上游与输入 | 浏览器 `File`、可选原生路径和 MIME，以及当前会话或新对话草稿的上下文。既有会话使用[已打开且与活动线程匹配的工作区](open-workspace.md)，新对话在发送前[领取草稿工作区](acquire-and-recycle-draft-workspace.md)。 |
| 输出 | 工作区 `inputs/` 下的原件和可选 JPEG 预览。renderer 为附件保留显示名、会话输入类型及实际路径。GLB 提交前另行登记，交接使用登记后的版本路径。 |
| 完成条件 | 每个接纳项均有写入回执或原有暂存路径。待写入的 `pendingFile` 尚不能作为可读引用交付。发送时所有附件准备完毕，`missingAttachments` 为 0，发送草稿进入 `ready`。轮次受理另行确认。 |
| 下游交接 | [构建当前轮的工作区上下文](llm-context.md#组装本轮正文和附件)把附件与用户正文组装为类型化输入。[素材与模型版本查询](query-assets-and-model-versions.md)按路径复查原件。[确认建模主体](../../atomic-nodes/confirm-modeling-subject.md)使用可读取的图像及用户说明。进入 3D 文件列表前还须另核实际文件的格式、大小和内容。 |

## Skill 与 LLM Tools

附件接入、类型判断及落盘由桌面宿主执行，适用于普通会话。选用建模 Skill 后，下游再应用对应的参考图角色、命名和评审规则。本节点的直接调用为宿主 IPC 和 RPC。若下游需要重新读取全分辨率原件，可按实际路径调用看图工具。 [通用建模 Skill](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [看图工具说明](../../tools/view-image.md)

## 宿主接口

| 名称 | 类型 | 参数或结果 |
| --- | --- | --- |
| `files.pathForDroppedFile(File)`、`files.importFile({assetId}, File)` | preload 桥接 | 用 Electron `webUtils.getPathForFile` 获取原生路径。`importFile` 用路径、basename 和可选 MIME 构造 `file:importPath` 请求。 |
| `file:importPath` | Electron IPC | 要求 `assetId` 和非空绝对 `sourcePath`，后者最长 4096 字符。可选 `mimeType`。preload 一并传入 `fileName`，保存时由主进程重新从真实源路径取 basename。成功返回 `{fileName, path}`。 |
| `file:writeInput` | Electron IPC | 要求 `assetId`、非空 `fileName` 和 `ArrayBuffer` 类型的 `bytes`，可选 `mimeType`。成功返回 `{fileName, path}`。 |
| `workspace/acquireDraft`、`workspace/open` | Runtime 宿主 RPC | 前者在新对话首发时取得 `assetId`，后者供主进程在目录缓存未命中时解析 `cwd`。 |
| `workspace/import` | Runtime 宿主 RPC | 只有待登记的 GLB 附件发送时调用。传 `{assetId, name, sourcePath}`，成功返回 `{workspace, file}` 并发布 `workspace/modelUpdated`。 |
| `localImage`、`localAudio`、`mention` | 会话输入类型 | 图片、音频和通用文件路径引用，由宿主随 `turn/start` 或续轮输入交付。 |

两条写入 IPC 均要求 `assetId` 为非空字符串，最长 256 字符。`file:writeInput` 的 `fileName` 最长 255 字符，可选 MIME 字符串最长 255 字符。返回的 `path` 为绝对路径。已知路径的展示读取另由 `file:resolveImagePreview` 处理。 [图片预览读取 IPC](interfaces/image-preview-ipc.md)

**按安装包重建的 preload IPC 请求。** 路径示例来自用户所选 `File`。

```javascript
const original = await ipcRenderer.invoke("file:importPath", {
  assetId: "asset_demo",
  fileName: "front.png",
  sourcePath: "D:\\photos\\front.png",
  mimeType: "image/png",
});
```

## Hi3D 实现

### 决策

1. **统一接入。** 文件选择、拖放和含文件的粘贴进入 renderer 的 `Wa`。每个编辑器最多 10 个附件，按剩余名额截取本批候选，再顺序处理。若能取得原生路径，则与当前已有及本批成功接入的路径比较去重。单项失败会计数并收集首条原因，其他项继续处理。纯文本粘贴沿用编辑器默认行为。
2. **确定输入类型。** `YI` 根据 MIME 和扩展名判为 `localImage`、`localAudio` 或 `mention`。图片后缀包括 PNG、JPG/JPEG、GIF、WebP、BMP、AVIF、SVG。无名称文件由 `He` 用时间、序号及 MIME 后缀生成显示名。普通 MP4、MOV 走 `mention`，只交付视频文件路径。
3. **选择落盘时机。** 活动线程 `cwd` 与当前工作区 `cwd` 精确匹配时，添加附件就用当前 `assetId` 写入。新草稿先保留 `pendingFile`、原生路径和图片临时 `blob:` 预览，正式路径留空。发送时 `QI` 记录发送意图、领取草稿工作区，再逐项落盘。已有 `stagedPaths` 的附件直接采用原路径。 [草稿领取与首轮受理](acquire-and-recycle-draft-workspace.md#领取和首轮受理)

### 执行

1. **保留原件。** `A2` 优先使用原生路径复制，其余取 `File.arrayBuffer()` 写入。主进程校验调用方，由 `assetId` 查询缓存或经 `workspace/open` 解析工作区，按需创建 `inputs/`。保存名从 basename 清理 Windows 文件名非法字符，截取主名与扩展名后加上时间戳和八位 UUID 后缀。路径复制验证源文件是否存在且为普通文件，拒绝最终路径项为符号链接，以 `COPYFILE_EXCL` 执行复制并复核大小。字节写入用 `wx` 独占创建。普通导入写入文件并回填会话引用。已核查的两个处理器直接从解析得到的 `cwd` 拼接 `inputs/`，没有额外核验写入目标的真实路径。
2. **按入口复核大小。** 实际写入的大小档为图片 50 MiB，`.glb/.gltf/.obj/.stl/.3mf/.zip` 1 GiB，其余 256 MiB。模型扩展名优先于图片 MIME 参与大小判断。草稿初接入的前置检查只给 `.glb` 1 GiB 档，其他非图片类附件先受 256 MiB 限制。这是两个不同阶段的检查。
3. **按需另存 JPEG。** 普通聊天先写原件。对至少 512 KiB 的图片，`GS` 尝试解码并重编码为 JPEG，长边最多 1536 像素，质量参数 0.85。原图在尺寸上限内也可重编码。只有 JPEG 更小时才另存。未生成更小 JPEG 时，图片条目使用原件。`GS` 返回候选后，第二次 IPC 写入失败会进入外层错误分支。此时原件可能已经写入，附件未取得准备完成的状态。
4. **准备本轮输入。** 原件及适用的预览写入成功后，`QI` 回填实际路径、清除 `pendingFile`，逐项更新发送草稿的已解析输入和 `missingAttachments`。GLB 在此阶段经 `workspace/import` 重新校验源文件真实路径位于本工作区 `inputs/` 内，再由 Runtime 校验文件并登记根目录的模型版本，回填版本路径。普通图片有 JPEG 时以 `localImage` 提供预览，以同名 `mention` 提供原件路径。没有 JPEG 时用 `localImage` 直接提供原件。`O3` 将正文中的附件占位符展开为显示名，`cS` 将 `mention` 汇总到 `# Files attached to this message` 文本段并保留类型化附件。 [导入或登记模型版本](import-or-register-model-version.md#执行) · [会话输入示例及转发](llm-context.md#组装本轮正文和附件)

**首页示例分支。** 用户选用首页内置示例时，renderer 可以获取示例图片并携带额外附件，领取草稿工作区后直接调用 `A2`。示例图片以 `localImage` 交付，额外附件以 `mention` 交付。这条路径跳过 `GS`。若发送失败且活动线程和导航仍匹配，宿主将取得的 `stagedPaths` 交回编辑器复用。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

**根据安装包重建的实现伪代码。** 这里展开普通聊天的写入与发送前准备，省略入口数量、去重、已暂存路径和导航检查。`trySmallerJpeg` 对应 `GS`，返回空值时使用原件。

```javascript
async function writeAttachment(file, assetId, displayName, sourcePath) {
  checkWriteSize(displayName, file.size, file.type);
  if (sourcePath && files.importFile && typeof file.name === "string") {
    return files.importFile({ assetId }, file);
  }
  return files.writeInput({
    assetId,
    fileName: displayName,
    bytes: await file.arrayBuffer(),
    ...(file.type ? { mimeType: file.type } : {}),
  });
}

async function stageOriginalAndPreview(file, attachment, assetId) {
  const original = await writeAttachment(file, assetId, attachment.name, attachment.sourcePath);
  const preview = attachment.type === "localImage"
    ? await trySmallerJpeg(file, attachment.name)
    : null;
  if (!preview) return { path: original.path };

  const savedPreview = await writeAttachment(preview.blob, assetId, preview.fileName);
  return {
    path: savedPreview.path,
    fullResolution: { name: attachment.name, path: original.path },
  };
}

async function prepareTurnAttachments(attachments, workspace) {
  const items = [];
  for (const attachment of attachments) {
    if (attachment.pendingFile) {
      attachment.pendingModelImport = isGlb(attachment.name);
      Object.assign(attachment, await stageOriginalAndPreview(
        attachment.pendingFile, attachment, workspace.assetId
      ));
      delete attachment.pendingFile;
    }
    if (attachment.pendingModelImport) {
      const registered = await importGlbVersion(workspace.assetId, attachment);
      Object.assign(attachment, {
        name: registered.fileName,
        path: join(workspace.cwd, registered.path),
        pendingModelImport: false,
      });
    }
    items.push({ type: attachment.type, name: attachment.name, path: attachment.path });
    if (attachment.fullResolution) {
      items.push({ type: "mention", ...attachment.fullResolution });
    }
    recordPreparedAttachment(items);
  }
  return items;
}
```

### 验收

验收先核对附件归属的工作区和原件实际路径。预览另存时核对原件与预览是否都能读取，并检查会话组装正确交付 `localImage` 和原件 `mention`。GLB 要取得版本登记回执。已准备的附件可交给会话发送，供 Agent 检查图片主体和后续处理所需的视角。主图、补充参考、目标方向和必保特征继续由用户正文和下游业务记录提供。 [主体确认](../../atomic-nodes/confirm-modeling-subject.md#决策)

### 作为 3D 输入的交接

会话里的 `localImage` 说明该附件走图像消息通道。`YI` 可按 MIME 或后缀将 GIF、BMP、AVIF、SVG 等归为图片；宿主图片写入上限为 50 MiB。若 `GS` 另存了 JPEG，它首先是供对话看图的预览。`generate_3d` 接下来读取的是 Agent 明确放入 `images` 的工作区路径。随包规划器要求它指向非空普通文件，按 `.png/.jpg/.jpeg/.webp` 后缀及单文件上限 40 MiB 检查并取 SHA-256；正式 multipart 读取该路径的字节，按扩展名设置 MIME。其间未发现将会话预览自动替换进 `images` 或解码图片像素的分支。 [文件计划与 multipart](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:175>) · [生成前预检](../../atomic-nodes/preflight-generation.md#验收)

**Vet3D 交接建议。** 优先用通过检查的原件。原件格式、大小或解码不符合后端要求时，保留原件并向用户取得兼容副本，或在流程允许时显式产出建模用副本。记录副本与原件的关联、实际路径和哈希，并对副本解码，检查方向（含 EXIF 处理）、主体、姿态和必保特征。通过整组验收后才更新入选视图，再按新路径配对和预检。仅用于会话的预览继续作为预览。 [整组回填与验收](../../atomic-nodes/review-and-finalize-view-set.md#验收)

## 完成与恢复

| 情形 | 已核查行为 |
| --- | --- |
| 批次部分失败 | `Wa` 保留成功附件。路径复制及复制后复检共用错误分支，主进程尽力删除目标并抛回错误。模拟的 `EEXIST` 也会进入该清理分支。预览写入失败时该项可能待重试，原件可能已写入。准备阶段的文件写入各自完成，磁盘上的附件可能比编辑器中的成功项多。 |
| 导入迟到或用户移除附件 | 导入开始时捕获目标工作区和会话。切换后，已有线程的迟到结果归入原线程缓存，已离开的未绑定草稿丢弃编辑器结果并回收临时 URL。编辑器移除会撤销临时 URL 和附件项，已写文件留在工作区供其生命周期另行处理。 |
| 新对话仍有待写入项 | 发送草稿逐项保留准备进度。失败后在导航仍匹配时恢复编辑器附件，可复用已返回的实际路径。发送草稿、基线和浏览器 `File` 保存在 renderer 内存，Runtime 另行持久化工作区领取。进程重启后应核对磁盘及已有轮次，未使用草稿的 `inputs/` 可能被启动回收清理。 [草稿生命周期的恢复边界](acquire-and-recycle-draft-workspace.md#完成与恢复) |
| 附件准备完成但发送状态不明 | 用原 `assetId`、`threadId` 和发送前轮次基线续查。通过 `thread/read` 比对新增轮次中的规范化正文及附件类型、名称和路径。匹配则沿用原轮次，线程空闲且没有新增轮次时才重试。若附件缺失，`continueDraft` 阻止直接续发。 [会话发送恢复](llm-context.md#完成与恢复) |

## Vet3D 迁移与核查范围

Vet3D 可让宿主用稳定的工作区 ID 和素材 ID 记录附件，分别保存显示名、媒体类别、原件引用、可选预览引用，以及导入状态。原件与预览通过同一素材 ID 关联，模型适配器再将预览和可读取的原件引用转换为供应商支持的输入。素材导入和轮次受理分别记录。主体基准、补充参考、目标视角和必保特征留给业务层，即使附件同名也用稳定引用选图。

若需支持重启续办，可持久化发送意图 ID、工作区 ID 和逐项导入结果。完成项在重试时先核对文件归属与存在性，未完成项按同一素材 ID 补齐。写入前验证工作区和目的目录的真实路径归属。将原件写入和预览派生分别记录，明确预览失败后允许使用原件的条件。并发写入测试应覆盖重名文件、跨工作区切换和迟到回包。这里的稳定素材 ID、持久化和重试约定属于 Vet3D 设计。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与文件摘要 | 原安装目录 `D:/install/Hi3DAgent` 为空，复核使用同级安装事务备份中的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| renderer | `out/renderer/assets/index-CDPCug_K.js` 内 `1575640` 为 `YI`，`1577413` 为 `Wa`，`1263972` 为 `A2`，`1265491` 为 `GS`，`1587765` 为 `QI`，`1072602` 为 `cS`，`1314501` 为发送草稿 store，`4740915` 为首页示例写入调用。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| preload 与 main | `out/preload/index.js` 内 `5291`、`5346`、`5888` 对应字节写入、本地文件及原生路径桥接。`out/main/index.js` 内 `178874`、`179199` 为两条写入 IPC，`186888` 为原生来源校验，`190756` 为命名，`206403` 为目录解析，`183286` 为 GLB 登记前路径检查。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime | `runtime/dist/runtime.mjs` 内 `2721999` 为 `workspace/acquireDraft`，`2722874` 为 `workspace/import`，`3163249` 为会话归属校验。偏移均为相应文件或解出成员内的零基字节位置。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 验证结果 | 从安装包提取函数并使用替身，复现了两条写入路线、大小上限、部分成功、预览生成、输入排序和复制失败清理。本机首轮记录包含三个原件 PNG 的路径及三个 JPEG `input_image`，JPEG 数据逐字节对应磁盘预览。 [首轮会话记录](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:13>) |
| 3D 规划器离线复核 | 用隔离临时工作区直接运行随包 `generate-3d --dry-run`：有效 GIF 后缀仍被拒绝，40 MiB + 1 字节的 JPG 后缀被拒绝，使用 `.png` 后缀的非图片字节仍可得到 `consent.result: "ready"`。测试拦截任何远端客户端初始化，未创建作业或输出目录。 [预检入口](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:177>) |
| 待验证 | 真实桌面的选择、拖放、粘贴各入口及 IPC 回包，浏览器能否解码其他手机格式（如 HEIC），真实磁盘故障与并发切换，应用重启后的实际续办表现。现有会话记录用于核对会话组装及本地文件，实际模型供应商的外发请求需独立捕获。 |
