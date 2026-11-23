---
name: metahuman-fit
description: "Turn a portrait or rendered head GLB into a frontal, neutral-expression bald color reference, generate Hi3D quality geometry and textures, register MetaHuman topology with the bundled 3D Gaussian brush, and bake albedo/normal after bounded local corrections. Deliver static MetaHuman geometry, the original high mesh and topology/wireframe views. Includes a Taro template, matching atlases and frozen ear landmarks for optional multiview ear fitting; requires source-bound target annotations. DNA and rigging are optional extensions."
---

# MetaHuman Fit

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 metahuman-fit 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


默认流程：**原图（输入人头 GLB 时先渲染成参考图）→ 正面、无表情、带真实肤色纹理的光头图（无眼镜/胡须/假睫毛，去掉颈部以下）→ Hi3D quality 几何与纹理 → 以该 quality 高模为目标做 3D brush 注册 → 有限局部微调 → Blender 本地 bake 纹理与法线 → MetaHuman 几何资产、高模与拓扑/布线展示**。保留身份、脸型和自然不对称；默认交付静态几何资产，不执行绑定、DNA 导出、头发制作或动画。同一次任务已验收的中间产物可从对应阶段恢复；用户新传入的人头 GLB 默认先渲染＋图生图，不因已有几何跳过图像预处理或 quality。quality 返回的同一份带纹理高模贯穿注册、微调对照和烘焙，不额外调用 texture、texture-bake、四视图上色或 UV 服务；生成后贴图问题仅在本地修补，无法解决时记录缺陷，不自动转服务补色。

已有带发高模且只需要面部 donor/鼻修复前注册时，交接独立 [face-fit](../.dependency-face-fit/REFERENCE.md)，保留原高模，不启动本 workflow 的光头生成。全头模板交付继续使用下述默认流程和自己的 fit 适配；两者共用底层 surface-fit，局部 donor 不冒充全头拟合结果。

## 执行与停止规则

- 按阶段只读对应参考章节，使用已有脚本和配置；不先通读源码、全部参考或历史日志。正常运行只取状态、产物路径和阶段摘要，失败才读取该阶段日志尾部与相关函数。
- 图像默认一次编辑、一次集中验收；成功出图且有明确缺陷时按已有授权修相应图，无需逐轮确认；仅图像调用失败时停止自动重试并报告，用户明确要求后才恢复。注册默认一套粗到细 brush；结束后统一列出可定位的问题，默认最多两轮局部修订，每轮先写区域、缺陷、预期改善与保护项。通过即冻结，不因“还可以更精致”再试参数、生成候选或重做上游。
- 使用同一组相机和同口径误差比较；只接受修正目标缺陷且未破坏身份、拓扑或几何检查的改动，否则回退。两轮后仍有硬性缺陷，保留最佳候选、明确失败项和所需输入；不无限迭代，也不降低验收标准。单次优化器内部迭代不计作人工修订轮数。
- 任务 ID、配置、哈希与阶段结果保存到任务目录；恢复复用原任务与有效缓存。pending 不重提。修改颜色不重做几何；修改局部几何只重跑受影响检查、bake 和展示。

## 阶段

