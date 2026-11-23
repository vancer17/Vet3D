# 优化、恢复与验收

## 执行与原子职责

流程为 prepare → working_surface → remesh → facial_topology → lowpoly_rig → lowpoly_validate → bake → deliver → metrics → review → package_review。先验证低模变形，再烘焙、导出并回读交付 GLB；本流程不含参数化人头注册。

| 模块 | 主要契约 |
| --- | --- |
| run.py | `preflight` 解析配置、检查路径/参数与输入哈希；`stages` 声明依赖、配置键和产物；`stage_fingerprint` 计算局部内容指纹；`run_stage` 执行/清理子进程；`workflow` 记录计时、缓存和恢复状态。 |
| blender_io.py | `load_source` 经共享 head_io/scene_io 选择一个头部与显式头发网格，保留世界变换后应用变换；`coordinates` 批量读取顶点；`make_mesh`、`material`、`studio`、`render_view` 经 [model-preview 的 head_preview](../../.dependency-model-preview/references/head-preview.md) 创建网格/UV 和固定相机审阅。 |
| prepare.py | `prepare` 导入高模、检查尺度/有限性、面积采样并保存源工程；`open_boundary` 焊接完全重合位置后识别开放边界。 |
| retopology.py | `working_surface` 仅对 remesher 副本焊点/减密；`ordered_cut` 验证唯一眼口边界；`build_patch` 创建高模投影环；`create_controls` 计算局部位移；`facial_topology` 建立拓扑、UV 与头/颈/颌权重。 |
| collision.py | `crossing_pairs` 用 BVH 宽阶段再做严格三角形内部交叉判定，排除共享顶点和宽阶段误报；`triangle_stats` 检查有限性及退化。 |
| low_rig.py | `repair_shapes` 在位移预算内修正中性、端点与插值形态；`build_rig`/`bind` 建立基础六骨 LBS；`add_eyes_and_cavity` 保留扫描可见眼面并补基础后衬/口腔；`attach_hair` 简化显式头发附件并绑定到 Head。 |
| bake.py | `bake` 从完整原高模烘焙 albedo、OpenGL +Y tangent normal 及有变化的 PBR 标量通道，保留/恢复原材质连接并保存打包贴图。仅适配已检查的 Principled 材质。 |
| deliver.py | `deliver` 保存可编辑工程并仅导出低模对象与骨架；`inspect_glb` 检查嵌入资源、UV、蒙皮、albedo/normal 材质和命名 morph 列表。 |
| validate.py | `evaluate` 读取实际依赖图求值并清理临时网格；`inspect_states` 检查中性、插值/组合形态、权重及交叉；`validate` 重开工程并输出检查结果。 |
| metrics.py | `run` 计算原高模与低模的采样表面距离；`glb_roundtrip` 在新场景回读 GLB，将 UV 接缝拆点映射到中性低模，检查中性及全部形态键端点的坐标误差。 |
| review.py | `select_variant` 切换高模/低模及各自头发；`render_review` 固定同一相机渲染三视图、关键表情、真实线框及可选连续帧，不修改交付工程。 |
| package_review.py | `montage` 拼接同规格渲染；`package` 创建审核索引、对比图及可选视频，发布由用户当前授权决定。 |
| test_core.py / test_hair.py | 离线验证缓存恢复/失效、中断计时和交叉分类；Blender 合成网格夹具验证显式头发的变换、UV、减面与头骨绑定，不代替真实发型视觉验收。 |

Blender 原子模块可直接调用：`blender -b --python-exit-code 1 --python <script.py> -- <config.json>`。retopology 在配置前加 working/facial；validate 在配置前加 low/final。普通 Python 执行 `run.py`、`package_review.py` 和 `test_core.py`。直接调用原子模块时由执行者记录对应阶段计时；不要把“可单独调用”当作无视输入依赖的许可。

## 提速策略

- 复用现有依赖和已验证配置，避免重复下载、导入服务或重新测量同一高模。原高模保持完整，只对 remesher 工作表面减密。
- 规则多边形面中心按 NumPy 批量计算；眼面 UV loop 索引用 Blender `foreach_get` 读取；全高模最小深度在眼部循环外只计算一次。
- 修复期间只复用位坐标完全相同状态的交叉判定；坐标一变就重新检测。独立的最终低模变形检查仍执行，未降低采样状态或穿插判定标准。
- 默认 CONFORMAL UV 以缩短展开耗时；ANGLE_BASED 可用于 UV 拉伸影响重要细节的输入。几何和表情不随 UV 方法变化；不同展开会改变 texel 密度，应检查重烘后的眼、嘴、耳及接缝。MINIMUM_STRETCH 不保证对所有人头更快或更好。
- BaseColor/albedo 与 Normal 始终烘焙。多个源材质的 Roughness/Metallic 若同值且无纹理驱动，直接将该值写入低模材质；否则正常烘焙，避免丢失真实变化。`bake_pbr_extras: all` 可强制生成常量贴图。
- 默认仅渲染最终必要审核图。诊断图和连续视频显式开启，视频时间独立列在 review/package_review 阶段，不混入“建模核心耗时”。
- 局部缓存按实际输入、配置、脚本、执行器、命令及依赖产物的 SHA256 验证。贴图尺寸变化只影响 bake 及下游，不重做拓扑/表情；预览尺寸变化只重做审阅与打包。产物缺失或被修改时重做所属阶段；如果恢复后的内容与旧产物相同，其他依赖仍可复用。

