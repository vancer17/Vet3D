# hi3dreamer-workflows

可打印头雕制作和头发分割交付属于 workflows；支持两种四视图基准的头部参考图、灰树脂外观、视觉分析、鼻部修复和眼球修复属于可独立调用的 skills；通用 API、Blender 与运行能力属于 tools。原子函数不必各自包装成 skill，各入口按实际输入输出组合，可从已有中间产物续接。

## Doc

创建或迁入任何入口前完整阅读 [hi3d-api 文档](hi3d-api.md)、[维护规则](repository-AGENTS.md)与本 README，并按 [新增前阅读与复用规则](repository-AGENTS.md#新增前阅读复用与经验保留) 盘点当前能力：新 skill 先完整阅读所有 tools 入口，新 workflow 先完整阅读所有 tools 与 skills 入口。工具代码与服务资料见 [doc 索引](README.md)。

<!-- DOC_TABLE:START -->
| 文档 | 内容 |
| --- | --- |
| [auto-rig](mdf/auto-rig.md) | SkinTokens 身体输入、GLB 输出、参数与版本边界、默认 HTTP 调用，以及 rig-retarget 高模回迁和局部蒙皮修复交接。 |
| [blender-tools](blender-tools.md) | 后台 Blender、Cycles 设备选择/恢复、场景 IO、完整资产载入、网格快照、检查点渲染与原子函数契约。 |
| [capability-design](capability-design.md) | 三层构成、原子复用及保留边界，涵盖头部两种四视图模式、人像与分割流程、GLB/STL、拼版、测量及哈希；区分实际接入与待实施扩展。 |
| [capability-usage](capability-usage.md) | 每个 tool/skill 的反向使用方、孤立/仅资料接入分类及全部三层入口的物化、引用、条件调用和交接证据。 |
| [capability-usage-declarations](capability-usage-declarations.json) | 无法由文件清单推导的调用/交接及非调用说明，保留所属入口原文证据，供使用关系生成器校验。 |
| [game-deploy](game-deploy.md) | 网页游戏部署工作流与实现说明导航。 |
| [hi3d-api](hi3d-api.md) | Hi3D 通用 API 工具的模块、接口、账号请求关联头（X-Session-Id/X-Turn-Id）、子模块图像策略（prompt 4000 字符、生成前 Python 计数与超长精简、默认 GPT Image 2）、3D 免费重试根任务解析、次数查询与账号校验、受理即时事件、任务 ID 持久化、提交恢复、调用方错误处理契约、内部错误码映射、失败状态同步与验证。 |
| [mdf-call](mdf-call.md) | MDF 默认 HTTP 中控与显式 SDK 调用、入口预检、统一业务 CLI、auto-rig 到 rig-retarget 的文件交接及产物校验。 |
| [mdf-contract](mdf/README.md) | MDF 服务契约导航，链接随 service-select 提供的二进制/数组、成功判定和部署约定。 |
| [mdf-deploy](mdf-deploy.md) | MDF 服务部署工作流与实现说明导航。 |
| [mdf_list](mdf_list.md) | 12 个已记录契约的下游服务、露出状态与 2 个外部中控来源的输入输出参数。 |
| [mesh-lod](mdf/mesh-lod.md) | 多档网格减面、纹理/法线重烘及完整传参。 |
| [mesh-watertight](mdf/mesh-watertight.md) | GLB 水密重建、补洞与可选减面；mdf-call 维护完整参数、调用及验收边界。 |
| [package-tools](package-tools.md) | 显式文件依赖、独立包生成、路径保护、使用关系生成/检查、skills/workflows 的 pcg 入库校验及仓库提交门禁；拒绝缺失或嵌套入口造成的漏记。 |
| [pcg-loop](pcg-loop.md) | 宿主 Agent 循环与仓库衔接：检查点 load、不可逆权限、前端 option、阶段架构与产物槽；每轮 loop/compact/流中断重投影画板；session 只作进度索引；load 按 `injected` 去重；`stream.incomplete` 可续跑；`waiting_choice` 由宿主编排注入统一触发；tools 不设 pcg。 |
| [pcg-view](pcg-view.md) | skill 线形回退进程与 workflow 编排树；可投影为 G6 `{nodes, edges}`；产物目录每次可定位；cache 按 semantics 清理；routes 决策图的 `waiting_choice` 弹窗服务选型与宿主注入的决策时刻。 |
| [rhino-control](rhino-control.md) | Rhino 应用控制的安装/文件夹搜索、版本探测、MCP 安装与调用、Python/桌面操作、脚本编写与预检、共用/差异文档、两级精确行号索引、紧凑批量检索、接口注意事项联读、平台分支/框架隔离及几何验收契约（Rhino 5–8）。 |
| [run-tools](run-tools.md) | 阶段记录、多输入/输出路径、显式环境、子进程、包外会话产物留痕、对话产物 `@name` 引用、短工具回写，以及本地无界 CPU 的预算、心跳、超时杀进程与心跳弹窗分类。 |
| [sapiens2](mdf/sapiens2.md) | 五项人体视觉推理、单项/组合调用、CPU offload 与原图坐标输出；MDF3 托管、自动构建及部署验收边界。 |
| [service-select](service-select.md) | 服务能力选择与本地几何输入组装的独立契约导航。 |
<!-- DOC_TABLE:END -->

## Tools

<!-- TOOLS_TABLE:START -->
| Tool | 能力 |
| --- | --- |
| [blender-tools](../.dependency-blender-tools/REFERENCE.md) | 使用 Blender 的后台进程、Cycles 设备选择/恢复、显式对象导入/保留/创建、原始/求值网格快照、场景读写、原生依赖检查和有检查点的帧渲染，为原子能力及工作流提供通用操作。 |
| [hi3d-api](../hi3d/SKILL.md) | 公共 Hi3D API 与独立账号 Runtime 图像/3D 模式；单图/多视图建模、贴纹理、浮雕、拆件、多色、公共余额与任务恢复，兼容含点号的任务 ID 并保留提交恢复检查点，提供原始产物下载校验及 Blender 基础检查。账号 Runtime 另提供 3D 免费重试次数查询（`retry-quota`）与按原任务提交（`retry`，正文仅根任务 parentGenerateId，由桌面代理转正式账号接口；新 ID 与可用次数快照落盘后立即报告受理，桌面由 Runtime 自动登记新版本）。v2.0 原生档位 balanced/quality、v2.1 原生档位 fast/quality；v3.0 前端 quality/master 分别传原生 standard/quality，默认推荐 quality；文生图/图生图免弹窗，默认 GPT Image 2、AI 推荐比例，生成前 Python 检查4000字符、超长等义精简复查，调用失败不自动重试并返回脱敏原因，成功出图后的效果迭代照常继续；网页带钻 option 与其他生成任务的宿主参数 preference 由本包维护；Agent 生模可选用，网页表面锁定。 |
| [mdf-call](../mdf-api/SKILL.md) | 基于已确认的 MDF 服务契约执行单次调用，支持账号公开 mesh/invoke，内部模式默认经 HTTP 中控调用，可显式选择需要 worker TCP 回连的官方 ServiceInvokeSession，提供运行时预检、逐服务诊断、脱敏审计与产物/checkpoint 校验；异步状态查询和业务成功条件由调用方提供。 |
| [package-tools](../.dependency-package-tools/REFERENCE.md) | 将显式 package.json 依赖物化为仓库外的独立能力包，验证来源、冲突与依赖；支持 desktop 子模块平面分发与安装别名；按明确仓库路径生成和检查能力使用关系，并校验 skills/workflows 的 pcg 衔接（缺 architecture 时按入库格式补齐）。 |
| [pcg-view](../.dependency-pcg-view/REFERENCE.md) | 把 skill 画成可回退的线形进程，把 workflow 画成 spawn 编排树，并可投影为 AntV G6 流程图数据；每次打开用产物目录定位文件；按语义清理 cache 槽。routes 决策图的 option 弹窗同时服务选型、宿主决策时刻与 Hi3D 带钻 chips。提供宿主编排注入提示，供宿主嵌入，不执行 Agent。 |
| [rhino-control](../rhino-control/SKILL.md) | 控制 Rhino 5–8，自动定位或搜索用户文件夹，核对可执行文件和 Python 命令入口；验证运行版本后优先 MCP、其次原生 Python、最后 computer use；自动安装 Rhino 8 的 RhinoMCP，提供共用/差异 API 正文、版本→接口两级精确行号索引、紧凑批量查询、契约与对应注意事项联读、平台分支/框架隔离及完整官方来源、双引擎编写清单与一次提交的 20 项几何验收。 |
| [run-tools](../.dependency-run-tools/REFERENCE.md) | 为各原子能力和工作流提供显式输出路径、阶段 CLI、耗时记录、内容缓存校验、子进程恢复、包外会话产物留痕、短工具回写、load 注入去重、流中断续跑、本地预算心跳杀进程与心跳弹窗分类，以及对话产物 `@name` 引用。 |
<!-- TOOLS_TABLE:END -->

## Skills

<!-- SKILLS_TABLE:START -->
| Skill | 能力 |
| --- | --- |
| [asset-page](../.dependency-asset-page/REFERENCE.md) | 将版本化本地图片、GLB、视频和下载文件生成静态成果页与实际资产清单；发布另行处理。 |
| [audio-mix](../audio-mix/SKILL.md) | 按裁切、偏移、增益及淡入淡出混合本地音轨，输出 WAV 或搭配视频/字幕输出 MP4；验证解码和采样率。 |
| [ball-joint](../.dependency-ball-joint/REFERENCE.md) | 为明确的两个刚体生成配对球窝和间隙试片，保留局部来源表面；用于可打印活动连接的单点设计。 |
| [brep-build](../.dependency-brep-build/REFERENCE.md) | 依据明确毫米配方用 CadQuery 无头构建可导出 STEP 的 B-rep 实体（盒/柱/锥、抽壳、ISO 螺纹与孔、命名布尔与倒角）；受墙钟预算与心跳约束，不反求网格。 |
| [cad-file-verifier](../cad-file-verifier/SKILL.md) | 检查 CAD 文件在指定环境中能否打开并继续编辑，校对图层、对象、参数、装配与外部引用是否保留；输出中文差异报告、机读结果和可追加实测记录。默认不修复、不转换、不覆盖原工程。ClassCAD 源端证据另列，不代替目标软件原生验收。 |
| [cad-sketch](../cad-sketch/SKILL.md) | 创建全约束矩形/圆草图、拉伸和直孔口袋，修改命名尺寸，另存 FCStd 和 STEP 并回读体积；单位毫米。 |
| [closed-quad-transition](../closed-quad-transition/SKILL.md) | 对已有规则四边面里平缓且未保护的 4×4 片保留外边链，做成 1 个粗中心面和 14 个闭合过渡面，并用双向采样误差验收局部 16→15。不负责整模重拓扑或动画布线。 |
| [connector-select](../.dependency-connector-select/REFERENCE.md) | 根据自由度、载荷、制造与释放条件选择打印连接构型，输出有依据的接口设计简报。 |
| [dcc-preset](../dcc-preset/SKILL.md) | 按软件和版本检索 Blender、Houdini、UE 的水体类内置预制并执行这一条操作；UE 5.7 及以上只改插件启用项，不搭建场景。 |
| [delivery-review](../.dependency-delivery-review/REFERENCE.md) | 核对已有模型、图片、制作文件与成果页是否同版且可打开下载，输出交付清单和实际检查范围。 |
| [exterior-surface](../.dependency-exterior-surface/REFERENCE.md) | 从装配模型的表面体素剔除封闭内部结构，保留外露表面并生成 Geo2 稀疏坐标；原 mesh 不改。 |
| [eye-repair](../.dependency-eye-repair/REFERENCE.md) | 对已有头模定位并切除错误瞳孔或虹膜几何，以光滑球冠补全可见眼球，检查眼睑边界和多视角效果；按需交接 continuous remeshing。 |
| [face-fit](../.dependency-face-fit/REFERENCE.md) | 将已有带发或光头高模的同源面部观测注册为局部 Taro donor，保留原高模，输出五官/鼻部指标与来源绑定；不生成光头参考或要求全头拟合。 |
| [fit-coupon](../.dependency-fit-coupon/REFERENCE.md) | 从真实配合件裁切局部试片，组织明确间隙系列与配对来源，保留朝向及待实测状态。 |
| [game-browser-check](../game-browser-check/SKILL.md) | 浏览器玩法验收：验证游戏真实开局、交互按需资源或重开后报错；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-collision](../game-collision/SKILL.md) | 连续盒体碰撞：高速物体穿墙或角色碰撞代理需要扫掠检测；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-combat](../game-combat/SKILL.md) | 游戏战斗结算：添加伤害、攻击冷却、击败或重复攻击保护；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-economy](../game-economy/SKILL.md) | 游戏经济账本：商店扣币、奖励领取、重复兑换或离线收益；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-entitlement](../game-entitlement/SKILL.md) | 购买权益归约：实现购买后下载、退款撤销或重复支付事件处理；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-input](../game-input/SKILL.md) | 游戏输入映射：键鼠、手柄或触屏操作需要统一为动作；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-level](../game-level/SKILL.md) | 游戏关卡检查：配置关卡、检查传送门引用或出口不可达；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-loop](../game-loop/SKILL.md) | 游戏时钟与生命周期：暂停后时间跳跃、重复开局或帧率影响玩法；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-network](../game-network/SKILL.md) | 联网快照接收：处理迟到快照、旧局消息、插值或重连退避；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-package](../game-package/SKILL.md) | 游戏包清单检查：上传游戏、发布 UGC 或检查版本文件清单；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-pool](../game-pool/SKILL.md) | 游戏对象池租约：敌群或弹幕频繁创建销毁、重用对象被旧回调污染；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-profile](../game-profile/SKILL.md) | 游戏帧预算分析：游戏卡顿、手机掉帧或需要画质分档；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-replay](../game-replay/SKILL.md) | 游戏规则回放：复现战斗 bug、验证重开状态或确定性输入序列；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-save](../game-save/SKILL.md) | 游戏存档迁移：保存游戏进度、恢复旧版存档或处理损坏存档；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-score](../game-score/SKILL.md) | 游戏成绩排名：添加最高分榜、同分名次或显示榜外本人排名；提供独立 JS 核心与行为验证，服务接入另验。 |
| [game-vehicle](../game-vehicle/SKILL.md) | 平面驾驶与赛道检查点：添加简单赛车、车辆驾驶或顺序计时检查点；提供独立 JS 核心与行为验证，服务接入另验。 |
| [geometry-input](../.dependency-geometry-input/REFERENCE.md) | 将图像或已有 Geo bridge 产物规范为几何服务的对齐图像和 prep.zip，提供纯本地输入组装。 |
| [glb-clips](../.dependency-glb-clips/REFERENCE.md) | 合并已有 GLB 中显式同播的片段，检查时间/通道冲突，保持非动画 JSON 和二进制数据。 |
| [gray-resin](../.dependency-gray-resin/REFERENCE.md) | 将照片、头模渲染或已有四视图转成保持辨识度的灰树脂参考图，控制皮肤微肌理、实体发束与无瞳孔眼睛；仅处理图像。 |
| [grid-path](../grid-path/SKILL.md) | 网格寻路：敌人需要绕开障碍、检查起点到终点可达；提供独立 JS 核心与行为验证，服务接入另验。 |
| [head-reference](../head-reference/SKILL.md) | 转正或当前视角四视图二选一；转正侧图按画面鼻尖朝向命名 right/left，当前视角保留原图朝向、俯仰与侧倾。共用裁切/造型/材料，单图独立可用；内置逐项评审与人工放行，相对视角不冒充标准正面，无自动视觉检测，不建模。 |
| [head-template](../.dependency-head-template/REFERENCE.md) | 解析有来源与许可的 Taro 头部拓扑、分区及眼唇/固定耳部关键点映射，为固定拓扑拟合提供一致几何先验。 |
| [image-sheet](../.dependency-image-sheet/REFERENCE.md) | 将有序图片与标签拼成检查图和格位映射，保留等比缩略/明确拉伸、字体留白及可选来源哈希校验。 |
| [landmark-project](../.dependency-landmark-project/REFERENCE.md) | 将带相机与来源证据的 Sapiens2 眼唇或多视角耳部关键点投影为目标网格三维配准点。 |
| [media-check](../.dependency-media-check/REFERENCE.md) | 检查已有图片或视频的尺寸、帧率、帧数、时长及完整解码，输出可机读媒体验收报告。 |
| [media-edit](../media-edit/SKILL.md) | 将本地视频按入出点、变速和有理帧率裁切拼接，统一画幅并解码验证；不隐式保留音轨。 |
| [media-encode](../.dependency-media-encode/REFERENCE.md) | 将连续 PNG/JPEG 帧按明确帧率、CRF 与覆盖策略编码为 MP4，复用独立解码验收，并可生成检查图和哈希。 |
| [mesh-audit](../.dependency-mesh-audit/REFERENCE.md) | 对已有网格执行明确类型的拓扑、STL、表面相交（含同拓扑基线比较）或通道距离检查，以及资产回读测量，输出诊断而不修改源模型。 |
| [model-preview](../.dependency-model-preview/REFERENCE.md) | 从已有模型与明确展示姿态产生多视角图片、可视 GLB 和姿态构图检查，复用当前几何。 |
| [motion-check](../.dependency-motion-check/REFERENCE.md) | 对明确刚体装配执行多部件实体离散检查，并提供显式场景采样与任意轴姿态，保留碰撞后端边界。 |
| [motion-retarget](../.dependency-motion-retarget/REFERENCE.md) | 依据源/目标休止姿态、骨骼层级与映射，将已有动作样本转换为目标骨架的旋转和根位置。 |
| [nose-repair](../.dependency-nose-repair/REFERENCE.md) | 从已有高模与同源注册 Taro donor 切除错误鼻部、移植鼻子并构造 Poisson 接缝，验证局部几何和区域外来源。 |
| [portrait-analysis](../.dependency-portrait-analysis/REFERENCE.md) | 对已有头模渲染调用 Sapiens2，获得关键点、人体分割和预测法线，保留源模型、图像与真实相机绑定；不生成或修补几何。 |
| [print-export](../.dependency-print-export/REFERENCE.md) | 将已确认的网格写为毫米制 STL/3MF，并保持部件坐标和真实实体组织。 |
| [print-plan](../.dependency-print-plan/REFERENCE.md) | 把既定产品结构转换为制造版本、全打印可行性、BOM、配对试片与验证计划（通用规则唯一来源）。 |
| [pub-roblox-game](../pub-roblox-game/SKILL.md) | 发布已有 Roblox Place，处理公开受众与真实多人验收，记录实际账号手续；首次默认 Studio，已有目标可选云端更新。 |
| [pub-steam-mod](../pub-steam-mod/SKILL.md) | 对已对齐的 Steam 创意工坊内容执行授权发布，并分别核验上传、可见性和订阅结果。 |
| [relief-map](../.dependency-relief-map/REFERENCE.md) | 以共享首击采样、显式基线/归一化/低谷修补提取浮雕高度，或映射到目标曲面，保留尺度与来源。 |
| [remotion-render](../remotion-render/SKILL.md) | 使用本地 Remotion 模板组合文字、矩形、图片、音轨及平移/淡入关键帧，渲染视频并验证帧数。 |
| [replace-brief](../.dependency-replace-brief/REFERENCE.md) | 根据用户截图框出要分割替换的位置，生成裁切与标注，并列出仍需向用户索取的替换物件素材；不生成 3D、不调用分割服务。 |
| [roblox-api](../roblox-api/SKILL.md) | 适配 Engine/Open Cloud 接口，静态检查 Place、保护远程调用并诊断聊天；单次上传回执不等于公开发布。 |
| [scale-aware-quad-rings](../scale-aware-quad-rings/SKILL.md) | 对已有低模四边面按冻结尺度划分转角、折边和接缝保护，选择性融并缓曲面，并用连续环带连接粗细网格；保留可编辑四边面并检查闭环。 |
| [service-select](../.dependency-service-select/REFERENCE.md) | 根据已有输入和目标效果选择 Hi3D/MDF 原子服务，输出精确的服务契约、参数与产物交接方案。 |
| [shape-build](../.dependency-shape-build/REFERENCE.md) | 依据明确轮廓、截面和尺寸构建放样、回转、管道与板壳网格原语；几何与预览、打印、审查通过显式领域接口组合。 |
| [skin-weights](../.dependency-skin-weights/REFERENCE.md) | 对已有网格与骨骼权重执行局部约束修复或图正则求解，保留范围外权重并输出质量指标。 |
| [solid-edit](../.dependency-solid-edit/REFERENCE.md) | 对带逐面来源与 UV 的闭合实体执行局部布尔并回写几何/材质来源，保留未改表面。 |
| [source-prepare](../.dependency-source-prepare/REFERENCE.md) | 将明确选定的来源模型规范为指定高度、可选朝向与可回溯 NPZ/Blender 输入，保持 UV 和材质来源；预览独立组合。 |
| [steam-ugc](../steam-ugc/SKILL.md) | 对单次 Steam UGC 操作核对接口、字段及提交前检查；保留真实回执与执行边界。 |
| [stroke-animate](../stroke-animate/SKILL.md) | 从明确二维笔划创建 Grease Pencil 图层、逐帧画稿和对象变换关键帧，保留可编辑 BLEND 并重开验证。 |
| [subtitle-track](../subtitle-track/SKILL.md) | 将明确时间戳文本排成 UTF-8 SRT/ASS 字幕，校验重叠、精度和行长；不做语音识别。 |
| [support-check](../.dependency-support-check/REFERENCE.md) | 对明确实体密度或质量、重力和真实接触点计算重心、支承凸包与静态裕量，不证明实物抗推倒。 |
| [surface-fit](../.dependency-surface-fit/REFERENCE.md) | 将固定拓扑模板以相似变换、局部 Gaussian brush 和可选耳部共享体积形变拟合到目标表面，并有界修正新穿越。 |
| [svg-edit](../svg-edit/SKILL.md) | 通过白名单操作编辑 SVG 节点、文字、样式、变换和路径布尔，并用 Inkscape 导出 PNG/PDF；保护原输入。 |
| [taubin-smooth](../taubin-smooth/SKILL.md) | 调用 Blender 原生邻域算子对三角网格做 Taubin λ/μ 光顺，按 1 倍对应 10 轮换算用户声明的光顺倍数，支持固定边界与顶点，保持拓扑、属性和源文件，另存 BLEND 与重开检查报告，并提供 PCG 槽位回写、会话绑定与恢复投影。 |
| [texture-bake](../.dependency-texture-bake/REFERENCE.md) | 本地高模到目标 UV 的颜色/切线法线烘焙，显式区域与设备参数并恢复临时状态。 |
| [video-sequence](../video-sequence/SKILL.md) | 创建或按命名条带修订 Blender VSE 的图片、视频、声音、文字和颜色轨道，另存 BLEND、重开并渲染序列帧。 |
<!-- SKILLS_TABLE:END -->

