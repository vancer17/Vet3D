# 绑定与恢复工作区会话

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。Runtime 按工作区的 `cwd` 绑定新建线程，随后按已登记的 `threadId` 恢复会话。renderer 采用有效会话后，再将线程及其工作区交给桌面导航和本轮输入组装。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 用户在尚无线程的工作区发送首条消息、打开历史会话，或在侧栏确认删除会话。宿主也可以恢复已登记线程，或在列表刷新时补录已有归属。 |
| 上游与输入 | 创建使用已登记工作区的绝对 `cwd`。若来源是新对话，先[领取草稿工作区](acquire-and-recycle-draft-workspace.md)并[准备参考素材](import-reference-materials.md)。恢复使用已登记的 `threadId`，调用方可带历史列表中的 `cwd`。 |
| 输出 | Runtime 注册表中的 `threadId → assetId → cwd` 关联及返回的线程对象。Runtime 对有登记匹配且含字符串 `cwd` 的回包统一目录值。renderer 按导航状态采用返回对象或缓存，用线程 ID 读取轮次，用 `cwd` 定位工作区。 |
| 完成条件 | 创建或补录时，以 app-server 返回线程 ID、写入对应 `threadIds` 并成功刷新注册表为准。恢复时，以有效缓存或成功的恢复及必要补读被当前导航采用为准。归档时分别核对 Codex 已归档和宿主已完成清理。会话绑定、桌面工作区激活和轮次受理分别验收。 |
| 下游交接 | [打开与切换工作区](open-workspace.md)按活动线程的 `cwd` 读取工作区及模型目录。[构建当前轮的工作区上下文](llm-context.md#校验后转发给-codex)按 `threadId` 发送新轮或续轮，并核对可用历史和附件。 |

## Skill 与 LLM Tools

创建、登记、列表补录和恢复均由宿主接口实现，适用于普通会话。Runtime 在 `thread/start`、`thread/resume`、`thread/fork` 时准备工作区的有效 Skill 配置和开发者指令；新建线程时还合并 renderer 与 Runtime 的动态工具定义。显式选用 Skill 后，正文和阶段规则按本轮上下文处理。列表查询和线程绑定本身由宿主发起。 [随包 Skill 归档](../../upstream/1.2.11/README.md) · [有效 Skill 的选用](llm-context.md#有效目录与选用)

## 宿主接口

| 名称 | 作用与边界 |
| --- | --- |
| `workspace/list` | Runtime 宿主 RPC。给 renderer 提供登记工作区及其 `cwd`，用于枚举历史。 |
| `thread/start` | app-server RPC，经 Runtime 转发。以登记的 `cwd` 创建线程，可带模型、推理配置、动态工具和开发者指令。Runtime 用返回的 `thread.id` 建立归属。 |
| `thread/list` | app-server RPC。宿主按登记的 `cwd` 分页查询，响应的 `data` 与 `nextCursor` 用于补录及继续分页。 |
| `thread/resume`、`thread/fork` | app-server RPC。以已登记的 `threadId` 恢复或分叉，Runtime 以该线程的登记路径准备 `cwd`。分叉还可传递 `turnId`。 |
| `thread/read` | app-server RPC。以已登记的 `threadId` 读回线程。renderer 请求 `includeTurns: true` 时用于补齐轮次或对账。 |
| `thread/archive` | app-server RPC，经 Runtime 转发。侧栏确认删除普通会话时以 `{threadId}` 提交，归档后保留工作区绑定。 |
| `thread/unsubscribe` | Runtime 向 app-server 发出的内部请求。恢复已登记线程时，若当前未跟踪该线程的运行中轮次，先解除旧订阅。 |
| `runtime:request`、`runtime:cancel-request` | Electron IPC。主进程校验可信 renderer、方法和请求上下文，并经队列转发。可取消的调用以客户端请求 ID 关联取消。 |
| `runtime/executionState`、`transcriptInvalidated` | 前者是 Runtime 的执行快照通知。后者是桌面主进程告知 renderer 转录需重同步的事件。 |

**根据安装包协议重建的 JSONL 请求。** 假设 `asset_demo` 已登记，`thread/start` 返回了 `thread_demo`。恢复示例故意传入另一个目录，Runtime 会用 `thread_demo` 的登记路径覆盖它。第三条展示恢复结果无轮次时的补读，第四条展示独立的会话归档动作。

```jsonl
{"type":"request","requestId":"bind-demo","method":"thread/start","params":{"cwd":"D:/example/workspaces/asset_demo"}}
{"type":"request","requestId":"resume-demo","method":"thread/resume","params":{"threadId":"thread_demo","cwd":"D:/example/workspaces/asset_other"}}
{"type":"request","requestId":"read-demo","method":"thread/read","params":{"threadId":"thread_demo","includeTurns":true}}
{"type":"request","requestId":"archive-demo","method":"thread/archive","params":{"threadId":"thread_demo"}}
```

## Hi3D 实现

### 决策

1. **首次发送。** renderer 的 `Sn` 优先沿用现有线程。无可用线程时，`xt` 用已选工作区的 `cwd`、桌面动态工具及会话设置请求 `thread/start`。工作区 `assetId` 用于宿主的目录和附件管理。已有活动轮次时，`Sn` 可先尝试带预期轮次 ID 的 `turn/steer`，并在需要时读回状态，再决定是否开启新轮。 [会话转发](llm-context.md#校验后转发给-codex)
2. **启动刷新。** Runtime 就绪后，renderer 先取 `workspace/list`，再按各工作区的 `cwd` 枚举 `thread/list`。标准列表每页 50 项，`archived: false`，按 `updated_at` 降序。游标缺失或重复即停止。单目录查询失败时保留该目录的旧列表，合并时按线程 ID 去重并重新排序。新 renderer 没有活动线程时，历史刷新保持空选择。同一 renderer 内重启 Runtime 后，仍在列表中的当前项可以重新打开。
3. **选择恢复方式。** 侧栏点击进入 `ri`。它优先采用正在启动或运行的线程缓存，其次采用已加载且时间戳未落后于列表摘要的缓存。时间戳缺失时也允许复用已加载缓存。无轮次且无活动轮次 ID 的空缓存另有快捷分支。缓存不满足条件时走 `thread/resume`。从系统通知进入会话时，也可经宿主的待打开会话入口调用同一个 `openThread`。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

### 执行

1. **检查登记和准备目录。** `assertAppServerScope` 对 start 和 list 检查 `cwd`，对 resume、read、fork 及轮次请求检查 `threadId`。`byCwd` 分别对输入及已登记目录尝试 `realpathSync`，失败时用 `path.resolve`，再比较结果。这是登记范围检查。实际目录可用性和路径布局由[工作区打开](open-workspace.md#执行)等文件入口另行校验。resume 和 fork 用 `byThreadId` 查到的 `cwd` 覆盖调用方值。
2. **转发并更新归属。** `forwardAppServerMethod` 先处理恢复前的订阅分支，再准备宿主参数并调用 app-server。收到成功响应后，`afterAppServerCall` 按下表决定是否登记线程。`Jg.attachThread` 只在目标记录尚无此 ID 时追加并更新工作区 `updatedAt`，适用的线程策略也可在缺失时写入。

   | 方法 | 登记行为 |
   | --- | --- |
   | `thread/start`、`thread/resume` | 用准备后的请求 `cwd` 定位工作区，采用回包 `thread.id`。首建还记录 Runtime 工具版本。 |
   | `thread/list` | 将这一页里有 ID 的条目登记到请求 `cwd` 对应的记录。Runtime 不逐条以回包 `cwd` 复核。这个补录可以恢复缺失的关联。 |
   | `thread/fork` | 将新线程登记到源线程的工作区，继承源线程已记录的 Runtime 工具版本及语言。 |
   | `thread/read` | 读回已登记线程，并在有轮次数组时更新执行快照。其成功后处理没有新增绑定或强制刷新注册表。 |

3. **处理回包并落盘。** `finishAppServerCall` 先应用登记。read、resume、start 和 fork 在返回有效线程及轮次数组时更新执行快照并发出 `runtime/executionState`。对 `thread/*` 回包中的字符串 `cwd`，`normalizeThreadCwds` 优先按返回线程 ID 找登记，找不到时回退按回包 `cwd` 查，再用登记路径改写。`thread/start`、`thread/resume`、`thread/fork`、`thread/list` 和后续的 `turn/start` 都等待 `registry.flush()` 后再返回 RPC 响应。执行快照通知发生在刷新等待之前。
4. **在 renderer 采用有效结果。** resume 成功但轮次缺失或为空时，`ri` 再请求 `thread/read(includeTurns: true)`。请求序号和取消信号仍有效时，`Ti` 合并线程快照、更新历史并设置活动线程 ID。迟到的 `thread/start` 回包可进入历史缓存，只有原导航仍有效时才设置活动选择。当前会话切换后，由根组件监听线程 ID 与 `cwd`，发起独立的工作区打开。 [工作区打开](open-workspace.md)

注册表位于受管工作区根的 `registry.json`，关联实际保存在各工作区记录的 `threadIds`。启用 `relative-v1` 时，写盘以 `assetId` 保存 `cwd`，读取时由受管根重建绝对目录。列表补录和显式登记共用 `attachThread`，只在目标记录内去重。如果同一 ID 出现在多条记录，`byThreadId` 取注册表中的首个匹配项。会话历史由 Codex 另行存储，归档会话在已核查的本机样本中仍有工作区登记。 [Runtime 安装包](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Codex 会话历史](llm-context.md#读取线程和恢复有效历史)

**根据安装包控制流重建的 Runtime 伪代码。** 展示本节点的归属检查、回填与提交顺序。省略宿主参数过滤细节、策略记录和转发错误包装。

```javascript
async function routeThreadRequest(method, request) {
  assertAppServerScope(method, request);
  const source = request.threadId ? registry.byThreadId(request.threadId) : null;
  const needsRegisteredCwd = method === "thread/resume" || method === "thread/fork";

  if (method === "thread/resume" && !runningTurns.has(request.threadId)) {
    await appServer.request("thread/unsubscribe", { threadId: request.threadId });
  }
  const scopedRequest = needsRegisteredCwd ? { ...request, cwd: source.cwd } : request;
  const params = await prepareHostParams(method, scopedRequest);
  const result = await appServer.request(method, params);

  if (method === "thread/list") {
    const workspace = registry.byCwd(params.cwd);
    if (workspace) {
      for (const row of result.data ?? []) {
        if (row.id) registry.attachThread(workspace.assetId, row.id);
      }
    }
  } else if (method === "thread/fork") {
    const parent = registry.byThreadId(params.threadId);
    if (parent && result.thread?.id) registerFork(parent, params.threadId, result.thread.id);
  } else if (method === "thread/start" || method === "thread/resume") {
    const id = result.thread?.id;
    if (id) {
      const workspace = params.cwd ? registry.byCwd(params.cwd) : registry.byThreadId(id);
      if (workspace) registry.attachThread(workspace.assetId, id);
    }
  }

  if (["thread/read", "thread/start", "thread/resume", "thread/fork"].includes(method)) {
    if (result.thread?.id && Array.isArray(result.thread.turns)) {
      publishExecutionSnapshot(result.thread.id, result.thread.turns);
    }
  }
  normalizeThreadCwds(result);
  if (["thread/start", "thread/resume", "thread/fork", "thread/list"].includes(method)) {
    await registry.flush();
  }
  return result;
}
```

### 归档会话

1. **桌面处理用户确认。** 本地已缓存线程、轮次列表为空且没有活动轮次标记时，renderer 可直接移除侧栏会话。其他会话走 `thread/archive({threadId})`。仍能取得活动轮次 ID 时，renderer 先等待停止处理器尝试 `turn/interrupt`。停止处理器返回失败标记也会继续发归档。
2. **Runtime 中断关联处理并转发。** `terminateThread` 取消该线程的上下文压缩，按线程中断符合条件的免费重试、给 Runtime 在途 Hi3D 调用发取消信号并取消待答交互。它转发 `thread/archive` 给 Codex，并在 Codex 成功响应后再次中断残余请求。
3. **清理归档后的状态。** Runtime 清除该线程的语言缓存并等待删除关联 Skill 草稿，再返回 RPC 结果。renderer 成功拿到结果后清理会话缓存及侧栏项，原本活动的会话还可能触发下一条历史会话的打开。工作区记录和模型文件继续独立保存。 [移除工作区](remove-workspace.md)

### 验收

- **归属已建立。** 工作区注册记录已包含返回的 `threadId`，刷新成功。重启后可从绝对展开的 `cwd` 和同一线程 ID 找回归属。回包中的工作区路径可用于 renderer 的目录匹配。
- **会话已采用。** renderer 已将有效线程设置为当前会话并取得可用轮次。命中缓存时可以没有本次 RPC。工作区模型目录由后续 `workspace/open` 取得。
- **轮次已受理。** 新轮或续轮以转发结果、轮次通知或历史对账确认。创建线程的回执和运行态快照各有自己的含义，不能据此直接判首轮已受理。 [会话上下文验收](llm-context.md#验收)
- **会话已归档。** 使用原工作区 `cwd` 查询归档列表，按 `threadId` 核对。宿主归档回执和侧栏移除可用来核对桌面完成状态。工作区范围另查注册表。

## 完成与恢复

| 情形 | 已核查行为或核对方式 |
| --- | --- |
| 参数或登记错误 | start 和 list 的 `cwd` 未匹配登记记录时返回 `METHOD_NOT_ALLOWED`。resume、read 或 fork 缺少 `threadId` 时为 `INVALID_ARGUMENT`，未知 ID 为 `METHOD_NOT_ALLOWED`。由原工作区列表发现的线程可通过补录取得归属。 |
| 建线程回包不明或注册表刷新失败 | app-server 建线程先于绑定刷新，失败回包仍可能留下线程或待写登记。应以原 `cwd` 查询历史并对照登记和轮次。列表补录只有在 app-server 能枚举此前线程时才生效。线程已建立也可能尚未受理首轮。 |
| 恢复失败或返回迟到 | 当前打开失败时在 renderer 记录错误，已提交的选择可保留。新导航使旧请求失效，旧结果不可设置活动线程。 |
| 转录失步 | 主进程可合并可见窗口的文本增量。窗口隐藏时省略部分事件并按线程标记需同步，重新显示后发出 `transcriptInvalidated`。renderer 按线程合并补读任务，用 `thread/read(includeTurns: true)` 更新轮次，再重放读取期间暂存的通知。该路径与 resume 空轮次后的补读独立。 |
| Runtime 或 app-server 重启 | 按注册表恢复归属，按 Codex 会话存储恢复历史。renderer 可暂将旧缓存中的进行中轮次显示为中断，再用读回结果校准。若 renderer 命中缓存，后续发轮时 Runtime 仍可在配置代次缺失或变化时执行内部恢复。 |
| 首轮提交不明 | 同一 renderer 内保留原工作区、线程 ID、发送前的轮次基线及附件引用。通过 `thread/read` 比对新增轮次。已有匹配则确认受理。线程空闲且没有新增轮次时才重试。发送草稿及基线保存在 renderer 内存，工作区归属由 Runtime 另行持久化。 [会话发送恢复](llm-context.md#完成与恢复) |
| 归档返回错误或结果不明 | 在途处理可能在 Codex 归档前已被中断。Skill 草稿清理可能在 Codex 已归档之后失败。保留原 `threadId` 和 `cwd`，按 `archived: true` 和 `archived: false` 核对原线程，再核对关联草稿和侧栏状态。 |

## Vet3D 迁移与核查范围

Vet3D 可在宿主持久化稳定的工作区 ID、内部会话 ID 和引擎线程引用。在当前环境及账户范围内为引擎线程引用建立唯一归属，按工作区解析受管目录。列表发现可以补齐缺失映射，遇到不同归属则保留冲突供核对。LLM 及执行引擎的适配器负责创建、恢复和读取轮次，工作区归属由宿主维护。

将**绑定已提交、会话已采用、轮次已受理**分别记录。首发可持久化发送意图 ID、工作区 ID、已知引擎线程引用和轮次基线。提交不明时先查原意图对应的记录和历史。供应商支持幂等键或可按意图查询时，可由适配器建立关联。缓存和轮次补读路径应用同一导航有效性检查。会话的当前历史与模型有效上下文可以分别恢复。上述唯一归属、持久化发送意图和冲突处理是 Vet3D 设计。

迁移验收覆盖首建和重启恢复、错误目录提示、未知线程、列表发现与归属冲突、快速切换与迟到响应、转录重复合并，以及引擎先成功但本地落盘失败和首轮确认丢失。分别核对持久登记、可见会话和实际执行状态。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与摘要 | 原安装目录 `D:/install/Hi3DAgent` 为空，核查使用同级安装事务备份的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Renderer | `out/renderer/assets/index-CDPCug_K.js` 内 `1075262` 为恢复请求，`1075411` 为补读请求，`1076099` 为分页列表，`1119370` 为历史刷新，`1120134` 为建线程，`1120722` 为打开会话，`1121496` 为采用活动线程，`1135966` 为转录补读，`4735562` 为工作区打开交接。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Preload 与 Electron main | `out/preload/index.js` 内 `4393` 为请求桥接。`out/main/index.js` 内 `175764` 为 IPC 入口，`203759` 为 Runtime 请求转发，`291149` 为转录增量处理，`293216` 为转录失效事件。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime | `runtime/dist/runtime.mjs` 内 `2673574` 为注册表，`2676553` 为 `byCwd`，`2677013` 是 `byThreadId` 的参数锚点，`2699293` 为线程登记，`2709919` 为序列化，`3101273` 为等待刷新方法集合，`3143897` 为 app-server 转发，`3153565` 为成功回包处理的参数锚点，`3154446` 为目录归一，`3155489` 为参数准备的参数锚点，`3163249` 为归属校验，`3164883` 为登记分支。偏移均为原始文件或解出 ASAR 成员中的零基字节位置。 [Runtime 安装包](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 已验证 | 从包中提取函数并使用替身，复现了归属拒绝、创建与刷新顺序、列表补录、目录覆盖、分叉继承、恢复补读和导航竞态。本机注册表的线程 ID 与活动、归档两份 rollout 相符。已有队列日志按请求诊断 ID 记录首次绑定及两次新 app-server 握手后的列表和恢复顺序。 [本机登记](</D:/download/.sparc3d-runtime/environments/prod/workspaces/registry.json>) · [建线程日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:158>) · [第一次恢复日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261113T081710Z-42224.log:72>) · [第二次恢复日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261113T083555Z-17988.log:51>) |
| 归档证据 | renderer 成员 `1128122` 为停止处理器，`1129988` 为归档调用。原始 Runtime 的 `3142711` 为 `terminateThread`，`3155094` 为 `abortThreadCalls`。安装包静态核对了中断顺序和归档后的草稿清理。同一诊断 ID 的日志记录了归档请求和完成。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [归档请求日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1887>) · [归档完成日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1889>) |
| 待验证 | 完整桌面中的注册表刷新故障、resume 返回空轮次时的实际补读、窗口恢复引发的转录重同步，以及 Codex 已归档但 Skill 草稿清理失败时的界面表现。现有日志可对照队列事件和附近的线程状态。 |
