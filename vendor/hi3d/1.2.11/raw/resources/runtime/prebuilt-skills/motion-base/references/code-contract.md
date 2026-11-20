# 本地代码契约

先遵守 [显式本地执行契约](../../.dependency-run-tools/references/runtime.md#显式本地执行) 的物化导入、状态传参、文件/场景副作用和失败传播约定。依赖见 `requirements.txt`；本包 `main(argv=None)` 解析/调度，`execute(...)` 是有副作用的阶段，不能当作任意模型自动转换 API。

本地阶段允许覆盖同名派生产物，进程不读取 Hi3D 凭据或发网络请求。不使用 `python -O`，本包几何有效性检查含 assert；单位和品类输入限制见下文。

单位：标准源GLB由显式目标高度归一化，NPZ/CSG/二进制STL坐标为毫米，Blender/GLB为米。STL本身无单位标签，交付说明须写明毫米。可视贴图和几何原件不互相替代。

## 可独立组合的核心

- `solid_tools.Source(npz_path)`：读取`vertices[N,3]`、`faces[T,3]`、逐角`uv[T,3,2]`、`material_index[T]`，建立有效Manifold；无效拓扑失败。`Source.write(solid,path,translation)`写NPZ并返回体积/外廓/来源面数，保留原面UV，新增面材质索引为-1。`cube`/`cylinder`纯计算返回实体；`stl`/`write_solid`仅负责明确路径导出。
- `diy_snap_geometry.ring_solid(profile,n)`：从显式径向轮廓构造回转实体。`wheel(c,clearance_offset)`、`pin(c)`、`socket(c,clearance_offset)`、`release_tool(c)`分别返回轮、肩销、配对固定座、释放工具Manifold；`c`为runtime所述完整配置，坐标毫米，函数不写文件。
- `compressed_mesh(s,c,delta)`：返回预设双叉内收后的Manifold，不是材料应力解；`insertion_delta(c,shift)`给出示意装入所需压缩量。调用者须检查实体有效性、孔壁交集和全装配路径，不能把预设变形称为力学求解。
- `build_diy_solids`中的`pair`、`maxshift`、`writeprint`分别执行带显式checks累积器的碰撞记录、轴向极限二分、指定变换的打印导出。`execute(namespace)`是限定标准车输入→10正式件+试片/工具、NPZ、config/measurement的文件适配器。
- `check_diy_interface.execute(namespace)`回读真实打印件核对保持/转动/释放路径；`check_diy_motion.execute(namespace)`基于fresh-import保存的逐帧信息核对轮转、装入与变形。空网格/无效实体应先失败，不能以零交集通过。
- `build_diy_scene.execute(namespace)`读取源scene材质及高模、几何NPZ，生成静态/爆炸/装配native和同步GLB；网页高模副本的cache由调用者传入。`inspect_diy_exports.execute(namespace)`重新导入实际导出；`render_diy_frames.execute(namespace)`只渲指定场景/帧段。
- 标准路线的`prepare_source.execute([input,prepared,height_mm])`、`build_solids.execute([prepared,out,config])`、`build_scene.execute(["05",prepared,out,work])`是顺序阶段适配器，输入数组按上述顺序传；不能在导入时执行。`check_support.execute(case_dir)`计算实心同密度打印件体积重心；不代表填充件真实质量。

`run.py`组合标准四轮车；`run_diy.py`组合限定DIY车。完整流程还需用户目标的调研/概念、产品说明/BOM和网页，由执行者按SKILL继续，CLI不会自动发布。

## 模块与公开边界索引

此索引便于定位完整签名；带`execute`的模块是相应文件/场景阶段，`main/build_parser`为CLI层。原子函数的参数直接可检查其签名，不要求先执行CLI。

| 模块 | 函数/类 |
|---|---|
| `build_diy_scene.py` | `web_export`, `still`, `ease`, `build_parser`, `execute`, `main` |
| `build_diy_solids.py` | `sha`, `good`, `readstl`, `place`, `writeprint`, `savepart`, `pair`, `maxshift`, `build_parser`, `execute`, `main` |
| `build_scene.py` | `loadmesh`, `prep`, `setup`, `web_export`, `frames`, `ease`, `execute`, `main` |
| `build_solids.py` | `safest`, `execute`, `main` |
| `check_diy_interface.py` | `load`, `check`, `build_parser`, `execute`, `main` |
| `check_diy_motion.py` | `build_parser`, `execute`, `main` |
| `check_rolling.py` | `execute`, `main` |
| `check_support.py` | `execute`, `main` |
| `detail_views.py` | `execute`, `main` |
| `diy_snap_geometry.py` | `ring_solid`, `dsolid`, `wheel`, `pin`, `socket`, `compressed_mesh`, `insertion_delta`, `release_tool` |
| `encode_review.py` | `build_parser`, `execute`, `main` |
| `fresh_review.py` | `execute`, `main` |
| `glb_bounds.py` | `inspect` |
| `inspect_diy_exports.py` | `sha`, `inventory`, `build_parser`, `execute`, `main` |
| `lifestyle.py` | `execute`, `main` |
| `native_dependencies.py` | `execute`, `main` |
| `prepare_source.py` | `execute`, `main` |
| `render_diy_frames.py` | `build_parser`, `execute`, `main` |
| `render_frame_chunk.py` | `execute`, `main` |
| `render_video_chunks.py` | `build_parser`, `execute`, `main` |
| `run.py` | `run`, `build_parser`, `execute`, `main` |
| `run_diy.py` | `sha`, `run`, `blender`, `build_parser`, `execute`, `main` |
| `solid_tools.py` | `Source`, `write_solid`, `cube`, `cylinder`, `stl` |
| `stage_cli.py` | `StageFinished`, `_finish_stage`, `cli_arguments` |
| `studio_core.py` | `reset`, `mat`, `tag`, `apply`, `smooth`, `cube`, `cyl`, `uv`, `tube`, `bar`, `empty`, `parent`, `boolop`, `cutbox`, `hole` |
| `studio_preview.py` | `stage`, `camera`, `render`, `export`, `save`, `animate_video` |
| `studio_print.py` | `stl` |
| `studio_audit.py` | `bounds`, `metric` |
| `studio_source.py` | `source` |
| `validate_stl.py` | `inspect_binary_stl`, `main` |

## 写入前路径边界

主入口的保护对象、配置位置和失败留存见 [本工作流运行说明](runtime.md#写入前路径边界)；路径比较与通用预检边界由 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 唯一维护。独立文件适配器仍须按自身契约调用。

## 媒体调用边界

`build_parser()` 默认 `no_video=True`；`--render-video` 显式设为 False，旧 `--no-video` 仍可用，二者同时出现会在执行前拒绝。默认流水线保留静态图片和 GLB 动作检查，跳过帧渲染/编码，不要求 FFmpeg。只有视频分支实际启动时才需要编码器。`build_scene.frames` 在环境变量未指定时也跳过连续帧；本包显式批量渲染入口仅供已请求的视频追加。

GLB 合并算法唯一源为 [glb-clips 契约](../../.dependency-glb-clips/references/contract.md)，通过 package.json 物化；本地函数保留原片段名称和返回字段适配。

来源阶段的规范化由 [source-prepare](../../.dependency-source-prepare/references/code-contract.md) 唯一维护，来源检查图由 [model-preview](../../.dependency-model-preview/references/source-views.md) 提供；工作流物化两者必需模块，保留原位置参数及跳过视图行为。

支承阶段通过 [print-export](../../.dependency-print-export/references/code-contract.md) 的 decode_stl 读取严格长度的二进制 STL，按原毫米坐标保留几何；重心/合成/边距分别复用 [support-check](../../.dependency-support-check/references/contract.md) 的 mass_properties、combine_mass、signed_margins。它只接受已通过实际 STL 闭合/绕序验证的打印件；标准 runner 先运行 validate_stl。仍使用全部打印件均质实心、排除金属轴/紧固件的假设，内部相同的合成密度只用于体积加权，不作为实物质量报告。

保留每件哈希/有向体积/重心、组合重心、轮心矩形及 X/Y 两轴最小裕量字段；四元体积分以局部均值改善数值稳定性，末位舍入可变化。空件集、截断/非有限/塌缩 STL、零/负体积、退化接触域和非严格正裕量显式失败，成功才写 support-centroid-check.json。轮宽、填充、真实载荷、抗推倒和滚阻仍未由此证明。

标准 runner 的 JSON 预检和本地子进程复用 [run-tools](../../.dependency-run-tools/references/local-runtime.md)；路径策略见上面的运行说明。子进程继承原四个显式环境键并保留视频/来源视图/静态图控制，流式输出，非零退出仍抛 CalledProcessError，父级异常清理直接子进程。阶段图、配方标识、变体顺序和本品类检查仍在本工作流。

网页预览的副本、减面、缩图和失败恢复复用 [model-preview 的网页派生契约](../../.dependency-model-preview/references/web-derivative.md)；本流程保留对象选择、300000 面/2048 像素预算与动画名称。

已有场景的帧执行复用 [Blender 帧渲染](../../.dependency-blender-tools/references/render-scene.md)，本流程保留帧段、引擎、fps、尺寸与命名策略。

资产回读的公共载入和测量按 [mesh-audit 场景测量](../../.dependency-mesh-audit/references/scene-measure.md) 组合；本工作流保留文件筛选、采样帧、空对象策略与原报告字段，使用 package.json 物化的共享函数。回读入口直接接收已有资产，不触发上游生成或建模，也不缓存旧回读报告。

`inspect_diy_exports.execute` 读取 GLB JSON 时复用 [glb-clips.read_glb](../../.dependency-glb-clips/references/contract.md) 的完整容器校验；不在检查阶段合并动画。原 `clips` 名称/通道报告、部件 ID、单片段要求、逐帧矩阵/形变、native 打包贴图与真实回读图保持在本脚本。截断或非对齐尾块明确失败；容器可读不代表运动、碰撞或制造通过。
