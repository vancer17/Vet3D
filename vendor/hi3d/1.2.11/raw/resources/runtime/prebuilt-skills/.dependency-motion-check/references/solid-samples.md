# 完整实体姿态采样

`solid_samples.sample_solids(solids, samples, pairs, *, tolerance, inclusive=False, aabb_epsilon=None, absolute_volume=False)` 接收毫米制 Manifold 实体字典、按序样本、明确对象对和有限非负体积公差。每个样本为 `{value, poses:{id:matrix}}`，必须覆盖全部实体；静止对象也给单位矩阵。matrix 为有限 proper rigid 4×4 列向量矩阵；不接受缩放、反射或投影。共享 `pose_math.is_rigid` 校验，`axis_pose` 可构造绕轴并沿轴平移的姿态。

输入对象对不可自配、重复或引用不存在的 ID；可以为空以仅测姿态包围盒。samples 必须非空；value 原样返回，由调用方表示距离、角度或 progress。核心不修改原实体，不执行文件/场景写入，不加载 Blender。物化后可直接 `from solid_samples import sample_solids`，依赖 NumPy、manifold3d 和同包 pose_math。

每个样本对所有实体调用 Manifold transform，再按显式 pairs 执行完整实体交集。`intersection_volume(a,b, *, aabb_epsilon=None, absolute_volume=False)` 可单独调用，检查输入/交集状态和体积有限性；布尔异常不能计作零碰撞。默认不做 AABB 提前排除，包含关系会被实际测量；指定 epsilon 时仅在三轴重叠均大于 epsilon 后执行布尔。该近似属于调用方策略，不能与无快速排除的结果混淆。

返回 `{samples,max_overlap_mm3,first_collision}`；每行包含 value、pair_checks、max_overlap_mm3、全部 collisions、bounds_mm 和 dimensions_mm。碰撞项为 `{a,b,volume_mm3}`，first_collision 另带样本零基索引 sample 和 value。按样本/对象对的输入顺序取首次；最大体积从零开始累计。默认 `volume > tolerance` 判碰撞，inclusive=True 使用 `>=`；absolute_volume=True 才取 abs。所有实体坐标必须按毫米提供才能使用报告的 mm/mm³ 标签。

原一般装配 profile 保留 AABB epsilon=1e-6、非 abs 体积、静态 `<.01` 才通过及路径/运动 `>.01` 才碰撞的差异；端点脱离 AABB 仍在路径适配。螺旋适配显式选择全部对象对、不启用 AABB 排除、abs 体积和严格大于调用方公差；progress、螺旋运动与原报告字段留在调用方。只共享测量，不合并互锁/轨道/止挡/保持结论。

验收覆盖两件同时移动、完整包含、临界公差两种等号策略、非法矩阵、布尔错误/非有限体积和全部样本范围。离散样本不能证明连续无碰撞、柔性接触、强度或实物可玩性。现有实体检验入口每次直接测量，没有可跳过该测量的阶段缓存。
