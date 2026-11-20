# 移除工作区

本节点属于工作区基础设施的生命周期。核查对象为 Hi3D Agent 1.2.11（Windows x64）。宿主以 `assetId` 请求注销。Runtime 先清理线程关联的 Skill 草稿，再按路径校验结果处理磁盘目录，清理工作区登记及工作流图，最后刷新注册表并通知桌面。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 桌面宿主调用 `workspace/remove`。包内已定位的直接调用来自[显式创建后的打开失败补偿](create-workspace.md#验收与恢复)。 |
| 上游与输入 | 提供已登记的 `assetId`。Runtime 从工作区登记取 `cwd` 和 `threadIds`，以这些标识定位应清理的 Skill 草稿、产物、版本及工作流记录。 |
| 输出 | 成功返回 `{assetId}`，同时发布 `workspace/removed`。工作区及其关联数据从注册表注销。受管路径校验决定是否执行磁盘删除。 |
| 完成条件 | Runtime 完成登记清理和注册表刷新后返回成功。目录或工作流图文件的实际删除结果需另查。 |
| 下游交接 | [打开与切换工作区](open-workspace.md)按移除事件更新列表及当前资产。会话和工作流读取继续按已登记线程校验归属。 |

## Skill 与 LLM Tools

移除入口由桌面宿主和 Runtime 调用。关联 Skill 草稿属于此节点处理的宿主记录，是否选用建模 Skill 无需作为输入。历史会话归档及启动时的草稿回收各有自己的入口和作用域。

## 宿主接口

| 名称 | 类型及行为 |
| --- | --- |
| `workspace/remove` | Runtime 宿主 RPC。参数为 `{assetId: string}`，成功返回相同字段。工作区路径取自注册表。 |
| `workspace/removed` | Runtime 通知。在工作区注册表刷新成功后发布 `{assetId}`。renderer 也可根据 RPC 回执应用相同的移除状态。 |
| `runtime:request` | Electron IPC。preload 把方法和参数交给主进程，主进程验证可信 renderer、白名单及请求上下文，再转发 Runtime。 |
| `asset:setCurrent` | Electron IPC。已移除项为当前资产时，renderer 以 `null` 同步主进程的当前资产引用。 |
| `workspace/list` | Runtime 宿主 RPC。查询当前登记，用于移除结果不明时的对账。 |

**根据安装包协议重建的 JSONL 请求与结果。** 示例资产 ID 仅用于展示协议结构。通知和 RPC 回执分别交付桌面。

```jsonl
{"type":"request","requestId":"remove-demo-1","method":"workspace/remove","params":{"assetId":"asset_demo"}}
{"type":"notification","method":"workspace/removed","params":{"assetId":"asset_demo"}}
{"type":"response","requestId":"remove-demo-1","result":{"assetId":"asset_demo"}}
```

## Hi3D 实现

### 决策

| 入口 | 触发与处理范围 |
| --- | --- |
| 移除工作区 | renderer 的创建封装在 `workspace/create` 成功而打开失败或失效时，以本次返回的 `assetId` 调用移除。补偿异常被捕获，调用方仍收到原打开错误。主进程白名单开放该 RPC。已核查的界面未找到独立的工作区删除按钮。 |
| 历史侧栏「删除」 | 普通会话经确认走 `thread/archive`，按线程中断关联处理，归档后清理 Skill 草稿及桌面会话显示。本地已缓存线程、轮次列表为空且没有活动轮次标记时，可直接从界面移除。两条分支都保留工作区登记。 [归档会话](bind-and-restore-workspace-session.md#归档会话) |
| 启动回收草稿工作区 | 通过布局、领取状态和线程检查后，回收符合条件的 `inputs/` 并保留工作区记录及根目录供后续领取。 [领取与回收草稿工作区](acquire-and-recycle-draft-workspace.md) |

### 执行

1. **查工作区。** Runtime 按契约解析 `assetId`，用 `mustWorkspace` 读取登记。未知 ID 返回 `INVALID_ARGUMENT`（`-32602`）。
2. **处理关联 Skill 草稿。** `skillDrafts.deleteByThreads` 逐项处理所属线程的未删除草稿。删除前校验线程归属和 `stateVersion`，以 `thread_deleted` 记录删除原因，将草稿和修订的删除状态写入草稿存储，尽力回收修订目录。对于同一草稿触发的安装任务，等待可取消任务完成取消。状态为 `succeeded`、`committing` 或 `refreshing` 的安装跳过取消。安装管理器中的卸载是独立入口。
3. **按路径条件处理磁盘。** `Jg.remove` 取得登记的 `cwd`。受管路径校验要求逻辑路径等于 `resolve(workspacesRoot, assetId)`，路径存在且最终路径项为非符号链接，真实路径等于 `resolve(realpath(workspacesRoot), assetId)`。校验通过时调用 `rmSync(cwd, {recursive: true, force: true})`。校验异常由 `isManagedWorkspaceDirectory` 转为假值，后续仍执行注销。这个检查未调用 `isDirectory()`，处于精确受管路径的普通文件也可能走删除分支。
4. **移除登记。** 从 `workspaces` 删除目标记录。按 `assetId` 清理 `artifacts`、`modelMetadata`、`hi3dDownloads` 和草稿领取映射 `drafts`。按登记的每个 `threadId` 清理 `threadPolicies`、`threadRuntimeToolVersions`、`threadLocales` 和 `imageClassifications`。调用 `Jg.save()` 标记注册表待写。
5. **清理工作流图并刷新。** 按线程清除图缓存和待绑定映射，尝试以 `force: true` 删除 `<dataDir>/workflow-graphs/<sha256(threadId)>.json`。图文件删除异常只记录日志。Runtime 随后等待 `flushRegistry()`，成功才发送 `workspace/removed` 并返回 `{assetId}`。 [工作流图状态](workflow-graph-state.md) · [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

磁盘递归删除覆盖实际工作区内的输入、导出、模型版本和本地作业文件。其余目录和服务各自管理生命周期。已核查的 Runtime 链路未调用 Codex 的归档、删除或轮次中断，也未调用远端作业取消。Codex 会话历史、独立重试登记和 Skill 捕捉数据分别存放。注销后，普通会话与工作流读取按原有规则检查线程是否仍有工作区归属。 [会话归属校验](bind-and-restore-workspace-session.md#执行) · [工作流读取 RPC](interfaces/workflow-read-rpc.md)

**根据安装包重建的核心伪代码。** `isManagedWorkspacePath` 将路径校验异常转换为假值，工作流图文件清理由其内部处理错误。磁盘移除、内存注销与注册表刷新顺序执行。

```javascript
async function removeWorkspace(assetId) {
  const workspace = requireRegisteredWorkspace(assetId);
  await skillDrafts.deleteByThreads(workspace.threadIds);

  if (isManagedWorkspacePath(workspace)) {
    removeManagedPathSync(workspace.cwd, { recursive: true, force: true });
  }
  registry.removeWorkspaceRecord(assetId);
  registry.clearThreadMetadata(workspace.threadIds);
  registry.clearAssetMetadata(assetId);
  registry.scheduleSave();

  workflowGraphs.removeThreadsBestEffort(workspace.threadIds);
  await flushRegistry();
  notify("workspace/removed", { assetId });
  return { assetId };
}
```

### 验收

1. **登记已注销。** 成功回执或 `workspace/removed` 表示运行时注册表刷新已返回。可用 `workspace/list` 和磁盘注册表核对目标 ID。目录曾因缺失或路径校验失败被跳过时，按受管路径另查实际文件结果。
2. **桌面已应用。** renderer 将回执和移除通知交给同一个处理函数，从列表删除该 ID。目标为当前资产时，失效正在进行的打开请求，清空模型目录、所选文件和待展示请求，再同步 `asset:setCurrent(null)`。App 可因模型 URL 为空而隐藏 Studio。聊天历史没有对应的直接清除分支。 [工作区活动状态](open-workspace.md)
3. **缓存有独立边界。** Electron 主进程的 `assetId → cwd` 缓存只合并收到的目录。移除通知、回执和之后的列表缺项均不会单独逐出旧值。隔离测试还复现了在移除处理后收到迟到的旧列表响应，renderer 可以重新插入该旧条目。对账使用新取得的 Runtime 列表，先前的目录缓存仅作定位辅助。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

## 完成与恢复

| 情形 | 状态及对账方式 |
| --- | --- |
| Skill 草稿处理或安装取消抛错 | 在移除目录之前中止。已写的草稿删除标记和已回收的修订可能保留。核对草稿与关联安装状态后再决定是否重试原资产。 |
| 目录缺失或不符合受管路径条件 | 跳过磁盘删除，仍清理工作区登记。若原目录仍有文件，应分别核对登记和磁盘。 |
| `rmSync` 抛错 | 在工作区注销前中止，普通文件系统错误由通用包装返回 `INTERNAL`（`-32603`）。前序 Skill 清理可能已完成，目录内容需另查。 |
| 工作流图文件删除失败 | 图缓存及待绑定映射已清除。异常记日志，注册表刷新及回执继续。磁盘图文件仍可能存在。 |
| 注册表刷新失败 | 返回 `INTERNAL`，本次不发布移除通知。目录、内存登记和图可能已经清理，磁盘注册表仍待写。后续刷新可再次尝试写入。 |
| 结果不明或重复请求 | 按原 `assetId` 对照最新 `workspace/list`、磁盘注册表、原目录和图文件。已经注销的 ID 再请求会按未知工作区处理。因此，重送的结果只说明重送时的登记状态。 |

## Vet3D 迁移与核查范围

Vet3D 可用稳定的工作区 ID 确定移除目标。宿主从登记解析允许操作的实际路径，并用工作区级的状态控制新写入和打开请求。定义独立的移除意图 ID，分别记录关联任务、磁盘清理、登记提交与界面失效的进度。响应中可明确区分已清理、缺失、因路径校验而跳过以及部分失败。移除事件和回执使用同一意图关联，便于重试和对账。

会话归档、远端任务取消和永久目录清理各有独立的动作及完成条件。登记提交后，以同一版本或删除标记使路径缓存、活动资产和在途回包失效，并按记录复查尚未完成的清理项。工作区级状态、持久化移除意图及显式清理结果是 Vet3D 设计，独立于采用的 LLM、3D 供应商和视窗实现。

| 核查依据 | 定位与结论 |
| --- | --- |
| 版本与摘要 | 核查使用安装事务备份中的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) |
| Renderer | `out/renderer/assets/index-CDPCug_K.js` 内 `1107232` 为创建与打开补偿，`1107473` 为移除请求，`1108847` 和 `1108891` 为通知分派及桌面状态更新，`1129871` 为侧栏归档。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Electron main | `out/main/index.js` 内 `82131` 为 RPC 契约，`175764` 为可信请求入口，`182824` 为白名单，`209998` 为工作区路径缓存更新。 [桌面 ASAR](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime | `runtime/dist/runtime.mjs` 内 `2166888` 为请求契约，`2722337` 为处理器，`2698415` 为 `Jg.remove`，`2704346` 为受管路径校验，`2727325` 为注册表刷新。`3013641`、`2973576` 是 Skill 草稿按线程清理及草稿删除的参数锚点，`3053017` 为图文件路径函数，`3075247` 是图清理的参数锚点。偏移均为文件或解出 ASAR 成员内的零基字节位置。 [原始 Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 已验证 | 以替身执行安装包提取的函数，复现了执行顺序、受管路径校验失败后注销、目录删除错误停止、图文件删除错误继续、刷新失败不通知，以及桌面的回执和通知处理。抽查四份生产日志，观察到独立的 `thread/archive` 请求及完成记录。 [侧栏归档日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1887>) |
| 待验证 | 核查日志中未发现 `workspace/remove` 或 `workspace/removed` 的生产样本。完整桌面触发、真实磁盘故障、并发操作及通知时序仍待实测。未删除实际工作区。 |
