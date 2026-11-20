---
name: image-to-print-forms
description: 将单张标志、线稿或剪影做成可选的分层标牌、轮廓落地桌摆、波浪镜像围合或弧形竖片，交付经数字检查的 GLB、毫米 STL 和可编辑工程。适用于用户要比较或选定这些几何款式；不是普通照片自动重建，不承诺免支撑、实物强度或打印成功。
---

# 单图立体打印制品

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D，已有图片走本地构造。没有内容图、并且用户明确要求先生成标志图时，才交接 [hi3d-api](../hi3d/SKILL.md)；生成失败不自动重试。不要把普通照片交给生模来冒充这四种构造。

## 独立工作流与依赖

执行前按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 准备分发目录。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者把 intake、select、build、deliver 的真实起止、状态和耗时写到包外任务目录；辅助脚本不采集全流程计时，token 无采集时标 unavailable。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。

通过 `$image-to-print-forms` 或显式读取本文件调用。款式判断见 [选项](references/options.md)，构造与检查见 [几何与检查](references/geometry-and-checks.md)，一次已运行样例见 [运行样例](references/tested-example.md)。

本地构造需要 Python 3.9+，以及 [requirements.txt](requirements.txt) 中的 NumPy、OpenCV、Manifold、trimesh、Shapely 和 Pillow。渲染与 GLB 导出需要调用方提供的 Blender，独立 Python 没有 bpy。宽度示例 144 mm 只是样例；辅助器接受 60–300 mm，不代表该范围都做过工艺验证。

## 输入

内容图决定图案，侧面参考决定构造。不把参考图里的文字、品牌和外轮廓换成用户主体。只有单图时，背面复用同一图案，不能声称实现了两幅不同图形的切换。

图片无法唯一确定真实尺寸、隐藏面或曲率。用户给的尺寸、背面和工艺优先；缺失项标为设计假设。适合清晰标志、字标、线稿和剪影。

缺内容图时停在 intake，用文字索取图片。这是宿主硬门 `input_gap`，不另做上传弹窗，也不把图片放进偏好默认值。

未点名款式时，由宿主 `waiting_choice` 使用本入口 `choices_example`。用户已经说「四种都做」或点名某一款时直接执行，不再询问款式。只修订一个已有分支时保留原输入和参数，用 `--update` 与对应 `--forms`，不重做其他合格模型。更换图片或宽度时新建输出目录。

识别到「可打印」但没有打印机或喷嘴时，只交付带限制的数字基线，不承诺免支撑。用户要求机型适配、最小壁厚或分件配合时，先收集会改变结果的事实。

## 与已有能力的边界

- 轮廓追踪、四种实体、融合 STL 的零面积碎片清理留在本包 `scripts/logo_forms.py`。通用毫米导出在 [print-export](../.dependency-print-export/REFERENCE.md)，它不包含这次序列化碎片清理，所以不改由它写这批 STL。
- 回读闭合由辅助器检查。通用拓扑测量在 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md)，本入口不复制那套测量核心。
- 均匀密度重心是否落入底座低点凸包，由 `scripts/deliver_forms.py` 按本生成器的底座记录计算，并标明是假设。通用支承计算在 [support-check](../.dependency-support-check/REFERENCE.md)，不把这次凸包结果写成实物抗推倒。
- 放样、波浪和弧形竖片的相位留在本品类配方。[shape-build](../.dependency-shape-build/REFERENCE.md) 的通用放样、回转和管道不包含这些标志款式。
- 这不是浮雕高度场，不交接 [relief-map](../.dependency-relief-map/REFERENCE.md)。也不是激光分层切割，不交接 [layered-laser-ornament](../layered-laser-ornament/SKILL.md)。
- 预览使用固定正交方位 -45°、仰角 35.264°，并从回读后的 GLB 渲染。该机位不改用 [model-preview](../.dependency-model-preview/REFERENCE.md) 的头部或产品镜头。
- 后台 Blender 进程由 [run-tools](../.dependency-run-tools/references/budget-run.md) 的 `process_run.run_budgeted` 启动。场景读写的通用约定见 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。本渲染脚本自带样例灯光，并把 Cycles 设为 CPU；这是该辅助器的已测路径，不是其他生产渲染可以静默改走 CPU 的理由。建议低档 120 秒、中档 600 秒、高档 1800 秒。低档可直接跑；中高档先由宿主确认。超时记 `interrupted`，不写半截 BLEND。

