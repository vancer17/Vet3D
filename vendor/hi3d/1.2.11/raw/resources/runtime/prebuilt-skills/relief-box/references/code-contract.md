# 本地代码契约

这些入口是有明确适用范围的业务配方，不是任意自然语言建模引擎。运行前读 [输入配置](configuration.md)；超出范围应在本次任务目录基于原子几何函数扩展，再实际验证，不向旧CLI传不存在的参数。

## 环境、路径和副作用

先读 [本品类依赖与交接](tooling.md)。后台命令、嵌入 Python 依赖与导入/副作用边界按其中的工具契约执行；本配方可显式选 `-t 2`，通过目标脚本的 `--help` 核对真实 CLI。

- 业务入口关键字路径接受 str 或 Path；缺文件报 FileNotFoundError，非法配置/数组可能抛 ValueError、KeyError 或解析异常。业务入口拒绝包内输出；独立调用原子写入函数时调用者仍须提供包外路径。几何/场景函数会修改当前 Blender 场景，使用专用后台进程。
- build/extract/animate 等文件产出函数可创建/覆盖显式输出目录中的同名资产。不要将未归档旧成品作为输出目标；新修订新目录。脚本不保证全事务回滚；失败保存日志，修复后在独立尝试目录重跑受影响阶段。
- 各原子函数只完成下文列出的职责；后续渲染、检查与网页由主流程按用户范围组合。应用/几何导出不等于实物制造验收，正式成品需独立回读。

## 每个模块的可调用边界

### `animate_lift.py`

读取本配方原生场景与邻接measurements，按真实组/枢轴创建动作并导出，必要时渲染帧。不可跨配方套对象名；布局变化须重验路径。

- `keyframe_translation(obj, keys, base_location)`
- `animate(*, scene, output, frames=None, render=False)`

### `animate_travel.py`

读取本配方原生场景与邻接measurements，按真实组/枢轴创建动作并导出，必要时渲染帧。不可跨配方套对象名；布局变化须重验路径。

- `animate(*, scene, output)`
- `merge_scene_animation(path)`：调用 [glb-clips](../../.dependency-glb-clips/references/contract.md) 合并明确同播的派生 GLB，片段名保持 `Complete unlocking access and relocking`；返回原 `source_actions`、`final_actions`、`channels`、`disjoint_node_properties` 字段。采样时刻、非动画 JSON 和全部尾块保持，零/空片段、无效引用/时间存储与冲突明确失败且不改该 GLB。旅行配方的解锁/取物/复锁动作、对象角色、fps、镜头及其他产物仍由本脚本负责；合并的失败保持不代表全流程回滚。入口直接执行，无阶段结果缓存。

### `audit_models.py`

新导入当前目录GLB得到实际边界、动作/网格统计并写JSON；不读native。报告不是自动功能通过。

- `audit(*, input, output)`

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
- `union_solids(target, cutters, *, solver='MANIFOLD')`
- `apply(o)`
- `boolean(o, c, op='UNION')`
- `cyl(name, r, h, loc, mat, axis=(0, 0, 1), n=64)`
- `hole(o, x, y, r, z0, z1)`
- `clean_solid_mesh(obj, *, tolerance_m=1e-09)`

### `box_runtime.py`

CLI参数切片与显式路径规范化/存在检查，无模型/网络操作。

- `cli_arguments(argv=None)`
- `validate_paths(options)`
- `load_config(path, *, required=())`

### `box_stl.py`

普通Python独立binary STL解析，精确float坐标焊接后检查边/方向/零面积/连通/Manifold实体。返回实际字典，不修网格。SciPy/Manifold为独立验证依赖。

- `inspect_binary_stl(path, near_area=1e-08)`

### `build.py`

读取配置和实际高度场，调用几何原子函数构造本配方，输出模型、制造件、测量、native及可选渲染。返回值通常None，结果以显式目录文件为准。

- `build(*, output, heightfields, config, no_render=False)`

### `build_travel.py`

读取配置和实际高度场，调用几何原子函数构造本配方，输出模型、制造件、测量、native及可选渲染。返回值通常None，结果以显式目录文件为准。

