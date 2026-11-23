# 原子能力整合决策

本页维护跨包复用的设计决策、唯一维护源和不得合并的边界。三层入口及数量以 [README](repository-README.md) 和 [能力使用关系](capability-usage.md) 为准；这里不复制依赖清单，不保存单次扫描或测试日志。

本页记录已采用的复用决策与应保留的差异，详细运行契约链接到实际能力包。采用某个共享能力不代表所有历史脚本和配方都已接入；后续修改仍先核对当前实现，同步更新失效决策，不把本页作为第二份实现说明或执行依赖清单。

## 构成与判断

| 层 | 当前构成 | 复用时的判断 |
| --- | --- | --- |
| tools | Hi3D/MDF 调用、Blender 操作、运行记录、依赖物化与仓库使用关系检查 | 工具操作和运行机制，不因为代码能复用就承接全部几何、展示或制造能力 |
| skills | 来源准备、服务选型、几何构造/拟合、连接与制造、诊断、媒体和交付等单点能力 | 单一目标有明确输入、输出、不变量和失败条件；函数/模块已足够独立时不再套一层新入口 |
| workflows | 产品与打印、头部与角色、场景/游戏、部署等端到端交付 | 保留品类约束、阶段图、对象角色、选择和最终交付；已有中间产物可直接续接 |
| doc | 工具完整契约、服务导航、反向使用关系和本整合决策 | 开发规则仍由根 AGENTS 唯一维护，运行时必需契约随所属能力包提供 |

判断重复须比较真实源码、输入输出和副作用，并先沿 `package.json.files` 还原唯一源。同名安装文件、简短调用导航、相似 CLI 或共用一个服务，不足以证明存在重复能力。资料引用、条件调用、下游交接和实际代码物化分别记录，不能把整张静态关系图当作执行顺序。

已有较完整的共享主干：

- 形体构造、来源处理、预览、制造导出和网格检查已分别归入 `shape-build`、`source-prepare`、`model-preview`、`print-export`、`mesh-audit`；[组合边界](../.dependency-shape-build/references/composition.md) 明确米/毫米及各 profile。茶壶、花器、水景、相框等物化这些源码不构成第二维护源。
- 可导出 STEP 的 B-rep 实体归入 `brep-build`（CadQuery 配方，毫米）。它不替代 `shape-build` 的网格放样/回转，也不替代 `solid-edit` 的带 UV 网格布尔。网格反求 B-rep 不在本入口。本地无界 CPU 的预算/心跳/杀进程唯一实现于 [run-tools 预算契约](../.dependency-run-tools/references/budget-run.md)，业务档位由调用入口声明。
- 头部模板、关键点投影、表面拟合和纹理烘焙分别由 `head-template`、`landmark-project`、`surface-fit`、`texture-bake` 维护。MetaHuman 静态模板交付、保留原高模的人像修复、来源衍生的低模拓扑属于不同工作流目标。
- `rig-retarget` 组合 `motion-retarget` 和 `skin-weights`；动画舞台和游戏继续承担下游编排。重定向计算、权重修复、绑定工程交付不能合为一个无条件执行的入口。
- `print-plan`、`connector-select`、`fit-coupon`、`delivery-review` 分别承担制造规划、连接选型、真实试片和交付审查。规则型能力通过明确资料契约使用，不因为没有 Python 调用而视为孤立；业务限制留在各品类。

## 复用决策列表

以下为已采用的维护源选择；优先完善已有能力，保留有意义的薄编排。只融合高度可复用且契约一致的公共部分，特异性脚本继续独立；后面的逐项取舍明确已接入范围，不以包级关系推断全部分支完成。

### 1. 头部检查场景分层：采用

头部展示归入 [model-preview 的头部 profile](../.dependency-model-preview/references/head-preview.md)，基础网格/材质仍复用 Blender 工具，单头选择与保留对象继续由 head_io 维护。关键点投影只保留 IO 依赖，调用方缓存纳入实际共享预览源码。

### 2. 网页预览副本与临时资源恢复：采用

[model-preview 的网页派生接口](../.dependency-model-preview/references/web-derivative.md) 统一副本、显式预算、内容缓存与失败清理；业务保留单角色/多对象选择和同步动作名称。原始制造网格、可见性和资产属性保持，形变或未知属性不冒用缓存。

### 3. 已有场景的帧渲染执行：采用

[blender-tools 的显式帧渲染](../.dependency-blender-tools/references/render-scene.md) 统一已有工程到 PNG 的执行。逐帧/animation、EEVEE/Cycles、命名、保留或指定 fps 均由适配显式选择；分块检查点同时核对渲染源码，建模不随渲染模块变化重跑。

