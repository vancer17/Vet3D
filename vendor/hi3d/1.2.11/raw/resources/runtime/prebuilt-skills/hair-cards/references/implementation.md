# 代码与原子能力

包内只保留一份带状网格实现；入口按预检、读取、计算、创建与保存组合它。依赖显式传入，不访问相邻 skill、全局 RNG 或工作目录中的隐式资源。所有脚本导入不触发场景读写。

## `scripts/hair_card_core.py`

| 函数 | 输入、输出与副作用 |
| --- | --- |
| `resample_path(points, count)` | XYZ 路径与采样数 → 等弧长 Vector 列表；纯计算，移除连续重复点，拒绝非有限或零长度路径 |
| `ribbon_frame(tangent, normal, previous)` | 单位切线、表面法线与上一横向 → 横向与朝外偏移法线；纯计算，退化时选择不平行轴，不把连续性翻转误用于朝内偏移 |
| `transport_frames(path, root_normal)` | 已重采样路径、初始法线 → 各行横向与法向；纯计算，沿相邻切线做最小旋转，拒绝切线退化及近反向，不查询局部表面 |
| `build_card_geometry(paths, spec, atlas_columns, clearance, nearest_surface, seed, placement='head_surface')` | 已校验配置、世界坐标路径与模式 → vertices/faces/uvs/card_ids/card_count；局部 RNG 决定每束宽度，按截面角度生成实际发片，不操作场景 |
| `surface_query(surface, depsgraph)` | Blender 网格 → 最近表面查询闭包；快照评估几何及世界矩阵，finally 释放临时 Mesh，无可查询面或法线时失败 |
| `create_card_object(bpy, name, geometry, material, collection, uv_name)` | 将数组写入新 Mesh/Object，设置平滑、UV、面属性与来源标记；失败清理创建资源；调用者负责对象生命周期 |

每条路径按长度重采样；这不包含曲线去噪。`guides` 用 `root_normal` 初始化截面，再平行传输；交叉片绕同一偏移中心线旋转，拥有独立 card_id。`head_surface` 保留切线与逐点最近法线定向及顶点接触外推，旧配置不改变输出。该兼容模式不适合以细碎雕刻头发表面约束发片。

宽度变化为每束固定的 `[0.8,1.17]` 随机因子，长度因子为 `(.45 + .55*min(1,9*t))*(1-.76*t^3)`；不是逐点随机。浅弧峰值为宽度的 0.11 倍，`guides` 同时乘长度因子，使弧高随宽度收窄；兼容模式保留旧弧高。偏移因子为 `sin(pi*min(1,2*t))`，后半段无额外抬升。以上只是基础形状函数，不自动生成自然弯曲、完美尖端或包络内收。

UV 逐片分配等宽图集列并按根→梢递增。原子计算要求合法 spec，可先调用 `validate_config`；`head_surface` 的 `nearest_surface(Vector)` 必须返回位置与单位法线，`guides` 可传 None 且不会调用该回调。算出的数组可直接供其他 Blender 编排器使用，不必执行 CLI。表面外推与几何检查的边界见 [输入契约](pipeline.md)。

## `scripts/rebuild_from_scene.py`

| 函数 | 契约 |
| --- | --- |
| `validate_config(config)` | 检查完整 JSON 结构、有限数值、正整数、列号与名称冲突，无文件/场景副作用，返回原配置 |
| `read_curve_paths(obj)` | 基础开放曲线 → 世界坐标路径；Bezier 先采样，不读取求值后的子发丝，不修改输入 |
| `prepare_scene(bpy, config)` | 当前 scene 与配置 → 可选头部、材质、路径缓存、现有输出集合；只读，提前拒绝输入/输出混用及共享对象冲突 |
| `run_rebuild(bpy, config, output, overwrite=False)` | 校验后计算所有候选数组，再创建新对象、替换点名输出，隐藏源引导渲染，保存独立候选及 `.rebuild.json`；返回产物与几何计数 |
| `main(argv=None)` | CLI 参数解析、JSON 读取、调用与结果输出；导入本模块不会运行它 |

在 Blender 中把独立包的 `scripts` 加入模块搜索路径即可显式导入这些函数。`run_rebuild` 要求输入工程已保存；`output` 必须是包外现有目录中的独立 `.blend`。既有文件默认拒绝覆盖；输入文件始终保护。预检/几何计算失败不替换旧对象，创建失败清理本批新对象；保存/报告失败后内存候选可能已变，重新加载输入后重试。阶段时间由执行者按 [统计契约](timing.md) 记录，报告没有伪装成自动计时。

## 可复用验证

普通 Python 执行 `tests/test_config.py` 检查两种模式配置。Blender 执行 `tests/test_blender.py`，以临时场景检查无头模交叉片、截面连续性与独立 ID，以及原有曲线类型、世界空间、UV、修改引导重建和失败保护。测试产物写系统临时目录，不写回 skill；测试尺寸与名称不是业务默认值。

独立迁移验证时按入口打包约定在仓库外物化完整分发目录、从不相关工作目录运行入口；带 `--python-exit-code 1`，再重开候选检查数据。实际视觉验收另行完成，脚本测试不证明某个发型达到目标美术质量。


## 执行范围与编排边界

参考就绪门槛、稀疏参考拟合、顶部覆盖修正及发丝材质诊断由执行者按 [参考交接](reference-model.md)、[建模决策](modeling.md) 执行；本模块不自动进行这些步骤。GLB 材质通道与目标视窗检查按 [导出回读](pipeline.md#重建与导出回读) 单独完成。补充这些业务约束不改变现有函数、配置字段、采样或宽度算法，也不暗示已有自动图集生成、GLB 导出或阶段调度器。