## 验收范围

检查实际头部/附件面数、四边形比例、眼口环线、UV/纹理接缝与保形程度。自动重拓扑不是手工动画布线；对遮挡和薄片头发先检查视觉与保留语义，不把所有发型视为同一种可简化几何。

低模检查包含中性、每形态键 0.25/0.5/0.75/1，闭眼额外 0.9/0.97，以及双闭眼、闭眼笑、张嘴笑组合。修补超过位移预算或仍有交叉时回到 patch 边界和局部场配置，不无限加平滑。严格交叉检查不覆盖切触、共面重叠及独立眼球/口腔/头发与头皮之间的碰撞；视觉检查仍必要。

`metrics.json` 的 GLB 回读检查容差为头部跨度的 2e-5，覆盖中性和全部命名形态键端点，并区分 GLB UV/法线接缝拆点与真实增面。表面距离报告 RMS/p95/max 和采样量；高模→低模排除明确重建的眼口 patch，不等于整头精确 Hausdorff 距离。几何检查通过也不代表完整生产口腔、任意组合表情或发型都已验收。

## 计时和恢复

每次尝试用单调时钟记录总墙钟区间及阶段耗时；阶段含子进程运行与等待，总时长不与子阶段重复相加。`bake_report.json` 的逐图时间包含在 bake 阶段内。阶段记录包含 task_id、attempt_id、带时区起止时间、状态和 elapsed_seconds；同目录恢复保留 task_id 并生成新的 attempt_id。

`timings.jsonl` 追加全部阶段历史，`timing_summary.json` 汇总当前尝试，`workflow.json` 保存阶段内容缓存及前一尝试关联。缓存跳过记录本次校验成本与 reused_attempt_id；失败/可捕获中断保留实际耗时，后续阶段标记未执行。强制终止导致精确结束时间不可得时，恢复记录保留 null 与原因，不伪造 0。

完整冷运行、缓存恢复、局部重烘的时间分别报告。对比优化前后时使用同一高模、相同面数/贴图规格与验收范围；若改变 UV 方法、视频或材质通道策略，单列差异。自动流水线不计入此前人工标注、首次依赖安装；这些步骤实际发生时另记范围。计时与具体运行报告只保存在仓库外的任务目录，不写入 skill 或 commit 正文。

烘焙公共执行与状态恢复见 [texture-bake 契约](../../.dependency-texture-bake/references/contract.md)。本地材质与区域适配参数、常量通道跳过及模板融合仍按本工作流配置；共享代码纳入 bake 阶段内容指纹。

三角检查的缓存依赖包含物化的 collision.py 与其 [mesh-audit 三角度量核心](../../.dependency-mesh-audit/references/mesh-measure.md) triangle_arrays.py；核心代码变化使相关几何阶段重新验证，未使用该核心的阶段仍按原指纹复用。head-lowpoly 的 low_rig/validate 间接调用方也纳入同一依赖。

package_review 的视频分支复用 [media-encode](../../.dependency-media-encode/references/sequence.md)，保留 8fps/JPEG/CRF20；成功写 expressions.video.json，相关编码与检查源码纳入 package 阶段指纹，无视频时不执行或依赖 ffmpeg。

图片画布、标签与缩放复用 [image-sheet](../../.dependency-image-sheet/references/contract.md)，本入口保留来源选择、字号、采样器、标签格式及业务验收/归档职责。

`deliver.inspect_glb` 的容器读取复用物化的 [glb-clips.read_glb](../../.dependency-glb-clips/references/contract.md)，仅解析，不执行动画合并；嵌入资源、骨骼/形态键名称顺序、UV 与材质判定仍留在此脚本。容器损坏或尾块截断会明确失败，不仅检查首段 JSON。deliver 阶段指纹包含 glb_clips.py；核心变化使导出与结构检查重跑，bake/prepare 等无此依赖的阶段保持复用，下游仍按实际产物内容判断。

## Runtime 阶段

working_surface 以 GLB 交接，remesh 前 prepare_handoff 写计划并校验原任务；暂停时 downstream 标 skipped。`mdf_handoff.request_plan/prepare_handoff/resolve_result/unpack_geometry` 负责指纹、HTTP/业务成功码、路径与哈希、唯一 OBJ 几何读取；`retopology.import_retopology` 验证单网格、有限坐标、输入尺度/轴向和非退化原生四边面，不配对三角面。源码、后端、返回账本与 OBJ 均参与重拓扑指纹；纹理尺寸只使 bake 下游失效。详细输入/恢复见 [远程重拓扑](retopology-api.md)。

`test_mdf_import.py` 在 Blender 的合成立方体上验证公开 OBJ ZIP 的坐标转换、原生四边面与三角面拒绝；test_mdf_handoff.py 验证等待/恢复、指纹、文件篡改与本地阶段缓存。均不调用线上服务。