### 4. 视频编码与解码检查：采用

[media-encode 的序列契约](../.dependency-media-encode/references/sequence.md) 支持 PNG/JPEG，头部视频和三个产品说明均复用该入口。保留各自 fps/CRF/起始编号、覆盖及无视频分支；全片技术检查归 media-check。

### 5. 检查图拼版：采用独立 image-sheet

[image-sheet 契约](../.dependency-image-sheet/references/contract.md) 独立承接有序图片与标签到画布和格位映射。各调用方保留拉伸/等比缩略、字体/时间标签、上下标签和留白差异；视频抽帧、业务清单与 ZIP 留在调用方。

### 6. 全实体姿态采样与碰撞：采用

[motion-check 的实体采样](../.dependency-motion-check/references/solid-samples.md) 接收全部刚体矩阵和明确对象对，复用完整 Manifold 相交。调用方显式保留 AABB、体积绝对值与公差等号策略；螺旋工作流继续独立验证捕获、止挡、轨道和保持。

### 7. 人头几何检查包装：保留薄编排

face-fit 与 MetaHuman 流程中的 check_geometry 保留读取 NPZ、按需另存修复、写 OBJ/JSON 与 neutral-head 范围说明。纯比较已经由 [mesh-audit](../.dependency-mesh-audit/scripts/geometry_compare.py) 唯一维护，可选修复与 native 坐标反变换已经由 [surface-fit](../.dependency-surface-fit/scripts/registered_geometry.py) 唯一维护；这里没有第二份几何算法。

继续保持检查模式不写几何、修复模式才生成新资产、rest/current 基线、原 NPZ 字段及 OBJ UV。不为消除这段短包装新增综合入口；只有新增独立归档需求时，再判断是否值得提取文件适配。业务目标不同的两条完整工作流不合并。

### 8. 阶段计时规则：归入统一契约

[run-tools 阶段记录](../.dependency-run-tools/references/stage-records.md) 维护事件身份、语义字段/profile 映射、崩溃恢复、墙钟/token 和追加尝试。灯具、面具、护甲、耳机外套和运动底座只保留品类阶段、日志/manifest 字段与人工覆盖范围；工具 runtime 直接链接统一契约。既有 profile 格式不改，局部脚本不冒充全流程自动采集；耳机外形减薄仍保留启用、跳过和复用分支。

### 9. 工具操作说明与业务规则：归回所属能力

相框、收纳盒和笔刷的 tooling 保留本品类触发条件与输入输出交接，完整安装、调用/恢复、后台 ABI 与本地副作用规则分别链接到 [package-tools](../.dependency-package-tools/references/usage.md)、[hi3d-api](../hi3d/references/calling.md)、[blender-tools](../.dependency-blender-tools/references/code-contract.md) 和 [run-tools](../.dependency-run-tools/references/runtime.md)。Blender 5.2 与 Python 3.10 等本品类限制继续保留，不成为所有能力的默认要求。

