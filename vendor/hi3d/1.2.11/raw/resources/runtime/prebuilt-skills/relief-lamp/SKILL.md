---
name: relief-lamp
description: 将文字、图片或已有浮雕模型做成可装配的透光浮雕灯；文字经 Hi3D 文生图、图片经 Hi3D 图生浮雕，再做光学厚度与本地结构。支持连接配合微调与筒面纵带修复。建模交付后总结切片工艺并询问是否继续；仅经同意后打开所选切片软件，把整灯放入一个工程并按颜色与工艺分盘。不用于通用艺术灯具、灯具安全认证，也不默认启动实体打印。
---

# 透光浮雕灯

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。新图和浮雕经 Runtime `hi3d_api` 完成；已有产物继续本地步骤。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。通用艺术灯具、内腔藏光与 Logo 放射竖片仍用 [lamp-design](../lamp-design/SKILL.md)；带 LED 背板的发光浮雕相框用 [lithophane-lightbox](../lithophane-lightbox/SKILL.md)。不把本流程扩成任意灯罩或相框设计。

## 独立工作流与依赖

执行 relief-lamp 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。本包没有造型内核脚本，灯罩与结构由执行者在 Blender 中按引用资料完成。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文阶段一起使用；已有合格浮雕、整灯或切片工程可从对应阶段继续。

这是同一任务的两个独立交付阶段：

1. **A：建模与交付。** 完成模型、检查、文件与工艺总结，到此可以结束。
2. **B：可选打印配置。** 只有用户明确同意才执行。B 只续用已交付几何，不重复生成整灯。

用户仅问填充、盘数或工艺原理时直接答疑，不启动建模或切片。已有模型且只要求打印设置时，从已完成的 A 续接。

## 输入与完成结果

以 `$relief-lamp` 或显式读取本文件调用。输入为文字、图片、浮雕网格，或已交付的整灯。多种同时存在时保留用户指定的主输入。

成功时：

1. 照片明暗型与形体型透光已区分；光学厚度不把雕塑高度直接当材料厚度。
2. 灯罩、框体/底座、灯托、维修盖和紧固件是独立打印件；外购 LED、开关、螺丝和线缆只作包络，不混入打印件。
3. 可编辑工程、装配 GLB、毫米 STL、清单和开关灯对照实际生成。局部修订另交参数前后值、同相机对照和重打范围。数字检查不等于切片、透光试印或温升通过。
4. 未获打印配置同意时，不探测或打开切片软件。用户要求先 review 时停在模型交付。同意后才交付一个原生整灯工程，且不发送实体打印。

## 执行顺序

先读 [建模与透光](references/modeling.md)。同类筒形灯或处理连接/表面反馈时同时读 [连接配合与筒面修订](references/fit-and-surface.md)；其中毫米数值是案例起点，不强制套到任意灯型。进入 B 时读 [切片与分盘](references/slicing.md)。验证范围见 [依据与验收](references/evidence.md)。PCG 路径：`main` 从文字或图片做到建模交付；`reuse_relief` 已有浮雕或整灯时跳过生成，含连接配合与筒面局部修订；`slice_only` 在 A 已完成后只做可选切片。

1. **intake**：判断新建、局部修改、打印设置或单纯问答。记录 LED 发光面、开关卡脚、喷嘴等实物事实；未知值标待确认。只做数字概念时写明假设。
2. **generate**：文字先经独立 [hi3d-api](../hi3d/SKILL.md) 文生图，查看后再提交图生浮雕；已有合格图片直接 `submit relief`。浮雕询问 `rmbg`，不把普通整物图生 3D 替代浮雕，也不把预览图或 EXR 登记成已完成 GLB。已有浮雕网格跳过。图像调用失败立即停止该链路，不自动换模型重提。
3. **build**：在 Blender 中建立有真实壁厚的闭合灯罩和可拆结构。源图背景不直接充当浮雕高度；筒形非图案区使用统一圆柱基面，按主体轮廓窄带连接。同结构灯优先复用圆柱插销与底部向上螺丝；六角松动且公头合格时只缩母孔。后台打开、导入、另存交接 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。开关灯对照交接 [model-preview](../.dependency-model-preview/REFERENCE.md)，固定几何与相机，只改变内部光源。局部修订用同相机、同诊断材质做前后对照；法线诊断图不充当点亮效果。
4. **deliver**：毫米 STL 调用 [print-export](../.dependency-print-export/REFERENCE.md)。闭合、法线、正体积调用 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md)。开合与退出姿态的实体干涉调用 [motion-check](../.dependency-motion-check/REFERENCE.md)。槽口试片需要成对裁切时交接 [fit-coupon](../.dependency-fit-coupon/REFERENCE.md)；透光阶梯片留在本流程。销孔、六角母孔和自攻底孔试片按连接修订资料执行。先交付真实文件和工艺建议表，再用无默认答案的确认询问是否配置切片。局部修订额外列出参数前后值、保留项和需重打零件；旧 3MF 不含新几何。
5. **slice**：仅在明确同意后探测已安装切片器，收集真实打印机和喷嘴，把整灯放入一个工程并按颜色与工艺分盘。灯罩写入对象级覆盖并回读刀路。筒面修复后用新几何检查接缝，不沿用旧 G-code。不启动升温、回零或实体打印。

登记和嵌入式预览只在当前环境明确提供调用定义时执行；缺失时标记该集成为不可用，并继续交付已验证文件。

## 本地长任务预算

高度网格、封边、布尔、筒面顶点修订和离线开关灯渲染可能长时间占用 CPU。进入这些步骤前，任务目录必须已有预算和心跳；后台 Blender 由 [run-tools](../.dependency-run-tools/references/budget-run.md) 的 `process_run.run_budgeted` 启动。建议低档 120 秒、中档 600 秒、高档 1800 秒。低档可直接跑；中高档由宿主 `waiting_choice` 使用本入口 `choices_example` 确认后再启动。超时记 `interrupted`，不写半截 BLEND。Hi3D 远端等待继续走原 job，不套用本地 kill。

## 恢复与记录

阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者把真实起止、状态和耗时写到包外任务目录。本包没有自动计时脚本，token 无采集时标 unavailable。已提交生成任务恢复原任务；切片失败只重做 B。局部结构修改只修订相关网格与下游 STL，未改件复用已有验收。授权配置切片不等于授权实体打印。

迁入后实测：筒形灯罩本地亮度厚度、Bambu Studio 原生四盘工程、圆柱插销/底部自攻螺丝/六角母孔微调和空白筒面统一已完成数字修订并获用户 review。文字→图片→浮雕和图片→浮雕链路按方法定义，创建草稿时未逐条实跑。连接与筒面修订后尚未重配切片。OrcaSlicer 未完成对应原生路线。新结构的保持力、透光和温升仍待实物再验证。

<!-- managed-by: sparc3d-runtime -->
