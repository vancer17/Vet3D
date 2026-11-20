# 本地代码契约

这些入口是有明确适用范围的业务配方，不是任意自然语言建模引擎。运行前读 [输入配置](configuration.md)；超出范围应在本次任务目录基于原子几何函数扩展，再实际验证，不向旧CLI传不存在的参数。

## 环境、路径和副作用

先读 [本品类依赖与交接](tooling.md)。后台命令、嵌入 Python 依赖与导入/副作用边界按其中的工具契约执行；本配方可显式选 `-t 2`，通过目标脚本的 `--help` 核对真实 CLI。

- 业务入口关键字路径接受 str 或 Path；缺文件报 FileNotFoundError，非法配置/数组可能抛 ValueError、KeyError 或解析异常。业务入口拒绝包内输出；独立调用原子写入函数时调用者仍须提供包外路径。几何/场景函数会修改当前 Blender 场景，使用专用后台进程。
- build/extract/animate 等文件产出函数可创建/覆盖显式输出目录中的同名资产。不要将未归档旧成品作为输出目标；新修订新目录。脚本不保证全事务回滚；失败保存日志，修复后在独立尝试目录重跑受影响阶段。
- 各原子函数只完成下文列出的职责；后续渲染、检查与网页由主流程按用户范围组合。应用/几何导出不等于实物制造验收，正式成品需独立回读。

## 每个模块的可调用边界

### `animate_crescent.py`

读取本配方原生场景与邻接measurements，按真实组/枢轴创建动作并导出，必要时渲染帧。不可跨配方套对象名；布局变化须重验路径。

- `animate(*, scene, output, render=False)`
- `merge_scene_animation(path)`：调用 [glb-clips](../../.dependency-glb-clips/references/contract.md) 合并明确同播的派生 GLB，保留片段名 `Complete eclipse window assembly`。

### `animate_frame.py`

读取本配方原生场景与邻接measurements，按真实组/枢轴创建动作并导出，必要时渲染帧。不可跨配方套对象名；布局变化须重验路径。

- `animate(*, scene, output, render=False)`
- `merge_scene_animation(path)`：复用同一合并核心，保留片段名 `Complete synchronized frame assembly`。

以上两个合并适配保持 `source_animation_count`、`final_animation_count`、`channels`、`distinct_node_properties`、`merge_rule` 报告键；动作、对象角色、镜头与 fps 继续由各配方负责。合并核心保持采样时刻、非动画 JSON 和全部尾块，拒绝零/空片段、无效引用、时间存储与通道冲突；校验失败不修改该 GLB。配方本身仍可能已写出其他产物，不承诺整流程回滚。这些 animate 入口直接执行，无阶段结果缓存。

### `audit_models.py`

新导入当前目录GLB得到实际边界、动作/网格统计并写JSON；不读native。报告不是自动功能通过。

- `audit(*, input, output)`

### `build_crescent.py`

读取配置和实际高度场，调用几何原子函数构造本配方，输出模型、制造件、测量、native及可选渲染。返回值通常None，结果以显式目录文件为准。

- `build(*, output, heightfield, config, artwork, preview=False, no_render=False)`

### `build_frame.py`

读取配置和实际高度场，调用几何原子函数构造本配方，输出模型、制造件、测量、native及可选渲染。返回值通常None，结果以显式目录文件为准。

- `build(*, output, heightfield, config, preview=False, no_render=False)`

### `check_motion.py`

真实重新导入资产/动作或STL，对本配方的几何功能给数量/尺寸报告，不自动认证；详见验证。

- `inspect_motion(*, input, output)`

### `check_mount_walls.py`

真实重新导入资产/动作或STL，对本配方的几何功能给数量/尺寸报告，不自动认证；详见验证。

- `measure_mount_walls(*, input, output)`

### `check_support.py`

真实重新导入资产/动作或STL，对本配方的几何功能给数量/尺寸报告，不自动认证；详见验证。

- `measure_support(*, input, output)`

### `extract_relief_stl.py`

Blender入口：读取明确以毫米表示的binary STL，用mathutils/BVHTree射线提取并局部修补高度，写NPZ/JSON和可选中性源渲染；不是普通Python拓扑验证器，返回None，原件不改。GLB/glTF输入先核对单位、轴向并在任务目录转换为毫米binary STL，不能直接传给此入口。

