---
name: body-spring-connector
description: 使用本地 Blender 将已有角色、动物或摆件的身体中段改为连续宽圆片螺旋弹簧，制作内藏配对 D 形插桩和盲槽，保留外观并交付可装配模型。支持默认配方及保持接口不变的片厚、圈隙修订；不重新生成主体，不用于球窝人偶、互锁螺旋玩具或实物强度认证。
---

# 身体中段弹簧连接

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交图像或模型生成；已有网格在本地 Blender 中处理。只有用户没有可用网格、并且明确要求先生成主体时，才交接 [hi3d-api](../hi3d/SKILL.md)；生成失败不自动重试，已有模型不因此重提。

## 独立工作流与依赖

执行前按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 准备分发目录。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者把 intake、socket、spring、deliver 的真实起止、状态和耗时写到包外任务目录；本包没有自动计时脚本，token 无采集时标 unavailable。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。

已有中间件可从对应阶段继续。默认配方见 [最新参数](references/latest-parameters.json)，几何方法见 [建模配方](references/geometry-recipe.md)，检查边界见 [验证清单](references/validation-cases.md)，文件路线见 [执行契约](references/execution-contract.md)。这些毫米值是可回填的默认设计，不是所有模型的固定模板。

## 输入与分支

通过 `$body-spring-connector` 或显式读取本文件调用。接受用户明确指定的 GLB、STL 或当前 Blender 能可靠导入的模型。修改已有家族时读用户已确认的最新版本，保留原件。版本无法判定时询问。

1. 区分首次拆分、已有分件装配、仅修改弹簧。已有合格身体和插槽直接复用；仅圈隙修订不重新切身体或扩孔。
2. 核对世界变换、单位、主体部件、材质、可用实体厚度和原有接口。STL 没有可靠单位标记，不能把坐标值擅自当作毫米。尺寸未知时询问，补齐前不猜测。
3. 只有切分部位、朝向、主要形象或实际尺寸存在不可替代歧义时才询问。
4. 用户尚未指定弹簧、只要求选择连接方式时，先交接 [connector-select](../.dependency-connector-select/REFERENCE.md)；选定本构型后不再改选。
5. 需要参数化 STEP 时交接 [brep-build](../.dependency-brep-build/REFERENCE.md)。本入口交付可编辑网格，不把网格称为 CAD。

用户要求在已有模型身体中间加入弹簧，或修改这种弹簧的片厚、圈隙及端部接口时使用。优先编辑现有资产。

## 与已有能力的边界

- 后台 Blender、场景读写、网格快照和检查点渲染调用 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。螺旋扫掠、布尔和回读可能长时间占用 CPU 且期间没有业务产物，必须用 [run-tools](../.dependency-run-tools/references/budget-run.md) 的 `process_run.run_budgeted` 启动。建议低档 120 秒、中档 600 秒、高档 1800 秒。低档可直接跑；中高档由宿主 `waiting_choice` 使用本入口 `choices_example` 确认后再启动。超时记 `interrupted`，不写半截 BLEND。
- 闭合、绕序、单连通和表面变化调用 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md)，不在本入口重写测量。
- 带逐面来源与 UV 的槽体减料调用 [solid-edit](../.dependency-solid-edit/REFERENCE.md)。无 UV 的纯网格布尔仍在 Blender 内按配方完成，并复查外表面。
- 0.15/0.25/0.35 mm 试片的间隙系列与配对来源调用 [fit-coupon](../.dependency-fit-coupon/REFERENCE.md)。试片必须带本配方的 D 面、卡舌和完整插入深度，不能换成光圆孔。
- 静态装配和有限姿态的实体相交调用 [motion-check](../.dependency-motion-check/REFERENCE.md)。卡舌弹性只标注为假定包络。
- 毫米 STL 调用 [print-export](../.dependency-print-export/REFERENCE.md)。GLB 几何按米，并保留节点 `extras.sparc3dPhysicalUnits = {version: 1, unit: "meter"}`；导出开启自定义属性。
- 多视角效果图调用 [model-preview](../.dependency-model-preview/REFERENCE.md)，复用当前几何。未请求时不渲染视频。
- 制造版本、试印限制和未验证项交接 [print-plan](../.dependency-print-plan/REFERENCE.md)。计划不是成品，也不代替本入口的几何配方。
- 用户要求估算静态支承裕量时交接 [support-check](../.dependency-support-check/REFERENCE.md)。正裕量不是实物抗推倒。
- [ball-joint](../.dependency-ball-joint/REFERENCE.md) 负责球窝，不用于本 D 形桩槽。[twisty-fidget](../twisty-fidget/SKILL.md) 负责互锁螺旋瓣，不用于身体中段弹簧。[source-prepare](../.dependency-source-prepare/REFERENCE.md) 会合并并按目标高度缩放，本流程禁止用它改尺寸。[shape-build](../.dependency-shape-build/REFERENCE.md) 的放样、回转和管道不包含本配方的端部相位、端盘区间和 D 桩，螺旋仍按建模配方构造。