## Workflows

<!-- WORKFLOWS_TABLE:START -->
| Workflow | 能力 |
| --- | --- |
| [api-demo-service](../api-demo-service/SKILL.md) | 将用户自己的可运行算法封装成单任务本地 HTTP 演示服务和测试页；校验失败与执行失败分开，不把请求拼进命令行，面板不索取密钥。 |
| [app-prototype](../app-prototype/SKILL.md) | 把明确业务流程做成列表、详情、编辑三页网页并本地保存；示例数据必须标注；导入失败不覆盖；登录支付与多人同步显示为未实现。 |
| [articulated-sculpture](../articulated-sculpture/SKILL.md) | 将长形雕塑按语义分成刚性节段，设计真实铰链与止退，保留细节并验证完整实体碰撞和同步关节动画；由执行者校准建模，交付 Blender、GLB 与阶段耗时，制造释放和疲劳另验。 |
| [asset-review-board](../asset-review-board/SKILL.md) | 将本地图片、视频和模型按资产分成版本，并排或单版对比并写下批注；批注绑定原版本，导入失败不覆盖，不提供协作账号云端。 |
| [audio-prep](../audio-prep/SKILL.md) | 整理本地音频：按探测时长做首尾静音裁切、淡入淡出与目标响度，试听对照后导出 WAV 与实测响度；不默认裁切中间停顿，未实现降噪则不提供该选项。 |
| [body-spring-connector](../body-spring-connector/SKILL.md) | 把已有角色、动物或摆件的身体中段改为连续宽圆片螺旋弹簧，内藏配对 D 形插桩与盲槽，保留外观并交付装配、分件、试片和尺寸说明；不重新生成主体，不用于球窝人偶、互锁螺旋玩具或实物强度认证。 |
| [build-explorable-3d-game](../build-explorable-3d-game/SKILL.md) | 先提问、盘点素材并展示玩法方案，用户选择或明确委托后开始制作；从简单主题或参考图构建完整可玩的三维探索游戏，默认 Hi3D Quality，负责场景、主题交互、自由飞行或铁路；显式组合 rig-retarget 完成角色蒙皮与动作适配，持续展示成果并交付验证与阶段耗时。 |
| [cinematic-camera-director-visual](../cinematic-camera-director-visual/SKILL.md) | 为已有 Blender 或 GLB 场景创建电影镜头；先用视觉理解与对象清单判断主体，弹窗核对运镜与基调后生成并验收连续相机动画。默认 Blender 本地执行，可按真实环境接入 GenDoP 或 CinemaTraj。 |
| [clip-edit](../clip-edit/SKILL.md) | 将本地图片或视频按排序、入出点与画幅剪成横屏或竖屏成片；可选用户配乐与字幕；先生成低分辨率预览再导出 MP4、封面、存在字幕时的 SRT 与配置清单。 |
| [connected-faceted-lowpoly](../connected-faceted-lowpoly/SKILL.md) | 把已有角色、手办或雕塑高模做成真实连通的块面低模和有限纯色分区，保留姿态与主要轮廓；交付同坐标对照工程、GLB、预览和按需逐面材质 3MF，附阶段耗时。 |
| [cosplay-armor](../cosplay-armor/SKILL.md) | 从人体来源与艺术高模设计 Cosplay 护甲，完成内腔、固定、打印拆分，尽可能提供含快脱与接触件的全打印版；交付 FDM、穿脱关键姿态与 3D 并主动打开成果页，视频交付后按需追加，个人适配与舒适度另验。 |
| [create-roblox-game](../create-roblox-game/SKILL.md) | 从需求或已有工程制作 Roblox 游戏，组织资产、Luau、多人与性能验收，按授权发布；不固化类型、布局或审美。 |
| [create-skill](../create-skill/SKILL.md) | 从本对话成功经验或用户提供的已有 Skill 生成可复用草稿，多个相关 Skill 默认整合为统一入口并保留内部模块，仅组织方式不明确时澄清；经 Runtime 提交结构检查，不安装、不执行草稿脚本，不声称未经实际运行的内容已验证。 |
| [device-enclosure](../device-enclosure/SKILL.md) | 围绕明确设备或名义参考包络设计艺术外壳，完成内腔、支座、端口、可拆盖和紧固件配合；由执行者建模，交付 Blender、GLB、维护路径检查与阶段耗时，型号兼容和实物性能按证据限定。 |
| [display-base](../display-base/SKILL.md) | 为雕塑或半身像制作静态展示台座与铭牌，保留主体高模/纹理并校准承托、总高和文字；由执行者建模，交付 Blender、GLB、真实预览及阶段耗时，固定与稳定性按实际验证说明。 |
| [earbud-case-cover](../earbud-case-cover/SKILL.md) | 按明确品牌/型号设计充电盒艺术外套，处理内腔、分盖、接口及显式减薄，尽可能完成全打印保持结构；交付 FDM、图片与交互动作并主动打开成果页，视频默认关闭、交付后按需追加，实际配合另验。 |
| [exhibition-tour](../exhibition-tour/SKILL.md) | 将展品模型、图片和文字做成单展厅网页，支持热点说明、自由查看与可暂停的固定路线导览；虚拟展厅不充当测绘或 BIM。 |
| [flex-motion](../flex-motion/SKILL.md) | 在 Blender 中为已绑定角色的头发末梢、衣摆、宽袖、披风、飘带和宽松裤脚添加辅助骨，并把走动、转向、停止时的惯性随动烘焙进动作；保留网格和身体动作，缺有效绑定才交接 rig-retarget。 |
| [frame-design](../frame-design/SKILL.md) | 从作品尺寸设计艺术相框、背板与支座，保留外购版并优先完成全打印机械版；内置限定圆口旋锁/燕尾配方与试片，交付 FDM、装配图及 3D 并主动打开成果页，视频交付后按需追加，附阶段耗时。 |
| [game-deploy](../game-deploy/SKILL.md) | 将已有网页游戏适配并部署到 GitHub Pages，处理子路径、模型资源、公开仓库和 Actions，验证匿名加载与实际开局；按需接入独立排行榜服务和 GitHub 快照。 |
| [hair-cards](../hair-cards/SKILL.md) | 从发型图片、头发模型或已有引导制作平滑分束发片；按需组合图生图拆出主体与独立 hi3d-api QUALITY 参考，实际 3D 参考就绪后布局引导，提供无头模连续截面/交叉片转换并保留头部接触模式；支持保形材质修订、细丝质感诊断与最终 GLB 回读验收，交付可编辑工程、多视角对照和阶段耗时；拟合、材质与导出检查由执行者完成。 |
| [head-hair-split](../.dependency-head-hair-split/REFERENCE.md) | 带纹理头模与白发黑头标签生成内嵌交互 HTML，必交付并打开，由用户调阈值、执行 mincut 和下载双对象漫反射 FBX，不默认代切割；支持标签准备、预算心跳及明确授权的无损 GLB 分区，不补头皮或封口。 |
| [head-lowpoly](../head-lowpoly/SKILL.md) | 高模人头 GLB 转独立四边形低模、albedo、normalmap、基础绑定与 blendshape，导出 GLB/Blender；推荐光头，支持带发输入，提供按阶段内容缓存与耗时统计。 |
| [hex-terrain](../hex-terrain/SKILL.md) | 在 Blender 中按 JSON 规则做 lowpoly 正六边形地形：分离地格、36 张自然贴图、装饰与草坪、水域河流、文明布局和城墙，导出重导入检查过的 GLB。基线规则 2.1.2；不含贴图与模型原件，不能从本包直接跑出原工程画面。 |
| [hi3d-game-demo](../hi3d-game-demo/SKILL.md) | 先提问、盘点素材并展示玩法方案，用户选择或明确委托后开始制作；将图像或已有 Hi3D 模型制作成展示几何与纹理精度的可玩 demo，组织资产交接、精度保留、坐标尺度、加载优化与增量验证；角色绑定/动作显式交接 rig-retarget，发布按需交接 game-deploy，记录业务耗时。 |
| [hi3d-model-gpt-animation](../hi3d-model-gpt-animation/SKILL.md) | 编排模型到 Blender 动画的交付，显式组合 rig-retarget 完成绑骨与动作适配，自身保留模型交接、舞台裁剪/朝向/文字、次级运动、接触和按需预览，交付可编辑工程与阶段耗时。 |
| [image-to-assembly](../image-to-assembly/SKILL.md) | 从参考图或已有艺术整模完成高精度静态装配；正交与多视角之外，以可环绕观察贯穿生成前、逐件生成中和交付前，并分开记录参考可见与设计推断。支持粗模/四视图/Hi3D Quality 重建及整模语义裁切、碎片归属后封口，保护外观建立真实公母接口并验证完整装入，交付阶段耗时，数字检查不等于制造认证。 |
| [image-to-print-forms](../image-to-print-forms/SKILL.md) | 把单张标志、线稿或剪影做成可选的分层标牌、轮廓落地桌摆、波浪镜像围合或弧形竖片，交付同方向预览、毫米 STL 和可编辑工程；不是照片自动重建，也不承诺免支撑或试打通过。 |
| [jewelry-reconstruction](../jewelry-reconstruction/SKILL.md) | 根据单张首饰图在 Blender 中分阶段恢复基础造型、表面细节、宝石与对应镶嵌，支持局部修订，交付可编辑工程、结构清单、预览与验收记录；尺寸和隐藏结构按证据标明推定。 |
| [keychain](../keychain/SKILL.md) | 为已有或图生模型及艺术佩饰选择挂点，建立双孔弯道或一体吊耳，按需匹配连接环并验证真实装配与孔道通行；提供局部布尔、网格诊断、可编辑工程和阶段耗时，数字连接与实物强度分别验证。 |
| [lamp-design](../lamp-design/SKILL.md) | 从文字、参考图或点选设计艺术灯具，支持 Logo 放射竖片、严格顶视投影及增量修订，完成可装配结构、同版开关灯交互及 FDM 制作包；优先完成可行的全打印机械版，功能电气件另列，主动打开图片与 3D 成果页，视频交付后按需追加，附阶段耗时。 |
| [layered-laser-ornament](../layered-laser-ornament/SKILL.md) | 从参考图或主题制作可装配的分层激光切割饰品，交付毫米制 SVG、分层排版、试片、同版预览、装配说明及阶段耗时；提供独立几何审计，AI/XCS 按实际导出能力交付，数字检查与软件/实机验证分别报告。 |
| [lithophane-lightbox](../lithophane-lightbox/SKILL.md) | 根据照片或已有浮雕制作发光浮雕相框，先选择外框尺寸及混色或 UV 工艺，复用 V5.1 参数化框体，生成制造文件并在实际切片软件中配置、检查和打开项目；支持尺寸评审、照片板适配或已有项目修改，不默认启动实体打印。 |
| [lowpoly-quad-face-neck](../lowpoly-quad-face-neck/SKILL.md) | 对话中须已有约两百万面的高模 GLB；没有低模时先交接 connected-faceted-lowpoly。再以该低模为拓扑起点建立流形四边面，识别到脸时提取下巴并校准现有颈部，烘焙后交付可编辑工程、OBJ 贴图包、GLB 和阶段耗时。 |
| [mask-design](../mask-design/SKILL.md) | 从照片/默认头型与 Hi3D 外壳设计面具，保留贴合、对称、通风与固定检查；尽可能完成全打印固定，交付 FDM、适配图及 3D 并主动打开成果页，视频交付后按需追加，实物舒适度另验。 |
| [mdf-deploy](../.dependency-mdf-deploy/REFERENCE.md) | 将算法封装为常驻 MDF3 服务，提供独立脚手架、本机 Docker 部署、模型与配置隔离、SDK 队列/TCP 往返和内容验收；需完整 MDF3 SDK、可达测试基础设施及目标算法依赖。 |
| [memory-scene](../memory-scene/SKILL.md) | 引导上传熟悉地点照片，按独立物件重建三维记忆空间，完成主题动作、个人故事、自由布置、保存恢复与前后对照；交付交互网页、Blender/GLB 和阶段耗时，主动打开并说明查看、操作与备份方式。 |
| [metahuman-fit](../metahuman-fit/SKILL.md) | 图片或人头 GLB（先渲染）经图生图转正面无表情彩色光头参考，Hi3D quality 生成几何与纹理，直接以 quality 高模做 3D brush 注册、有界微调后本地烘焙 albedo/normal，不额外调用 texture/bake 服务；交付 MetaHuman 静态几何、原高模及真实四边拓扑/布线展示，内置 Taro 模板及皮肤/眼睛/口腔贴图并自动解析默认路径，内置 Sapiens2 68 点眼唇和 49 点固定耳部映射，支持目标多视角反投影与耳部共享体积拟合，需本次来源标注，支持缓存和计时，DNA/绑定/头发仅按需扩展。 |
| [miniature-scene](../miniature-scene/SKILL.md) | 根据参考图重建包含建筑、底座、人物、动物或植被的微缩景观/沙盘；支持主题/视频选帧、独立对战角色与接触检查，按需组合 hi3d-api、树脂分件 STL 和可保存摆放的交互网页；交付同版可编辑工程、GLB、渲染、验证与阶段耗时。 |
| [motion-base](../motion-base/SKILL.md) | 为角色设计滑板、圆盘载具与运动支架；完整设计必须包含全打印机械方案并保留已有外购版，轮轴、止退、释放工具及试片齐全；交付 FDM、动作关键姿态与 3D 并主动打开成果页，视频显式请求后渲染，附阶段耗时。 |
| [multiview-parts](../multiview-parts/SKILL.md) | 根据同一对象的多视图参考，在 Blender 中程序化创建独立部件、统一比例与材质并按指定顺序排列，交付可编辑工程和按需 GLB；造型由执行者读图编写，提供独立入口、结构校验和业务阶段耗时统计。 |
| [phone-case-relief](../phone-case-relief/SKILL.md) | 根据可靠手机包络设计带连续彩色或纯几何浮雕的保护壳，处理内腔、功能开口、折叠机分件、颜色保留和装配检查；交付可编辑工程、GLB、按需网页与阶段耗时，实机兼容和防护性能另验。 |
| [portrait-reconstruction](../.dependency-portrait-reconstruction/REFERENCE.md) | 可打印头雕五阶段：两种四视图姿态模式，Hi3D 按分支组合 prompt，生成前 Python 检查4000字符上限，超长用保留全部约束的 H/E 紧凑表达并复查；大片发体形成雕刻发流，独立细发加粗或局部去除、邻近碎发并入主体；只避免明显假睫毛，保留自然睫毛及原妆容；四视图耳朵位置/头发遮挡须一致，不要求露耳。评审、人工确认及服务视角门槛后再建模（当前相对视角适配待验证）。修鼻/去噪默认关闭但须询问确认，纹理默认用已生成的 front，拆分阶段必交付并打开交互 HTML，让用户调阈值/处理/下载 FBX，不默认代切割；无眼球修复，完整 PBR/打印适配另验。 |
| [print-joints](../print-joints/SKILL.md) | 设计或改造 A/T-pose 活动打印人偶，选例优先关节外露的骨架造型，区分自由摆动、保持姿势与外力驱动；保留高模表面和纹理，提供原位球窝、间隙试片及分件/铰链流程，交付制造文件、运动与导出验收及阶段耗时，实物性能另验。 |
| [print-kit](../print-kit/SKILL.md) | 从简单物体参考与尺寸设计免胶拆件 FDM 模型，比较榫卯、卡扣、旋锁与紧固件，完成外购配件及全打印两版；每版交付装配 GLB、STL 打印包和下载展示页，附源码、配对试片及装入/保持验证，实物配合另验。 |
| [product-configurator](../product-configurator/SKILL.md) | 为已有产品模型制作颜色、材质显示和部件显隐的交互配置页；互斥规则生效；无报价时不显示虚构总价；默认不含支付库存订单。 |
| [product-design](../product-design/SKILL.md) | 从文字、图像或已有艺术模型完成通用产品设计、工程化、验证和图片/3D/制造包交付，供品类工作流组合。 |
| [promo-layout](../promo-layout/SKILL.md) | 从品牌或产品名称、准确文案与可选产品图生成方图、横幅和竖版海报；文字与图像分层且禁止静默截断；交付 PNG、可编辑 SVG/HTML、素材参数包与阶段耗时。无产品图时必须明确纯文字版式。 |
| [quad-flow-plus](../quad-flow-plus/SKILL.md) | 按模型在四种初始重拓扑中选一条，复用已有四边面与可靠边链；保形减密交接尺度分区和 16→15 闭合过渡，允许时按边链预算重建，分别验收面数、边链和形状误差。不保证动画拓扑或打印适用。 |
| [relief-box](../relief-box/SKILL.md) | 按收纳物设计浮雕收纳盒与首饰盒，完成分区、内托和保持，优先实际完成可行的全打印盖锁/连接及所选接触件；交付 FDM、存取图解与 3D 并主动打开成果页，视频交付后按需追加，附阶段耗时。 |
| [relief-brush](../relief-brush/SKILL.md) | 从 Hi3D 纹样制作线性高度图、原生笔刷、几何印章与边饰，验证实际应用；实体附件优先全打印，默认交付应用前后图、工具与 3D 并主动打开成果页，视频帧显式启用，纯数字缩减范围仍保留。 |
| [relief-lamp](../relief-lamp/SKILL.md) | 把文字、图片或已有浮雕做成可装配的透光浮雕灯；先按光学厚度完成灯罩与结构，支持圆柱插销、底部螺丝、六角母孔与筒面纵带修订，仅经同意后才配置整灯切片。不用于通用艺术灯具或灯具安全认证，也不默认启动实体打印。 |
| [relief-palette](../relief-palette/SKILL.md) | 从产品参考与照片制作多色浮雕彩妆盘，显式组合图像能力与 Hi3D，提供粉体浮雕映射、可开合外壳与附件建模原语、运动检查和质感渲染；布局造型由执行者校准，支持已有资产续接并交付阶段耗时。 |
| [rhino-build](../rhino-build/SKILL.md) | 透传 Rhino 建模需求给 rhino-control，定位安装或搜索用户文件夹，验证版本与入口后自动配置受支持的 MCP，否则使用原生 Python/桌面操作，按运行版本、平台分支和框架按需联读必要约束，另存模型并交付验收及阶段耗时。 |
| [rig-retarget](../rig-retarget/SKILL.md) | 为 T/A-Pose 人形建立或修正骨架与蒙皮，支持 auto-rig 高模回迁、受限局部权重修复、已有骨架的休止轴校准与动作序列重定向，烘焙手指/根位移/脚步并按全段形变和保存重开验收。 |
| [scene-render](../scene-render/SKILL.md) | 以真实 Hi3D 主角及多种配景高模完成影视/游戏环境搭建、材质光照和离线渲染，交付高清静帧、可编辑工程、成果页与阶段耗时；默认不渲染视频，交付后询问视频及运镜要求，按需完成内部穿行、适度近景与播放验收。 |
| [screw-bottle](../screw-bottle/SKILL.md) | 从参考图或艺术模型设计带真实内腔和旋拧盖的水瓶，显式组合 Hi3D，提供参数化公母螺纹、材质保留、整盖运动检查、动画与按姿态构图的产品渲染，交付阶段耗时；数字配合与实物密封分别验证。 |
| [sculpture-container](../sculpture-container/SKILL.md) | 将已有或图生艺术实体掏空并分出可拆盖，校准真实口沿、连续内腔、定位裙及取盖路径；由执行者建模，交付 Blender、GLB、开合预览和阶段耗时，数字配合不等于水密或食品接触验证。 |
| [steam-mod](../steam-mod/SKILL.md) | 盘点已有模组素材，对齐目标游戏内容与创意工坊要求，完成离线预检并按授权交接发布。 |
| [stream-scene](../stream-scene/SKILL.md) | 从参考、截图或已有模型编排可编辑溪流；调用 dcc-preset 打开 UE 5.7 及以上水体插件、Houdini 海洋谱或 Blender 流体域，再装配岸线与可选网页。不代替可装泵水景或通用 UE 展示。 |
| [summon-card-game](../summon-card-game/SKILL.md) | 先提问、盘点素材并展示玩法方案，用户选择或明确委托后开始制作；制作实体卡牌游戏：制作阶段备卡、Hi3D Quality 原模召唤、Blender 战场、场内召唤攻击与第一/第三人称飞行，保留原模和贴图，随包提供 Hi3D Logo、对决封面与阶段计时；游戏默认不设造卡界面。 |
| [teapot-design](../teapot-design/SKILL.md) | 按用途、壶身、把型与工艺组合设计水壶/茶壶，吸收分类建模、真实水道、表面分区与逐阶段验收方法；交付全打印冷态样件文件、图片与 3D 并主动打开成果页，视频交付后按需追加，热液/加热成品另验。 |
| [twisty-fidget](../twisty-fidget/SKILL.md) | 将雕塑或头部改为可长伸展的螺旋互锁瓣，修复散架与配合不均；新建默认16瓣，保持径向捕获、双向止挡和整环实测验收，覆盖壁厚、间隙、试片与全玩法证据；控制扫掠面数，优先交付经回读核对的整件3MF及备用STL，另附Blender/GLB动画、工程包和耗时，实物手感另验。 |
| [ue5-exploration-demo](../ue5-exploration-demo/SKILL.md) | 把文字或参考图做成紧凑、可编辑的 UE5 展示场景，组织概念、高精资产与人物绑定交接、样板区、天气和外围验收。未安装虚幻引擎时不把空目录称为可打开工程；本仓库迁入时未安装引擎，未执行编辑器或打包。 |
| [unity-cozy-exploration-game](../unity-cozy-exploration-game/SKILL.md) | 把主题、角色参考或已有 Unity 工程做成第三人称治愈系探索游戏，组织走路、任务存档、草地接触和 Windows/Mac 交付；柔性随动只交接 flex-motion，缺资产或绑定时交接已有能力。本仓库迁入时未安装 Unity，未执行 Editor 或 Player。 |
| [vase-design](../vase-design/SKILL.md) | 设计自然开口雕塑花器与可拆内胆、隐藏承托和清洗路径，尽可能完成全打印机械版并列明盛水内胆依赖；交付 FDM、图片与 3D，主动打开成果页，视频交付后按需追加，附阶段耗时及水密/稳定待测项。 |
| [water-feature](../water-feature/SKILL.md) | 设计循环水景的连续水路、泵管与维护结构，优先完成可行的全打印机械版并明列泵/供电/密封依赖；交付 FDM、启停关键姿态与 3D 并主动打开成果页，视频交付后按需追加，水密和运行性能另验。 |
<!-- WORKFLOWS_TABLE:END -->

