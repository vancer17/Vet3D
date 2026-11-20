---
name: head-lowpoly
description: 将高模人头 GLB 制作成独立 lowpoly，输出 albedo、normalmap、基础骨骼绑定和 blendshape；推荐光头输入，也支持带头发的人头。用于已有高模的人头低模化和表情交付。
---

# 高模 GLB → lowpoly、贴图与表情

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 head-lowpoly 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


**推荐输入光头人头 GLB；包含头发也可以使用。** 优先使用中性表情、眼口可见的完整人头。发型遮挡眼睑、嘴角或耳朵时先分离遮挡物并明确可见皮肤，不能把头发当作皮肤去修补。独立头发网格可保留 UV/材质、按预算减面并绑定到头骨；与皮肤融合的雕塑头发作为外表面一起处理。毛发曲线、粒子和 strand groom 先转成明确的网格资产。

| 输入 | 输出 |
| --- | --- |
| 已有高模人头 `.glb` | `Lowpoly_Rigged.glb`：低模、UV、嵌入贴图、骨骼蒙皮和命名 blendshape |
| 同一高模的原材质与纹理 | `textures/Lowpoly_BaseColor.png`：albedo / sRGB；`textures/Lowpoly_Normal.png`：OpenGL +Y tangent normal / 16-bit PNG |
| 执行者根据本输入确认的眼口位置与局部参数 | `Heads_Rigged.blend`：可编辑四边形低模、贴图、骨骼和形态键；`lowpoly_data.npz`：有序拓扑及表情位移 |

本工作流只负责高模到低模，**不执行 GNM 或 MetaHuman 注册**。其他注册 skill 可显式接收本流程产物。低模拓扑来自输入高模，烘焙始终使用完整高模，不依赖参数化人头模板。

接入完整人物时，身体新绑定推荐显式提供独立 `rig-retarget` 与 `mdf-call`，按前者的 `references/service-rig.md` 经 HTTP 调用 auto-rig、回迁高模并检查手指拉伸。交接头部/身体工程、骨架及保留项；本工作流的六骨面部绑定和 blendshape 继续保留，不用全身自动绑定替换。仅制作人头时无需这两个依赖。

## 执行

1. 按需读取 [输入与配置](references/inputs.md)。检查高模正面、侧面、眼口结构、材质、对象和坐标；用户只需提供高模，执行者负责在任务目录生成本输入的 `face_config`，或校验并复用已有配置。配置绑定输入 SHA256，不能套用另一张脸的坐标。
2. 显式配置 Blender、Instant Meshes 和输出目录，运行 `python <skill>/scripts/run.py <task>/config.json --check`，通过后去掉 `--check` 执行。依赖已存在时直接复用；不自动生成高模、下载模型或读取凭据。
3. 默认保留必要的三视图、关键表情和线框审核；连续展示视频和中间诊断图按需开启。先完成 remesh、眼口环线、基础绑定和表情检查，再烘焙、导出与回读 GLB。实际面数以报告为准，Instant Meshes pure-quad 输出可能高于请求值。
4. 查看 `REVIEW.md`、同机位对比、眼睑/唇角及贴图接缝。`CONFORMAL` UV 是默认速度优先方案；若重要区域拉伸影响细节，可改 `uv_method: "ANGLE_BASED"`。不通过减少必要表情检查、放宽穿插阈值或从减密副本烘焙来提速。实现与取舍见 [优化、恢复与验收](references/implementation.md)。
5. 局部调参后在原输出目录重跑，自动验证并复用未受影响的阶段；例如修改贴图尺寸不重做减面、绑定和几何检查。`--fresh` 会重建该目录的生成物，原始输入不得与输出文件重名。

## 完成与耗时

交付 GLB、Blender 工程、albedo、normalmap、表情 NPZ、审核图与报告。六骨基础绑定和当前命名形态键不等于 ARKit 52 或完整口腔制作；隐藏眼球/口腔采用的先验及头发简化范围要如实说明。GLB 已三角化并可能因 UV/法线接缝拆点，四边形编辑稿保存在 Blender 中。

`run.py` 自动记录每阶段及每次尝试的任务标识、状态、带时区起止时间和单调时钟耗时。`timings.jsonl` 追加历史，`timing_summary.json` 汇总本次墙钟区间，`workflow.json` 保存内容缓存。失败、中断和跳过也记录；缓存命中的耗时仅是本次校验成本，不冒充完整处理时间。配置测量/标注和依赖安装不在自动运行计时内，发生时另记实际时间与范围；不估算 token。运行统计留在任务产物目录，不写回 skill 仓库。

本地阶段记录、内容校验或子进程操作按 [run-tools 契约](../.dependency-run-tools/references/local-runtime.md) 复用；本工作流保留阶段图、输出格式和失效策略。

本地高模到 UV 烘焙执行复用 [texture-bake](../.dependency-texture-bake/REFERENCE.md)；源材质解释、目标区域和后续绑定/融合由本工作流保留。

Runtime 下 `retopology_backend=runtime`（desktop 分发默认）从 working_surface.glb 生成公开重拓扑交接，缺结果返回 waiting_retopology/退出码 3；读取 [远程四边面契约](references/retopology-api.md)。独立包默认 `retopology_backend=instant_meshes` 并要求原 instant_meshes 路径。所有模式保留完整高模烘焙与共享源码缓存。

<!-- managed-by: sparc3d-runtime -->