两份无独有条款的打印补充合入既有 [print-plan 通用规则](../.dependency-print-plan/references/print-diy-workflow.md)，六个产品入口与物化映射使用同一来源，品类装配和材料限制仍各自维护。概念图/网页工具选择归 [product-design](../product-design/references/full-workflow.md#概念图与网页工具)，同版结果与打开下载检查归 [delivery-review](../.dependency-delivery-review/references/delivery-policy.md)。

服务提交不确定时的恢复与业务一般重试继续分开，不能因通用工作流允许有限重试而绕过工具的禁止重提状态。来源链接、实际适配与回读、数字结果不等于制造通过等边界仍在各唯一源中可发现。

### 10. 资产回读测量：共享原子函数，保留三个特异性脚本

[blender-tools 的完整资产载入](../.dependency-blender-tools/references/asset-scene.md) 维护 BLEND 整工程打开与 GLB 清场导入；[mesh-audit 场景测量](../.dependency-mesh-audit/references/scene-measure.md) 维护原始对象计数、世界包围盒及显式对象的局部拓扑/体积。函数不承担产品目录、报告或完整流水线。

护甲、浮雕笔刷的 validate_assets 和 mesh-audit 的 fresh_review 保留为各自脚本：文件枚举、当前帧/第 0 帧、float64/float32、空对象与报告键不同，不能统一丢失；fresh_review 的边界先转 Python 数值再相减。护甲图片清单不替换成材质节点依赖检查。具体 profile、独立调用、源保持与验收由上述唯一契约维护；计时和建模仍由调用方负责。

### 11. 本地路径与执行：复用工具契约，保留入口保护策略

[run-tools 路径契约](../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 维护解析、重叠、已有根续接和非事务边界；[显式执行](../.dependency-run-tools/references/runtime.md#显式本地执行) 维护导入、状态传参、场景副作用和失败传播。原路径实现与 runner 继续保留，配置不是所有入口都可豁免的派生输入。

护甲生成 work/config.json；耳机与运动标准入口保护模型和配置，配置不能在写入根内；运动 DIY 保护整个 source-case，配置须避开固定输出名，缺源检查也可能留下已建目录。三者分别在自己的 runtime 声明，code-contract 链接该适配；拟合和减薄的独立文件边界、几何单位及业务阶段仍各自维护。

### 12. 产品推进与交付：通用规则共用，品类指南保留

[product-design](../product-design/references/full-workflow.md) 唯一维护首轮与等待、阶段产物、缺数据续接和完整任务终点；[print-plan](../.dependency-print-plan/references/print-diy-workflow.md) 维护制造版本、BOM、同层向试片与完成条件；[delivery-review](../.dependency-delivery-review/references/delivery-policy.md) 维护同版资源、网页/下载验收和按需视频。规则引用仍按实际条件使用，不把制造规划或验收原子能力扩成生成全套产品的入口。

护甲、耳机外套与运动底座的 user-guidance 保留各自首轮示例、输入表、设备/身体/原模型保护、材料与装配路线、专属减薄或运动构型及脚本支持范围；共有等待正文、阶段表和交付清单改为可发现的唯一源链接。不同业务脚本和品类步骤继续独立维护。

## 公共内核的逐项取舍

以下明确实际复用与保留范围，不再作为待实施清单。原子能力可以是已有函数或模块；这些接入没有新增入口或合并业务脚本。后续新增候选仍先比较当前实现，再决定是否值得抽取。

| 项 | 处理结果 | 唯一维护源 / 保留范围 |
| --- | --- | --- |
| A. GLB 同播合并 | 三个旧配方接入已有核心 | `glb-clips.merge_file`；相框/新月相框/旅行盒的动作脚本与报告适配保留 |
| B. STL 序列化 | 仅整合相同 NumPy 数值 profile | `print-export.stl_bytes` 被 `solid-edit.stl` 调用；灯具标准库与面具 mathutils 写入器保留 |
| C. 图片拼版 | 补充底部标签，接入 MetaHuman | `image-sheet.compose_sheet`；业务标题、模式/视角排序和 JPEG 保存保留 |
| D. GLB 容器读取 | 三个检查分支接入现有解析 | `glb-clips.read_glb`；人头交付、MetaHuman 预览和运动底座验收各自保留 |
| E. STL 解码 | 保持独立 | 严格制造转换、诊断、浮雕采样、护甲 Mesh64 的接受范围与数据策略不同 |
| F. 三角度量 | 浮雕接入既有数组核心 | `mesh-audit.triangle_arrays`；浮雕字段口径和高度流程保留 |
| G. 文件哈希 | 保持短小局部函数 | 不为几行流式读取增加跨工具依赖；状态保存/恢复不能一并合并 |

### A. GLB 同播合并：公共核心复用，配方独立

[animate_frame.py](../frame-design/scripts/animate_frame.py)、[animate_crescent.py](../frame-design/scripts/animate_crescent.py) 与 [animate_travel.py](../relief-box/scripts/animate_travel.py) 的 `merge_scene_animation` 调用既有 [glb-clips.merge_file](../.dependency-glb-clips/references/contract.md)，与相框 [DIY 分支](../frame-design/scripts/animate_frame_diy.py) 共用同一核心。动作编排、对象角色、fps、镜头、片段名和原报告字段继续由各脚本维护。

输入是本配方明确同播的派生 GLB；核心校验完整容器、时间 accessor、引用与目标冲突，原样保持非动画 JSON 语义、BIN/未知尾块和采样时刻。零/空片段、不支持的时间存储或无效引用明确失败，不能为沿用旧手写解析的宽松行为绕过校验；转换失败不改源。此失败保持仅覆盖合并函数，不承诺整个建模/导出流程回滚。

### B. STL 序列化：仅合并同精度、同依赖的分支

[solid-edit.stl](../.dependency-solid-edit/references/code-contract.md) 使用 [print-export.stl_bytes](../.dependency-print-export/references/blender-stl.md)，保留毫米坐标、float32 中间计算、法线下限、头部零填充和写入行为。Manifold 取面、布尔来源/UV 与路径仍归调用方；不为来源保留布尔创建综合制造入口。

[lamp-design.make_coupons](../lamp-design/scripts/make_coupons.py) 的试片只需标准库；引入 NumPy 或拆一层只转发 `struct.pack` 都缺少足够收益。[mask-design.stl_mm](../mask-design/scripts/mask_geometry.py) 保留 mathutils 归一化、逐记录流式写入、排他创建与临时 mesh 清理。这两份特异性脚本继续独立，不能用当前 NumPy 字节聚合替换后悄悄改变依赖、数值或失败/资源语义。

### C. 图片拼版：公共格位与业务标题分开

[image-sheet](../.dependency-image-sheet/references/contract.md) 提供显式 `label_position`，默认 top，MetaHuman 使用 bottom。[contact_sheet.py](../metahuman-fit/scripts/contact_sheet.py) 保留 `make_sheet`、`make_expression_sheet`，继续负责 70 像素标题区、列名、模式/视角与文件对应、表情报告读取和 JPEG 编码；共享函数只负责读图、缩放、格位与标签。缺图/坏图失败；空姿势明确报错，不写伪造的空检查图。

`overview`、`expression_review` 的源码指纹纳入物化的拼版核心；该源码变化不要求重新拟合或烘焙。其他既有适配仍使用自己的缩放、字体、时间标签和上方标签参数。

### D. GLB 容器读取：解析共用，验收各自负责

[head-lowpoly.inspect_glb](../head-lowpoly/scripts/deliver.py)、[metahuman-fit.export_preview](../metahuman-fit/scripts/preview_export.py) 与 [motion-base 导出检查](../motion-base/scripts/inspect_diy_exports.py) 调用 [read_glb](../.dependency-glb-clips/references/contract.md)，不因复用该模块而执行动画合并。骨骼、形态键名称与顺序、嵌入贴图、附件、回读几何及对象角色仍由各自脚本检查。

完整 chunk 校验会拒绝仅首段 JSON 可读但容器已损坏的输入；支持静态无动画文件并保留未知尾块。这不是完整 glTF 验证。head-lowpoly 的 deliver 和 MetaHuman 的 review 指纹纳入解析源码；运动底座回读阶段直接重读当前产物，无旧报告缓存。当前不为现有独立函数再建同义 skill。

### E. STL 解码：特异性大于可共享部分，保持独立

[print-export.decode_stl](../.dependency-print-export/scripts/stl_to_3mf.py) 检查法线有限并拒绝塌缩三角；[mesh-audit.inspect_binary_stl](../.dependency-mesh-audit/scripts/frame_stl.py) 需保留退化项用于诊断；[relief-map.extract](../.dependency-relief-map/scripts/extract_stl.py) 精确焊点后重排轴并采样；[cosplay-armor.load_stl](../cosplay-armor/scripts/validate_split.py) 使用 Mesh64 精度路径。空输入/非有限值的接受范围、索引化与顺序、内存和流式处理策略都不能无条件互换。

当前共性主要是短小的头部/计数读取和 STL 固定记录布局。为这部分另设带多种 profile 的通用解码器，会增加依赖和分支；维持各自脚本及独立格式验收。后续只有出现足够复杂、契约一致的原始记录需求才重新评估，不能直接拿严格制造读入器替代诊断。写入与读取须保留独立样例和断言，避免共享错误互相通过。

### F. 三角度量：直接复用现有核心，保留浮雕口径

[relief-map.extract](../.dependency-relief-map/references/code-contract.md) 调用 [mesh-audit.triangle_arrays](../.dependency-mesh-audit/references/mesh-measure.md) 的 `edge_incidence` 和 `triangle_double_areas`。输入仍是当前采样坐标中的顶点和索引；严格 `area == 0`、`counts > 2`、塌缩边参与及原精度保持，不套用 `counts != 2` 或 epsilon 判定。高度采样、基线、修补、来源图与 JSON 适配仍在浮雕入口。

直接包声明新的物化关系，间接相框/收纳盒已物化同一三角核心；这些 extract 入口显式运行，不读取阶段结果缓存。

### G. 文件哈希：保持简单函数，不扩大工具耦合

[run-tools.checkpoints.digest](../.dependency-run-tools/scripts/checkpoints.py)、[hi3d-api.hi3d_storage.digest](../hi3d/scripts/hi3d_storage.py) 与 [skin-weights.io_utils.file_digest](../.dependency-skin-weights/scripts/rigging/io_utils.py) 的完整文件 SHA-256 分块读取虽相同，但实现短、稳定；当前维持局部函数，不为这几行增加跨工具依赖或新模块。

API job 排他保存、提交恢复、普通原子 JSON、脱敏摘要、数组指纹与业务缓存键继续各自负责：权限、内容和失败语义不同。将来若有真实的公共文件流处理需求再评估，不能把全部哈希与状态机制合为一个入口。

## 不应按表面相似继续拆分的部分

- `motion-base/run.py` 与 `earbud-case-cover/run.py` 很相似，但路径预检、子进程、来源、编码等已经复用；减薄/贴合、滚动/稳定、装入验证及阶段顺序仍属品类编排。不把两条 runner 整体放入 `run-tools`。
- 两者的 lifestyle.py 共用材质色和最终相机/渲染形式，但书堆、笔记本/线缆与构图是不同场景配方，底层构造和展示已经复用；不为几行相似布局新建产品场景 skill。
- 相框与收纳盒的 motion 检查已共用 `scene_samples`、`surface_pairs`，不同对象对、16fps→导入帧换算及 raw/evaluated 策略仍有意义。不要为同名 `inspect_motion` 再建第二个检查 skill。
- `hi3d-api` 与 `mdf-call` 的鉴权、提交/恢复、传输和业务成功语义不同；`service-select` 只做服务选择。三个入口继续分开，不能因都有“调用服务”就统一成一份泛化客户端。
- `relief-palette` 的 `fit_vertices` 对完整浮雕顶点做 XY 等比适配与独立深度缩放；`relief-map` 的首击高度场会丢倒扣。两者不直接等价。
- 螺纹水瓶的公母螺纹与伸缩玩具的螺旋互锁共享螺旋运动概念，接触/保持条件不同。可复用姿态和实体测量，不合并机构规则。
- `asset-page` 已承接资产读入/模板共用部分；离线 STL 装配页、手机内外相机页、灯具选型页的用户交互不同，保留 [现有页面边界](../.dependency-asset-page/references/contract.md)。

## 后续维护入口

先按 [AGENTS 的前置比较](repository-AGENTS.md#先理解再修改) 确认当前唯一源，再按每项契约修改；不得以本页决策代替必读入口或当前实现。共享实现的输入、单位、异常和状态保持必须先明确，业务默认与品类经验通过显式适配保留。

每项落地同步源码、调用方、`package.json.files/requires`、阶段缓存/源码指纹、运行契约、入口/元数据、工具 doc、README 与 [使用关系](capability-usage.md)。具体门禁和提交要求只维护于 [AGENTS](repository-AGENTS.md#能力使用关系必须同步维护)。无依赖变化时生成结果可以无差异，不需要为表示“已维护”而人为改表。

现有使用关系机制是“物化清单/资料链接 + 有原文证据的显式交接声明 → 生成反向表 → 提交钩子检查”。它覆盖所有 tool/skill，包括无使用方的入口；每个 workflow 的出边保留证据。检查器能验证目录覆盖、来源与文档一致性，不能证明自然语言分类、隐藏动态调用或分层设计正确；这些仍需代码和契约审阅。本地钩子不会自动成为远端强制检查，不能据此声称所有克隆或服务器都已启用门禁。

### 人头完整 workflow 与局部 skills

[portrait-reconstruction](../.dependency-portrait-reconstruction/REFERENCE.md) 保留从图像准备、建模、可选后处理到纹理与拆分交付的阶段编排。[gray-resin](../.dependency-gray-resin/REFERENCE.md) 维护图像配方，[portrait-analysis](../.dependency-portrait-analysis/REFERENCE.md) 维护同源渲染与视觉推理交接，[nose-repair](../.dependency-nose-repair/REFERENCE.md) 唯一维护鼻移植算子。独立 [eye-repair](../.dependency-eye-repair/REFERENCE.md) 仍维护局部切除和球冠验收，但不再纳入此头雕 workflow。已有中间产物可以直接进入所需 skill。

鼻部和渲染源码迁出后，workflow 通过 package.json 保持原物化路径；共享几何、相机、审计和运行工具继续复用，不复制新客户端。旧 references 地址保留导航。眼球 skill 是有人工区域选择与验收的操作契约，未把有开边的原型包装成通用自动修复或闭合保证。

### 两种四视图模式与共用图像处理：已接入参考图阶段

[head-reference](../head-reference/SKILL.md) 在 `four-views` 中维护两种姿态：`aligned` 转正四视图，`current` 保留原图左右朝向、抬头/低头及侧倾的当前视角四视图。后者固定头部姿态，只换相机方向，采用 view_0/90/180/270 相对标签，不冒充标准解剖正侧后。裁切、颈部、背景、造型与材料共用；head/front 单图独立可用，不是前置链。约束与验收由其 [提示词](../head-reference/references/prompts.md) 唯一维护，各模式建立自己的基准。它不生成 mesh，也不把转正解释为改表情或对称化。

必选造型与可选材质分开：头雕所有模式均必带的头发实体块 H 和彩色材料 C 在 [可打印头雕 workflow](../.dependency-portrait-reconstruction/references/prompts.md)，灰树脂特异材料继续由 gray-resin 维护。workflow 将 H 传入每次生成/修订，不随视角或材料取消，不为不同模式复制 skill，不混用灰模与彩色虹膜。只在明确续接时复用合格图。aligned 检查转正，current 对照原图分别保留 yaw/pitch/roll 并检查固定头姿。旧 manifest 未写 pose_mode 时 head=current、front/four-views=aligned，避免重新解释旧输入；切换模式使旧评审失效。图像 approved 不证明服务兼容：当前相对视角在契约确认与适配验证前停在图片交付，不能改名 front 或静默转正。

这是可由宿主按说明执行的图像 skill，不内置生成服务。分发 profile 公开其入口；真实生图效果、自动发现和完整业务回归需分别验收，入口/打包检查不能替代这些验证。

### 可打印头雕与头发分割：现有归属与待集成边界

原子能力表示职责粒度；skill 表示可独立发现的能力封装，workflow 表示端到端交付编排。三层都使用 SKILL.md，文件名不是分类依据。

portrait-reconstruction 的显示名称为“可打印头雕”，内部名称保持兼容。实体发束、自然连接的发根、圆润发梢和浅刻细节是所有图像模式共同必选约束；过细发流及有根连接的悬空刘海可在生图时适度加粗并保留，不一律删除或强制贴额，也不用皮肤薄膜桥接。局部加粗保留主要发型、自然走向及雕刻层次，不默认留到几何后处理；材料与皮肤处理单独选择。通用参考图执行者必须遵守调用方传入的必选造型，但非头雕任务不被自动改成打印风格。“可打印”不代表已经完成水密、最小厚度、支撑或实际工艺验收，不能把参考图或文件格式作为通过依据。

| 内容 | 维护归属与现状 |
| --- | --- |
| 原图到人头高模 | portrait-reconstruction 保留品类选择、阶段衔接、来源版本与交付；已有输入允许跳过上游 |
| 已有头模到头发/头部两部件 | [head-hair-split](../.dependency-head-hair-split/REFERENCE.md) 是可独立执行的 workflow；标签图生成、贴图、图割及验收合成业务流程，不冒称一个纯 mincut skill |
| 同源视觉分析、局部注册与鼻移植 | 已有 portrait-analysis、face-fit、nose-repair 独立承担；工作流不再维护第二份实现 |
| 标签采样、面映射、图割与 GLB 分区 | 当前分别在 head-hair-split 的 label_texture、apply_labels、graphcut、partition 模块；模块独立不等于必须新建 skill |
| 网络请求、Blender 进程及任务记录 | 复用 tools；不因四视图、彩色纹理与黑白标签业务不同而复制客户端 |
| 双色交互 HTML 与浏览器 FBX | 是分割的交互产物及运行适配，不是新 workflow；当前尚未作为仓库入口交付，不能把外部固定样例原型视为通用已集成能力 |

当前 graphcut.solve 不只是最大流：还包含图准备、不对称种子带、连通域清理与隐藏壳归属。后续抽取通用内核时应分清图求解与人像策略，不能只换目录便宣称通用于所有语义分割。眉毛、耳朵等类别约定与参数选择属于业务配方；浏览器和 Python 如保留不同运行时实现，须由同一能力维护契约并做逐面对照。

主 workflow 按五个阶段组织：**图像处理 → 几何生成 → 几何后处理 → 纹理生成 → 几何拆分**。这五个阶段不是五个新 skill；已有入口分别承担具体能力。后处理只保留可选修鼻与可选几何去噪，不包含眼球修复；默认都不启用，但必须询问并得到明确答复，不能把未答复当作跳过。需要哪些分析/注册由已确认的所选操作决定，仅去噪不要求先修鼻。启用去噪后仍沿用受保护语义权重与 80 轮起点，算法默认不等于 workflow 默认开启。纹理接收最后一个通过验收的后处理输出或原高模，默认 condition 是前面已生成并验收的 front，不是原照片；缺失 front 则询问，具体来源/复用约束见 workflow 执行契约。

主入口按需交接 head-hair-split；缺失标签按原流程补齐，已有标签默认运行 html。交互 HTML 必须给链接并主动打开，然后等待用户调阈值、点击 mincut 和下载静态双对象漫反射 FBX，不默认代切割或用普通成果页代替。图预处理由 graphcut.prepare_graph 唯一维护，Python/浏览器分别求解并做逐面 parity；完整 PBR 不属于此 FBX 导出契约。CLI GLB 分区是明确要求代执行并确认阈值后的可选路线。统一冻结白模的彩色/标签双请求调度仍待接入，不因页面就绪声称收费端到端或打印适配已验证。

接入需保持以下交接条件：

- 冻结同一份白模输入供彩色及标签请求使用，分别保留 job 与产物；同输入不保证服务永远保持拓扑，顶点/面数量相同也不足以证明对应。
- 将标签用其自身 UV 采样成逐面分数，经几何/面的一一对应映射到彩色结果；UV 可以不同，不能直接把黑白贴图套进彩色 UV。彩色结果为待拆分材质基准，仍须核对其与冻结几何的形状和修复区域保持。
- 映射失败时停止，保留原任务和产物；近邻匹配须有角点、面积与法线验证，不静默重网格或重提交服务。
- HTML 只显示双色与光影，viewer 内独立控制头部/头发显隐；原纹理只供导出。预览显隐不决定导出部件，滑块预览不是最终 mincut。
- 生成 HTML 表示交互产物就绪，不等于用户已经选定阈值并完成 FBX。图割后的标签、阈值、输入版本与实际 FBX 才能构成最终交付记录。

后续先消除原型的固定样例路径、单一根变换及贴图假设，接入既有采样/映射/分区维护源，再提供分割 workflow 的页面出口，由主 workflow 的几何拆分阶段选择该出口。提交时同步实际 package 依赖、使用关系、阶段指纹与独立包验证；待实施步骤不写成当前执行依赖。静态单材质、沿原边切分、不补头皮或封口等限制不能被 UI 包装掩盖。

### 参考图评审的内置边界

`head-reference` 内部的 [reference review](../head-reference/references/review.md) 维护纯评审契约、完整必查矩阵、源码/策略/输入指纹、人工确认与静态报告；不是新仓库、skill 或视觉服务。`portrait-reconstruction` 的 [品类策略](../.dependency-portrait-reconstruction/references/image-review.md) 追加实体发束、中尺度雕刻发流、微丝抑制和刘海适度加粗/根部连接等硬项，并负责选择、定向修订及停止的业务编排；共享脚本通过 package.json 物化，单份维护。`unsupported_fringe` 保留 ID，但不再按发梢悬空一律拒绝；旧策略结果按新版重审。四视图另有 set/ear_hair_consistency 硬项，按本模式基准检查耳朵位置及头发遮挡一致；全部或部分遮耳可通过，不强行露耳，也不要求不同投影具有相同二维可见面积。基准生成与补图共带 E，定向修订关系矛盾的视图，不拨开头发或转正 current。基础姿态检查不复制到头雕策略，打印风格也不强加给通用人像。

实现能拒绝缺项、旧版本、无证据及不匹配的确认，并输出未校准观察评分和修订建议；实际看图与真实人工确认仍由宿主承担。没有自动视觉推理、候选排序、修图循环或已测 reward 准确率。现有 media-check 管文件可读性，delivery-review 管交付来源，资产审阅看板管版本批注，均不替代此造型评审；本次不复制它们的解码/存档实现。真实案例及偏好校准记录留在任务目录，不进入共享仓库。新图评审失效不删除或重提交历史几何任务。

### 装配模型的外露表面条件

[exterior-surface](../.dependency-exterior-surface/REFERENCE.md) 独立承接高分辨率表面格网的外部空气连通性筛选与 Geo2 坐标交接。它不属于来源规范化、闭合实体布尔或图像 ZIP 构造：现有三者都不能剔除封闭内部表面。GLB 体素化复用目标 hitem_infer 的 CUDA 算子，哈希复用 run-tools；已有图像包仍由 geometry-input 维护，只新增唯一坐标成员。不输出清理后的 mesh，也不承诺水密；口腔开口与装配漏缝须在模型层判断。

## 创作软件适配的复用边界

媒体剪辑、字幕与混音分别由 [media-edit](../media-edit/SKILL.md)、[subtitle-track](../subtitle-track/SKILL.md)、[audio-mix](../audio-mix/SKILL.md) 承担；序列编码及完整视频解码仍复用原媒体能力。参数化模板由 [remotion-render](../remotion-render/SKILL.md) 维护；原生条带与笔划分别由 [video-sequence](../video-sequence/SKILL.md)、[stroke-animate](../stroke-animate/SKILL.md) 维护，不能把二维笔划当VSE条带。矢量文档由 [svg-edit](../svg-edit/SKILL.md) 维护；原生约束草图由 [cad-sketch](../cad-sketch/SKILL.md) 维护，不合并不同内核的CadQuery配方。它们共享任务路径/哈希/预算；各领域解析、单位和回读留在所属能力。端到端宣传物料、视频剪辑与音频整理分别由 [promo-layout](../promo-layout/SKILL.md)、[clip-edit](../clip-edit/SKILL.md)、[audio-prep](../audio-prep/SKILL.md) 编排上述原子能力；工作流只保留品类交互、三种海报规格、预览/成片分档和响度实测适配，不复制 Inkscape/FFmpeg 剪辑或混音内核。业务 App 原型由 [app-prototype](../app-prototype/SKILL.md) 编排列表/详情/编辑页，本地持久化复用 [game-save](../game-save/SKILL.md) 的 encode/decode/writeSave，浏览器操作验收复用 [game-browser-check](../game-browser-check/SKILL.md)，不另写存档格式或假登录支付。产品配置页由 [product-configurator](../product-configurator/SKILL.md) 编排已有 GLB 的改色/显隐，容器读取复用 [glb-clips](../.dependency-glb-clips/REFERENCE.md) 的 read_glb，配置存档同样复用 game-save；不另写 GLB 解析器，也不把显示改色写成物理材质或收银。单展厅导览由 [exhibition-tour](../exhibition-tour/SKILL.md) 编排热点与可暂停路线，模型容器同样复用 glb-clips，图片验收复用 [media-check](../.dependency-media-check/REFERENCE.md)；虚拟布置不是测绘或 BIM。资产审阅看板由 [asset-review-board](../asset-review-board/SKILL.md) 编排多版本对比与批注，模型仍复用 glb-clips，图片/视频复用 media-check，批注存档复用 game-save；批注绑定原版本，导入失败不覆盖，不另写协作账号。算法演示由 [api-demo-service](../api-demo-service/SKILL.md) 把用户自己的一个入口封成本地 HTTP 与测试页，请求经契约校验后交给固定 argv，不封装宿主内部算法，也不复制 [mdf-deploy](../.dependency-mdf-deploy/REFERENCE.md) 的队列部署。

### 发光浮雕相框与艺术相框、透光灯：保留三入口

[lithophane-lightbox](../lithophane-lightbox/SKILL.md) 承接照片/已有浮雕到发光相框：V5 尺寸接口、V5.1 十二件框体、混色或 UV 照片板，以及完整制作时的切片打开。它不是通用艺术相框，也不是筒形透光灯罩。

[frame-design](../frame-design/SKILL.md) 仍负责作品窗口、装饰轮廓与可拆背板/支座；[relief-lamp](../relief-lamp/SKILL.md) 仍负责光学厚度灯罩与整灯结构。框体生成器、UV 制版脚本和混色工艺规则是本品类特异性实现，不抽成 tools；高度场提取有已有浮雕时交接 [relief-map](../.dependency-relief-map/REFERENCE.md)，网格检查/导出/运动/试片复用已有 skills。混色一键 3MF 算法原包未提供，迁入后也不宣称补齐。

### 单图打印款式与激光分层、浮雕高度：保留独立工作流

[image-to-print-forms](../image-to-print-forms/SKILL.md) 承接一张清晰标志、线稿或剪影，做成可选的分层标牌、轮廓落地桌摆、波浪镜像围合或弧形竖片，并交付网格与固定轴测预览。它不是 [layered-laser-ornament](../layered-laser-ornament/SKILL.md) 的激光 SVG，也不是 [relief-map](../.dependency-relief-map/REFERENCE.md) 的高度场。标志分色、四种实体和 STL 零面积碎片清理留在本品类脚本；通用放样、毫米导出、网格测量和支承计算仍各自维护，不把辅助器的绿色点缀规则升成通用蒙版。

### 身体中段弹簧与球窝、互锁螺旋：保留独立工作流

[body-spring-connector](../body-spring-connector/SKILL.md) 承接已有角色、动物或摆件的身体中段：连续宽圆片螺旋、内藏 D 形桩与配对盲槽、保持接口的圈隙修订，以及同版网格交付。它不是 [ball-joint](../.dependency-ball-joint/REFERENCE.md) 的球窝，也不是 [twisty-fidget](../twisty-fidget/SKILL.md) 的互锁螺旋瓣，不并入 [print-joints](../print-joints/SKILL.md)。螺旋相位、端盘和 D 桩留在本品类配方；闭合检查、试片记录、毫米导出、实体相交、预览、带 UV 布尔和后台 Blender 仍调用已有入口。来源高度归一化会改变尺寸，本流程不使用。迁入时没有随包几何脚本，也未在新输入上端到端运行。

## 面部局部注册与全头交付

[face-fit](../.dependency-face-fit/REFERENCE.md) 接收已有高模的同源观测，维护可见面部筛选、局部注册适配和 donor 导出。portrait-reconstruction 物化并调用该唯一源，nose-repair 接收 donor；metahuman-fit 仅在用户目标为局部 donor 时交接，默认全头生成/拟合流程保持。共同 brush 算法仍在 surface-fit，模板与投影分别在 head-template、landmark-project。局部注册不自动证明全头质量，不要求光头生成。