## 架构与调用

| 目录 | 唯一职责 | 放入条件 |
| --- | --- | --- |
| tools/ | 通用工具使用类 skill | 大多数原子能力或工作流可能使用的运行工具；例如 API、Blender、记录与打包 |
| skills/ | 单点原子能力 | 输入/输出和完成条件明确，可跨工作流复用 |
| workflows/ | 端到端交付 | 从文本、图像或已有资产，组合原子能力输出真实文件 |
| doc/ | 工具实现文档、能力使用关系与服务契约导航 | 工具的代码文件、接口、算法依据、调用与失败边界，以及反向使用记录 |

每个入口独占所属目录的一个直接子文件夹，包含 `SKILL.md`；目录名、frontmatter、调用名与上表名称一致，全仓库唯一。`SKILL.md` 是三类入口共用的宿主格式，目录分类中的 skill 专指单点原子能力。脚本和必需资源由所属能力维护；相同代码、资源或规则只留一份。工作流通过明确的输入输出调用原子能力，保留产品专属规则与差异适配；专属代码不要求为拆分而机械提取。

共享文件的来源与包内位置在各入口 `package.json` 中声明。执行前按 [package-tools](../.dependency-package-tools/references/usage.md) 在仓库外生成完整分发目录，保留其中依赖与文档的相对布局；仅复制未经物化的源码目录不保证依赖完整。宿主安装若改变布局，须验证资源及引用仍有效；显式路径调用与宿主自动发现分别验证。

