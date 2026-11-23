# 创建工作区

本节点位于工作区基础设施的生命周期部分。核查对象为 Hi3D Agent 1.2.11（Windows x64）。创建成功交付一个有实际目录、初始指令文件和持久化注册记录的工作区。桌面随后可以打开该工作区，并在用户发送消息时绑定 Agent 线程。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 桌面宿主显式请求 `workspace/create`。草稿领取在没有可复用目录时也会调用相同的 `Jg.create`，其对外入口是 `workspace/acquireDraft`。 [领取与回收草稿工作区](acquire-and-recycle-draft-workspace.md) |
| 上游与输入 | 运行环境已确定 `workspacesRoot` 并初始化工作区注册表。显式请求提供显示名称 `name`。Runtime 用当前配置渲染工作区指令。 |
| 输出 | 工作区记录 `workspace`，含 `assetId`、`name`、绝对 `cwd`、`threadIds`、`createdAt` 和 `updatedAt`。新建记录的 `threadIds` 为空。磁盘已有初始目录和指令，注册表已写入，宿主另收到 `workspace/updated`。 |
| 完成条件 | 核心创建以注册表刷新成功并返回工作区记录为准。桌面封装还会打开返回的 `assetId`，在打开结果仍属于当前导航时更新当前工作区。 |
| 下游交接 | [打开与切换工作区](open-workspace.md) 以 `assetId` 取得工作区和模型列表。[构建当前轮的工作区上下文](llm-context.md#验收) 使用已确定的 `assetId` 和 `cwd` 绑定会话。[接收并导入参考素材](import-reference-materials.md) 按实际工作区写入附件，首次导入时创建 `inputs/`。 |

创建受宿主和 Runtime 的接口契约约束。`templates/AGENTS.md` 是创建时写入的工作区指令模板。安装包中未发现该创建入口依赖 Skill 选用，或通过同名 LLM Tool 调用。 [随包模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md>) · [LLM 工具索引](../../tools/README.md)

## 宿主接口

| 名称 | 类型 | 参数或结果 |
| --- | --- | --- |
| `workspace/create` | Runtime 宿主 RPC | `params` 严格接受 `{name}`。`name` 必填，必须为字符串。去掉两端空白后长 1–120 个 UTF-16 代码单元，拒绝内部 CR、LF 和 NUL。调用方无需提供 `assetId` 或路径，同名可创建不同工作区。成功返回 `result: {workspace}`。 |
| `workspace/updated` | Runtime 通知 | `params: {workspace}`。创建处理器在成功刷新注册表后发出。通知与 RPC 响应分别交付。 |
| `runtime:request` | Electron IPC | preload 把方法、参数及可选超时和客户端请求 ID 交给主进程，再由主进程转发 Runtime。 |

**按随包协议重建的请求和成功响应。** 以下使用示例名称、路径和时间戳。JSONL 通道用同一个 `requestId` 关联请求和响应。创建契约没有幂等键。

```jsonl
{"type":"request","requestId":"req-example","method":"workspace/create","params":{"name":"猫模型参考"}}
{"type":"response","requestId":"req-example","result":{"workspace":{"assetId":"asset_a1b2c3d4","name":"猫模型参考","cwd":"D:\\example\\workspaces\\asset_a1b2c3d4","threadIds":[],"createdAt":1794715200000,"updatedAt":1794715200000}}}
```

## Hi3D 实现

1. **定位环境根目录。** Electron main 的 `tc` 从存储根和当前环境派生 `<dataRoot>/environments/<env>/workspaces`，通过 `SPARC3D_WORKSPACES_ROOT` 传给 Runtime。Runtime 用该根初始化 `Jg`，创建根目录并在其中查找 `registry.json`。本机生产环境使用 `D:/download/.sparc3d-runtime/environments/prod/workspaces`。已存在的注册表按其路径格式读回。解析失败会报错并保留原文件。 [本机存储根配置](<C:/Users/11408/AppData/Roaming/Hi3D/runtime-storage.ini>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
2. **检查请求。** 主进程核对受信任的 renderer、允许的 RPC 方法、当前环境和请求上下文。`workspace/create` 在宿主白名单内。Runtime 的 `dispatchRuntimeMethod` 再按 `cg['workspace/create']` 校验参数，失败时返回 `INVALID_ARGUMENT`。当前安装包保留 renderer 的 `Jr.b(name)` 创建封装，未定位到普通界面直接调用它的按钮。「新对话」先进入聊天草稿，首条消息发送且缺少已选工作区时由 `QI` 调用 `workspace/acquireDraft`。领取可复用目录，需要新目录时才执行 `Jg.create`。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [草稿转会话的入口](llm-context.md#决策)
3. **创建目录并组装记录。** `Jg.create` 用 `asset_` 加随机 UUID 的前八个字符生成 `assetId`，用 `join(workspacesRoot, assetId)` 得到 `cwd`。依次创建 `exports/`、`scripts/`，调用 `Uj` 渲染 UTF-8 的 `AGENTS.md`，以 `wx` 独占写入同名文件。`Uj` 填入显示名称、Blender 和 Python 路径及平台说明，缺少工具路径时填对应说明。随后在内存新增工作区记录，两个时间戳取自同一次 `Date.now()`，并初始化空产物列表和空模型元数据映射。 [初始指令模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:5>)
4. **确认持久化后发布结果。** `Jg.save()` 标记待写，RPC 处理器显式等待 `flushRegistry()`。写入队列串行处理注册表快照。`serialize()` 检查记录的 `cwd` 对应受管目录，在 `relative-v1` 格式中把 `cwd` 保存为 `assetId`，去掉临时的 `missing` 字段。`writeRegistryFile` 在注册表同目录创建 `.registry-<uuid>.tmp`，以 `wx` 打开，写入并同步文件，关闭后重命名替换 `registry.json`，最后清理临时文件。重命名遇到 `EPERM` 或 `EBUSY` 时最多尝试五次，其他错误立即上抛。刷新成功后，处理器先调用 `notify('workspace/updated', …)`，再返回 `{workspace}`。 [Runtime 注册表实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
5. **打开并确认当前工作区。** `Jr.b` 先把返回记录合并进桌面列表，再调用 `workspace/open({assetId})`。renderer 仅在打开请求未取消且导航代次匹配时设置当前 `assetId`、模型列表和初始选中项。新工作区的模型列表通常为空。创建及打开阶段结束时，Agent 线程仍由后续 `thread/start` 建立。 [打开与切换工作区](open-workspace.md#执行) · [会话绑定与转发](llm-context.md#校验后转发给-codex)

**根据安装包控制流重建的伪代码。** 省略 IPC 包装、注册表写队列和具体错误码映射。`registry.flush()` 封装上文的快照写入和替换。

```javascript
async function runtimeCreate(params) {
  const { name } = parseStrictCreateParams(params);
  const assetId = `asset_${randomUUID().slice(0, 8)}`;
  const cwd = join(workspacesRoot, assetId);

  mkdirSync(join(cwd, "exports"), { recursive: true });
  mkdirSync(join(cwd, "scripts"), { recursive: true });
  writeFileSync(join(cwd, "AGENTS.md"), renderAgentsMd(name), { flag: "wx" });

  const now = Date.now();
  const workspace = { assetId, name, cwd, threadIds: [], createdAt: now, updatedAt: now };
  registry.data.workspaces.push(workspace);
  registry.data.artifacts[assetId] = [];
  registry.data.modelMetadata[assetId] = {};
  registry.save();

  await registry.flush();
  notify("workspace/updated", { workspace });
  return { workspace };
}

async function desktopCreateAndOpen(name) {
  const { workspace } = await rpc("workspace/create", { name });
  mergeWorkspace(workspace);
  if (await openWorkspace(workspace.assetId)) return workspace;

  const openError = currentOpenError() ?? studioNotReadyMessage();
  try {
    await removeWorkspace(workspace.assetId);
  } catch {
    // 补偿失败时保留原打开错误。
  }
  throw new Error(openError);
}
```

### 启动时刷新既有工作区指令

Runtime 启动时并行执行随包 Skill 安装和 `Jg.refreshAgentsFilesAsync()`，等待两项结束后再启动 Codex。刷新按注册表遍历已有工作区，校验受管目录，用当前模板、工作区显示名及本地工具配置重新渲染 `AGENTS.md`。已有内容相同则跳过。文件缺失或内容不同时，以 `wx` 写入同目录的 `.agents-<UUID>.tmp`，用 `Qz` 重命名到目标，并在退出时清理临时文件。已有 `AGENTS.md` 为符号链接时拒绝刷新该项。

单项错误按 `assetId` 汇总，其余项目继续处理。刷新失败只记录启动警告，随包 Skill 安装失败则中止启动。该写入由 Runtime 宿主触发，文件随后作为 Codex 工作区说明参与上下文。具体采样是否包含新内容仍需核对该轮记录。 [当前轮的工作区上下文](llm-context.md#当前轮的上下文契约)

## 验收与恢复

成功时核对响应中的 `assetId`、绝对 `cwd` 和空 `threadIds`，确认目录结构和注册表项对应同一 ID。通过桌面封装创建时，另核对 `workspace/open` 的结果是否采用为当前工作区。注册表文件的替换与目录创建各有失败边界。

| 情形 | 已核查行为与恢复边界 |
| --- | --- |
| 参数错误 | Runtime 返回 `INVALID_ARGUMENT`（`-32602`），尚未进入目录创建。修正参数后可发起新请求。 |
| 目录创建或指令写入失败 | Runtime 创建分支没有补偿删除。已经完成的 `mkdir` 可能留下目录，此时还未插入内存项。目录残留与正式登记分别核对。 |
| 注册表刷新失败 | `flushRegistry` 包装为 `INTERNAL`（`-32603`）。本次创建处理器未发布成功通知。目录和内存条目可能已经存在，写入失败后仍保持待写状态，后续刷新可能把该条目持久化。 |
| 创建成功后，桌面打开失败或被判为过期 | renderer 对本次返回的 `assetId` 尝试 `workspace/remove`。补偿失败会被捕获，对调用方仍抛出原打开错误。创建 RPC 自身失败时，没有取得返回的 `assetId`，也不会进入这段补偿。 [移除工作区](remove-workspace.md) |
| 超时或结果不明 | 桌面经通用请求队列发起 RPC。此版本为已发送的单次请求设置 60 秒默认限时，队列等待单独计量。超时和 `RESULT_UNKNOWN` 不会由该队列自动重发。应先通过 `workspace/list` 和注册记录核对创建结果，显示名称单独不足以确认本次请求。盲目重发可能创建另一条同名记录。 [传输限时的安装包定位](open-workspace.md#vet3d-迁移与核查范围) |
| 既有工作区指令刷新失败 | Runtime 继续后续启动，已成功写入的项保留。根据警告中的 `assetId` 核对实际文件。下一次 Runtime 启动会重新检查登记记录及文件内容。 |

## Vet3D 迁移与核查范围

创建接口可保持与 LLM、渲染器和 3D 供应商无关。宿主令显示名与目录身份分别存储，向下游交付稳定的工作区引用和可用目录。将**准备目录、注册提交、界面激活**表示为可独立核对的阶段。若 Vet3D 要支持创建超时后重试，持久化一条以创建意图 ID 为键的记录，分配工作区 ID 后复用该记录。恢复时查同一意图及其已完成阶段，再决定返回原工作区、继续初始化或报告失败。这个幂等契约属于 Vet3D 设计。

优先覆盖同名工作区、注册表写入失败后的恢复、响应丢失后重复调用、已提交但打开被取消，以及重启后从相对 `cwd` 恢复目录。会话绑定以已确认的工作区引用为输入，附件和模型的读写继续使用该工作区的范围。 [Vet3D 的会话上下文契约](llm-context.md#当前轮的上下文契约)

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与文件摘要 | [安装包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) 确认为 Hi3D Runtime 1.2.11、Windows x64。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 |
| Electron 证据 | [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) 中 `out/preload/index.js` 第 1 行偏移 `4393` 是桥接入口。`out/main/index.js` 第 18 行偏移 `81822` 为 schema，第 29 行偏移 `175764` 为 IPC 分发，第 30 行偏移 `258289` 为 `tc`。`out/renderer/assets/index-CDPCug_K.js` 第 147 行偏移 `1106837`、`1107232` 分别为 `C`、`Jr.b`，第 627 行的 `QI` 可核对草稿领取。偏移均为解出成员中的零基 UTF-8 字节位置。 |
| Runtime 证据 | [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) 中原始零基字节偏移 `2166457` 为 `workspace/create` schema，`2473266` 为 `Uj`，`2673574` 为 `Jg`，`2679576` 附近的 `_0x542698` 为创建实现锚点，`2688340` 为 `refreshAgentsFilesAsync`，`2709917` 为 `serialize`，`2710729` 为重命名重试函数 `Qz`，`2721567` 为创建处理器，`2727319` 为 `flushRegistry`，`3111564` 为刷新启动调用。 |
| 离线与本机记录 | 对安装包提取的创建处理器、注册表及 renderer 封装使用替身执行，验证了写入顺序、相对 `cwd`、写入失败后的待写状态、打开失败的补偿和创建失败时跳过补偿。本机注册表确认使用 `relative-v1`，已有工作区均包含初始指令与目录。现有[桌面日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:156>) 记录了 `workspace/acquireDraft` 请求和回执。 |
| 启动刷新记录 | 安装包静态核实了刷新、跳过和逐项失败分支。桌面日志记录先执行 `Workspace AGENTS.md` 步骤，随后进入 `Starting Codex`。耗时日志来自 `finally`，只确认步骤已执行。 [刷新步骤](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261115T032556Z-30688.log:19>) · [启动 Codex](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261115T032556Z-30688.log:25>) |
| 待验证 | 普通界面直接触发显式 `workspace/create` 的入口、显式创建的生产 RPC 轨迹，以及真实磁盘写入或窗口切换失败时的界面表现。启动日志没有记录各工作区文件变动，尚未实测刷新故障及其后续采样。未在生产工作区执行创建或删除。 |
