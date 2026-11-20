# 本地代码契约

## 依赖与调用

本工作流专属代码与显式物化的共享代码在安装包的 `scripts/` 中组合；共享来源由 package.json 声明，不通过相邻目录导入，不内置网络客户端。场景模块需要 Blender 5.x 的 `bpy`、`bmesh`、`mathutils` 与 NumPy；普通 Python 可运行 CLI `--help` 和路径预检，不能运行 Blender 建模。外部 Blender 可执行文件由用户环境提供。仅渲染实际帧需 Blender；编码需普通 Python、Pillow 与环境提供的 FFmpeg。Hi3D 是按主入口明确提供的独立工具，已有输入直接跳过它。

```sh
blender -b -t 2 --python-exit-code 1 --python "$SKILL_DIR/scripts/run.py" -- \
  --input "$TASK_INPUT" --config "$TASK_CONFIG" --output "$TASK_OUTPUT" --geometry-only
```

这些变量是调用方显式选择的非敏感路径，不是固定目录。`--config` 必填，构建器不在缺省时偷偷加载示例。输出必须是包外的新空目录；同目录重放拒绝，局部恢复使用独立原子函数及新修订目录。失败可能已写部分文件，`stage-time.json` 记录本地尝试状态，不把失败目录改称成功。

不加 `--geometry-only` 会渲染通用中性主/前/后/顶视图，仍需根据本次产品设计使用场景、细节镜头和实际验收。原生动作场景是后续渲染输入，不自动生成视频或验证装配。

```sh
blender -b -t 2 --python-exit-code 1 --python "$SKILL_DIR/scripts/render.py" -- \
  --input "$TASK_ANIMATION" --output "$TASK_FRAMES" --resolution 720
python "$SKILL_DIR/scripts/encode_sequence.py" --ffmpeg "$FFMPEG" \
  --frames "$TASK_FRAMES" --output "$TASK_VIDEO" --fps 24 --start 1 --crf 18
```

已请求视频时，编码与全片解码统一使用 [media-encode](../../.dependency-media-encode/references/sequence.md)，保留起始帧 1、CRF18 和拒绝覆盖策略。读取源场景真实 fps；示例 24 只在源为 24fps 时适用。分段渲染用 `--start/--end`，范围必须在原生动作内，已有帧拒绝覆盖，恢复只渲缺帧。编码和画面审查另计时，不能重复帧补帧率。

## 可独立调用的通用原子

在 Blender Python 中把本包 `scripts` 加入模块搜索路径，然后从 `teapot_model` 导入对应模块；不运行 CLI 也可调用。