## 四个款式

编号沿用辅助器：3 分层标牌，4 轮廓封底曲面落地，5 波浪镜像围合，7 弧形竖片。它们是可选构造，不是每张图都必须四套全做。

分层标牌保留孔洞和线条，用外扩层、颜色层和浮起笔画形成前后层级。离散点、星标和文字必须与背板相交。可以给背板封底，不能抹掉前景字符里的留白。

轮廓落地先得到承托用的闭合外轮廓，再在倾斜前盖与 XY 落地盖之间做对应轮廓的连续放样。落地盖要有面积，不是一点接触。离散字标需要外扩连接时，说明这是设计的背板，不是原图的唯一答案。

波浪围合先做出真实前后凹凸，再按中面对称。样例是有厚度的前后皮、侧边和底边，上口开放。封闭版本要另估桥接、支撑和分件。

弧形竖片按真实片宽切开，笔画在竖片前缘上。竖片、后脊、横梁和底座用同一弧形映射。必须留下片间空隙，不能用一整块图板假装竖片。

## 执行

```text
"$PYTHON" "$SKILL_DIR/scripts/logo_forms.py" --input <内容图> --output <新的任务输出目录> --width 144 --forms 3 4 5 7
"$BLENDER" --background --python "$SKILL_DIR/scripts/render_forms.py" -- --directory <任务输出目录>
"$PYTHON" "$SKILL_DIR/scripts/deliver_forms.py" --directory <任务输出目录>
```

可能长时间占用 CPU 的构造和 Blender 渲染，用物化后的 `run_budgeted` 包住那一次进程，到点停止。只修订一款时，生成器加 `--update --forms 4`，渲染器加 `--forms 4`。可编辑工程里四款共用同一取景并重叠，保存时只显示本次 `--forms` 中编号最小的一款，其余集合保留在文件中但隐藏，可在 Blender 里手动切换。

工程使用米。节点写入 `sparc3dPhysicalUnits={version:1,unit:"meter"}`，GLB 导出保留 extras。STL 数值是毫米，并说明打印朝向。颜色分区不等于装配榫、独立拆件或多色切片计划。

辅助器按纯色或透明背景、浅色主体和绿色点缀测试过。复杂图像不能直接套这套分色。

## 验收与交付

核对字形、孔洞、点状细节和颜色语义。低分辨率轮廓要说明误差。各部件闭合且体积为正；融合 STL 是单一连通体，没有浮岛。第 4 类检查落地盖面积和与底座的相交；第 5 类核对空腔、镜像和壁厚；第 7 类核对每片与连接结构相连。

选定款式都保存同一轴测方向、同一灯光和同一比例的 PNG。模型可以按包围盒居中，不能为每款改一个最有利的角度。第 4 类补侧视，第 5 类补顶视，第 3 类和第 7 类补正视。必须看过实际 PNG。

交付独立轴测 PNG、总览图、毫米 STL、可编辑工程，以及 `hi3d-logo-forms.json` 与 `hi3d-logo-verification.json`。用户只要预览时可以缩小范围，但不能把没生成的制造文件写成已完成。

GLB 回读通过后，宿主若提供 `workspace_commit_model`，按 Runtime 约定登记并写「产物：<实际 GLB 文件名>」。没有该工具时交付真实文件，并标明未登记。不猜测序号。

数字闭合、切片、试打和强度是不同结论。未切片就直说还要按机型和材料确认工艺。构造失败时保留输入、诊断和已完成分支，只修失败的分支。

## 非私有测试例

一张纯色背景、带几个不相连字母和一个绿色点缀的标志，要求比较四种桌面或标牌效果并保留配色。预期不再重复询问是否做四款，并得到四张同方向轴测 PNG、四个 GLB 和四个毫米 STL。STL 为单一闭合体，点缀与承托体相连。第 4 类侧视能看到从顺形前盖放到 XY 平面的落地结构。样例图不是以后必须使用的图案。

<!-- managed-by: sparc3d-runtime -->