## 默认设计

中段为一根连续、单连通的宽圆片螺旋：6 圈，外径 30、内径 8、径向带宽 11、轴向片厚 2.6、轴向净圈隙 1.25 mm。不得做成互不相连的圆盘或带刚性中轴的假弹簧。

默认端盘直径 28、厚 2 mm。两端为名义直径 12、插入长 10 mm 的 D 形桩，D 平面距轴心 4.6 mm，带一体双卡舌止退；不增加独立锁销。插槽默认单侧间隙 0.25、底余 0.5 mm。

圈隙指相邻圆片的轴向净空，不是螺距。`螺距 = 片厚 + 净圈隙`。说“再小一半”时以最近成功版本的净圈隙为基准；本配方 1.25 mm 的一半是 0.625 mm。

“加粗”可能指外径、片厚或截面积。上下文没有明确含义时询问。本配方已确认的是片厚 2.6 mm。

默认沿用“保留 6 圈、缩短中段”的长度策略。缩小圈隙后重新对位身体，不通过整体缩放修改局部配合。用户要求身体位置不变时，重新协商圈数或其他参数。

用户要求接口保持不变时，锁定桩、端盘、卡舌和槽的局部几何及配合参数。新模型不能安全容纳默认接口时，先调整连接轴或切分位置；仍不适合则询问尺寸取舍。不得悄悄缩放主体、减薄外壁或套用另一模型的切面和轴高。

## 执行

### 1. intake：理解主体与连接位置

读取并查看模型，按语义判断身体两端。狗等长体动物通常沿躯干纵向，上下身体则沿相应身体轴。不能直接把世界 Z 轴或包围盒最长轴当成语义结论。

建立局部连接坐标系，确定身体两端的切面、中心轴及插入方向，避开脸、耳、四肢、尾巴等主要特征。记录原部件名及材质。有贴图的模型保留外表面 UV 与材质。

仅修订弹簧时，从最新版本读取身体与槽。此阶段不新切身体。

### 2. socket：内藏接口

首次处理完整模型时，先形成两个闭合身体部件，再从其相向切面向内部制作配对盲槽。按照建模配方创建 D 形定位与一体卡舌。

在原实体内检查槽、卡钩凹槽及保护包络是否完全容纳。只允许切面入口开口。保护包络不适合当前模型时应调整设计。

已有合格接口则复用，不改变局部接口形状。

### 3. spring：连续螺旋并重新装配

在局部轴上沿螺旋路径扫掠圆角矩形截面，与两个端盘及插桩做实体并集。默认螺距 3.85、中心跨度 23.1、身体切面间距 27.1、含插桩总长 47.1 mm。这些长度来自配方约定。原模型切去多少躯干、两端如何定位，按实际切面计算。

按目标切面位置刚性移动身体，保持身体自身比例、外观及插槽几何不变。默认不添加独立锁销，也不把全部模型融成一个打印实体。

### 4. deliver：检查与交付

按验证清单完成闭合性、单连通、装配、插入方向、止转、卡舌保持、槽壁保护和有限运动包络检查。接口未变时复用先前检查，只重查受改动影响的内容。

至少交付装配 GLB、展开分件 GLB、独立弹簧 GLB、身体和弹簧 STL、试片、可编辑 Blender 工程、关键尺寸与装配说明、实际效果图及制作包。部件名优先沿用已有名字；新模型可用 `body_a`、`body_b`、`spring_connector`。

回读部件、变换、单位与关键尺寸。不覆盖原始输入。当前聊天支持文件链接时提供真实相对路径。未经请求不启动实体打印、网页、视频或付费重生成。

数字样机完成不等于实物验证。始终列明未试印、弹力、抗拔、疲劳、蠕变和站立稳定等未实测项。

## 失败与恢复

单位、目标模型或主要连接位置无法判定时，停在 intake 并保留已完成工作。网格无法形成可靠实体或外壁保护不通过时，不发布可装配结论。中断后从原输入、用户确认版本和已有输出恢复，只补缺失步骤。

<!-- managed-by: sparc3d-runtime -->