| 本包模块 | 唯一契约（使用前按调用接口读取） |
|---|---|
| `product_source` | [source-prepare 的 product 来源](../../.dependency-source-prepare/references/code-contract.md#product-接口契约) |
| `product_core` | [shape-build 的米制几何](../../.dependency-shape-build/references/code-contract.md#product-接口契约) |
| `media` | [model-preview 的展示与动作](../../.dependency-model-preview/references/code-contract.md#product-接口契约) |
| `product_print` | [print-export 的制造导出](../../.dependency-print-export/references/code-contract.md) |
| `validation` | [mesh-audit 的 STL/通道检查](../../.dependency-mesh-audit/references/code-contract.md#product-接口契约) |

本地 `run.load_request / run.run` 接收显式文件与新输出，负责预检/编排；不读凭据、不调用服务，只编排本品类构建并写阶段时间。通用执行契约见 [run-tools](../../.dependency-doc/run-tools.md)。

场景函数在调用时修改 Blender；导入模块本身不解析参数、创建文件、重置场景或启动流水线。函数不隐式调用其它 Skill。脚本构建输出是待验收候选，不承诺自动设计任意输入或生成所有DIY连接。

## 圆形侧把构建器与配置

当前构建器只支持圆形旋转体、封闭端侧把、宽口桥钮盖。`body_height_mm=66`、口沿外半径32mm是此构型的边界，壁厚2.5–3.5mm；不是品类默认尺寸。容量在所给剖面径向调整 [-5,8]mm 的可达范围内求解，超范围报错，0.05mL为数值收敛容差。其它器形需扩展接口与验证。

`validate_config` 要求显式容量 `capacity_ml`、`wall_mm`、`floor_mm`、`fill_height_mm`、`body_height_mm`、`body_profile_zr_mm`（递增Z/半径，起Z0、末Z66/R32）。`solve_profile(config)` 是纯计算：输出 Z、外半径、积分容量和可达范围，不改场景/文件，不把壶嘴占位混入主腔容量。

扫掠输入 `handle_curve_mm`+`handle_sections_mm`、`spout_curve_mm`+`spout_outer_sections_mm`、`spout_inner_curve_mm`+`spout_inner_sections_mm`；截面数字为椭圆全直径，数量与中心线一致。内道路径明确伸入主腔并穿出口，不能仅由外形推定。`build_body(config,profile,material)` 先并外体，再局部圆滑/嘴根融合，最后切精准内腔/内道；`build_lid(config,material)` 创建配套盖/桥钮/通气，均在当前场景创建真实对象。

结构数值：`outer_voxel_mm`、`junction_smooth_iterations`、`spout_root_blend_mm`、`vent_xy_mm`、`vent_diameter_mm`。局部融合区属于本有限家族；大幅改嘴柄根位置必须扩展区域和动作，不能只修改路径坐标。`surfaces.pchip` 和 `catmull_arclength` 为纯曲线计算；`surface_of_revolution / swept_ellipse / smooth_junctions / blend_spout_root` 是分别可调用的场景适配函数，前者保留单顶点极点，扫掠使用平行输运避免截面轴突然翻转。

浮雕输入为正面朝 +Z 的实际毫米 STL 或 NPZ（有限二维 `height`、同形 `mask`、2×2 `bounds_xy_mm`）；使用 `sampling.sample_relief(input_path,output_path,resolution)` 独立重新采样，可选 `sampling_resolution` 默认1024。它根据源背板Z分位估计基面，保留原长宽比和未命中mask，不覆盖源，丢失倒扣必须说明。异常方向/空高度明确失败。

`relief.apply_metric_relief(object,source,profile_z_m,profile_r_m,config)` 从显式源沿横截面与母线弧长映射，并在足迹内局部加密。必填 `motif_width_mm`、`motif_height_mm`、`motif_angle_degrees`、`motif_center_z_mm`、`relief_height_mm`、`subdivide_edge_threshold_mm`、`subdivision_cuts`。前三维受源比例约束，不能按矩形强拉伸；微细纹保留需实际看图。`hardware_policy` 显式记录，一体柄/钮不靠螺钉，但不自动实现新的可拆连接。

输出两份实际毫米STL、未量化 `model-full.glb`、`model.glb`、展开/剖面、`source.blend`、`animation.blend` 和测量。可选 `compress_web=true` 使用Draco16bit位置量化，普通场景导出不默认减面。`author_use_motion(path,body,lid)` 写完整取盖/复位/抬壶/正确方向倾倒/回正；假设此有限侧把方向，修改模型后仍核验全程，不伪造液体性能。

内置参考配置 [round-side-handle.json](round-side-handle.json) 是可选的300mL有限家族演算起点，无源图/主题/用户偏好，不自动读取；调用方必须明确选择并改为本次简报。它不是所有茶壶的默认模板，也不包含材料认证或打印通过结论。

保留可独立组合的 `relief.ellipse_arc_coordinates(rx,ry,angles)`：按每一椭圆行的实际弧长积分给出纹样横坐标，单位随输入；它不生成后把、椭圆盖或等厚椭圆壳。新非圆器体需另建实际内外轮廓，再用此原子适配纹样和独立容量/壁厚检查。

构建器保存测量后调用 [mesh-audit 的打印拓扑门槛](../../.dependency-mesh-audit/references/code-contract.md#打印拓扑门槛)；本品类的尺寸、净空及实物待测项仍按上述要求交付。

`relief.load_metric_heightfield(source)` 独立读取/关闭无pickle的NPZ，检查二维0–1高度、同形mask与正XY范围；异常数据明确报错，供映射函数复用。
