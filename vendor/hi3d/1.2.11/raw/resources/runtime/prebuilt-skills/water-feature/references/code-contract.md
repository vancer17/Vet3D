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

在 Blender Python 中把本包 `scripts` 加入模块搜索路径，然后从 `water_model` 导入对应模块；不运行 CLI 也可调用。

| 本包模块 | 唯一契约（使用前按调用接口读取） |
|---|---|
| `product_source` | [source-prepare 的 product 来源](../../.dependency-source-prepare/references/code-contract.md#product-接口契约) |
| `product_core` | [shape-build 的米制几何](../../.dependency-shape-build/references/code-contract.md#product-接口契约) |
| `media` | [model-preview 的展示与动作](../../.dependency-model-preview/references/code-contract.md#product-接口契约) |
| `product_print` | [print-export 的制造导出](../../.dependency-print-export/references/code-contract.md) |
| `validation` | [mesh-audit 的 STL/通道检查](../../.dependency-mesh-audit/references/code-contract.md#product-接口契约) |

本地 `run.load_request / run.run` 接收显式文件与新输出，负责预检/编排；不读凭据、不调用服务，只编排本品类构建并写阶段时间。通用执行契约见 [run-tools](../../.dependency-doc/run-tools.md)。

场景函数在调用时修改 Blender；导入模块本身不解析参数、创建文件、重置场景或启动流水线。函数不隐式调用其它 Skill。脚本构建输出是待验收候选，不承诺自动设计任意输入或生成所有DIY连接。

## 水景配置与专属原子

`validate_config` 校验字段；`build` 编排实际雕塑、孔槽、盆、支撑、设备和导出。

- 源定标：`source_width_mm`、`source_ratio`、`depth_factor`、`sculpture_offset_mm`，所有改动在测量中明示。
- `channels` 每项含 `name`、局部雕塑毫米 `points_mm` 与 `radius_mm`；圆管扫掠可作为封闭通道或与外界相交的开放槽。`carve_channels` 返回真实采样中心线，仍需与实际通道有限净空/出口复核。
- `basin_profile_rz_mm` 是包含底、外壁、口沿、内壁的闭合材料剖面，`basin_y_factor` 控制椭圆平面；`make_basin` 独立创建它。
- `supports` 每项为 `xy_mm`、`base_mm`、`radius_mm`、`fitting_stock_mm`；`add_supports` 按实际岩底射线创建柱并报告顶面。正修配量表示需要磨配，不是无干涉装配。
- `pump` 必含 `dimensions_mm`、`location_mm`、`source`、`port_diameter_mm`、`port_location_mm`、`voltage`、`operating_point_status`。设备仅为包络，端口位置/规格是核对输入，现构建器不会仿制真实泵或自动证明接合。`hose` 含 `points_mm`（世界毫米）、`inner_diameter_mm`、`outer_diameter_mm`、`source`。`make_device` 创建泵包络与真正空心软管。
- `waterline_mm`、`return_volume_ml`；可给 `inner_profile_zr_mm` 明确内腔Z/半径分支以积分名义液位余量。未扣浸没物的体积不能称实际安全余量。`service_offset_mm` 必须依据本次取出路径；`hardware_policy` 只记录路线，不自动制造锁件。
- 可选 `print_voxel_mm` (0.1–2)：`make_print_derivative` 封闭独立打印副本，再按原路径重切内孔。自由表面复杂时可直接调用 `envelope.visibility_hull(source,work,pitch,max_cells)`，构建三轴可见包络交集并保存占用格；它会损失凹面/微细形状，需要重新切接口与验收，不用于未经评估的薄壳。

`flow.create_flow_illustration(points_mm,radii_mm,material)` 创建本次通道对应的真实水形；`flow.author_flow_cycle(output,objects,water_objects,fps)` 写出完整启停可见状态，仍需按当前实际水路细化启动和排空运动并验证，非流体模拟。二者可独立使用，不是 `run.py` 的隐式一步。

输出 `print/sculpture.stl`、`print/reservoir.stl`、装配/展开/盆体剖面 GLB、`source.blend`、`maintenance.blend` 和测量。默认没有后盖、泵锁、软管紧固或电源部件的自动设计；任务需要时按实际设备和 DIY 简报扩展。源保真/打印差异、水道/泵口匹配、实物性能、BOM/启停视频和网页由完整流程完成。

`repair.repair_stl(input_path,output_path,area_threshold_mm2,weld_mm,max_iterations)` 对毫米量化后的少量近共线面作局部修复；输入/输出必须分开，清理后非闭合则明确失败。它不会自动掩盖孔洞或大尺度形状缺陷，返回运行诊断由调用方保存于任务目录。

构建器保存测量后调用 [mesh-audit 的打印拓扑门槛](../../.dependency-mesh-audit/references/code-contract.md#打印拓扑门槛)；本品类的尺寸、净空及实物待测项仍按上述要求交付。

可选 `print_cleanup_mm` 使 `clean_print_mesh` 在打印副本上按显式阈值焊接/消退数值退化边；可选 `print_fragment_limit_mm` 仅删除小于阈值的独立碎片，逐项记录尺寸。默认不删分件，不能用大阈值掩盖缺失主体；真实雕塑原件保留，删除真实细节需在外观/打印差异中明示。

当实际布尔后的打印体仍有退化或非流形时，可显式给 `final_print_voxel_mm`（0.1–1mm）在全部孔槽之后做独立打印闭合；这是有损工艺副本，最终孔径不再等同名义切刀尺寸，必须回读实测有限通路、最小壁厚及外观差异。不可写成精确重切已保留所有名义尺寸。
