# 登记文件产物

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。宿主为已落盘的文件登记工作区归属、相对路径和内容摘要，交付可复验的 `artifactId`。工作流挂接、模型版本发布和外部切片器交接各有独立的确认条件。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 受信任的宿主准备好要交付的工作区文件，并请求 `artifact/register`。已核查的桌面入口为 Studio 截图和用户发送 3MF 至切片器。 |
| 上游与输入 | 已登记的工作区 `assetId`、实际存在的文件路径 `path`、产物角色 `role`。可附加 `mimeType`、`threadId` 和 `turnId`。桌面生产者通过 IPC 交付文件名与字节，由主进程落盘后组装 Runtime 请求。 |
| 输出 | `{artifact}`，含 `artifactId`、`assetId`、工作区相对路径、角色、字节数、SHA-256 和创建时间。可选字段随请求保存。Runtime 同时发布 `artifact/registered`。 |
| 完成条件 | 文件通过工作区边界和普通文件检查，记录已追加并刷新到注册表，宿主能以同一 `artifactId` 取得回执。登记阶段核验文件身份与字节快照。格式、几何和画质由消费方验收。 |
| 下游交接 | 宿主以 `assetId + artifactId` 引用原文件，消费前按需复核。同一线程和轮次已有工作流图时可挂接文件。GLB 版本提交、Studio 加载及切片器打开各自确认，登记完成即可交付给这些步骤。 [工作流图状态](workflow-graph-state.md) · [加载指定版本并确认](load-studio-revision.md) · [预览与交付文件](preview-and-deliver-files.md) |

## Skill 与 LLM Tools

