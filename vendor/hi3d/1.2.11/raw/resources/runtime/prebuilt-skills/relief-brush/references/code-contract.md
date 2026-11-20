# 本地代码契约

这些入口是有明确适用范围的业务配方，不是任意自然语言建模引擎。运行前读 [输入配置](configuration.md)；超出范围应在本次任务目录基于原子几何函数扩展，再实际验证，不向旧CLI传不存在的参数。

## 环境、路径和副作用

先读 [本品类依赖与交接](tooling.md)。后台命令、嵌入 Python 依赖与导入/副作用边界按其中的工具契约执行；本配方可显式选 `-t 2`，通过目标脚本的 `--help` 核对真实 CLI。

- 业务入口关键字路径接受 str 或 Path；缺文件报 FileNotFoundError，非法配置/数组可能抛 ValueError、KeyError 或解析异常。业务入口拒绝包内输出；独立调用原子写入函数时调用者仍须提供包外路径。几何/场景函数会修改当前 Blender 场景，使用专用后台进程。
- build/extract/animate 等文件产出函数可创建/覆盖显式输出目录中的同名资产。不要将未归档旧成品作为输出目标；新修订新目录。脚本不保证全事务回滚；失败保存日志，修复后在独立尝试目录重跑受影响阶段。
- 各原子函数只完成下文列出的职责；后续渲染、检查与网页由主流程按用户范围组合。应用/几何导出不等于实物制造验收，正式成品需独立回读。

## 每个模块的可调用边界

### `application_demo.py`

读取对应场景或STL，产生指定帧/细节/截面；数值/图像写显式输出。

- `animate(*, scene, heightfields, config, output, frames=None, no_render=False, render_animation=False)`

### 显式几何与领域接口

下列函数按 [组合契约](../../.dependency-shape-build/references/composition.md) 从对应 `*_core`、预览、打印和审查模块显式导入，物化路径见 package.json；不再提供旧聚合文件。函数签名、单位和品类差异保持。

几何原子：loop/ring3/sample为数组计算；mesh/loft/tube/plate/height_mesh/ring_relief创建Blender对象；export_glb/export_stl写显式文件；stage/camera/render修改渲染场景，save写native。尺寸输入为mm，Blender空间为m；bounds回mm。

- `clean()`
- `material(name, color, metal=0, rough=0.36)`
- `mesh(name, v, f, mat=None)`
- `bevel(o, width=0.4, segments=3)`
- `bore(o, xy, r, z0, z1)`
- `repair_boolean_flaps(o)`
- `cube(name, dim, loc, mat, bev=0.4)`
- `loop(w, h, kind='rect', n=256, r=5)`
- `loft(name, rings, mat, cap_start=False, cap_end=False)`
- `ring3(xy, z)`
- `tube(name, w, h, depth, wall, base, kind, mat)`
- `plate(name, w, h, thick, z, kind, mat)`
- `sample(a, u, v)`
- `height_mesh(name, a, w, h, depth, base, mat, nx=500, ny=160, warp=None)`
- `ring_relief(name, w, h, band, kind, a, mat, depth=1.2, n=768, radial=28, z=7)`
- `export_glb(path, objects)`
- `export_stl(path, objects)`
- `stage(target, span)`
- `camera(cam, target, delta, scale)`
- `render(path, w=1200, h=1000, samples=24, *, enabled=True, engine=None)`
- `save(path)`
- `bounds(objects)`

### `brush_runtime.py`

CLI参数切片与显式路径规范化/存在检查，无模型/网络操作。

- `cli_arguments(argv=None)`
- `validate_paths(options)`
- `load_config(path, *, required=())`

### `build.py`

读取配置和实际高度场，调用几何原子函数构造本配方，输出模型、制造件、测量、native及可选渲染。返回值通常None，结果以显式目录文件为准。

- `build(*, output, heightfields, config, no_render=False)`

### `extract.py`

Blender入口：只直接读取GLB/glTF，用mathutils/BVHTree射线提取并局部修补高度，写NPZ/线性PNG/JSON；返回输出路径字典，不修改原件。STL必须先经prepare_stl的显式单位转换和新会话尺寸核对，不能直接交给本CLI。

- `sample_scene(*, resolution, axes, front_sign, ray_margin=0.1)`
- `write_height_assets(*, output, processed, metadata)`
- `extract(*, source, output, config)`

### `field_ops.py`

纯numpy：局部中值/低谷修补（返回数组、掩膜、统计）、显式裁区、淡出、镜像周期与一阶差分、区域处理、按弧长的曲面映射。无文件或场景效果。

- `median_filter(array, kernel=5)`
- `repair_pits(array, *, kernel=5, threshold=0.12, median_floor=0.2, iterations=3)`
- `crop_region(array, bounds)`
- `edge_fade(array, fx, fy)`
- `periodic_mirror(array)`
- `seam_metrics(array)`
- `prepare_regions(raw, config)`
- `warp_surface(points, kind, radius_mm)`

