# 提取与验收

## 选择正确的表面定义

| 目标 | 本 skill 的处理 |
| --- | --- |
| 剔除封闭在头部内部的眼球背面、内壳、牙齿等体素 | 在完整分辨率格网上，从外部空气 flood fill，保留邻接外部空气的原表面体素 |
| 张嘴时露出的牙齿、舌头、鼻孔内壁 | 与外部空气连通，保留；这不意味着内部清理失败 |
| 只保留指定相机能看到的表面 | 需要带遮挡的首击深度/多视角融合；与外部空气连通不是同一定义，本实现不做可见性筛选 |
| 删除三角面、获得可打印闭合外壳 | 本实现不输出该结果；不能把稀疏坐标当作已清理的 GLB |

不要只按连通分量保留最大块：外露眼球可能是独立对象；融合后的内部面也可能与脸皮同属一个块。不要先用凸包，会丢失鼻孔、嘴缝和耳部凹陷。普通表面体素化会命中内外三角面；填充整个实体也不是表面坐标。

## 输入与坐标

目标模型须是当前姿态的静态装配，只含要进入几何条件的部件，先核对节点变换和装配位置；不能对带动画的 GLB 默默使用错误 rest pose。保留源文件。上游的 mesh loader/归一化为唯一几何坐标依据，不另做毫米归一化或交换 Y/Z。

读取实际 pass 配置的 `grid_size=G`、`latent_scale=L`、`coord_resolution=G/L`，CLI 无通用默认值。高分辨率输入 NPZ：

- `voxel_coords`: 非空整数 `[N,3]`，XYZ，范围 `[0,G)`，表示三角面命中的格子，**不是实体填充、格点世界坐标或已降采样 latent coords**。
- `grid_size`: 标量整数 G。
- `source_sha256`: 原装配 GLB 哈希。
- `grid_binding_json`: 非空 JSON 对象，绑定生成算子、格网/归一化依据。`voxelize` 保存上游源码 SHA、pad/shift 与归一化方法；不伪造世界坐标矩阵。

外部生成器也可提供该格式，但执行者必须核验它与目标部署同尺度、同格网；元数据本身不证明正确。本实现不支持 packed coords 或 batch 维输入，避免将不明确的整数误当 XYZ。输入不要用低分辨率 Geo2 latent 坐标顶替原始表面，粗化后嘴缝可能已经封死。

## 执行

`PYTHON`、`SKILL_DIR`、`RUN_DIR` 是调用者选择的实际路径；输出放包外。GLB 入口在已经安装相符 hitem_infer/CUDA 依赖的解释器运行，仅体素化，不加载生成模型。CPU 过滤可在另一台内存足够的主机运行。

```bash
"$PYTHON" "$SKILL_DIR/scripts/exterior_surface.py" voxelize \
  --mesh "$RUN_DIR/assembled.glb" --grid-size "$G" \
  --output "$RUN_DIR/raw_surface.npz"
"$PYTHON" "$SKILL_DIR/scripts/exterior_surface.py" filter \
  --raw "$RUN_DIR/raw_surface.npz" --latent-scale "$L" \
  --output "$RUN_DIR/exterior"
```

`voxelize_mesh` 直接调用安装版 `coord_fitting.glb_to_mesh_voxelizer_coords(..., pad=0)`；按已核对实现限制 G 为 2..2048（11 位编码）。不会自动安装上游或猜 GPU 主机。部署改用 flexible dual grid 时不要照搬 mesh_voxelizer 路径，应重新核对其 encoder 后坐标定义。

`exterior_voxels` 在 G+2 格网上加空白外框，以六邻域传播外部空气；保留至少一个六邻域空气格属于外部的原表面格。封闭腔体里的悬浮网格不保留。返回外露/删除坐标及计数，不改变输入。六邻域是一项离散约定，角点/细缝的连通性会随分辨率改变。

算法目前是 CPU 稠密 flood fill，内存随 G³ 增长；默认 `max_cells=150000000` 可容纳 G=512 的格网，但并不保证主机内存足够。SciPy 队列和数组还有额外开销。超预算在分配前失败；更高分辨率须选足够内存主机或实现经验证的稀疏/分块后端，不悄悄降低分辨率。`--max-cells` 仅改变预算，不改变算法。

`extract` 在剔除之后才执行 `unique(exterior // L)`。输出：

- `surface.npz`、`removed.npz`：原始分辨率坐标，保留绑定，用于切片与前后对照。
- `geo2_coords.npz`：`coords[N,3] int32`，附 latent_scale、coord_resolution、grid_size 与来源绑定。
- `report.json`：输入/算子/产物哈希、实际计数与耗时；状态始终为 `computed_requires_visual_review`，不会自动声称人头通过。

## 开口与虚拟封口

颈底开口、眼球与睑缘装配漏缝可能让空气进入整颗头。此时保留过多内部体素是连通性结果，不能无依据重复平滑或减少迭代。

先检查真实模型和切片。仅当任务需要阻止指定开口泄漏时，可显式制作同格网的 barriers NPZ，字段同 raw NPZ，运行 filter 增加 `--barriers PATH`。它仅阻挡空气传播，不进入输出、不修改原模型；绑定必须与 raw 完全一致。保留 barrier 可视化与原文件，不自动封嘴/鼻孔。barrier 不能补出缺失的真实外表面，也不能代替修复装配。

## 验证与失败边界

检查眼球、牙齿、口腔深处、颈底及耳部的原/外露/剔除体素切片；尤其核对眼球正面保留、封闭背面剔除、张口可见牙齿保留。删除比例不是质量指标。外界可达但被遮挡的深腔仍会保留；若用户明确不要该部分，改用明确 ROI 或可见性定义。

比较轮廓、细缝和不同分辨率的连通性。该方法给出格子级外露性：同一格子内混有内外面不能进一步分开。它不证明全模型水密、自交消除、形态正确或生成输出忠实。

每次写新输出，不以路径存在复用；源码、输入、barrier 或参数改变需新计算。失败可能留下部分输出，保留用于诊断。离线 tests 覆盖封闭内壳、开口、虚拟封口、池化和包交接；CUDA 体素化与真实头模/线上生成需在目标环境另验，不以 CPU 合成格网测试冒充完成。
