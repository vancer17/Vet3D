# 领取与回收草稿工作区

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。桌面在首次发送需要独立目录的对话时领取工作区。Runtime 在首轮受理时清除草稿标记，并在启动时另行检查哪些目录可以重新进入可复用池。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 首次提交有效内容且没有可沿用的工作区时领取。`turn/started` 通知或 `turn/start` 成功返回后消耗草稿标记。每个 Runtime 实例首次完成 Codex app-server 初始化后启动一次回收扫描。 |
| 上游与输入 | 桌面提供发送意图的 UUID `draftId` 和工作区显示名 `name`。Runtime 使用当前环境的 `workspacesRoot`、工作区注册表、实际目录和 Codex 线程查询结果。 |
| 输出 | 领取返回 `{workspace}`，包含稳定的 `assetId` 和可用于附件、线程的绝对 `cwd`。回收保留同一工作区记录和根目录，将草稿标记设为可复用。 |
| 完成条件 | 领取以注册表刷新成功及 RPC 回执为准。首轮受理后，关联工作区的草稿标记从注册表内存状态移除并进入保存流程。回收以文件与会话检查通过、标记入池和注册表落盘为准。 |
| 下游交接 | [接收并导入参考素材](import-reference-materials.md)使用已领取的 `assetId` 暂存附件，`thread/start` 使用同一工作区的 `cwd`。桌面视窗另按活动线程的 `cwd` 定位工作区。两种发送入口都使用同一领取接口。 [创建工作区](create-workspace.md#hi3d-实现) · [当前轮的工作区上下文](llm-context.md#决策) · [打开与切换工作区](open-workspace.md#执行) |

## Skill 与 LLM Tools

领取、首轮标记消费及回收均由宿主调度，无对应的 LLM Tool，也无需用户选用 Skill。创建分支可能写入通用工作区指令 `AGENTS.md`。Skill 发现完成是扫描启动的时序条件。会话后续可以按任务选用建模或领域 Skill，其规则从进入对应会话流程起生效。 [通用建模 Skill](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [随包 Skill 归档](../../upstream/1.2.11/README.md)

## 宿主接口

| 名称 | 类型 | 参数及用途 |
| --- | --- | --- |
| `runtime:request` | Electron IPC | preload 将方法及参数交给主进程。主进程核对 renderer 来源、请求上下文和方法白名单，再经 JSONL 转发给 Runtime。 |
| `workspace/acquireDraft` | Runtime 宿主 RPC | `name` 和 `draftId` 均必填。`name` 去掉首尾空白后长 1–120 个 UTF-16 代码单元，禁止内部 CR、LF 和 NUL。`draftId` 为 UUID。成功返回 `{workspace}`。 |
| `workspace/updated` | Runtime 通知 | 参数为 `{workspace}`。领取在刷新注册表后发出，启动回收入池后立即发出，扫描结束再统一刷新。 |
| `thread/start`、`turn/start`、`thread/read` | Codex 会话 RPC | 建立线程归属、提交首轮，以及在发送结果不明时读回轮次。`turn/started` 是 app-server 通知。 |
| `thread/list` | Codex 会话 RPC | 回收扫描直接请求当前 app-server，以同一 `cwd` 先查 `archived: false`，再查 `archived: true`。每次 `limit: 1`，超时 5 秒。 |

**根据已核实协议重建的请求和成功响应。** 示例表示首次领取所得的未绑定工作区。传输层以 `requestId` 关联一对请求与回执。同一个发送意图重试时沿用 `draftId`。

```jsonl
{"type":"request","requestId":"draft-demo-1","method":"workspace/acquireDraft","params":{"name":"session-20261115080000","draftId":"49b16560-94ad-466c-8b5a-d4f81e21b100"}}
{"type":"response","requestId":"draft-demo-1","result":{"workspace":{"assetId":"asset_a1b2c3d4","name":"session-20261115080000","cwd":"D:\\example\\workspaces\\asset_a1b2c3d4","threadIds":[],"createdAt":1794729600000,"updatedAt":1794729600000}}}
```

## Hi3D 实现

### 决策

点击「新对话」先进入空白草稿界面。提交时，renderer 优先沿用同一发送草稿保存的 `assetId`，或当前有效会话已绑定的工作区。需要领取时，`QI` 以发送意图 UUID 作为 `draftId`，用 UTC 时间生成 `session-YYYYMMDDhhmmss` 显示名，先记录内存发送草稿，再通过 `Jr.M` 发出 RPC。首页快速发送 `jn` 也是独立的 UI 入口，复用同一 RPC。 [Electron 桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

Runtime 注册表的 `drafts` 以 `assetId` 为键。`{draftId: UUID}` 表示已领取，`{draftId: null}` 表示可从池中领取。首轮受理后该项被删除。显式创建的工作区也可以没有这项记录。`workspaces` 仍保存工作区本身，在 `relative-v1` 磁盘格式中以相对位置记录 `cwd`。 [注册表路径格式](create-workspace.md#hi3d-实现)

### 执行

#### 领取和首轮受理

1. **合并在途领取。** Runtime 先将 `draftId` 加入 `activeDraftClaims`。同 UUID 的并发调用共享 `draftAcquisitions` 中的 Promise。请求结束后删除 Promise 项，活动领取集合在当前 Runtime 进程内保留。回收读取当前工作区标记，只有其中仍指向活动 UUID 时才用这项保护。
2. **恢复原领取。** 优先查 `drafts` 中同 UUID 的记录。登记的 `cwd` 必须是 `<root>/<assetId>`，路径须存在且是非符号链接目录，真实路径须对应真实根目录下的该 ID。通过则返回原记录。这条路径允许已有附件或线程。
3. **检查可复用池。** 只检查标记原为 `null` 且当前仍为 `null`、登记无 `threadIds`、没有附件清理锁的候选，最多检查四个。每项先将标记改成当前 UUID，再异步检查严格空目录条件。检查失败只移除该池标记。命中时沿用原 `assetId`、名称和目录。池复用不重写 `AGENTS.md`，也无需重建已回收的 `inputs/`。
4. **按需创建并发布。** 没有合格目录时调用 `Jg.create(name)`。选定工作区后登记草稿标记并请求保存。RPC 处理器等待 `flushRegistry()`，发出 `workspace/updated` 后返回 `{workspace}`。renderer 合并工作区记录，再用 `assetId` 暂存附件。 [创建工作区](create-workspace.md#hi3d-实现)
5. **建立线程并消耗标记。** `thread/start` 成功后，Runtime 以 `cwd` 找到工作区并登记 `threadId`。收到同时带 `threadId` 和 `turn.id` 的 `turn/started`，或成功完成 `turn/start` 转发时，调用 `consumeDraft(threadId)`。它删除已绑定工作区上的草稿标记并保存，重复调用为空操作。目录、附件和线程绑定均保留。视窗打开是独立流程。 [绑定与恢复工作区会话](bind-and-restore-workspace-session.md) · [工作区打开](open-workspace.md)

**根据安装包控制流重建的领取伪代码。** 省略在途 Promise 合并及传输层校验。`strictEmpty` 使用后文的文件范围，要求 `inputs/` 若存在也为空。

```javascript
async function acquireDraftInternal(name, draftId) {
  const prior = await findSafeWorkspaceClaimedBy(draftId);
  if (prior) return prior;

  let checked = 0;
  let workspace;
  for (const candidate of reusablePoolSnapshot()) {
    if (!stillUnclaimed(candidate) || isCleaningInputs(candidate) || hasRegisteredThreads(candidate)) {
      continue;
    }
    if (checked === 4) break;
    checked += 1;

    setDraftMarker(candidate.assetId, { draftId });
    if (await strictEmpty(candidate.assetId)) {
      workspace = candidate;
      break;
    }
    deleteDraftMarker(candidate.assetId);
  }

  workspace ??= registry.create(name);
  setDraftMarker(workspace.assetId, { draftId });
  registry.save();
  return workspace;
}
```

#### 启动回收

1. **取得快照并调度。** Runtime 构造时复制注册表中的全部工作区记录。候选也可以来自没有草稿标记的工作区。首次完成 app-server 初始化和 Skill 发现后调度 `z8`，扫描逐项让出事件循环。Runtime 停止、app-server 更换或退出时停止扫描。同一 Runtime 内重启 Codex 子进程不会重新调度。这里没有按年龄或 TTL 筛选。
2. **预检文件和当前使用状态。** 要求工作区位于受管根下，路径与真实路径匹配，目录无符号链接，且无登记产物或模型元数据。根目录只允许普通 `AGENTS.md` 和 `exports/`、`scripts/`、`inputs/` 目录，这些项都可缺省。`exports/` 和 `scripts/` 必须为空。回收预检允许 `inputs/` 直接存普通文件，链接、嵌套目录、其他内容或读取失败都会否决。RPC 分派从 `assetId`、`cwd`、`threadId` 或 `cwds[]` 识别正在使用的工作区并加入进程内保护集合，`workspace/list` 和 `thread/list` 除外。
3. **向 Codex 核对线程。** 两次 `thread/list` 都须返回空 `data` 数组，且 `nextCursor` 为假值。`threadIds` 是登记缓存，启动快照中有旧 ID 也可以继续核对。出现普通或归档线程、有游标、结果结构异常或查询错误时跳过。查询抛错会记录该项警告。
4. **仅清理附件子目录。** 清理前后复核停止状态、保护状态和活动领取。源码复核工作区布局和 `inputs` 位置，在 `cleaningInputAssets` 挂起标记期间，仅对 `<root>/<assetId>/inputs` 执行递归删除。已有空 `inputs/` 也可删除。完成后再次用严格空目录条件检查，并在 `finally` 释放清理标记。保护状态在删除发出后才改变时，后续检查可阻止入池，已发生的删除不会回滚。
5. **登记入池。** `collectDraft(assetId, true)` 再确认工作区仍在且没有活动领取，清空登记的 `threadIds`，写入 `{draftId: null}` 并请求保存。扫描发出 `workspace/updated`。整个扫描正常结束且 Runtime 仍在运行时，统一等待注册表刷新。工作区根目录和 `assetId` 保留。 [Runtime 启动回收实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)

**根据安装包控制流重建的扫描伪代码。** `clearUnusedInputs` 内部包含路径、活动领取、并发保护及删除后的复检。两次 `listThreads` 的超时分别计量。

```javascript
async function recycleStartupSnapshot(candidates) {
  for (const workspace of candidates) {
    await yieldToEventLoop();
    if (stopped()) return;
    if (isProtected(workspace) || !await safeLayout(workspace, { allowInputFiles: true })) continue;
    if (stopped() || isProtected(workspace)) continue;

    try {
      const { cwd, assetId } = workspace;
      const ordinary = await listThreads({ cwd, archived: false, limit: 1 }, 5000);
      if (!emptyWithoutCursor(ordinary)) continue;
      const archived = await listThreads({ cwd, archived: true, limit: 1 }, 5000);
      if (!emptyWithoutCursor(archived)) continue;
      if (stopped()) return;

      const shouldSkip = () => stopped() || isProtected(workspace);
      if (shouldSkip() || !await clearUnusedInputs(assetId, shouldSkip) || shouldSkip()) continue;
      if (registry.collectDraft(assetId, true)) {
        notify("workspace/updated", { workspace: registry.get(assetId) });
      }
    } catch (error) {
      warnSkipped(workspace.assetId, error);
    }
  }
  if (!stopped()) await registry.flush();
}
```

### 验收

领取成功应能从回执拿到可用 `cwd` 和对应 `assetId`，接下来在同一目录暂存附件并绑定线程。首轮受理后，可以核对 `threadId` 仍指向原工作区、草稿标记已被删除。启动回收则核对原 `assetId` 仍在、`threadIds` 为空、标记为 `{draftId: null}`，并检查 `inputs/` 已清理或原先缺省。入池通知可能早于最终 `flush()`，须单独核对落盘结果。工作区列表仍可包含池中记录，单有列表项无法证明它已经被领取。

## 完成与恢复

| 情形 | 已核查行为与边界 |
| --- | --- |
| 参数不合法 | Runtime 校验返回 `INVALID_ARGUMENT`（`-32602`），不进入选目录或创建。 |
| 领取提交不明或刷新失败 | 保留原 `draftId`。还没有 `assetId` 时，桌面续办可用原 ID 重新请求。原标记存在且目录仍安全时会返回同一工作区。`flushRegistry` 失败返回 `INTERNAL`（`-32603`），内存登记与已发生的文件写入可能仍在。首轮已消耗标记后，原 `draftId` 不再提供领取去重保证。 |
| 附件仍在暂存 | 桌面保留工作区和已准备的文件项，继续补齐剩余附件再发送。丢弃本地发送草稿只结束该次桌面续办，工作区仍由 Runtime 管理。 |
| 首轮结果不明 | 保留原 `assetId`、`threadId` 和发送前轮次基线。通过 `thread/read({threadId, includeTurns: true})` 比对新增轮次的规范化正文及附件类型、路径和名称。匹配时沿用原轮次。有活动轮次或新增但不匹配的轮次时暂停重发。线程空闲且无新增轮次时才继续提交。明确收到线程或 rollout 不存在时，清掉失效线程引用与基线，保留原工作区。该发送入口用历史对账确认受理，`draftId` 不作为 `turn/start` 的幂等字段。 [发送恢复](llm-context.md#完成与恢复) |
| 桌面或 Runtime 重启 | renderer 的发送草稿和轮次基线保存在内存。原领取标记由 Runtime 另行持久化，已有线程可以按其登记恢复。仅凭领取标记无法重建原正文、附件准备进度和发送基线。 |
| 候选查询或清理未通过 | 跳过该项，继续检查后续候选。 |
| 启动回收中止或落盘失败 | Runtime 停止或 app-server 失效时收尾可能未完成。最终刷新出错会记录扫描失败。目录清理先于入池登记，已删除附件无法靠注册表恢复。下一次由新 Runtime 取得快照并重新判断。 |

## Vet3D 迁移与核查范围

Vet3D 可在宿主中定义不依赖供应商的三个状态变化。`claim(sendIntentId)` 返回稳定的工作区引用，供附件暂存和会话创建使用。宿主在创建会话时建立工作区关联，收到可确认的首轮受理后结束草稿状态。回收只把符合宿主回收策略、没有可用会话或文件占用证据的目录恢复为可领取。LLM、生图及 3D 模型选择可独立于这些状态变化。

如果 Vet3D 要支持应用重启后续办，应持久化发送意图与工作区的映射、附件准备进度及可供对账的受理标识。首次提交不明时优先对账原意图。回收范围应有明确策略，例如仅回收宿主明确标为可回收的目录。若支持清理附件，删除前再次核对当前领取与会话状态，删除结果与入池登记各自可查。这里的持久化发送进度及回收范围是 Vet3D 设计选择。

迁移验收覆盖同意图并发请求、两个意图竞争同一池项、领取回执丢失、首轮已受理但回执丢失、归档会话阻止回收、清理期间新占用、清理后入池写入失败，以及重启时如何恢复或明确终止续办。

| 证据 | 定位与结论 |
| --- | --- |
| 版本与文件摘要 | 本机使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources` 留存包，原安装目录的 `resources/app.asar` 本轮不可用。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [Runtime 1.2.11 清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Electron 静态证据 | 解出 `out/renderer/assets/index-CDPCug_K.js` 后，零基 UTF-8 字节偏移 `1107606` 为领取接口，`1314505` 为发送草稿内存存储，`1587759` 为 `QI`，`4737367` 为「新对话」入口 `Ji`，`4739645` 为首页快送 `jn`。`out/main/index.js` 中 `81911` 为领取 schema，`182782` 为领取入口白名单。 [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime 静态证据 | 原始零基字节偏移 `2166571` 为领取 schema，`2721998` 为处理器，`2684984` 和 `2685424` 为领取及选目录方法的参数锚点，`2699856` 为 `consumeDraft`。`2676246` 为启动快照，`2681430` 和 `2682885` 是目录校验与附件清理的参数锚点，`2684407` 为 `collectDraft`，`3099317` 为 `z8`，`3119456` 为启动调度，`3131458` 为 RPC 保护分支。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) |
| 离线验证与本机记录 | 对安装包提取的方法用替身执行，验证同 UUID 合并、不同意图争用、四候选上限、同 ID 恢复保留附件、标记消费、普通与归档线程筛选、安全布局、保护复检及通知与刷新顺序。历史桌面日志另记录了实际领取、建线程、打开和提交首轮的 RPC 顺序。 [本机桌面日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:156>) |
| 待验证 | 真实目录上的启动回收、真实删除期间的并发时序，以及进程异常退出时目录与注册表的组合结果，本轮未在实际桌面环境触发。 |