- `build(*, output, heightfield, config, preview=False, no_render=False)`

### `check_travel_fit.py`

真实重新导入资产/动作或STL，对本配方的几何功能给数量/尺寸报告，不自动认证；详见验证。

- `inspect_fit(*, model, output)`

### `check_travel_motion.py`

真实重新导入资产/动作或STL，对本配方的几何功能给数量/尺寸报告，不自动认证；详见验证。

- `inspect_motion(*, input, output)`

### `extract_relief_stl.py`

Blender入口：读取真实GLB或binary STL，用mathutils/BVHTree射线提取并局部修补高度，写NPZ/JSON和可选中性源渲染；不是普通Python拓扑验证器。extract_relief_stl返回None，GLB extract返回输出路径字典；原件不改。

- `extract(*, source, output, resolution=(769, 769), axes=(0, 1, 2), front_sign=1, pit_threshold=0.2, median_floor=0.3, no_render=False)`

### `render_frames.py`

读取对应场景或STL，产生指定帧/细节/截面；数值/图像写显式输出。

- `render_frames(*, scene, output, frames='1,100,120')`

### `travel_details.py`

读取旅行配方场景，生成盖底/分区细节与软衬1:1SVG；SVG是软料加工模板，不是TPU实体。

- `render_details(*, scene, output)`

### `verify_stl.py`

批量编排本包STL原子检查器，报告每件与总passed；空集合失败，不把无文件视为通过。

- `validate(*, input, output)`

## 运行结果与完成边界

构建器和检查器不负责自动部署网页，也没有默认收费API调用。执行者使用其真实产物继续完整业务工作流。只有明确请求视频才渲帧/编码；视频帧需明确工作目录，编码后可不放交付包；实际生成的MP4须完整解码。Web GLB可做轻量副本，保留完整原件和native资源；packed纹理与配置随包，不以本机缓存补缺。

固定配方的检查器依赖自己的结构标签和测量契约；新分支修改对象名/角色、尺寸、锁止/路径时同步检查器并运行，不接受“找不到对象就跳过”。数字交叉检查采用离散帧/三角面相交的部分函数不能证明连续扫掠或完全内含实体无交叉；需要实体布尔、边界位置与临界姿态补证。严格失败字段不因图好看而改通过。

## 路径类型速查

| 入口 | 输入边界 | output / 结果 |
|---|---|---|
| build / build_travel | NPZ高度场＋JSON配置文件 | 目录：print、model等GLB、scene、measurements及可选图；返回None |
| extract_relief_stl | binary STL毫米文件 | 目录：heightfield.npz、source-inspection.json及可选源图；Blender中运行，返回None |
| animate_travel | 旅行配方scene＋同目录measurements | 目录：实际动画native/GLB/说明 |
| animate_lift | 基础盒scene＋同目录animation_groups/measurements | output目录：motion.blend/GLB和animation.json；render时frames另为显式目录；返回动作字典 |
| check_travel_fit / check_travel_motion | 实际对应GLB文件 | **JSON文件路径**，有限几何检查，不证明实物携带 |
| audit_models | 单一GLB文件或含GLB目录 | **JSON文件路径**，只审GLB |
| verify_stl | STL文件、print目录或含print构建目录 | **JSON文件路径**，返回含passed/parts字典 |
| travel_details | 旅行配方scene文件 | 目录：细节图、1:1软料SVG |
| render_frames | scene文件＋帧选择字符串 | 目录：frame-NNNN.png |

基础盒内托/隔板/取托边先通过box_core.union_solids变为连续实体。该函数修改target、移除cutters，调用者须同步对象清单；构件必须有实际交叠。数值cleanup默认1e-9m，返回清理前后顶点/面数，不代表毫米配合公差或验证通过。

姿态/求值公共能力按 [motion-check 契约](../../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

旅行盒配方的面积灯复用 [model-preview](../../.dependency-model-preview/references/preview-atoms.md) 的 area_light；毫米换算、目标高度 0.025 场景单位、SQUARE 形状及原灯光参数保留在本配方。构造函数不改变活动对象/选择。