- `extract(*, source, output, resolution=(769, 769), axes=(0, 1, 2), front_sign=1, pit_threshold=0.2, median_floor=0.3, no_render=False)`

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
- `prepare_stl_triangles(triangles_mm)`
- `export_stl(path, objects)`
- `stage(target, span)`
- `camera(cam, target, delta, scale)`
- `render(path, w=1200, h=1000, samples=24, *, enabled=True, engine=None)`
- `save(path)`
- `bounds(objects)`
- `applymods(o)`
- `boolean(o, c, op='UNION')`
- `cylinder(name, r, d, loc, mat, axis=None, n=64)`
- `hole(o, xy, r, z0, z1)`
- `smoothmesh(o)`
- `clean_solid_mesh(obj, *, tolerance_m=1e-09)`

### `frame_runtime.py`

CLI参数切片与显式路径规范化/存在检查，无模型/网络操作。

- `cli_arguments(argv=None)`
- `validate_paths(options)`
- `load_config(path, *, required=())`

### `frame_stl.py`

普通Python独立binary STL解析，精确float坐标焊接后检查边/方向/零面积/连通/Manifold实体。返回实际字典，不修网格。SciPy/Manifold为独立验证依赖。

- `inspect_binary_stl(path, near_area=1e-08)`

### `render_frames.py`

读取对应场景或STL，产生指定帧/细节/截面；数值/图像写显式输出。

- `render_frames(*, scene, output, frames='1,100,120')`

### `section_plot.py`

读取对应场景或STL，产生指定帧/细节/截面；数值/图像写显式输出。

- `render_sections(*, input, output)`

### `verify_stl.py`

批量编排本包STL原子检查器，报告每件与总passed；空集合失败，不把无文件视为通过。

- `validate(*, input, output)`

## 运行结果与完成边界

构建器和检查器不负责自动部署网页，也没有默认收费API调用。执行者使用其真实产物继续完整业务工作流。只有明确请求视频才渲帧/编码；视频帧需明确工作目录，编码后可不放交付包；实际生成的MP4须完整解码。Web GLB可做轻量副本，保留完整原件和native资源；packed纹理与配置随包，不以本机缓存补缺。

固定配方的检查器依赖自己的结构标签和测量契约；新分支修改对象名/角色、尺寸、锁止/路径时同步检查器并运行，不接受“找不到对象就跳过”。数字交叉检查采用离散帧/三角面相交的部分函数不能证明连续扫掠或完全内含实体无交叉；需要实体布尔、边界位置与临界姿态补证。严格失败字段不因图好看而改通过。

## 路径类型速查

| 入口 | 输入边界 | output / 结果 |
|---|---|---|
| build_frame / build_crescent | heightfield NPZ＋config文件；crescent另需artwork文件 | 目录：print、model/exploded GLB、scene.blend、measurements、可选图；返回None |
| extract_relief_stl | binary STL毫米文件 | 目录：heightfield.npz、source-inspection.json、可选中性源图；Blender中运行，返回None |
| animate_frame / animate_crescent | 对应scene文件＋同目录measurements | 目录：动画native/GLB、图及按参数渲染帧；函数改变场景 |
| audit_models | 单一GLB或含GLB目录 | **JSON文件路径**，只审GLB，不读native |
| check_support / check_motion | 对应model/motion GLB文件 | **JSON文件路径**，数值报告不自动物理认证 |
| check_mount_walls | 含print与measurements的构建目录 | **JSON文件路径**，自动识别一款支持的框STL |
| section_plot | 含print的构建目录 | **PNG文件路径**，同名JSON侧文件；普通Python/Pillow |
| verify_stl | STL文件、print目录或含print构建目录 | **JSON文件路径**，Python返回含passed/parts字典 |
| render_frames | scene文件＋帧选择字符串 | 目录：frame-NNNN.png |

frame_print.prepare_stl_triangles只在float32毫米序列化后移除精确零面积三角形；保留非零微小面，返回过滤后的数组和移除数量。export_stl不修非流形拓扑，最终文件仍独立验证。clean_solid_mesh的1e-9m默认值用于数值重复点/共线退化清理，不是打印配合公差。

## 圆口旋锁 DIY 模块

仅对应[配方](diy-recipe.md)的固定110mm圆口家族，原标准构建器不变；本地脚本不调用Hi3D、不会部署网页。输入数组、素材和目标路径均显式提供。此分支复用本包显式物化的planar_core/frame_core、frame_print、frame_runtime与frame_stl，不复制相邻包或另存frame_common。

