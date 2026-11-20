# 高度场核心

`height_sampling.sample_mesh(vertices,faces,resolution,axes=(0,1,2),front_sign=1,ray_margin=1,all_triangles=False)` 接收同单位的显式几何，返回 float32 signed raw_depth（缺射线为 NaN）、布尔 valid_mask、原坐标上下界。resolution 是 nx/ny，数组 shape 为 ny/nx，行从 height 轴最小值开始。仅依赖 NumPy 和 Blender mathutils BVH；不导入模型、不改场景、没有单位转换。投影面积必须非零，resolution 每轴至少 8，射线 margin 与几何同单位。首击无法保留背面、悬垂和遮蔽结构。

`height_ops.subtract_baseline(raw,baseline)` 把缺射线转换为零高度；`normalize_height(height,percentile=99.9,mask=None,positive_only=True)` 返回夹到 [0,1] 的高度与物理幅度；无有效正幅度失败。基线、mask、分位数必须由调用方明确选择。

`median_filter(array,kernel=5,dtype=float)` 与 `repair_pits(array,kernel=5,threshold=.12,median_floor=.2,iterations=3,dtype=float)` 是无副作用数组能力；后者返回字段、副本差异 mask 与数量/最大位移/参数记录。阈值与输入同单位，dtype 显式保留原 profile 的 float32/float64。低谷修补不能判断艺术孔洞，必须查看原始/修补/差异后接受。

- extract_stl：二进制毫米 STL 先按轴/正面变换；全轴非零，margin=1，基线最小 Z，正样本 99.9%，5 核、阈值 .2/中值下限 .3、1 次修补，保留 float32 及原 NPZ 字段。
- relief-brush：场景求值的源单位，margin=.1，基线默认 6 分位，源单位先 3 核/.004/1 次修补再 99.8% 归一化；区域裁切、边缘衰减、局部归一化、5 核修补与周期镜像仍在工作流，默认 float64。
- teapot：STL 源毫米、原 1e-6 焊接、X/Y 比例、margin=10、源顶点 1% 基线；99.9% 使用所有有效射线（包含零高度），没有低谷修补。mask 继续 uint8，NPZ 的 bounds_xy_mm/base_z_mm/height_scale_mm 不变。

源格式读取、Blender 图像输出、产品造型和笔刷创建均由原调用方负责。安装前用 package-tools 显式物化；工作流只保留 profile 和格式适配。