### `synchronize_morph_clips.py`

纯GLB JSON/binary适配：合并同长形变通道为同一动作并写新文件；时间/目标冲突失败，不重新建模。

- `synchronize(path)`

### `validate_assets.py`

inspect_asset独立打开一个native/GLB并返回实际对象/bounds/动作；validate_assets批量编排并写JSON。会替换当前场景。

- `object_bounds_mm(obj)`
- `inspect_asset(path)`
- `validate_assets(*, input, output)`

### `validate_stl.py`

普通Python独立binary STL解析，精确float坐标焊接后检查边/方向/零面积/连通/Manifold实体。返回实际字典，不修网格。SciPy/Manifold为独立验证依赖。

- `inspect_binary_stl(path, near_area=1e-08)`

### `validate_tile.py`

从实际场和区域元数据计算边缘/一阶差分；生成并渲染2×2闭合表面，报告镜像汇合；不能当自然随机纹样。

- `validate_tile(*, heightfields, region, output)`

### `verify_brushes.py`

新场景append实际Brush，使用其真实纹理进行DISPLACE顶点检查；空库失败。它验证纹理通路，不模拟鼠标笔划或其他软件UI。

- `verify(*, library, output, expected_count=None)`

## 运行结果与完成边界

构建器和检查器不负责自动部署网页，也没有默认收费API调用。执行者使用其真实产物继续完整业务工作流。只有明确请求视频才渲帧/编码；视频帧需明确工作目录，编码后可不放交付包；实际生成的MP4须完整解码。Web GLB可做轻量副本，保留完整原件和native资源；packed纹理与配置随包，不以本机缓存补缺。

固定配方的检查器依赖自己的结构标签和测量契约；新分支修改对象名/角色、尺寸、锁止/路径时同步检查器并运行，不接受“找不到对象就跳过”。数字交叉检查采用离散帧/三角面相交的部分函数不能证明连续扫掠或完全内含实体无交叉；需要实体布尔、边界位置与临界姿态补证。严格失败字段不因图好看而改通过。

## 路径类型速查

| 入口 | 输入边界 | output / 结果 |
|---|---|---|
| extract | GLB/glTF文件＋JSON文件；STL先独立转换 | 目录：heightfields.npz、16位PNG、metadata、repair、raw；Python返回路径字典 |
| build | NPZ文件＋同目录PNG/metadata＋JSON | 目录：brush-library.blend、scene、GLB/STL、measurements、可选图；返回None |
| verify_brushes | 原生库文件 | **目录**：brush-import-test.json和brush-fresh-session.blend；失败抛RuntimeError |
| application_demo | 本配方scene/NPZ/JSON文件 | output目录：application.glb/blend与说明；frames只在--render-animation时必需；默认生成前后图片与GLB/native，no-render仅跳过静态图并与视频请求互斥 |
| validate_assets | 单一GLB/blend文件或资产目录 | **JSON文件路径**；Python返回报告列表 |
| validate_tile | NPZ文件＋已声明tile的region名 | 目录：tile-validation.json、2×2 STL/GLB和对照图 |
| validate_stl | 一个或多个binary STL文件/目录 | `--json`是**JSON文件路径**，退出0表示所有文件检查通过 |

### `prepare_stl.py`：独立预处理，不是extract的STL分支

- `scene_bounds_m()`：读取当前Blender网格世界坐标，返回2×3 numpy边界；不写文件。
- `convert_stl(*, source, output, meters_per_unit, unit_basis, tolerance_m=1e-6)`：source为STL文件，output为包外GLB文件；单位比例必须为正有限数，unit_basis显式known/assumed。会替换当前场景、导出GLB并全新导入核对bounds；保留原STL不动，输出同名.conversion.json并返回实际报告字典。缺文件、非法单位/后缀或超出转换容差均失败；错误报告留在任务目录，不称已适配实物。
- CLI只解析/调用，须在Blender运行。具体单位决策、已知毫米命令和提取衔接见 [STL预处理](configuration.md#stl-预处理)。源STL与转换报告随本次任务来源记录保存，不能将临时GLB误标成新Hi3D生成结果。

`application_demo.animate` 默认只生成两张应用前后图、GLB 动作及原生源，不生成视频帧目录。明确请求视频后使用 `--render-animation --frames <任务目录>`；与 `--no-render` 同时使用会在场景写入前拒绝。未渲帧时元数据的 `video_rendered` 为 false，`frames/fps` 仅描述动作时间线。

GLB 合并算法唯一源为 [glb-clips 契约](../../.dependency-glb-clips/references/contract.md)，通过 package.json 物化；本地函数保留原片段名称和返回字段适配。

资产回读的公共载入和测量按 [mesh-audit 场景测量](../../.dependency-mesh-audit/references/scene-measure.md) 组合；本工作流保留文件筛选、采样帧、空对象策略与原报告字段，使用 package.json 物化的共享函数。回读入口直接接收已有资产，不触发上游生成或建模，也不缓存旧回读报告。