必要依赖显式提供；已有合格中间产物允许跳过上游。工作流源码不重复维护客户端、通用算法或协议正文，不通过当前工作目录或隐式相邻路径导入。修改唯一源后重新物化安装包。

## 维护约定

所有有效改动按 [AGENTS.md](repository-AGENTS.md) 完成检查、完整索引复核、离线验证、差异审阅和本地提交；默认交付流程及用户明确例外以该文件为准。用户明确要求不 push 时保留本地提交。

- [所有提交的前置比较](repository-AGENTS.md#先理解再修改)：无论内容类型，先对照当前约束与三层标准、比较已有实现，再整合到正确目录和唯一维护源，完成全部受影响关联内容（含阶段缓存与源码指纹）的更新与验证。
- [密钥规则](repository-AGENTS.md#hi3d-密钥统一规则)：真实密钥只能由已授权实际鉴权进程内部消费；维护与测试使用模拟鉴权。
- [阶段统计](../.dependency-run-tools/references/stage-records.md)：工作流记录实际阶段耗时与恢复状态，token 仅在真实采集时可选记录。
- [本地长任务预算与中断](repository-AGENTS.md#本地长任务预算与中断)：本地无界 CPU 必须先写预算/心跳再进内核，到点杀进程；决策时刻由 [宿主编排注入](../.dependency-pcg-view/references/host-orchestration.md) 统一 `waiting_choice` 弹窗，心跳分类唯一源为 [run-tools 预算契约](../.dependency-run-tools/references/budget-run.md)。入口不各自复制弹窗目录。Hi3D/MDF 远端等待不套用本地 kill。
- [阶段架构与产物说明](repository-AGENTS.md#阶段架构与产物说明)：新增或迁入 skill/workflow 时，同次创建 `pcg/architecture.yaml`，按实际实现描述各阶段流程、条件和产物；自动生成仅是初稿，交付前须补全并复核，后续流程变化同步维护。
- [代码与工具文档规则](README.md)：实现与文档同次修改，完整协议只维护一处。
- [使用关系维护](repository-AGENTS.md#能力使用关系必须同步维护)：新增或修改任何 tool/skill/workflow 时，同步物化/交接来源与反向记录；提交前通过 package-tools 的使用关系检查与 pcg 入库校验，启用仓库局部钩子并保留已有钩子行为。
- [复用与经验保留](repository-AGENTS.md#新增前阅读复用与经验保留)：新增前完成规定的全文阅读；优先完善已有能力，按第一性原理补充、整合或重组描述，禁止为原子化或精简而大量删除既有 tools/skills 的经验。迁移经验保留完整内容、适用条件与可发现的引用。
- 图片生成仅在调用失败时停止自动重试；成功出图后的质量修订仍按已有授权和原流程继续，不新增逐轮确认或中途停止，见 [维护规则](repository-AGENTS.md#维护三层能力与文档目录)。
- [质量与验证要求](repository-AGENTS.md#验证与审阅)：区分纯计算、应用状态、网络副作用和已验证范围，运行记录保存在任务目录，不写回能力仓库。

本 README 维护能力导航；长期开发约束唯一维护于 AGENTS.md，调用时必要的操作规则由其所属能力包维护。用户调整架构时同步实际文件、依赖与索引，不能仅改目录说明。

## Desktop 子模块分发

本仓库可作为 desktop 的 workflows 子模块固定版本引用。[平面分发 profile](../.dependency-package-tools/references/usage.md#desktop-profile) 物化已选工作流及共享依赖，映射账号工具安装名 hi3d、mdf-api；源码继续在三层唯一维护源修改，生成目录不提交。Hi3D 图片默认模型与 prompt 预算在工具的 agent 必读入口规定，由随包 Python 执行；desktop 只转发参数，不重复维护模型配置或长度限制。公共 Hi3D、内部 MDF 与本地模式保留；账号 Runtime 协议、业务交接及恢复在对应原入口内维护。Blender 使用实际渲染器标识，媒体工具接受宿主显式路径及打包 fallback。

桌面可发现入口由 [sparc3d 白名单](../.dependency-package-tools/profiles/sparc3d.json) 显式决定：`head-reference`、`taubin-smooth`、`product-design`、`rig-retarget`，以及 8 个媒体/软件工作流（`api-demo-service`、`app-prototype`、`asset-review-board`、`audio-prep`、`clip-edit`、`exhibition-tour`、`product-configurator`、`promo-layout`）均公开为同名 `$` 入口。`portrait-reconstruction` 与 `exterior-surface` 保持隐藏依赖，Hi3D Agent 不提供前者的 `$` 入口或技能库卡片；源码、独立包和 Agent Internal 的固定依赖保留。源码具有 `SKILL.md` 不等于桌面分发会保留该发现入口；安装与验证方式见 [分发契约](package-tools.md#desktop-平面分发与子模块)。

受 manifest 哈希校验的 head-template 文本资源由本仓库 `.gitattributes` 固定 LF；宿主仓库的换行配置不能替代子模块内的资源保护。生成包沿用原始资源字节和 manifest。

## 游戏原子能力

游戏核心按单点能力封装：时钟、输入、存档、碰撞、战斗、寻路、关卡、经济、驾驶、对象池、消息接收、性能、回放、浏览器验收、包清单、成绩排名和权益归约。以上入口纳入 desktop 分发选择，显式路径调用与宿主安装后发现分别验证。引擎适配、完整服务与云部署不由这些规则模块自动提供；按游戏工作流的可选能力表选择，禁止把离线回归解释为生产服务上线。
