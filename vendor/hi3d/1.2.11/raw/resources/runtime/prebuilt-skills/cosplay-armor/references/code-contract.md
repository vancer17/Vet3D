# 本地代码契约

先遵守 [显式本地执行契约](../../.dependency-run-tools/references/runtime.md#显式本地执行) 的物化导入、状态传参、文件/场景副作用和失败传播约定。依赖见 `requirements.txt`；本包 `main(argv=None)` 解析/调度，`execute(...)` 是有副作用的阶段，不能当作任意模型自动转换 API。

本地阶段允许覆盖同名派生产物，进程不读取 Hi3D 凭据或发网络请求。不使用 `python -O`，本包几何有效性检查含 assert；单位和品类输入限制见下文。

单位：标准源GLB由显式目标高度归一化，NPZ/CSG/二进制STL坐标为毫米，Blender/GLB为米。STL本身无单位标签，交付说明须写明毫米。可视贴图和几何原件不互相替代。

## 可独立组合的核心

- `armor_geometry.fit(z,*,FIT_SCALE,pf,zf)`：以显式剖面采样数组插值截面；`desired(z,theta,extra,*,CLEAR,FIT_SCALE,pf,zf)`返回目标截面XY。它们只计算，不读npz、不改场景。`pf`、`zf`必须同长度、Z递增，含当前身体的拟合字段。
- `mesh(name,v,f,material,*,S)`创建并返回Blender网格，毫米顶点以S=.001转米；`boolean(object,cutter,op)`应用布尔，显式改变传入对象。`solid`、`annular_liner`、`back_cutter`按传入剖面/余量/coverage生成体与开背负空间，材料/内层函数和参数显式传入。
- `inspect_source.execute([glb,inspection,height_mm,...])`归一化/焊接源、写NPZ/scene/检查，可`--skip-render`；不以照片推断真实身体长度。
- `sample_profiles.execute(configuration)`读取工作目录的两源检查结果，采样剖面；`build_armor.execute(configuration)`构造映射艺术甲片、平滑内腔、开背与真实槽；`finalize.execute(configuration)`在真实身体/壳体BVH上跨宽度采样垫/带并导出。三者共享`armor_geometry`，没有动态exec另一脚本源码。configuration包含显式work/out、长度/coverage、缩放、余量和附件条件。
- `finalize.grid_solid`、`pad`及相关采样/overlap函数可传入BVH/对象/材料单独调用；硬壳/人体余量按各Z截面，不以椭圆外包络值声称皮肤实际间隙。垫cap和织带偏移是设计输入，不是人体校准。
- `validate_assets.execute([case_dir])`fresh-import GLB/native；`validate_attachments.execute([scene,report])`实际身体↔附件↔主壳的BVH检查；`validate_stl`实际二进制STL检查。数字无交叉不证明舒适。
- `demonstrate_donning`独立穿脱路径适配器：只表示织带已解开/取下后的硬壳移除；`split_for_printer`按显式scene/Z/接口参数拆高模并保留UV；其定位榫需要整接缝胶粘，不能标全打印无胶锁止。`validate_split`检查实体/保真并组合`validate_split_surface_distance`与`validate_split_body`；新增切面需要排除在原表面距离外，但不能排除其它损失。

`run.py`依次编排两源检查、剖面、甲片、附件、STL/fresh-import验证。穿脱、长件拆分与网页是随后按任务执行的独立阶段；视频仅在交付后明确请求时追加，不谎称run.py一次完成所有业务产物。

## 模块与公开边界索引

此索引便于定位完整签名；带`execute`的模块是相应文件/场景阶段，`main/build_parser`为CLI层。原子函数的参数直接可检查其签名，不要求先执行CLI。

| 模块 | 函数/类 |
|---|---|
| `armor_geometry.py` | `fit`, `desired`, `mat`, `mesh`, `boolean`, `solid`, `annular_liner`, `back_cutter`, `save`, `check` |
| `build_armor.py` | `execute`, `main` |
| `demonstrate_donning.py` | `tree`, `build_parser`, `execute`, `main` |
| `finalize.py` | `skin`, `grid_solid`, `pad`, `overlap`, `stl`, `camera_at`, `render`, `glb`, `execute`, `main` |
| `inspect_source.py` | `execute`, `main` |
| `render_joint_details.py` | `build_parser`, `execute`, `main` |
| `render_saved_animation.py` | `build_parser`, `execute`, `main` |
| `run.py` | `sha`, `run`, `build_parser`, `execute`, `main` |
| `runtime_config.py` | `config` |
| `sample_profiles.py` | `execute`, `main` |
| `split_for_printer.py` | `volume`, `half`, `surfaces`, `boolean`, `box`, `stl`, `glb`, `build_parser`, `execute`, `main` |
| `stage_cli.py` | `StageFinished`, `_finish_stage`, `cli_arguments` |
| `validate_assets.py` | `bounds`, `execute`, `main` |
| `validate_attachments.py` | `tree`, `execute`, `main` |
| `validate_split.py` | `load_stl`, `volume_record`, `ray`, `wall_sample`, `component_metrics`, `add_functional_summary`, `main` |
| `validate_split_body.py` | `build_parser`, `execute`, `main` |
| `validate_split_surface_distance.py` | `closest64`, `build_parser`, `execute`, `main` |
| `validate_stl.py` | `inspect_binary_stl`, `main` |

## 写入前路径边界

主入口的保护对象、配置位置和失败留存见 [本工作流运行说明](runtime.md#写入前路径边界)；路径比较与通用预检边界由 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 唯一维护。独立文件适配器仍须按自身契约调用。

STL 提取/序列化复用物化的 [print-export 核心](../../.dependency-print-export/references/blender-stl.md)。保留本品类的 raw、坐标系、摆盘、精度、法线阈值与头部适配；不重新实现二进制编码。

表面树与对象对计数复用 [mesh-audit](../../.dependency-mesh-audit/references/surface-pairs.md)，使用原始世界坐标与 1e-8 场景单位 epsilon。保留对象角色、允许接触解释与离散采样范围，不按世界矩阵跨姿态缓存；护甲位移仍是移除织带后的刚体假设。

构图/相机或 GLB 输出复用 [model-preview 展示原子](../../.dependency-model-preview/references/preview-atoms.md)。保留本工作流画幅、边界 profile、材质与动画选项；临时导出对象和采样/选择状态在异常时也恢复。

来源适配器复用 [source-prepare](../../.dependency-source-prepare/references/code-contract.md) 的 normalize_source 与 [model-preview](../../.dependency-model-preview/references/source-views.md) 的来源视图；--yaw-deg、source_yaw_deg、--skip-render 和护甲灯光/相机参数保持。有限正高度与非退化检查、FILE 图片打包统一由来源核心执行；零高输入显式失败，不再生成无效来源。

护甲 yaw 现在对 glTF 四元数旋转对象同样生效；报告角度与实际几何一致。该修正会改变过去被忽略的非零 yaw 输出，已有派生来源需按原件和目标角度重新规范化。

已有场景的帧执行复用 [Blender 帧渲染](../../.dependency-blender-tools/references/render-scene.md)，本流程保留帧段、引擎、fps、尺寸与命名策略。

资产回读的公共载入和测量按 [mesh-audit 场景测量](../../.dependency-mesh-audit/references/scene-measure.md) 组合；本工作流保留文件筛选、采样帧、空对象策略与原报告字段，使用 package.json 物化的共享函数。回读入口直接接收已有资产，不触发上游生成或建模，也不缓存旧回读报告。
