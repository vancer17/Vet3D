# 打开与切换工作区

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。桌面从历史会话的 `cwd` 定位登记工作区，经 `workspace/open` 读取模型目录，并在导航仍有效时提交当前工作区。随后由模型选择器和 Studio 分别处理文件选择与视窗加载。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 用户选择已有会话，活动线程 ID 或该线程的 `cwd` 变化。宿主也可通过 `open(assetId)` 直接打开已登记的工作区，例如显式创建成功后的打开步骤。 |
| 上游与输入 | 历史会话提供 `threadId`、`cwd`，桌面从 `workspace/list` 缓存获得 `cwd → assetId` 的映射。直接打开由宿主提供 `assetId`。Runtime 注册表负责解析该 ID 的受管目录。 |
| 输出 | `workspace/open` 返回 `{workspace, models}`。桌面提交当前资产 ID、模型家族及版本目录、初始所选文件名。合法空目录返回 `models: []`，此时所选文件为 `null`。同工作区快速路径复用当前目录和选择。 |
| 完成条件 | 对需要查询的目标，成功响应属于最新且未取消的打开请求，桌面已提交工作区和对应目录。按会话进入时，还需核对当前工作区的 `cwd` 与活动线程一致。直接打开可在尚无活动线程时完成。 |
| 下游交接 | [素材与模型版本查询](query-assets-and-model-versions.md)使用当前资产和模型目录。[当前轮的工作区上下文](llm-context.md#当前轮的上下文契约)使用经过线程归属校验的目录。[加载指定版本并确认](load-studio-revision.md)以选中的文件为输入，另行确认 Studio 就绪。 |

## Skill 与 LLM Tools

工作区导航是桌面宿主与 Runtime 共用的基础设施，直接适用于普通会话和领域工作流。打开过程由宿主调度下面的 RPC 与 IPC。领域 Skill 的选择以及 LLM 调用 `studio_load_revision` 等工具属于后续会话流程。 [随包 Skill 归档](../../upstream/1.2.11/README.md) · [Studio 工具说明](../../tools/studio-load-revision.md)

## 宿主接口

| 名称 | 类型 | 在本节点中的作用 |
| --- | --- | --- |
| `workspace/list` | Runtime 宿主 RPC | 引导阶段取得已登记的 `{workspaces}`，用于枚举工作区下的会话和解析 `cwd`。 |
| `thread/list`、`thread/resume`、`thread/read` | Runtime 转发的会话 RPC | 分页读取历史会话、恢复已登记线程，以及在恢复结果缺少轮次时读回完整历史。 |
| [`workspace/open`](interfaces/model-catalog-rpc.md) | Runtime 宿主 RPC | 以 `{assetId}` 读取工作区记录和模型目录。桌面另行决定是否采用返回结果。 |
| `runtime:request`、`runtime:cancel-request` | Electron IPC | preload 将方法、参数和可选超时交给主进程。可取消的调用用客户端请求 ID 关联取消。 |
| `asset:setCurrent` | Electron IPC | 桌面提交或清空当前资产后，将 `assetId` 或 `null` 同步到主进程内存。 |
| `workspace/updated`、`workspace/modelUpdated`、`workspace/removed` | Runtime 通知 | 更新桌面索引，对活动工作区合并模型版本，或在当前工作区被移除后清理活动状态。 [移除工作区](remove-workspace.md#验收) |

**根据已核实协议重建的请求和响应。** 示例工作区已登记且没有版本文件。线上 JSONL 请求和响应以同一个 `requestId` 关联。

```jsonl
{"type":"request","requestId":"open-demo-1","method":"workspace/open","params":{"assetId":"asset_demo"}}
{"type":"response","requestId":"open-demo-1","result":{"workspace":{"assetId":"asset_demo","name":"示例工作区","cwd":"D:\\example\\workspaces\\asset_demo","threadIds":["thread_demo"],"createdAt":1794715200000,"updatedAt":1794715200000},"models":[]}}
```

## Hi3D 实现

### 决策

1. **建立可导航索引。** Runtime 就绪后，renderer 先调用 `workspace/list`，再对各已登记目录分页调用 `thread/list` 并合并为侧栏历史。Runtime 的 `Jg.list` 按工作区 `updatedAt` 降序返回注册记录，路径无效的记录标记为 `missing: true`。没有活动会话时，引导流程保留空选择。 [桌面包的 bootstrap 与 Runtime 工作区索引](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
2. **恢复用户选择的会话。** 侧栏把 `threadId` 和 `cwd` 交给 `chat.openThread`。有可复用缓存时直接取会话，否则调用 `thread/resume`。Runtime 校验线程归属，并以注册表中该线程的 `cwd` 准备转发参数。恢复结果没有轮次时再调用 `thread/read({threadId, includeTurns: true})`。renderer 只将仍属于当前导航的结果设为活动会话。 [绑定与恢复工作区会话](bind-and-restore-workspace-session.md)
3. **确定打开分支。** 根组件监听活动线程 ID 和 `cwd`，先重置组件内的会话预览、Studio 展示和待展示状态，再调用 `openForCwd`。该函数取消上一打开请求、推进打开序号，并在缓存索引中按 `workspace.cwd === cwd` 匹配。命中当前资产时复用目录和已选版本，命中其他资产时发起查询。空 `cwd` 或索引未命中时，清空当前资产及模型状态并返回 `false`。宿主明确持有 `assetId` 时可以直接调用 `open(assetId)`，使用同一套查询和提交保护。 [桌面包的工作区 store 和根组件监听](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

### 执行

1. **传送查询。** preload 经 `runtime:request` 交给 Electron 主进程。主进程校验可信 renderer、方法白名单和请求上下文，通过队列和 JSONL 将请求交给 Runtime。该版本在主进程创建传输客户端时将已发送请求的默认限时设为 60 秒。队列等待单独计量。 [桌面包的 preload 和 main](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
2. **读取登记记录与模型目录。** Runtime 校验 `assetId` 后查注册表，要求实际目录存在，逻辑路径和真实路径均对应受管根下的该 ID，并排除工作区目录本身为符号链接的情况。随后 `Jg.listModels` 扫描根目录，只收集匹配 `/^(.+)_(\d+)\.glb$/i` 的普通文件，按家族归组并补齐文件属性和已有元数据。家族内 `latest` 按数字版本号确定。通用分派会把已解析的工作区 ID 加入进程内的草稿保护集合，目录查询本身读取工作区和文件元数据。 [模型目录 RPC](interfaces/model-catalog-rpc.md) · [Runtime 安装包](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
3. **提交桌面选择。** 主进程从响应更新 `assetId → cwd` 缓存。renderer 收到成功响应后，同时检查打开序号和取消信号，再合并工作区记录、设置当前资产、替换版本目录并同步 `asset:setCurrent`。默认选中的文件取所有家族中 `updatedAt` 最大的版本，该值来自磁盘 `mtimeMs`。例如同一家族的第 2 版比第 3 版更晚修改，家族 `latest` 仍是第 3 版，打开时默认选中第 2 版。 [模型目录与版本结构](interfaces/model-catalog-rpc.md#参数结果与错误)

**根据安装包重建的 renderer 伪代码。** 上层监听会先重置会话预览。`replaceOpenRequest` 封装请求作用域及对上一请求的取消。错误保留分支只写入提示。

```javascript
async function openForCwd(cwd) {
  cancelOpenRequest();
  const generation = ++openGeneration;
  const target = cwd && workspaces.find(workspace => workspace.cwd === cwd);

  if (!target) {
    clearCurrentWorkspaceAndModelState();
    assets.setCurrent(null);
    return false;
  }
  if (target.assetId === currentAssetId) return true;

  return readAndCommitWorkspace(target.assetId, generation);
}

async function readAndCommitWorkspace(assetId, generation) {
  const request = replaceOpenRequest();
  openError = null;
  const isCurrent = () => generation === openGeneration && !request.signal.aborted;

  try {
    const { workspace, models } = await request.rpc("workspace/open", { assetId });
    if (!isCurrent()) return false;

    upsertWorkspace(workspace);
    currentAssetId = assetId;
    assets.setCurrent(assetId);
    modelFamilies = models;
    displayedFileName = newestFileByMtime(models)?.fileName ?? null;
    return true;
  } catch (error) {
    if (isCurrent() && !isCancelled(error)) openError = messageFor(error);
    return false;
  } finally {
    finishOpenRequest(request);
  }
}
```

### 验收

- **会话已恢复。** 目标 `threadId` 已成为活动会话。此时工作区查询可仍在进行。
- **工作区已切换。** 目标 `assetId`、所采用目录及初始文件选择属于同一次有效导航。会话入口还要核对 `cwd` 归属。活动工作区上的 `workspace/modelUpdated` 可继续更新目录。
- **Studio 已加载。** 所选文件可由预览通过 `sparc3d-asset://workspace/<assetId>/<path>` 读取。以 Studio 自身的加载确认判定已加载文件。底层 `StudioHost.load` 在目标资产不同的情况下有一个按 `threadIds` 校验的打开分支。常规 `studio_load_revision` 工具入口先将目标限定为当前上下文的资产。 [Studio 加载及验收](load-studio-revision.md#验收)

## 完成与恢复

| 情形 | 行为及恢复边界 |
| --- | --- |
| 请求在途或上一响应迟到 | 新导航取消旧请求。即使收到旧包，打开序号或取消信号也会阻止旧结果提交。完成与否以采用有效响应为准。 |
| 同工作区内切换线程 | 根组件重置会话展示状态。目录走复用分支，保留所选版本，沿用已有目录快照。 |
| `cwd` 为空或索引没有对应项 | 清空当前资产、模型目录、所选文件和待展示请求。若工作区应当存在，可续查 `workspace/list` 后重新发起打开。列表刷新与打开是独立操作。 |
| 有目标但查询失败 | 未登记 ID 返回 `INVALID_ARGUMENT`。路径校验或文件扫描失败可返回 `INTERNAL`。renderer 记录当前打开错误并保留上一份已提交的工作区及模型目录，根组件此前已清理会话预览。此时应依据当前线程与 `cwd` 的匹配确认附件和 Studio 范围。移除补偿只属于[显式创建封装](create-workspace.md#验收与恢复)。 |
| 超时、Runtime 重启或响应丢失 | Runtime 恢复后可用原 `assetId` 重查目录。恢复动作可以走显式打开或重新触发导航。重复选择同一 `threadId` 和 `cwd` 可能不会重新触发监听。 |
| 空目录或模型无法加载 | 空目录是成功结果，可交给模型选择器。已有目录中的某个文件加载失败时，保留工作区查询结果，由 Studio 加载流程处理该文件的失败或重试。 |

## Vet3D 迁移与核查范围

Vet3D 可由宿主定义稳定的工作区 ID，并把线程和工作区的绑定保存在注册表中。打开时按当前环境及账户范围解析绑定和受管目录，再取得模型版本快照。线程恢复、工作区应用和 Studio 加载分别返回状态。模型供应商、文件格式和 Studio 渲染实现可独立选型。Hi3D 的 `cwd` 精确比较和按修改时间选初始模型均为已核实行为。Vet3D 可用工作区 ID 判断归属，并独立定义默认版本策略。

**Vet3D 设计示例。** 宿主记录导航请求的目标线程、工作区 ID 和导航序号。切换完成时仅接受与这三项都匹配的结果，同一次提交更新可用目录和版本快照。切换期间或失败后，上一工作区快照仍可用于回退，但当前轮工具只能使用与活动线程匹配的有效工作区。显式重查针对原工作区 ID 发起，并复用取消和提交检查。同工作区切线程可保留目录快照，仍需重置线程相关的附件、待展示和 Studio 请求状态。

迁移验收覆盖快速切换 A → B 时 A 迟到、同工作区切线程、线程已恢复但目录查询失败、目标目录为空或已消失、返回结果丢失后重查，以及切换完成后旧 Studio 加载事件到达。目录读取与文件加载分别验证，覆盖有权目录中的文件路径和越界路径。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与摘要 | 原安装目录 `D:/install/Hi3DAgent` 为空，核查使用同级安装事务备份中的 Windows x64 Runtime 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Renderer | `out/renderer/assets/index-CDPCug_K.js` 内 `1106054` 为工作区 store，`1106837` 为打开并提交，`1120722` 为会话恢复，`1164830` 为启动刷新，`1222039` 为侧栏发起会话打开，`4715865` 附近是 Studio 的受限打开，`4735562` 为根组件调用 `openForCwd`。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Electron 传输 | `out/preload/index.js` 内 `4393` 和 `6127` 分别为请求桥接、当前资产同步入口。`out/main/index.js` 内 `111100` 为 JSONL 请求，`175764` 为 IPC 处理，`178233` 为当前资产同步，`201195` 为传输默认限时配置，`206409` 为 `assetId → cwd` 查询。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime | 原始 `runtime.mjs` 内 `2166330`、`2166722` 为 `workspace/list`、`workspace/open` 契约，`2721494`、`2721844` 为处理器。`2690065` 为 `listModels`，`2704346` 为路径校验，`3131458` 为草稿保护，`3149128` 为 `prepareAppServerParams`。上述偏移均为各文件或 ASAR 成员内的零基 UTF-8 字节位置。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 已验证 | 安装包静态核查覆盖会话、目录、提交和 Studio 的分支。对提取的 renderer store 使用模拟 RPC，复现列表刷新、迟到响应过滤、同工作区复用、失败保留旧状态、精确路径匹配、空目录与空 `cwd`。已有桌面日志用相同的队列诊断 ID 关联 `workspace/open` 的发出与完成。 [日志发出记录](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:679>) · [日志完成记录](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:686>) |
| 待验证 | 完整桌面环境中的快速切换、失败后的可见交互、真实目录 RPC 响应体，以及目录通知与 Studio 加载事件的交错时序。现有日志只记录队列事件和关联元数据。 |
