# 预览与交付文件

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。桌面宿主根据已确认的文件引用和用户动作选择预览、另存、导出下载或外部交接。各路径分别确认文件已显示、已保存或已交给系统处理。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 用户点击聊天文件链接、模型卡或工作流产物，或在 Studio 选择导出下载、发送 3MF。聊天中的已知图片也可由界面自动请求缩略图。 |
| 上游与输入 | 普通文件需要当前工作区 `assetId` 和已知路径。工作流预览还使用图、线程和产物类型，模型预览使用已选版本的 `fileName`。切片器发送使用已写入并登记的 `.3mf`，由同一回执取得 `assetId`、`artifactId` 和 `path`，另传目标 `slicer`。 [素材和版本查询](query-assets-and-model-versions.md) · [模型版本登记](import-or-register-model-version.md) · [文件产物登记](register-file-artifact.md) |
| 输出 | 桌面内预览得到预览地址或加载状态。HTML 返回 `{path, url}`。另存或 Studio 下载返回取消、失败或实际目标路径。打印宿主 RPC 返回本次 Runtime 内的 `printJob` 记录。 |
| 完成条件 | 图片已解码，Markdown 已显示，GLB 已确认加载目标版本。另存以复制完成回执为准，Studio 下载以 `completed` 事件为准。切片器交接分别核对系统打开应答和 Runtime 回执。浏览器加载内容、切片器实际读取和物理打印各有自己的验收结果。 |
| 下游交接 | 本地保存交付目标路径。打印交接交付已有登记引用及交接状态。视觉验收使用已确认的 Studio 版本及画面。 [Studio 加载验收](load-studio-revision.md#验收) · [获取模型的视觉证据](acquire-model-visual-evidence.md) |

## Skill 与 LLM Tools

工作区路径解析、桌面协议和系统文件交付由宿主提供，普通会话可用。包内通用 `AGENTS.md` 指示 Agent 确认文件实际存在后，发送 `[文件名](工作区相对路径)`。空格、括号等字符用百分号编码，目录先打包。模型版本提交后可输出 `产物：<实际 GLB 文件名>`。HTML 依赖放在入口的同目录或子目录并使用相对 URL。预览端口和令牌由客户端生成。 [随包工作区指令模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:44>) · [本地网页交付约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:64>)

已选用建模 Skill 时，按其规则决定何时验收并交付确切版本。选用场景渲染 Skill 时还需核对实际打开、渲染和下载结果。`scene-render` 的交付说明以该版本安装包副本为证据。文件预览没有主图、补充参考、目标方向或必保特征字段，这些建模语义保留在各业务节点。 [归档的通用建模 Skill](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [1.2.11 Skill 归档](../../upstream/1.2.11/README.md) · [随包场景渲染交付说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/scene-render/references/render-delivery.md:53>)

| LLM Tool | 调用时机与接口边界 |
| --- | --- |
| [`studio_load_revision`](../../tools/studio-load-revision.md) | Agent 需要显式加载并确认具体 GLB 版本时调用。用户点工作流模型或版本选择器可进入对应桌面加载流程。 |
| [`studio_export_3mf`](../../tools/studio-export-3mf.md) | Agent 需要打开打印计划面板时调用。文件的实际下载或发送由用户后续选择触发。 |
| [`workspace_commit_model`](../../tools/workspace-commit-model.md) | 上游需要将 `exports/` 中的选定 GLB 发布为模型版本时调用。提交后的实际文件名用于模型卡与后续下载。 |

图片预览、另存、浏览器打开和切片器打开均为宿主 IPC。`will-download` 是 Electron 事件，`print/send` 和 `print/status` 是 Runtime 宿主 RPC。工具的模型可见描述与通用实现由独立工具页维护。

## 宿主接口

| 名称 | 类型 | 参数、结果与用途 |
| --- | --- | --- |
| [`file:resolveImagePreview`](interfaces/image-preview-ipc.md) | Electron IPC | `{assetId, path}`，返回 `{url, fileName}`。支持图片扩展名 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.avif`、`.svg`。 |
| `sparc3d-asset://workspace/...` | Electron 本地协议 | 按工作区和相对路径读取字节，可供图片、Markdown 和 GLB 使用。 |
| `file:openHtml` | Electron IPC | `{assetId, path}`，核查入口并启动浏览器交接后返回 `{path, url}`。`path` 为入口的真实绝对路径。 |
| `file:saveAs` | Electron IPC | `{assetId, path}`，从工作区读取已有文件，用系统对话框选择目标。返回 `{canceled: true}` 或 `{canceled: false, path}`。 |
| `will-download`、`file:downloadEvent` | Electron 会话事件、桌面通知 | 为 Blob 等下载配置系统保存对话框。发送 `selecting`、`completed`、`cancelled`、`failed`，完成事件带实际 `path`。 |
| `file:openInSlicer` | Electron IPC | 接收 `{assetId, artifactId, path, slicer}`。发出系统打开请求后，以 `slicer` 通道调用 `print/send`，成功时交回该 RPC 的 `{printJob}`。 |
| `print/send` | Runtime 宿主 RPC | 接收 `{assetId, artifactId, channel, target?}`。`channel` 可取 `slicer`、`device`、`direct`，`target` 是可选字符串。复验已登记文件后返回 `{printJob}`。 |
| `print/status` | Runtime 宿主 RPC | 接收 `{printJobId}`。返回同一 Runtime 内存中原有的 `{printJob}`。ID 不存在时返回 `INVALID_ARGUMENT`（`-32602`）。 |

**根据已核实协议重建的调用示例。** 每个操作独立发起。示例假设当前工作区中已存在指定文件，HTML 放在 `exports/viewer/` 下。

```javascript
const files = window.sparc3d.files;
const assetId = "asset_example";

const image = await files.resolveImagePreview({ assetId, path: "exports/hi3d-front view.jpg" });
const saved = await files.saveAs({ assetId, path: "exports/hi3d-report%20bundle.zip" });
const html = await files.openHtml({ assetId, path: "exports/viewer/hi3d-viewer.html" });
```

图片示例可能返回 `sparc3d-asset://workspace/asset_example/exports/hi3d-front%20view.jpg?v=1700000000000-1024`。其中 `v` 来自实际文件的修改时间和大小。HTML 回执中的预览端口与令牌每次打开时生成。

## Hi3D 实现

### 决策

1. **从用户动作选择目标。** 聊天中的普通本地链接解析为另存动作，模型卡的下载入口使用版本目录里的实际相对路径。本地 HTML 链接生成打开浏览器的动作。工作流卡片可按 `assetId` 和路径预览图片或 Markdown、打开 HTML，或按 `fileName` 加载模型。普通文件和 ZIP 凭工作区路径即可交付。
2. **核对会话和工作区。** 聊天发起另存或打开 HTML 前要求活动线程的 `cwd` 与当前工作区一致。选择工作流产物时，renderer 检查活动线程、图和当前 `assetId`。预览响应回来后按请求代次丢弃旧结果。Electron 主进程另外校验 IPC 来源，从缓存或 `workspace/open` 解析工作区目录。
3. **选择生成字节或读取已有文件。** 聊天另存复制已有文件。Studio 导出从视窗模型或打印计划生成字节。3MF 发送额外把字节写入 `exports/` 并先完成 `export-3mf` 登记。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [3MF 产物写入和登记](register-file-artifact.md#写入和登记)

### 执行

#### 桌面内预览

- **图片。** `file:resolveImagePreview` 接受相对路径、仍位于该工作区内的绝对路径或可解析的本地 `file:` URL。主进程先校验词法边界、图片扩展名和实际路径，再要求目标是普通文件。允许最终真实目标留在工作区内的链接。返回地址附 `floor(mtimeMs)-size` 缓存键。聊天界面按工作区和原路径缓存 Promise，失败时清除该条，切线程时清理缓存。 [图片预览路径与错误](interfaces/image-preview-ipc.md#参数与结果)
- **协议读回。** `Ir` 处理 `sparc3d-asset` URL，要求主机名为 `workspace` 且路径含工作区 ID 和文件引用。它解码各路径段，复查词法边界和真实路径，再用 `net.fetch(fileURL, {headers})` 提供字节。主机或必要段缺失返回 `400`，路径不能在工作区内解析时返回 `404`。图片扩展名限制在图片 IPC 层。
- **Markdown 与模型。** Markdown 直接 `fetch` 本地资源并设置 `cache: "no-store"`。声明长度或实际文本的 UTF-8 字节数超过 4 MiB、有 NUL、HTTP 失败时进入错误状态。读取成功且当前图和代次仍匹配时渲染文本。模型先在版本目录精确匹配文件名，再由 Studio 用同一协议加载 GLB，依据加载代次和就绪状态提交实际加载身份。 [Studio 加载流程](load-studio-revision.md#执行)

#### 系统浏览器预览 HTML

`file:openHtml` 以工作区 `cwd` 解析路径，入口须为该工作区内的 `.html` 或 `.htm` 普通文件，文件自身不能是符号链接。`hc` 以入口所在的真实子目录为授权根，拒绝工作区根目录入口以及 `.hi3d`、`inputs`、`AGENTS.md` 路径段。每次重新打开都会在 `127.0.0.1` 建立随机端口和独立的 32 字节 Base64URL 令牌，再以 `shell.openExternal` 把 `/preview/<token>/<basename>` 地址交给系统浏览器。

服务每次核对 Host、令牌、`GET` 或 `HEAD`、词法与真实路径范围及普通文件属性。它支持单一字节范围，响应带 `no-store`、`no-referrer`、`nosniff` 和 `Cross-Origin-Resource-Policy: same-origin`。成功读取资源会刷新 30 分钟空闲期，应用关闭或到期撤销地址。端口只为本机浏览器提供资源。 [随包网页交付约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:64>) · [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

#### 普通保存与 Studio 下载

`file:saveAs` 解析本地路径及百分号编码，检查词法与真实路径均在工作区，并要求源是普通文件。打开源句柄后用 `dev/ino` 和真实路径复验，再弹出默认位置为 Downloads 的保存对话框。取消时关闭源句柄并返回取消。接受后打开并检查目标文件，目标与源为同一文件时直接成功。其他目标先截断再流式复制，成功后回实际保存路径。源和目标句柄分别在 `finally` 关闭。

Studio 底栏的单文件导出支持 GLB、STL、OBJ、3MF、USDZ 和 FBX，分件导出打 ZIP。打印面板单盘下载 3MF，多盘可合并为 3MF 或按盘打 ZIP。这些路径使用 Blob URL 和 `<a download>`。Electron 默认会话的 `will-download` 配置保存对话框，对 3MF、ZIP、GLB 添加对应过滤器，并发布下载状态。包内还保留 `file:saveBytesAs`，可用 `ArrayBuffer` 保存 3MF 或 ZIP。遍历该版本的 12 个 renderer JavaScript 成员，未找到这个 IPC 的调用点。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

**根据安装包控制流重建的文件另存伪代码。** `openVerifiedSource` 包含源句柄的身份和路径复验，`openRegularDestination` 包含普通文件检查。

```javascript
async function saveExistingFile(sender, { assetId, path }) {
  requireTrustedRenderer(sender);
  const cwd = await requireWorkspaceCwd(assetId);
  const source = await resolveWorkspaceRegularFile(cwd, path);
  const input = await openVerifiedSource(source);

  try {
    const target = await showSaveDialog(sender, source.fileName);
    if (target.canceled || !target.path) return { canceled: true };

    const output = await openRegularDestination(target.path);
    try {
      if (!(await sameFileIdentity(input, output))) {
        await output.truncate(0);
        await copyFileHandles(input, output);
      }
      return { canceled: false, path: target.path };
    } finally {
      await output.close();
    }
  } finally {
    await input.close();
  }
}
```

#### 切片器发送及本地交接记录

Studio 底栏发送和打印面板的非 SLA 发送汇入同一处理器。renderer 用登记回执发出 `file:openInSlicer`。主进程核对切片器选项、`.3mf` 后缀、`exports/` 的词法和真实范围及普通文件属性，拒绝文件自身为符号链接。随后为该文件创建 `127.0.0.1` 单文件服务，地址包含 32 字节随机值的十六进制和编码后的文件名。服务查 Host、令牌路径和请求方法，按实时文件大小提供 3MF MIME、长度和附件文件名。`HEAD` 返回头部并保持服务可用，首个完成的 `GET` 关闭监听。默认地址总期限 120 秒，连接和请求相关超时设为 60 秒。

主进程先用系统切片器 URI 调用 `shell.openExternal`，随后以 `channel: "slicer"` 调用 Runtime `print/send`。桌面实现分别检查 IPC 的 `path` 和 Runtime 记录中的 `artifactId`，正常 renderer 两个值都取自同一登记回执。renderer 等待 IPC，捕获失败并写 Studio 错误日志。外部程序在 Runtime 回包前就可能读取文件。 [切片器工具](../../tools/studio-export-3mf.md#参数与结果) · [Runtime 的产物复验](register-file-artifact.md#完成与恢复)

`print/send` 先检查工作区和登记项是否存在，再按 `assetId` 和 `artifactId` 复验文件路径、大小与 SHA-256。工作区或登记项不存在时返回 `INVALID_ARGUMENT`，复验失败时返回 `VALIDATION_FAILED`。成功时，该处理器根据通道及当前时间构造记录，保存到进程内 `printJobs`。`slicer` 返回 `handed-to-slicer`。`device`、`direct` 返回 `file-ready`，提示直连当前不可用。桌面的 `.3mf` 检查及系统打开动作均发生在 IPC 中。独立调用 Runtime 的 `print/send` 只会复验已有文件并生成本地记录。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)

`print/status` 按 `printJobId` 读回同一条记录。包内 renderer 的打印相关 schema 含 `print/statusChanged` 和 `uploading`、`device-received`、`printing` 等状态枚举。已核查的 Runtime 处理器只写上述两种状态，未发布该通知。遍历该版本 renderer 的 JavaScript 成员，普通 UI 中只找到 `file:openInSlicer` 桥接调用，未找到 `print/status` 轮询或 `device`、`direct` 通道调用。 [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)

**根据已核查协议重建的 JSONL 示例。** 假定示例 3MF 已登记并且摘要一致。最后一条在同一 Runtime 中按回执的 `printJobId` 查询。示例展示宿主 RPC 的 `device` 分支。

```jsonl
{"type":"request","requestId":"print-demo-send","method":"print/send","params":{"assetId":"asset_a1b2c3d4","artifactId":"art_e5f6a7b8","channel":"device"}}
{"type":"response","requestId":"print-demo-send","result":{"printJob":{"printJobId":"print_mwhjny80","assetId":"asset_a1b2c3d4","artifactId":"art_e5f6a7b8","channel":"device","status":"file-ready","message":"File is ready (direct device connection is not available yet)","createdAt":1794729600000,"updatedAt":1794729600000}}}
{"type":"request","requestId":"print-demo-status","method":"print/status","params":{"printJobId":"print_mwhjny80"}}
```

**根据安装包控制流重建的打印宿主伪代码。** 入口已校验 RPC 参数。例中省略可选提示消息。

```javascript
function recordPrintSend({ assetId, artifactId, channel, target }) {
  requireWorkspace(assetId);
  requireRegisteredArtifact(assetId, artifactId);
  verifyArtifact(assetId, artifactId);

  const now = Date.now();
  const printJob = {
    printJobId: `print_${now.toString(36)}`,
    assetId,
    artifactId,
    channel,
    target,
    status: channel === "slicer" ? "handed-to-slicer" : "file-ready",
    createdAt: now,
    updatedAt: now,
  };
  printJobs.set(printJob.printJobId, printJob);
  return { printJob };
}

function readPrintStatus({ printJobId }) {
  const printJob = printJobs.get(printJobId);
  if (!printJob) throw invalidArgument(`print job not found: ${printJobId}`);
  return { printJob };
}
```

### 验收

| 路径 | 可用于验收的结果 |
| --- | --- |
| 桌面预览 | 图片实际显示，Markdown 文本渲染，或 Studio 确认目标版本已 `ready`。取得地址或界面选中项只是读取的前置结果。 |
| 系统浏览器 | IPC 回 `{path, url}` 表示系统打开请求完成。页面和依赖是否可用以浏览器实际结果为准。 |
| 复制或导出下载 | `saveAs` 的 `{canceled: false, path}` 或下载事件的 `completed` 和 `path`。保存前按请求类型区分已有文件与新导出。 |
| 切片器发送 | 正常桌面链的 IPC 成功表示系统接受打开请求，且 Runtime 已复验并以 `handed-to-slicer` 记录交接。实际文件读取、切片器解析及打印进度由外部程序确认。 |
| `device`、`direct` | `file-ready` 表示登记文件已复验。该 RPC 分支没有设备上传动作。 |

## 完成与恢复

| 情形 | 本机恢复和后续交接 |
| --- | --- |
| 引用缺失、越界或线程切换 | 保留原工作区和文件指代，重新查询有效路径或版本。过期的界面请求丢弃结果。确认目标仍属于当前工作区后再发起。 |
| 图片地址有效但加载失败，或 Markdown、GLB 解码失败 | 核对真实文件内容、路径、格式和预览限制。原引用仍有效时可重试预览。用户若只需文件，可通过对应的另存动作重新交付。 |
| HTML 令牌失效或资源无法加载 | 回到原工作区路径重新打开，取得新地址。页面依赖须落在入口授权目录内，并可通过相对 URL 请求。系统打开回执只保留为交接记录。 |
| 保存取消、复制失败或下载结果不明 | 取消给出独立终态，后续可重用同一源。失败后检查目标是否留下部分文件，再决定重试。已生成 Blob 的下载等待 Electron 终态，保存结果以实际目标路径核对。 |
| 切片器打开或复验失败 | 保留原 `artifactId`、路径与摘要，先核对外部程序及原文件。文件未变且需要重新交接时，可用同一登记文件重新发起，生成新的临时地址。Runtime 复验失败有可能发生在外部打开之后。 |
| 打印交接回执不明 | 若已知 `printJobId` 且 Runtime 仍是同一实例，可以用 `print/status` 查交接记录。没有 ID 时，已核查接口未提供按产物查询通道记录的入口。Runtime 重启会失去该内存记录，仍可按原 `artifactId` 核对登记文件。决定是否重新交接前，先核对外部程序是否已打开或取走文件。 |

## Vet3D 迁移与核查范围

Vet3D 可把工作区引用、相对文件路径、选定版本和文件用途定义为供应商无关的输入。宿主交付预览引用或保存结果，保留用户选择的目标路径和取消状态。外部交接单独记录已请求打开、可确认的接收结果及地址有效期。图片和模型质量、浏览器实际页面可用性、物理打印进度各由下游验收。

对普通文件支持按路径保存。对需要身份复验的外部交接，可用同一个登记引用解析路径、校验摘要后再发出打开请求。HTML 入口以真实子目录授权，重开时重新签发；机器可读文件引用可持久化，授权 URL 由宿主临时生成。这些接口和处理次序属于 Vet3D 的设计选择，LLM、图片和 3D 模型可独立选型。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与文件摘要 | 核查使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources` 下 1.2.11 Windows x64 留存包。原安装目录的 `app.asar` 不可用。留存包 `app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [安装包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| 桌面内预览 | ASAR 解出成员的零基字节偏移。`out/preload/index.js` 的 `5660` 为预览桥接。`out/main/index.js` 的 `179685` 为图片 IPC，`190002` 为图片路径解析，`31584` 为协议处理，`206718` 为工作区真实路径检查。`out/renderer/assets/index-CDPCug_K.js` 的 `1510549`、`1568851`、`4744037` 分别为工作流缩略图、聊天图片、选中工作流图片的 IPC 调用，`4743081` 为 Markdown 读取。 [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| 另存、HTML 和外部交接 | main 成员 `180430`、`100599`、`101148` 为另存及复制，`180934`、`265535` 为 HTML IPC 和 HTTP 服务，`264515` 为下载事件，`181200`、`97330` 为切片器 IPC 和临时文件服务。renderer 成员 `1585327` 为聊天另存，`1602061` 为模型卡下载，`4226315` 为打印 Blob 下载，`4712216` 为待发 3MF 写入登记。 [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| 打印 RPC | 原始 `runtime.mjs` 零基偏移 `2168263`、`2168467` 为 `print/send`、`print/status` 的契约，`2172755` 为 `print/statusChanged` 通知 schema，`2725818`、`2726861` 为两个 RPC 处理器。main 成员 `182937` 附近列有这两个方法。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) · [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| 离线验证 | 用提取的函数、临时 Windows 文件、回环 HTTP 和替身验证图片路径与协议地址、另存取消和复制顺序、下载状态、HTML 资源范围及 `206` / `416`、空闲撤销，以及 3MF `HEAD`、`GET`、到期和先打开后复验。打印 RPC 的提取函数复现了三个通道映射、同一内存记录的读回、空状态表查询失败，以及复验失败时跳过记录。 |
| 实际运行与待验证 | 历史会话已观察到输出本地图片链接和实际 GLB 文件名。真实桌面对话框完成保存、HTML 页面和依赖加载、第三方切片器读取及解析 3MF 仍待端到端实测。物理设备接收和打印另需外部状态证据。 [本地图片链接记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:512>) · [GLB 引用记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:959>) |