| 模块/可调用函数 | 输入、职责和输出 |
|---|---|
| `build_frame_diy.build(*, output, heightfield, artwork, config, render_stills=True)` | 原NPZ/图片/JSON文件→验证配置→四件制造自由态STL、flat/model GLB、flat-assembly/scene.blend、measurements及可选主/背图；返回测量字典。改变当前Blender场景。 |
| `build_frame_diy.annular_sector(name,r0,r1,a0,a1,z0,z1,mat,n=None)` / `prism(name,xy,z0,z1,mat)` / `annulus(name,ri,ro,z0,z1,mat,n=768)` | 毫米和角度输入创建单一Blender几何；调用者保证有限非退化边界、正确环向与正厚度，不写文件。 |
| `build_frame_diy.moon_frame(cfg,field,mat)` / `build_connectors(frame,cfg,mat,backmat)` | 已校验本配方配置/场→固定轮廓与配对连接；后者修改frame并返回四件列表和展示变换。不能用于其它口径/轮廓的自动转换。 |
| `build_frame_diy.curved_tube(name,pts,radii,mat,ncross=24)` / `dovetail(name,x,y0,y1,mat,clearance=0)` | 创建连续管或此截面燕尾；dovetail的clearance为坐标偏置，不是斜面法向值。 |
| `build_frame_diy.board_release_shape(obj,delta=1.15)` / `stand_release_shape(obj,delta=1.5)` | 向此配方的局部网格添加Basis和一条预设释放shape，默认值零，返回release key。选择区依赖固定原点/尺度，不是任意卡扣自动变形或力学模拟。 |
| `build_frame_diy.setup_scene(parts,card,display,out,render_stills=True)` | 明确对象和变换→展示场景、可选图片及scene.blend；调用者先验证输出路径。 |
| `frame_diy_runtime.prepare_paths(*,output,raw_inputs=None,derived_inputs=None,work=None)` | 无写入路径预检，返回解析后的根目录与输入字典。原始输入必须是文件且在输出/工作树之外；派生输入可在输出树内继续分阶段工作。 |
| `frame_diy_runtime.paths_overlap(a,b)` / `require_distinct_outputs(inputs,outputs)` | 前者纯路径等同/祖先关系判断（现有符号链接会解析）；后者在写入前拒绝源/输出文件别名。不是并发符号链接安全沙箱。 |
| `frame_recipe.validate_recipe(config)` / `heightfield_io.load_heightfield(path,key)` | 前者返回有限范围配置新字典；后者只读NPZ、禁pickle、要求显式二维实数归一化数组，返回独立数组副本。错误抛ValueError/FileNotFoundError等，不改原件。 |
| `frame_diy_runtime.timed_stage(...)` | 对选定实际执行块追加JSONL成功/失败/中断和时区/monotonic计时；调用者先验证log目录。只有进入的本地阶段才有记录，不能冒充全部业务阶段遥测。 |
| `frame_diy_scene.load_flat_parts(source)` | 读取同目录measurements与flat native，要求四角色各一对象、单位变换、两释放key完整；归零并更新依赖图，返回parts/config。拒绝display scene与缺角色，不保存输入场景。 |
| `export_diy_flex.export_pressed(*,source,output)` | flat native→locking_ring/stand两件pressed STL，仅验证用途。逐对象设置/更新/导出，finally恢复key零；返回文件记录，不改原native。 |
| `make_diy_coupons.run(*,source,output)` | flat native→6真实接口裁切件+6燕尾配合档位件及manifest/coupons.blend；返回12记录。自由态原件不改，试片保持装配坐标以便数字配对；另按正式件生成打印方向。 |
| `check_diy_interfaces.solid(path)` / `inspect_interfaces(*,source,output)` | 前者读取非空binary STL并构建正体积Manifold；后者读四制造件+两pressed件与measurements，对固定装卸路径、自由/按压差异和实体止挡写JSON，返回passed。故意被挡动作的交体是保持证据，与可行路径零交体分别记录。 |
| `check_diy_coupons.inspect_coupons(*,source,output)` | 12件manifest和实际STL→三裁切对名义姿态、三燕尾档位完整离散滑入检查；返回JSON字典，CLI按passed退出。空/缺件失败；拓扑与配对检查都必须通过。 |
| `prepare_diy_print.orient(obj,flip)` / `run(*,source,coupons,output,render_layout=False)` | 前者按对象原始世界变换旋转并落台，返回装配世界米→打印世界米矩阵；后者读flat native与12试片native/manifest，将四件与12试片另存manufacturing/parts与coupons并写方向记录，可选排布图/native。不改变装配STL。 |
| `check_diy_manufacturing.inspect_manufacturing(*,source,output,tolerance_mm=0.00002)` | 构建根目录→严格16件制造清单、源与制造拓扑、刚性矩阵/落台、逆变换顶点双向误差与体积比较；返回并写JSON。精度阈值仅用于float序列化，不是打印公差。 |
| `check_diy_support.check(source,output)` | 重新导入五角色静态GLB，按四机械件同一实体PLA密度积分重心，纸卡质量排除，按真实接地点求支撑多边形/余量；返回JSON与passed。不是含填充率、载荷、滑动或实物倾覆测试。 |
| `animate_frame_diy.assembly_state(frame)` / `ease(f,a,b)` | 纯计算：帧号→完整装拆/换片/复位状态或有界缓动，不写场景。 |
| `animate_frame_diy.run(*,source,output,frames=None,render_stills=True,render_animation=False)` | 未动画display scene和同目录measurements→真实五角色完整289帧/12fps动作、装配native、单动作GLB、爆炸GLB、时序/镜头报告及可选图片/完整PNG序列。形变是预设几何位移，不是受力模拟。 |
| `animate_frame_diy.merge_scene_animation(path)` | 校验同一GLB中多个动作的通道无冲突后合并为一个同步clip，覆盖显式派生GLB，返回动作/通道数量；不改采样时刻。 |
| `check_diy_animation.mesh_roles()` / `pose_bounds(objects)` / `inspect_animation(*,source,native,output,tolerance_mm=0.001)` | 前两项从当前Blender场景要求完整五角色、计算真实求值网格世界包络；检查入口依次读取native与全新GLB，验证packed图片与无链接库、单动作8通道、289帧/12fps时间域，并比较17个对应时刻的包络。时刻使用源frame/fps与导入帧率换算，不假定时间零点。返回JSON与passed；不是逐顶点或连续扫掠验证。 |
| `run_diy.run(...)` / `executable(value)` | 前者验证路径/配置后按stage编排独立Blender/Python子进程及可选FFmpeg，返回阶段结果；后者只解析现有可执行文件。日志和计时在显式work，新attempt保留前次，不收费。 |