工作区解析、文件写入、路径校验、摘要与注册表保存是宿主通用规则，适用于普通会话。该登记接口没有同名 LLM Tool，也不要求先选用领域 Skill。选用建模 Skill 后，产物命名、评审和交付仍按对应工作流约定执行。`role` 表达文件用途，主图、补充参考、目标视角和必保特征由对应业务记录维护。 [通用建模 Skill](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [随包 Skill 归档](../../upstream/1.2.11/README.md)

| LLM Tool | 与本节点的关系 |
| --- | --- |
| [`studio_capture_view`](../../tools/studio-capture-view.md) | 需要取当前视窗截图时由 renderer 执行。截图编码成功后进入宿主写入与登记，工具回给模型的是 `artifactId`、`width` 和 `height`。 |
| [`studio_export_3mf`](../../tools/studio-export-3mf.md) | 需要打开打印面板时由 renderer 执行。用户选择发送至外部切片器并进入文件交接分支时，桌面才写入并登记 3MF。 |
| [`workspace_commit_model`](../../tools/workspace-commit-model.md) | 需要把已选的导出 GLB 发布为模型版本时使用，输入为导出路径。 |
| [`hi3d_api`](../../tools/hi3d-api.md#已下载-3d-产物与登记) | 保存作业下载结果及来源。符合条件的正式 `generate_3d` 可就下载到的 GLB 自动发布模型版本。 |

这些工具的模型可见描述和参数由各自的独立工具页维护。核查中的生产记录未确认截图或 3MF 分支实际触发了 `artifact/register`。

## 宿主接口

| 名称 | 类型 | 参数及结果 |
| --- | --- | --- |
| `files.writeArtifact`、`file:writeArtifact` | preload 桥接和 Electron IPC | `assetId`、`fileName`、`bytes`、`role` 必填，可带 `mimeType`、`threadId`、`turnId`。`assetId` 和 `fileName` 非空，最长分别为 256 和 255 字符。`bytes` 是最大 1 GiB 的 `ArrayBuffer`。成功返回 `{artifact}`。 |
| `artifact/register` | Runtime 宿主 RPC | `assetId`、`path`、`role` 必填，可带 `mimeType`、`threadId`、`turnId`。Runtime 依据已登记的 `assetId` 解析相对路径，也接受落在同一工作区内的绝对路径。成功返回 `{artifact}`。该方法由 Electron 主进程内部调用，通用 renderer RPC 白名单未开放。 |
| `artifact/registered` | Runtime 通知 | `params` 为 `{artifact}`，在注册表刷新后发布。通知分支还会尝试为对应轮次挂接文件。 |
| `workspace/commit`、`print/send` | Runtime 宿主 RPC | 使用 `{assetId, artifactId}` 定位登记项，再按各自用途复核文件。模型提交另需 `name`，打印交接另需 `channel`。交接记录有独立的 `printJobId`。 [打印交接与查询](preview-and-deliver-files.md#切片器发送及本地交接记录) |

`role` 的枚举值为 `studio-save`、`blender-output`、`export-3mf`、`export-zip`、`export-glb`、`layout`、`screenshot`、`report`、`other`。`mimeType`、`threadId` 和 `turnId` 在两个入口都是可选字符串，无固定默认值。Runtime 校验角色枚举，登记时不校验角色、扩展名和 MIME 的一致性。产物记录 schema 允许 `sha256` 缺省，本版本新登记始终计算摘要，消费端会拒绝没有摘要的登记项。

**根据已核实协议重建的 JSONL 示例。** 假定 `exports/hi3d-audit.txt` 已存在，内容恰为三个 ASCII 字节 `abc`，没有行尾。请求和应答用相同 `requestId` 关联。通知和应答用同一 `artifactId` 关联。Windows 回执路径来自 `path.relative`。

```jsonl
{"type":"request","requestId":"artifact-demo-1","method":"artifact/register","params":{"assetId":"asset_a1b2c3d4","path":"exports/hi3d-audit.txt","role":"report","mimeType":"text/plain","threadId":"thread_demo","turnId":"turn_demo"}}
{"type":"notification","method":"artifact/registered","params":{"artifact":{"artifactId":"art_e5f6a7b8","assetId":"asset_a1b2c3d4","path":"exports\\hi3d-audit.txt","role":"report","size":3,"sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","createdAt":1794729600000,"mimeType":"text/plain","threadId":"thread_demo","turnId":"turn_demo"}}}
{"type":"response","requestId":"artifact-demo-1","result":{"artifact":{"artifactId":"art_e5f6a7b8","assetId":"asset_a1b2c3d4","path":"exports\\hi3d-audit.txt","role":"report","size":3,"sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","createdAt":1794729600000,"mimeType":"text/plain","threadId":"thread_demo","turnId":"turn_demo"}}}
```

## Hi3D 实现

### 决策

1. **确定文件生产路径。** Studio 截图从当前 canvas 编码 JPEG，用 `screenshot` 登记。发送至切片器时先生成 3MF，用 `export-3mf` 登记。普通 3MF 下载只走文件保存对话框，按下载事件和目标路径验收。已存在的工作区文件由 Runtime 接口按路径接收。 [截图的宿主交接](acquire-model-visual-evidence.md#studio-当前视窗截图) · [普通保存与 Studio 下载](preview-and-deliver-files.md#普通保存与-studio-下载)
2. **确定工作区和可选归属。** renderer 的 `Ce` 在读取字节前后核对 `assetId`、活动线程和会话代次。已确认的截图和发送至切片器两处均可传 `threadId`，未传 `turnId`。Runtime 保存调用方提供的归属字段，线程与工作区是否匹配在通知挂图时检查。 [Electron 桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

### 执行

#### 写入和登记

1. **落盘。** preload 把字节交给主进程 `fileWriteArtifact`。主进程校验可信调用来源、参数和工作区，用 basename 去掉来路中的目录、替换文件名中的保留字符，并添加 `hi3d-` 前缀及时间与随机后缀。随后在该工作区 `exports/` 以 `wx` 独占写入，再将 `exports/<实际文件名>` 及角色和可选元数据交给 `artifact/register`。 [Electron 写入实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
2. **校验路径和文件。** `Jg.registerArtifact` 先确认 `cwd` 对应受管根目录下的 `assetId`，再解析文件路径并检查词法边界。basename 必须以区分大小写的 `hi3d-` 开头。文件须存在，文件自身不能是符号链接。`realpath` 复核真实目标仍位于工作区，拒绝经父目录链接出界，最终目标须是普通文件。Runtime 的路径范围是整个工作区，桌面写入入口固定在 `exports/`。
3. **记录身份和摘要。** 取实际字节数，读取文件计算 SHA-256，生成 `art_` 加随机 UUID 的前八个字符，保存本机格式的工作区相对路径、角色、创建时间和可选元数据。将记录追加到 `registry.json` 的 `artifacts[assetId]` 并调用 `save()`。同一个路径和摘要重复登记会追加新记录并返回新 ID。
4. **提交注册表并回传。** RPC 处理器等待 `flushRegistry()`。成功后执行 `artifact/registered` 通知路径，再返回 `{artifact}`。主进程将完整记录交给 renderer。截图工具回给模型的负载仅含 ID 和宽高。 [Runtime 登记与刷新](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)

**根据安装包控制流重建的伪代码。** 省略传输包装。`requireSafeArtifactFile` 使用上文的工作区、文件名、词法路径和真实路径校验。

```javascript
async function registerArtifactRpc(params) {
  const { assetId, path, role, mimeType, threadId, turnId } = parseRegisterParams(params);
  const workspace = registry.requireWorkspace(assetId);
  const artifact = wrapInvalidArgument(() => {
    const file = requireSafeArtifactFile(workspace, path);
    const record = {
      artifactId: `art_${randomUUID().slice(0, 8)}`,
      assetId,
      path: file.workspaceRelativePath,
      role,
      size: file.size,
      sha256: sha256File(file.realPath),
      createdAt: Date.now(),
      mimeType,
      threadId,
      turnId,
    };
    registry.appendArtifact(assetId, record);
    registry.save();
    return record;
  });

  await flushRegistry();
  notify("artifact/registered", { artifact });
  return { artifact };
}
```

#### 挂接图和交给消费方

- **工作流图。** 通知分支要求 `threadId`、`turnId`、`assetId` 和路径都有值，并确认线程仍属于同一工作区。满足时记录 Skill 捕获信号，再尝试追加到该轮已有的图。PNG、JPG、JPEG、WebP、GIF、AVIF 扩展名或以 `image/` 开头的 MIME 优先归为 `image`。`.glb` 路径精确匹配模型目录已有版本时归为 `model`。其余归为 `file`。图用 `kind`、`assetId`、`fileName`、`path`、`url` 派生独立的 `wfa_` ID 去重。无显式节点时优先挂到通用图的 `execute`，其次考虑唯一运行中的叶节点，仍无法确定时保留为未分配。缺轮次、归属不匹配或没有该轮图时，登记回执仍可成立。图有独立的保存及完成状态。 [工作流图状态](workflow-graph-state.md)
- **模型版本。** 宿主 `workspace/commit` 接收 `assetId`、`artifactId` 和 `name`，只接受角色为 `studio-save`、`blender-output` 或 `export-glb` 的 `.glb`。`verifyArtifact` 重验安全路径、大小和摘要，再由提交路径校验 GLB 首部，发布工作区根目录的 `hi3d-<家族名>_<序号>.glb`。刷新成功后发送 `workspace/modelUpdated`，桌面更新当前工作区的版本列表。本轮确认了宿主接口和白名单，未定位到普通 renderer 界面的直接调用。`workspace_commit_model` 和 `hi3d_api` 的自动发布分支均从导出路径提交版本。生成作业保存下载文件和摘要，匹配的 GLB 下载来源另存于 `hi3dDownloads`。只有走 `artifact/register` 才会获得通用文件登记的 `artifactId`。 [模型版本登记与生成作业恢复](import-or-register-model-version.md#完成与恢复) · [模型版本查询](query-assets-and-model-versions.md#执行)
- **切片器。** Electron 另查实际 `.3mf` 路径和文件范围，先发出外部打开请求，再调用 `print/send`。Runtime 用 `assetId` 和 `artifactId` 复验登记文件，另以 `printJobId` 标识本次内存交接记录。外部程序接收文件及设备进度各有自己的证据。 [切片器交接与查询](preview-and-deliver-files.md#切片器发送及本地交接记录)

### 验收

用回执或通知的 `artifactId` 核对 `artifacts[assetId]`，确认实际文件仍存在且相对路径、大小和摘要一致。工作流场景另读原轮次的图，确认所需引用及归属。模型交接另核对 `workspace/modelUpdated` 和模型版本列表，并在需要时确认 Studio 已加载选定版本。打印交付另核对切片器打开和打印交接回执。 [工作流读回](interfaces/workflow-read-rpc.md) · [Studio 加载确认](load-studio-revision.md#验收)

## 完成与恢复

| 情形 | 已核查行为与恢复边界 |
| --- | --- |
| IPC 校验或写入失败 | 主进程尚未请求登记。按原错误核对参数、工作区、目标路径和文件字节，再决定是否重试写入。 |
| 文件已写，登记被拒绝 | `artifact/register` 的工作区、参数或文件检查失败返回 `INVALID_ARGUMENT`（`-32602`）。主进程收到错误后拒绝 IPC 请求，已写文件可能仍在 `exports/`。确认实际文件、修复参数或路径后，宿主可以登记这个已有文件。 |
| 刷新失败或回执不明 | `flushRegistry()` 失败返回 `INTERNAL`（`-32603`），已追加的内存记录可能保留，本次处理器未发布登记通知。回执不明时，先从已收到的 `artifact/registered` 通知或注册表按工作区、路径和摘要对账。直接重送登记请求会追加新 ID。已核查的公开 RPC 与 LLM Tool 未发现通用 `artifact/get` 或 `artifact/list`。 |
| 文件已登记，图或模型尚未交付 | 按真实轮次检查图，或继续模型提交与视窗确认。单靠 `artifactId` 无法确认已完成挂图、模型版本发布或视窗加载。 |
| 登记后文件被移走或内容变化 | `workspace/commit` 与 `print/send` 均执行 `verifyArtifact`。缺摘要、路径失效、大小或 SHA-256 不匹配时返回 `VALIDATION_FAILED`。即使修改前后大小相同，摘要也能识别变化。原 `artifactId` 无登记项时，入口会先返回 `INVALID_ARGUMENT`。确定要交付新文件后，按新内容重新登记。 |

## Vet3D 迁移与核查范围

Vet3D 可用宿主接口接收工作区引用、文件引用、文件用途和可选的会话归属，输出稳定的产物引用、相对路径、字节数和内容摘要。文件实际落盘、登记持久化、工作流挂接及模型版本发布各自记录进度。需要发布模型版本时，用登记引用定位并复验原文件，再由独立版本逻辑完成提交。图片的建模角色和质量验收继续由业务层维护。LLM、生图模型、3D 模型和供应商 API 均可独立选型。

若 Vet3D 要保证重试复用同一次登记，可持久化由宿主分配的操作 ID，以及它对应的工作区、暂存路径、摘要和登记结果。文件写完后、登记应答前发生中断时，先用该记录对账。操作 ID 约束的是同一登记意图，相同字节仍可服务于其他独立产物。这个幂等契约和恢复记录属于 Vet3D 设计选择。迁移验收覆盖路径越界、链接出界、同路径重试、写入成功但登记刷新失败、同大小文件变更、无对应工作流图，以及版本提交完成后视窗尚未加载。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与文件摘要 | 本机核查采用 `D:/install/Hi3DAgent.__hi3d-transaction/resources` 留存包，原安装目录的 ASAR 与 Runtime 文件不可用。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [Runtime 1.2.11 清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Electron 静态实现 | `out/preload/index.js` 成员零基字节偏移 `5230` 为写入桥接。`out/main/index.js` 的 `178361` 为处理器，`178679` 为内部登记 RPC，`185052` 为 IPC 校验，`190756` 为文件名构造。renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 的 `4712216` 为切片器分支的写入调用，`4712791` 为共用桥接调用，`4717572` 为截图入口，`1108596` 为模型目录通知处理。 [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime 静态实现 | 原始 `runtime.mjs` 零基字节偏移 `2157874` 为角色枚举，`2158027` 为记录 schema，`2167637` 为登记 RPC schema，`2724948` 为登记处理器。`2700143` 和 `2701777` 分别为登记、复验方法的参数锚点，`3208403` 为通知挂接分支，`3072936` 为图产物方法参数锚点，`2723654` 为宿主模型提交。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) |
| 离线验证 | 用提取的包内代码、临时 Windows 文件和替身验证先写后登、路径与链接边界、重复登记、同大小文件变化、发布顺序、刷新失败后保留内存记录，以及工作流的归属与去重。 |
| 实际观测与待验证 | 本机生产注册表快照没有通用文件登记项，已核查日志未见对应 RPC 和通知。真实桌面截图或 3MF 从写入到登记再到下游消费的完整轨迹仍待采集。 |
