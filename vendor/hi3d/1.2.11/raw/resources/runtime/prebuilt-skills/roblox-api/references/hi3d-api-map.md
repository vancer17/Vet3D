# Engine、Studio 与 Open Cloud 接口地图

这里记录通用接口，不保留某个游戏的物品名、数值或场景坐标。列为“已用模式”表示原有制作代码确实使用过该接口族，不表示每个列出的成员都曾调用，亦不表示已在真实 Studio 或云端完成验收。聊天事件和资格查询模板是整理时补充的推荐诊断，不能计为此前已经执行的操作。

| 接口族/具体成员 | 运行位置与已用模式 | 公开文档 |
| --- | --- | --- |
| `game:GetService()`、`Instance.new()`、`FindFirstChild()`、`WaitForChild()`、`GetChildren()`、`GetDescendants()`、`IsA()`、`Clone()`、`Destroy()`、`GetAttribute()/SetAttribute()` | 编辑期建立对象树；运行期获取服务、生命周期和实例元数据。跨复制边界等待要有超时与恢复提示 | [Instance](https://create.roblox.com/docs/reference/engine/classes/Instance)、[ServiceProvider](https://create.roblox.com/docs/reference/engine/classes/ServiceProvider) |
| `Part`/`MeshPart`/`SpawnLocation`、`BasePart.Size/CFrame/Anchored/CanCollide/CanQuery/CanTouch` | 编辑期配置实体、出生点、碰撞与射线代理；属性是不同开关，不混用 | [BasePart](https://create.roblox.com/docs/reference/engine/classes/BasePart)、[MeshPart](https://create.roblox.com/docs/reference/engine/classes/MeshPart) |
| `Model:GetBoundingBox()/GetPivot()/PivotTo()/GetScale()/ScaleTo()` | 编辑期资产替换、对齐与尺度校准；保存 anchor/pivot，先预检所有输入再改对象 | [Model](https://create.roblox.com/docs/reference/engine/classes/Model)、[PVInstance](https://create.roblox.com/docs/reference/engine/classes/PVInstance) |
| `Vector3`、`CFrame.new/Angles/lookAt`、`Color3.fromRGB`、`UDim2` | 明确米/stud、弧度、颜色和屏幕空间；用变换而非位置猜朝向 | [数据类型](https://create.roblox.com/docs/reference/engine/datatypes)、[单位](https://create.roblox.com/docs/physics/units) |
| `Workspace:Raycast()`、`RaycastParams`、`RaycastResult` | 服务端验证射线、视线；客户端可做瞄准表现，不能决定伤害/奖励。direction 是带长度的位移向量 | [WorldRoot](https://create.roblox.com/docs/reference/engine/classes/WorldRoot)、[RaycastParams](https://create.roblox.com/docs/reference/engine/datatypes/RaycastParams) |
| `Players.PlayerAdded/PlayerRemoving/GetPlayers()`、`Player.CharacterAdded/Character` | 每玩家独立状态、重生世代和离开清理；启动时处理已在场玩家 | [Players](https://create.roblox.com/docs/reference/engine/classes/Players)、[Player](https://create.roblox.com/docs/reference/engine/classes/Player) |
| `Humanoid.Health/MaxHealth/Died/HealthChanged/TakeDamage/EquipTool/UnequipTools`、`Tool.Activated/Equipped/Unequipped` | 按当前玩法需要接入角色生命和工具，不默认启用任何战斗类型 | [Humanoid](https://create.roblox.com/docs/reference/engine/classes/Humanoid)、[Tool](https://create.roblox.com/docs/reference/engine/classes/Tool) |
| `RemoteEvent.OnServerEvent/FireServer/FireClient/FireAllClients/OnClientEvent` | 输入意图→服务器校验→权威状态/表现通知；玩家参数由引擎提供，不相信 payload 自报玩家身份 | [RemoteEvent](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent)、[边界校验](https://create.roblox.com/docs/scripting/security/client-server-boundary) |
| `ProximityPrompt.Triggered/MaxActivationDistance/HoldDuration/RequiresLineOfSight` | 引擎提供交互提示；服务器另验距离、视线、状态和领取幂等，提示可见不等于请求可信 | [ProximityPrompt](https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt) |
| `RunService.IsStudio/IsRunning/Heartbeat/RenderStepped`、`task.spawn/delay/wait`、`Debris:AddItem` | 运行侧判断、固定/节流更新、有限短命表现、旧回调取消。`RenderStepped` 属客户端，服务端不处理 UI | [RunService](https://create.roblox.com/docs/reference/engine/classes/RunService)、[Debris](https://create.roblox.com/docs/reference/engine/classes/Debris)、[task](https://create.roblox.com/docs/reference/engine/libraries/task) |
| `UserInputService.InputBegan/GetFocusedTextBox/TouchEnabled/MouseEnabled`、`GuiButton.Activated` | 尊重 processed 与文字框焦点；移动端/键鼠映射到同一语义动作 | [UserInputService](https://create.roblox.com/docs/reference/engine/classes/UserInputService)、[GuiButton](https://create.roblox.com/docs/reference/engine/classes/GuiButton) |
| `Workspace.CurrentCamera`、`Camera.ViewportPointToRay/ViewportSize`、`Player:GetMouse()` | 客户端镜头和瞄准；GUI 偏移/安全区、输入设备切换、重生后引用重绑另验 | [Camera](https://create.roblox.com/docs/reference/engine/classes/Camera) |
| `ScreenGui`、`Frame`、`TextLabel`、`TextButton`、`UIScale`、`BillboardGui`、`SurfaceGui` | HUD、交互反馈、角色/世界标签；`ResetOnSpawn`、重复连接和屏幕适配决定生命周期 | [GUI](https://create.roblox.com/docs/ui) |
| `TextChatService.CreateDefaultTextChannels/CreateDefaultCommands`、`TextChannel:DisplaySystemMessage`、`SendingMessage/MessageReceived`、`CanUserChatAsync/CanUsersChatAsync` | 默认聊天配置、元数据诊断和资格检查。系统提示仅本地显示；不自建未过滤转发 | [聊天](https://create.roblox.com/docs/chat/in-experience-text-chat)、[TextChatService](https://create.roblox.com/docs/reference/engine/classes/TextChatService) |
| `Workspace.StreamingEnabled`、`Model.ModelStreamingMode`、`Lighting`、`SurfaceLight.Shadows` | 编辑期加载和光照策略；Atomic 仅适合需一起出现的适度大小结构，不给整个世界无条件开启 | [流式加载](https://create.roblox.com/docs/workspace/streaming)、[Model](https://create.roblox.com/docs/reference/engine/classes/Model) |

## 后续按需能力，不能记成已经使用

- `DataStoreService:GetDataStore()`、`GlobalDataStore:UpdateAsync()`：持久化、并发和失败恢复；当前内存状态不自动成为云存档。服务端实现、测试命名空间、预算/重试和 `BindToClose` 另按官方契约设计。
- `PathfindingService`：真实可行走路径与动态障碍更新；静态通道抽样不等于 NavMesh/物理验收。
- Open Cloud `POST /universes/v1/{universeId}/places/{placeId}/versions?versionType=Published`：更新已有 Place，返回 `versionNumber`；此前对话中的准备/说明不属于调用过该 API。
- Assets API、OAuth、跨服消息、语音和付费能力：当前不是必需依赖；有明确需求再读取相应公开契约，不凭名字构造 API 或申请权限。

完整相关原文在 [官方资料](hi3d-sources.md) 的归档中；未归档的扩展项通过上面的在线文档核实。`security`、`thread_safety`、`serialization`、弃用字段和运行侧都属于接口契约，不能只看函数名。
