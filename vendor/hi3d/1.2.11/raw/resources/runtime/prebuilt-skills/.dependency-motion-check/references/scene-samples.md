# 显式姿态采样

[scene_samples.py](../scripts/scene_samples.py) 为 Blender 诊断提供 `sample_frames(scene,frames,inspect)`：逐一设定显式有限帧（含小数/负帧），更新依赖图，调用 inspect(frame)，返回其结果列表；成功/异常均恢复原 frame/subframe。callback 不应删除被检查对象或更换场景；采样不复制整个场景。

`world_mesh(obj,evaluated=True)` 返回世界坐标点、三角索引和 AABB；默认使用求值对象/变换，包括 modifier、shape key 和动画。evaluated=False 显式保留原网格 profile。临时 to_mesh 始终释放，不改变源几何/UV/材质/变换，输出只含几何诊断所需数据。坐标沿用场景单位。

[pose_math.py](../scripts/pose_math.py) 的 `axis_pose(center,axis,angle_rad,axial_travel=0)` 以 Rodrigues 计算任意轴的 proper rigid 4×4 列向量矩阵；弧度旋转后沿规范轴平移，单位由调用者决定，不限定螺距/旋向。原 `motion_check.rotation` 的 xyz/degree/pivot API 与 screw-bottle 的 mm/radian/lift API 均适配到此；不更换任一碰撞后端。

表面诊断交 [mesh-audit](../../.dependency-mesh-audit/references/surface-pairs.md)。frame-design 保留 23 个导入帧与对象对；relief-box 保留 32 个源 16fps 时刻、按导入 fps 换算及 raw mesh profile；relief-palette 保留控制器、静止对象、镜面间距、颜色与允许接触对判据。

motion-check 的 Manifold 整实体毫米³阈值、screw-bottle 的 Blender Exact 布尔非空判据、表面 BVH 数量互不等价。表面检查可能遗漏完整包含，离散采样可能遗漏采样间穿插。报告保留具体后端、单位、样本和判据，不汇总成未经证明的连续“无碰撞”。

网格读取与临时资源统一复用物化的 [blender-tools 快照](../../.dependency-blender-tools/references/mesh-snapshot.md)。原坐标、精度、三角面前提与领域拒绝条件由此入口保留。

`pose_math.is_rigid(matrix)` 检查有限 4×4 proper rigid 列向量矩阵，沿用原校验容差；motion_check 重导出兼容原调用。完整实体采样见 [solid samples](solid-samples.md)。