此分支的build入口在任何目录写入前校验原输入/配置/输出，拒绝技能目录本身、内部与其祖先输出，并拒绝输出或work树覆盖原始NPZ/图片/配置。派生阶段只允许明确生成的新文件，不能覆盖输入自身；可在同一派生目录重放同名输出，但每次运行日志使用不同attempt。中途失败不提供文件事务回滚。普通Python需要本包requirements，Blender使用自己的匹配ABI依赖。

制造STL的shape key值必须先全部置零，再更新依赖图后导出。全新会话应检查正式STL与自由态对应、与pressed确有位移；仅有不同文件哈希不足以证明正确形态。试片母体不得封住公件底座的进入空间。检查器的固定采样只能证明所列姿态/变形下的几何关系，不能自动证明手指力、连续接触弹性、PLA疲劳、支持可移除或实物抗滑。

配方由本工作流 [frame_recipe.py](../scripts/frame_recipe.py) 维护；高度场输入通过 package.json 物化 relief-map 的单一实现。

GLB 合并算法唯一源为 [glb-clips 契约](../../.dependency-glb-clips/references/contract.md)，通过 package.json 物化；本地函数保留原片段名称和返回字段适配。

姿态/求值公共能力按 [motion-check 契约](../../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

试片公共实现见 [fit-coupon 契约](../../.dependency-fit-coupon/references/contract.md)，通过 package.json 物化。既有报告字段保留；新增配对记录中的 physical_test=not_run 仅表示尚无实际反馈。

## 支承核心与配方适配

两套支承检查物化 [support-check 核心](../../.dependency-support-check/references/contract.md) 的质量积分、合重心、接触凸包和边距。标准配方保留对象子串、木板 0.75/主体 1.24 g/cm³；DIY 保留五角色预检、排除纸张、四机械件 1.24 g/cm³。两者继续使用新导入 GLB 的原始世界三角形、米转毫米、z < 0.02 mm 接触点与 XY 五位小数量化，报告字段不变；零体积/无接触/退化支承明确报错。核心改为 float64 相对原点积分，最后数位允许浮点差异，不能据此放宽实际支承验收。

标准和偏心圆口配方的面积灯复用 [model-preview](../../.dependency-model-preview/references/preview-atoms.md) 的 area_light；毫米换算、目标高度、DISK 形状及原灯光参数保留在本配方。构造函数不改变活动对象/选择。
