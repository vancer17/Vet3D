# 本地代码契约

先遵守 [显式本地执行契约](../../.dependency-run-tools/references/runtime.md#显式本地执行) 的物化导入、状态传参、文件/场景副作用和失败传播约定。依赖见 `requirements.txt`；本包 `main(argv=None)` 解析/调度，`execute(...)` 是有副作用的阶段，不能当作任意模型自动转换 API。

本地阶段允许覆盖同名派生产物，进程不读取 Hi3D 凭据或发网络请求。不使用 `python -O`，本包几何有效性检查含 assert；单位和品类输入限制见下文。

单位：标准源GLB由显式目标高度归一化，NPZ/CSG/二进制STL坐标为毫米，Blender/GLB为米。STL本身无单位标签，交付说明须写明毫米。可视贴图和几何原件不互相替代。

## 可独立组合的核心

- `fit_source.fit_vertices(vertices,width_mm,depth_mm,rear_depth_scale=1,transition_mm=5)`：有限非空Nx3顶点→变换后顶点、拟合元数据；XY按目标包络缩放，后部平滑压深，Z保留。拒绝非正尺寸、退化XY范围；不读文件、不改材质。变换可改变造型，必须实际看图判断。
- `fit_prepared_source(prepared,fitted,configuration)`：显式文件适配器，复用上函数，将`source.npz`的几何变换而保留faces/UV/material_index，写`fit-transform.json`并复制材质源blend。不会制造原本不存在的设备尺寸。
- `thin_source.thinning_parameters(configuration)`：缺省/false 返回 None，不启动减薄；true 时验证并返回显式名义内腔和两个减薄参数，缺项、非布尔开关、非有限或超界数值失败。[配置边界](runtime.md#可选外形减薄)与[设计依据](thin-wall.md)须一起使用。
- `thin_source.contract_excess(vertices, *, center, dimensions, radius, fraction, preserve)`：有限非空 Nx3 毫米顶点→新顶点、旧/新相对圆角内腔距离数组；不原位改输入。最近核心点与射线保持，以固定 0.6 mm C1 起始段收缩超过 preserve 的距离。拒绝圆角/尺寸无效、源点位于名义内腔内或边界、非有限计算。此计算不生成内腔、不改变拓扑、不证明最终网格闭合或鳍根强度。
- `thin_source.thin_prepared_source(source, output, configuration)`：显式文件适配器，要求启用开关，验证 NPZ 的顶点、三角索引、逐角 UV 和材料索引，复用上函数。先拒绝源/输出/包路径重叠、链接输出和缺失输入；通过后写新 NPZ、复制原材质 blend 并写变换摘要。faces/UV/material_index 保持，source.blend 不被谎称为减薄几何；下游从新 NPZ 重建原生工程。单 CLI 另保护配置文件免于覆盖，不读取密钥或网络。
- `solid_tools.Source`与`cube`/`cylinder`/`stl`契约同本包实现：毫米Manifold，Source.write以原面来源ID重建逐角UV，新增面独立标识。不需要导入运动底座Skill。
- `prepare_source.execute([input,prepared,height_mm])`归一化真实输入并输出NPZ/material源；`build_solids.execute([prepared,out,config])`构造艺术上下壳、精密数字设备包络、内腔和接口，检查内腔/壁厚包络逃逸。后处理union后重新切精密内腔，避免改变配合面。
- `build_solids.parse_lid_rear_clearance(value)`：None 关闭额外上盖切体；否则验证 `[dimensions_xyz,location_xyz,radius]` 的形状、有限值及正圆角核心，返回数值参数，不修改输入或场景。`execute`仅按明确参数额外裁切上盖，原下壳和设备构造不变；上壳对固定下设备的 116 个等间距开盖姿态新增为必须通过的交体检查，与已有壳对壳检查分开记录。结果仍是采样检查，不能冒充实物或连续时间保证。
- `build_scene.execute(["06",prepared,out,work])`将当前构建结果装配，生成native、静态/同步动作GLB；`review_native.execute([case_dir])`与`review_installation.execute([case_dir])`分别回读开盖/插头、取套动作与镜头/碰撞。设备参考体也必须真正开插口，不用黑色面片代替负空间。
- `fresh_review.execute(["06",out])`重新导入实际GLB；`native_dependencies.execute(out_path)`读取native图像依赖，`glb_bounds.inspect(path)`独立解析GLB节点变换与POSITION范围，返回实际包络/动作摘要。
- `render_video_chunks`按scene SHA分帧恢复；`encode_review`编码后解码；`render_frame_chunk`仅指定帧渲染。缓存只在同一源场景时复用。

已有CLI只实现分盖硬壳与名义设备运动，DIY卡笼/柔性衬/机械锁需独立新设计，不能以hardware_policy字段假装已生成。需要物理原盒试装的数据与保持/充电性能待测，数字无交叉不等于量产兼容。

## 模块与公开边界索引

此索引便于定位完整签名；带`execute`的模块是相应文件/场景阶段，`main/build_parser`为CLI层。原子函数的参数直接可检查其签名，不要求先执行CLI。

| 模块 | 函数/类 |
|---|---|
| `build_scene.py` | `loadmesh`, `prep`, `setup`, `web_export`, `frames`, `ease`, `execute`, `main` |
| `build_solids.py` | `rounded`, `parse_lid_rear_clearance`, `execute`, `main` |
| `encode_review.py` | `build_parser`, `execute`, `main` |
| `fit_source.py` | `fit_vertices`, `fit_prepared_source`, `main` |
| `fresh_review.py` | `execute`, `main` |
| `glb_bounds.py` | `inspect` |
| `lifestyle.py` | `execute`, `main` |
| `native_dependencies.py` | `execute`, `main` |
| `prepare_source.py` | `execute`, `main` |
| `render_frame_chunk.py` | `execute`, `main` |
| `render_video_chunks.py` | `build_parser`, `execute`, `main` |
| `review_installation.py` | `tree`, `execute`, `main` |
| `review_native.py` | `tree`, `execute`, `main` |
| `run.py` | `run`, `build_parser`, `execute`, `main` |
| `solid_tools.py` | `Source`, `write_solid`, `cube`, `cylinder`, `stl` |
| `stage_cli.py` | `StageFinished`, `_finish_stage`, `cli_arguments` |
| `studio_core.py` | `reset`, `mat`, `tag`, `apply`, `smooth`, `cube`, `cyl`, `uv`, `tube`, `bar`, `empty`, `parent`, `boolop`, `cutbox`, `hole` |
| `studio_preview.py` | `stage`, `camera`, `render`, `export`, `save`, `animate_video` |
| `studio_print.py` | `stl` |
| `studio_audit.py` | `bounds`, `metric` |
| `studio_source.py` | `source` |
| `thin_source.py` | `thinning_parameters`, `contract_excess`, `thin_prepared_source`, `main` |
| `validate_stl.py` | `inspect_binary_stl`, `main` |

## 写入前路径边界

主入口的保护对象、配置位置和失败留存见 [本工作流运行说明](runtime.md#写入前路径边界)；路径比较与通用预检边界由 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 唯一维护。独立文件适配器仍须按自身契约调用。

`fit_prepared_source`同样在读取/覆盖NPZ前拒绝prepared与fitted相同、互相包含或符号链接别名；不同且不重叠的已有fitted可更新，源NPZ/blend保持不变。

`thin_prepared_source`复用同一根路径保护，并在写入前拒绝固定输出名已是符号链接、多硬链接或目录的情况。单进程预检不防止其他进程随后改动这些路径；发生 I/O 失败仍可能留下部分派生产物，修复后应重跑本阶段并继续最终几何验证，不能凭目录存在判定成功。

## 媒体调用边界

`build_parser()` 默认 `no_video=True`；`--render-video` 显式设为 False，旧 `--no-video` 仍可用，二者同时出现会在执行前拒绝。默认流水线保留静态图片和 GLB 动作检查，跳过帧渲染/编码，不要求 FFmpeg。只有视频分支实际启动时才需要编码器。`build_scene.frames` 在环境变量未指定时也跳过连续帧；本包显式批量渲染入口仅供已请求的视频追加。

表面树与对象对计数复用 [mesh-audit](../../.dependency-mesh-audit/references/surface-pairs.md)，使用原始世界坐标与 1e-8 场景单位 epsilon。保留对象角色、允许接触解释与离散采样范围，不按世界矩阵跨姿态缓存。

原生动作与安装检查使用 [motion-check 姿态采样](../../.dependency-motion-check/references/scene-samples.md)，各姿态只建一次对象树；检查与逐帧构图均在成功/失败后恢复原帧和子帧。tree_cache 旧参数仍接受但不再使用，避免几何变化后误复用。

独立 Blender 回归见 [test_surface_review.py](../tests/test_surface_review.py)：合成场景完整报告、姿态恢复、网格变更与非法对象对。

构图/相机或 GLB 输出复用 [model-preview 展示原子](../../.dependency-model-preview/references/preview-atoms.md)。保留本工作流画幅、边界 profile、材质与动画选项；临时导出对象和采样/选择状态在异常时也恢复。

来源阶段的规范化由 [source-prepare](../../.dependency-source-prepare/references/code-contract.md) 唯一维护，来源检查图由 [model-preview](../../.dependency-model-preview/references/source-views.md) 提供；工作流物化两者必需模块，保留原位置参数及跳过视图行为。

标准 runner 的 JSON 预检和本地子进程复用 [run-tools](../../.dependency-run-tools/references/local-runtime.md)；路径策略见上面的运行说明。子进程继承原四个显式环境键并保留视频/来源视图/静态图控制，流式输出，非零退出仍抛 CalledProcessError，父级异常清理直接子进程。阶段图、配方标识、变体顺序和本品类检查仍在本工作流。

网页预览的副本、减面、缩图和失败恢复复用 [model-preview 的网页派生契约](../../.dependency-model-preview/references/web-derivative.md)；本流程保留对象选择、300000 面/2048 像素预算与动画名称。

资产回读的公共载入和测量按 [mesh-audit 场景测量](../../.dependency-mesh-audit/references/scene-measure.md) 组合；本工作流保留文件筛选、采样帧、空对象策略与原报告字段，使用 package.json 物化的共享函数。回读入口直接接收已有资产，不触发上游生成或建模，也不缓存旧回读报告。
