# 固定拓扑耳部注册

适用：已有整头注册，目标是同一坐标系中的带法线高模采样，并有来源绑定的左右耳三维点。输入轴约定 X 水平、Y 深度、Z 向上。先完成头部相似对齐；本能力不检测关键点、不选择图像、不调用服务，不承担整个头部的初始化。

`ear_fit.initialize(original, face, records, regions, target_vertices, target_normals, protected_indices)` 返回初始顶点、左右耳标签、目标点池、保护区和初始化诊断。`original` 含 `vertices/rest/quads`；`face` 是待保留的已注册脸；`records` 每项含固定 `id/ear/triangle/barycentric`、目标 `target` 和正 `weight`。`regions.ear_regions` 顺序必须为 right、left，各含 core_indices。所有索引零基，拓扑不得重排，数组在一个世界坐标系中。每侧至少四个非共线点，X/Z 投影不可退化；异常数据、重叠耳区和不足采样停止。此接口验证数值与索引，文件来源、模板哈希、映射一致性由调用方校验。

初始化按目标点而非旧模板大小确定耳朵搜索域：鲁棒加权仿射六轮，弱单位变换先验抑制近共面深度病态，奇异值限制在 0.5–2。以原模板 rest 的耳形为先验变形；耳根向外 18 拓扑环做双调和过渡，保护眼唇点及两环邻域。源耳点池使用 X/Z 凸包和深度范围约束，避免最近邻直接吸到侧脸。依赖 [brush.py](../scripts/brush.py) 的邻接/法线、[surface.py](../scripts/surface.py) 的采样平滑，不另建通用网格算子。

`ear_fit.deform(data)` 返回候选顶点和 landmark RMS/迭代诊断。每侧使用 0.04、0.025 倍高模最大轴范围的网格间距，每层 24 轮。点对点/点到面、反向覆盖与关键点项共同求解一个连续三线性体积位移场；耳的前后两层共用控制点，边界控制严格为零。法线不相容、过远最近邻不参与。单步位移上限 0.0025 倍范围，保守 Lipschitz 上界限制为 0.25；检查保护邻域未动。这里的上界约束连续位移场，不是最终离散三角网格无穿越证明。

`ear_guard.guard_ears(rest, baseline, initial, candidate, quads, ear_indices, protected_indices)` 在 Blender Python 中调用；输出验收后的顶点和报告。复用 mesh-audit 的三角化/穿越定义和 contact_repair 的有界修复。初值不能新增穿越；候选先尝试 1e-4 倍范围、最多 120 次的小接触修复，否则按 0.05 步长回退体积位移。保护点变化、耳区新穿越、相对输入新增穿越、非有限或退化三角形均拒绝。修复不保证所有输入都能接受；失败保留输入，由调用方保留候选和日志，不自动换参数重试。

报告分别列出 `new_crossings_vs_template`、`new_crossings_vs_baseline`、`ear_crossings`、`eye_lip_anchor_max_displacement`、`ear_geometry_passed`、`whole_geometry_passed`。整头旧眼唇接触可使 whole 失败，即使 ear 通过；不得合并成“全部几何通过”。穿越判定不包括共面/相切、共享顶点接触的全部语义。距离和关键点误差下降也不证明耳轮厚度、耳甲腔和耳垂形态符合人物，需要同相机对照后单独验收。

拓扑/UV 与文件持久化属于调用方。native 坐标使用 [registered_geometry.py](../scripts/registered_geometry.py) 的逆变换接口重建；不得把变化后的世界顶点与旧 native_vertices 一起作为已接受结果交付。
