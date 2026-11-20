# 工程接入与服务器权威

## 创建与组织

默认以现有 Roblox 工程为权威输入。保留最新用户修改，不从旧版本覆盖整场景。无工程时由执行者建立可编辑 Place 与独立 Luau 源文件；XML 可作为可审阅的序列化交付，但必须在 Studio 打开、保存、重开。Python 写 `.rbxlx` 是离线文件操作，不是远程控制 Studio，也不是官方 XML schema 验证。

| 容器 | 建议职责 |
| --- | --- |
| `Workspace` | 场景、可见交互对象与碰撞代理 |
| `ServerStorage` | 未实例化模板、仅服务端资产 |
| `ServerScriptService` | 权威业务脚本和私有状态 |
| `ReplicatedStorage` | RemoteEvent、双方确需的纯规则/展示定义；不能放密钥或私有状态 |
| `StarterPlayer.StarterPlayerScripts` | 客户端输入、镜头、HUD 接线 |
| `StarterGui` / `PlayerGui` | 界面模板与玩家实际界面 |

导入有来源许可的 FBX 等 Studio 支持格式；按 importer 的当前支持清单核实，不假定 GLB 在任意版本可直接导入。源 `.blend`、通用网格、纹理与导出配置一起交付。模板和实例分开维护，稳定 asset ID/节点名、placement anchor 与碰撞代理。

Roblox 的标准物理换算约为 **1 stud = 0.28 m**；几何目标要明确采用的尺度，不将 Blender 数字原样当 stud。统一缩放、坐标轴和 pivot，先测试一个导入实例，再批量复制。`Model:ScaleTo()` 参数是模型绝对规范缩放值；已有缩放必须计入，不能反复乘错。匹配包围盒时保留旋转关系，用实际 pivot/anchor，不按某个物件名决定转角。

本地 `.fbx/.glb` 路径不能作为运行时 MeshId。需要 Studio 导入为 MeshPart 并取得平台资产引用/权限。原生 Part 适配可以作为明确标注的替代表示或原型，但不声称保留了原网格倒角、UV、纹理或原来的三角面数。先完整验证替换模板，在受限目标容器内替换外观，保留原对象备份和碰撞/提示/脚本；只在编辑模式运行。不要调用整个 Workspace 的 ClearAllChildren。

## 资产硬约束与推荐预算

按 [建模规范](https://create.roblox.com/docs/art/modeling/specifications) 与 [纹理规范](https://create.roblox.com/docs/art/modeling/texture-specifications) 核对本次导入路径，完整原文随官方资料归档。当前快照列出**单个网格不超过 20,000 三角面**；角色身体和可上架配件另有更具体规则。逻辑资产可由多个网格组成，拆分后仍合计其总面数、实例和材质开销；不能拿拆分绕过项目性能预算。

每个 mesh 对象按单材质、单 UV 集准备，UV 在 0–1 内；PBR 法线采用 OpenGL 切线空间。复杂 Blender shader 不会自动变成相同的 Roblox 材质，应在 Studio 用实际导入结果验收。

该版本纹理页对一般图片写最高 4096×4096，但 PBR 表和 UV 段仍出现 1024 上限，不能把两者混为所有资产统一保证。保守运行版优先 256/512/1024；2048 等较大源贴图可保留，但在对应资源类型和当前 Studio 路径验证前不宣称支持/显示原始分辨率。需要高分辨率时核对当前规范、导入结果和设备降采样；不因网站一般上限放宽所有 PBR/头像资产预算。

## 纯规则与副作用分离

将 `validateIntent`、规则状态迁移和状态快照作为可独立测试的函数；实体创建、Raycast、网络发送、存档放在明确适配层。服务器接受动作意图，不接受最终伤害、奖励、命中对象或“已付款”等可信结论。

每次输入依次校验：动作白名单、载荷类型/有限数/长度、每玩家速率、当前角色与生命世代、装备与资源、服务器位置/距离/视线、动作冷却、实际目标所属与状态。`RemoteEvent.OnServerEvent` 首参 Player 来自引擎；客户端不能选择目标玩家身份。ProximityPrompt 的客户端状态不能替代上述检查。

同一击败、拾取、购买等结算先做状态迁移/标记，再发奖励和表现；避免在关键原子段 yield。任何网络或 DataStore yield 需要重新验证状态/事务语义。共享物件只允许一次有效领取；每玩家背包独立。`task.delay` 捕获动作 token 与角色世代，角色死亡、重生、卸下、离开时失效，避免旧回调作用于新角色。

初始化既订阅 PlayerAdded 也处理 GetPlayers；连接幂等，重生后重新取得角色对象，PlayerRemoving 清理状态与速率桶。对复制后的对象使用有限 WaitForChild，超时显示缺口，不能无限等待。流式加载的客户端对象可能消失；服务器判定不能依赖客户端已经加载完整地图。

## 输入、镜头和性能

文字输入优先：`InputBegan` 的 processed 为 true 或 `GetFocusedTextBox()` 非 nil 时不触发快捷键/攻击；不要劫持默认聊天。使用 `GuiButton.Activated` 统一鼠标/触摸；混合设备不能只在启动时固定 TouchEnabled。相机重建、窗口大小改变、重生需重新绑定当前对象。

视觉、碰撞和查询可分开：装饰关闭 CanCollide/CanTouch，是否 CanQuery 取决于是否应遮挡/被选择；实体遮挡代理保持可查询。局部灯先限制范围和重叠，仅对必要灯启用阴影。不要以零贴图或低源网格面数推断稳定 FPS。

场景变化从同一几何配置更新交互范围、出生支撑、碰撞、镜头和导航；不在多个脚本复制区域坐标。可达性要考虑角色半径/高度、跳跃落点、第三人称镜头和流式加载。静态抽样只减少明显错误，实际 Studio 物理仍须验收。
