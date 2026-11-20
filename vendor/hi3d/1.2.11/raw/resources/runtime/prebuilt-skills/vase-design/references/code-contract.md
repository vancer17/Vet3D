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

在 Blender Python 中把本包 `scripts` 加入模块搜索路径，然后从 `vase_model` 导入对应模块；不运行 CLI 也可调用。

| 本包模块 | 唯一契约（使用前按调用接口读取） |
|---|---|
| `product_source` | [source-prepare 的 product 来源](../../.dependency-source-prepare/references/code-contract.md#product-接口契约) |
| `product_core` | [shape-build 的米制几何](../../.dependency-shape-build/references/code-contract.md#product-接口契约) |
| `media` | [model-preview 的展示与动作](../../.dependency-model-preview/references/code-contract.md#product-接口契约) |
| `product_print` | [print-export 的制造导出](../../.dependency-print-export/references/code-contract.md) |
| `validation` | [mesh-audit 的 STL/通道检查](../../.dependency-mesh-audit/references/code-contract.md#product-接口契约) |

本地 `run.load_request / run.run` 接收显式文件与新输出，负责预检/编排；不读凭据、不调用服务，只编排本品类构建并写阶段时间。通用执行契约见 [run-tools](../../.dependency-doc/run-tools.md)。

场景函数在调用时修改 Blender；导入模块本身不解析参数、创建文件、重置场景或启动流水线。函数不隐式调用其它 Skill。脚本构建输出是待验收候选，不承诺自动设计任意输入或生成所有DIY连接。

## 花器配置与专属原子

`vase_model.build.validate_config(config)` 明确校验所需字段；`build(input_path,config,output,geometry_only)` 只编排下列阶段。

- `height_mm` 定标源高度，`source_ratio` 为 (0,1]；`hardware_policy` 为 standard/print_preferred/printed_only。
- `liner`：`outer_diameter_mm`、`inner_diameter_mm`、`length_mm`、`bottom_mm`、`axis_mm`（XY）、`source`（资料或明确假设）。当前仅圆直管、圆滑底型参考；不是扫描实物。全程提取需显式 `extraction_offset_mm`。
- `support`：`base_top_mm`、`pedestal_radius_mm`、`guide_z_mm`、`guide_height_mm`、`guide_wall_mm`、`radial_clearance_mm`、`spoke_width_mm`、`angles_degrees`。至少三个导向支点，必须命中本次源的墙体；射线缺失时明确失败，不造悬空支撑。

`make_liner(liner,material)` 创建独立开口内胆参考；`cut_liner_clearance(shell,liner,support,material)` 切完整轴向口；`add_integral_supports(...)` 先建宽底托，再用真实源壁射线定位导向横梁。三者可分别调用；均显式修改当前场景。源应是适合开口/承托的闭合艺术壳，布尔可能破坏不合适源；由当前多视图和打印回读拒绝失败结果。

输出 `print/shell.stl`、`model.glb`、`exploded.glb`、`section.glb`、`source.blend`、`cleaning.blend`、`measurement.json`；内胆是参考硬件，未自动作为打印件。原源文件、选型来源、BOM/试片/使用场景/按需视频/网页由完整工作流随任务交付。一体支承不需要额外机械件；选择可拆篮、锁键或打印内胆时扩展配对结构并另交实际文件，不假称此入口已实现。

导向横梁与环体保留半个环壁厚的正重叠，不能仅共面接触。可选 `numerical_island_limit_mm` 仅剔除至多32顶点且三轴包络均小于阈值的独立数值残屑，并记录每项尺寸；不用于删掉真实分件，原源保持。打印前仍核验最终连通体数量。

构建器保存测量后调用 [mesh-audit 的打印拓扑门槛](../../.dependency-mesh-audit/references/code-contract.md#打印拓扑门槛)；本品类的尺寸、净空及实物待测项仍按上述要求交付。