1. **正面无表情彩图**：输入为人头 GLB 时，先在 Blender 导入并检查朝向、材质和头部范围，保留原文件；渲染完整头、耳和颈部的正面参考图，必要时补侧面/斜面辅助身份，不以线框或法线图作为生图输入。然后与图片输入一样，用宿主 imagegen，先查看输入或实际渲染，按 [彩色参考提示词](references/color-reference-prompt.md) 输出一张独立图片。转成严格正面、头部无倾斜、肌肉放松的 neutral 表情，嘴唇自然轻合、双眼自然睁开直视。移除头发、眼镜、胡须/胡茬、假睫毛与饰品；保留人物身份、自然肤色、眼睛和皮肤纹理，不转灰模材质。完整保留头、耳、下巴、下颌和颈部，去掉肩胸、衣服、底座；不可见结构注明推定。
2. **quality 带纹理高模**：读 [默认调用](references/head-workflow.md#quality-与注册交接)，使用 `image_pipeline.py` 的彩图 `image` 入口，生成几何与纹理。导入检查皮肤对象、neutral、坐标、实际面数与贴图；原 Hi3D GLB 原样留存。采样/平滑只用于拟合副本。
3. **3D 注册**：按 [输入与运行契约](references/inputs.md) 默认使用 [随包 Taro 模板与贴图](references/bundled-template.md)，无需索要用户路径；也可显式指定自定义模板。优先复用 [Sapiens2 眼唇映射](references/sapiens2-landmarks.md)，通过 mdf-call 调用 Sapiens2 pose 检测新高模的正面彩图，再用 `project_sapiens2_landmarks.py` 按真实渲染相机反投影，准备来源哈希绑定的 3D landmarks 与 mask；仅有源 DNA 时可一次提取模板，这不等于输出 DNA 或执行绑定；缺标注时才读 [标注契约](references/annotations.md)。运行本包 `scripts/fit.py` → `scripts/brush.py:fit_brush`，基于用户指定 head-geometry-repair worker，使用分组权重与鲁棒残差扩展，映射见 [默认调用](references/head-workflow.md#brush-实现与阶段控制)。默认使用 36 个眼部点和 32 个嘴唇点，模板侧索引一次校准后复用；鼻子仅作审核后的可选辅助，轮廓由高模表面与侧视图约束。Sim(3) 对齐后，从高模采样带法线的表面点（默认约 10 万），每轮寻找法线相容近邻，以 40% 点间位移与 60% 法线方向距离修正结合眼唇拉力，做粗到细 Gaussian 位移场；左眼、右眼、嘴唇分别归一化总权重，过大非刚性残差降权。保留模板顶点顺序、四边形与 UV。不能用通用重拓扑替代注册。当前实现不含多视角法线图损失，不能把表面法线相容性描述成多视角法线拟合。
4. **局部微调与冻结**：先以真实对照图判断缺陷；有明确输入与保护项的局部操作可直接用已有确定性算子，不要求 agent 逐点介入。自动 refine/交叉修复只表示完成计算，仍需区分几何检查与外观验收。用可复现脚本落实选定区域、方向、幅度与衰减，记录编辑前后网格和同相机对比；没有证据支持的区域不动。先检查同相机正面、侧面、斜侧面的轮廓及眼睑、鼻、唇、下巴/腮部，再按修订预算处理实际缺陷。优先复用 brush 的空间平滑、mobility、位移上限与翻面回退；耳根/颈部使用现有局部算子。默认模板耳刚性恢复核心及窄根带；耳朵大小或外展不匹配时按 [耳部多视角注册](references/ear-registration.md) 读取固定模板索引，对目标多视角反投影后联合拟合耳与耳根，眼唇保持不动；颈部截断修补不得覆盖下巴、颏下、下颌角保护区。眼口内部不吸附外皮；禁止统一缩脸或用法线掩盖体积错误。细皱纹留给 bake。
5. **本地 bake**：几何冻结后，按 [颜色与交付](references/head-workflow.md#颜色与-bake) 调用本地 Blender `review.py -- <config> bake`，将同一 quality 高模已有颜色及几何细节烘焙到微调后的 MetaHuman UV。颜色取自高模原贴图，法线由原始高模几何烘焙；不得用拟合采样或平滑副本替代高模。这里的 bake 是本地计算，不是远端服务。眼口内部保留匹配模板贴图；只有已提供独立眼球/牙齿静态资产时才装配，不为静态头皮交付运行 DNA 分支。检查覆盖空洞、UV 接缝、眼唇、下巴和耳颈；未观测区域补色注明来源。
6. **交付**：返回保留 MetaHuman 模板拓扑/UV 的 OBJ/NPZ、带 albedo/normal 的静态 GLB/Blender、原 Hi3D 高模，以及真实模型的灰模几何对照、四边拓扑和眼口鼻局部布线展示。灰模仅用于最终几何检查渲染，不用于输入图生成。具体清单见 [交付验收](references/head-workflow.md#交付验收)。

几何验收要求坐标有限、无退化和新增交叉、模板拓扑/UV 不变，同时通过身份与眼口视觉检查。默认不配置 `dna`、`expression_presets` 或 RigLogic；从旧配置继续时显式省略这些可选分支，不能因旧文件存在而误运行或交付。仅用户后续明确请求时才按 [实现与验收](references/implementation.md) 做绑定数据迁移、DNA 导出和表情验证；静态资产不声称已绑定或可驱动。

## 依赖、可选入口与统计

图像编辑用宿主 imagegen；生成需独立安装完整 `hi3d-api` 并显式给 CLI 路径。默认 Sapiens2 pose 检测需独立 `mdf-call` CLI 和可达的目标服务，契约见 [眼唇映射](references/sapiens2-landmarks.md)；不需要额外 texture/bake 服务或其调用契约。注册需 Python、NumPy、SciPy、Pillow、Blender；颜色融合需 OpenCV；随包 Taro 模板及皮肤/眼睛/口腔 atlas 可直接使用，不需要 DNA 运行库；从 DNA 提取模板或显式 DNA 扩展才需要匹配运行库（当前写入器仅 legacy DHI）。模板来源、许可与索引见 [随包资源](references/bundled-template.md)；不隐式导入相邻 skill；已具产物不受上游缺失阻断。维护不调用收费服务，不读取真实密钥。

只有明确要求独立头发时读 [双参考扩展](references/separated-pipeline.md)；彩图生成/已有高模入口读 [图像与高模管线](references/image-pipeline.md)。非 MetaHuman 身体通用绑定按独立 `rig-retarget` 的 `references/service-rig.md` 与 `mdf-call` 处理，不替代本流程的 DNA。

业务阶段 image、quality、annotations、fit、refine、bake、showcase、delivery 记录任务/尝试 ID、状态、带时区起止及单调耗时到任务目录 `timings.jsonl`，失败/中断/重试追加，未执行记 skipped；缺失时间记原因，不填 0。脚本已有统计直接复用，图像和展示等人工编排阶段由执行者补记。总墙钟按起止计算，父子和并行阶段不重复求和，服务/等待时间分开；usage 可用才记录 token 与来源，不用字符数估算实测 token。交付阶段摘要，日志和用户资产不写回 skill 包。

基线几何验收与可选修复的交接见 [检查契约](references/geometry-comparison.md)。

本地阶段记录、内容校验或子进程操作按 [run-tools 契约](../.dependency-run-tools/references/local-runtime.md) 复用；本工作流保留阶段图、输出格式和失效策略。

本地高模到 UV 烘焙执行复用 [texture-bake](../.dependency-texture-bake/REFERENCE.md)；源材质解释、目标区域和后续绑定/融合由本工作流保留。

检查图格位复用物化的 [image-sheet](../.dependency-image-sheet/REFERENCE.md)，静态导出容器读取复用 [glb-clips](../.dependency-glb-clips/references/contract.md)；业务标题/排序、模型验收与回读保持在本工作流，布局与缓存交接见 [实现与验收](references/implementation.md)。

可选耳部阶段的配置、缓存、自动计时和整头/耳部独立验收见 [耳部多视角注册](references/ear-registration.md)。

Runtime 的高模输入、分体生成/贴色计划与公开 pose 转接见 [宿主交接](references/runtime-handoff.md)。公共 image→生成与内部贴色流程仍保留在普通分发。

<!-- managed-by: sparc3d-runtime -->
