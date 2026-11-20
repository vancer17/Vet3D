# 原子接口与 CLI

本地运行代码在物化后的工作流包 `scripts/` 中组合，共享实现来源由 package.json 声明，不从相邻 skill、仓库 `tools/` 或作者机器导入。Python 纯计算仅用标准库；Blender 函数由 Blender 内置 Python 执行。自行编排时将**本次物化后工作流包的** `scripts` 路径加入 `sys.path` 后显式导入，不使用通配符导入。

## 入口

`run.py` 不执行生图、Hi3D、语义分盖或完整产品设计，只对已明确的几何/场景运行三种本地阶段。下面的 `BLENDER`、`SKILL_DIR`、`RUN_DIR` 和输入文件均由当前环境提供，不是固定机器路径。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- threads \
  --spec "$RUN_DIR/thread-spec.json" --out "$RUN_DIR/thread-pair" --task-id local-design

"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- check \
  --input "$RUN_DIR/closed-assembly.blend" --spec "$RUN_DIR/check-spec.json" \
  --out "$RUN_DIR/assembly-check" --task-id local-design

"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- render \
  --input "$RUN_DIR/product-studio.blend" --spec "$RUN_DIR/render-spec.json" \
  --out "$RUN_DIR/hero-render" --task-id local-design
```

每次 `--out` 必须是包外不存在的新目录；拒绝覆盖，不修改输入文件。`--previous-attempt-id` 关联前次尝试。生成、检查及渲染均保存 `report.json` 和追加式 `timings.jsonl`；退出成功只表示阶段执行完毕，`quality_status=not_tested` 要求执行者继续完成整体验收。检测到碰撞时质量为 `failed`，CLI 非零退出。异常保留失败报告及后续跳过记录。

`threads` 输出一对同轴螺纹件的 `threads.blend` 和 `threads.glb`，几何从毫米实际换算成米。生成时的拓扑报告单位仍为毫米。此入口不自动将螺纹并入艺术壳，也不默认认定配合通过。

## 参数

下面仅是本地合成几何示例，不是瓶口规格或制造默认值：

```json
{
  "thread": {
    "root_radius_mm": 12, "depth_mm": 0.6, "pitch_mm": 3,
    "crest_half_mm": 0.2, "flank_half_mm": 0.8,
    "radial_clearance_mm": 0.25, "axial_relief_mm": 0.15,
    "phase_mm": 0, "hand": 1
  },
  "male": {"low_mm": 0, "high_mm": 9, "wall_radius_mm": 9, "lead_mm": 0.5},
  "female": {"low_mm": 0, "high_mm": 10, "wall_radius_mm": 15},
  "resolution": {"segments": 128, "rows_per_pitch": 48}
}
```

`Thread` 除 `phase_mm=0`、`hand=1` 外均需显式给定。尺寸必须有限，根半径/牙高/螺距/径向间隙为正；`0 ≤ crest_half_mm < flank_half_mm`，`flank_half_mm + axial_relief_mm < pitch_mm/2`。`hand=1/-1` 为右/左旋。此实现只支持单线螺纹。

每件 `low_mm/high_mm` 是闭合状态下的局部 Z 范围，后者须大于前者。公件 `wall_radius_mm` 是内孔半径，须小于根半径；母件则是外壁半径，须大于槽底最大半径。`lead_mm` 默认 0，只降低公件两端牙高，不能大于轴向长度的一半。`segments` 默认 128（至少 16），`rows_per_pitch` 默认 48（至少 8）；单件上限两百万顶点，解析间隙不保证粗采样网格也可配合。

已有装配的检查配置：

```json
{
  "frame": 1, "bodies": ["Bottle body"], "caps": ["Cap", "Cap gasket"],
  "center_mm": [0, 0, 100], "axis": [0, 0, 1],
  "pitch_mm": 3, "hand": 1, "unit_mm": 1000,
  "angles_deg": [0, 30, 75, 120, 360, 720, 1080, 1440]
}
```

对象名、闭合帧、轴线和采样位置来自当前工程。`unit_mm` 是**输入世界坐标每单位的毫米数**，默认 1；实际米制场景必须用 1000。`center_mm` 始终是毫米世界坐标；轴会归一化。角度列表从 0 开始，仅支持使位移非负的旋出方向；执行者按真实啮合长度和装饰净空选择退出姿态，不把示例列表作为通用放行标准。检查会快照所选闭合帧的求值几何并正确处理层级/缩放，不改原对象或它们的动画。

已有相机、灯光和材质的渲染配置：

```json
{
  "frame": 1, "camera": "Camera", "objects": ["Bottle body", "Cap"],
  "width": 2400, "height": 3000, "samples": 128,
  "device": "AUTO", "fit": true, "margin": 0.05
}
```

`width/height/samples/frame` 必填；设备默认 AUTO，尝试当前可用 GPU 并明确记录 CPU 回退。可显式指定 CPU、METAL、OPTIX、CUDA、HIP、ONEAPI；显式 GPU 不可用时报错。`fit` 默认 false，只做投影范围检查；为 true 时自动居中和缩放独立正交相机。`margin` 是各边留白比例，默认 0.05，须在 `[0,0.45)`。不修改艺术配色、光照或曝光，不自动把任意模型摆成摄影棚。

## 模块与契约

| 模块 | 可复用能力与副作用 |
| --- | --- |
| `geometry.py` | `Thread` 校验牙型；`thread_radius` 给出连续包络；`screw_lift` 给出同一螺距关系；`threaded_ring` 返回闭合网格；`profile_points/profile_radius/revolved_solid/profile_volume_ml` 校验、插值、生成回转负体积与计算几何容积。均不读写文件或导入 Blender。 |
| `blender_ops.py` | `mesh_object` 创建对象；`world_copy` 求值变换/修改器、转换毫米并只焊接完全相同坐标的 UV 拆点；`discard` 清理临时对象/孤立网格；`topology/require_solid` 诊断实体前提；`align_material_slots/boolean_copy` 在副本上保留材质并布尔；`screw_matrix/check_screw_path/intersection_check` 按世界轴验证整件；`point_location/probe_points/sample_radial_wall` 查询内部、腔体探针及原外壳径向距离。 |
| `motion.py` | `animate_screw` 对未绑定、无动画/约束的对象建立独立轴角父控制器并按相同螺距关键帧；`action_curves` 适配 Action 曲线访问。拒绝静默覆盖已有父级、动画或约束。 |
| `rendering.py` | `image_margin` 校验留边比例；`configure_cycles` 配置当前进程设备；`projected_bounds` 获取实际姿态投影；`fit_orthographic` 在最终画幅下居中与留边；`render_png` 按帧渲染到新 PNG 并回读像素尺寸，不保存输入工程或用户偏好。 |
| `timing.py` | `utc_now/append_event/stage/skipped` 记录包外 JSONL；阶段上下文用单调时钟，失败/中断也写终态，不保存异常正文或鉴权信息。 |
| `run.py` | 参数解析和阶段编排；`execute` 可由已有 Blender 编排器调用。`read_json/write_json/digest/new_output/meshes` 集中管理文件、只读摘要、新输出目录与对象解析。 |

`world_copy/boolean_copy` 返回毫米世界坐标网格，调用者负责清理。`boolean_copy` 的两个输入必须已在毫米世界坐标中；先前从米制输入取得的 `world_copy(...,1000)` 可直接组合。布尔不会自动证明连通或外表保护，需比较体积/分量并检查结果。

`sample_radial_wall` 只用于已校准轴为 +Z、X=Y=0 的未掏空原实体；各采样中心必须在原体内。返回最小径向余量和位置，不自行选制造阈值。`probe_points` 的点按毫米世界坐标给定，返回 inside/outside/boundary/ambiguous；边界或多射线结论不一致不能当作已验证。

`animate_screw(objects, center_mm, axis, pitch_mm, frames_angles, hand=1)` 的帧角对如 `[(1,0),(61,540)]`；场景几何使用毫米。创建后的实际姿态应与 `screw_matrix(center,axis,angle,screw_lift(...))` 乘以闭合变换一致。螺纹退出后的自由抬起另行明确连接；需要米制导出时真正缩放几何和所有动画平移值，或在米制父层上缩放整套 mm 装配，并在新场景回读确认。

## 独立验证

按入口打包约定在仓库外的新目录物化完整分发包，测试输出也置于包外；不能依赖本仓库中恰好存在的相邻实现。测试使用合成几何，不访问 Hi3D。

```bash
python3 -m unittest discover -s "$SKILL_DIR/tests" -p 'test_pure.py' -v
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/tests/test_blender.py" -- --out "$RUN_DIR/local-validation"
```

纯计算测试覆盖左右旋进给、不变量、闭合网格、容积与输入边界。Blender 测试覆盖带变换/四元数模式的配对、故意碰撞、完全包含、无效输入、布尔材质与 UV 保留、动画实际变换、导出回读、相机构图与渲染尺寸，以及 CLI 新目录和失败计时。宿主自动发现与显式调用是否验证应单独记录；脚本通过不能冒充 AI 已自动加载 skill。

姿态/求值公共能力按 [motion-check 契约](../../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

网格拓扑测量通过物化的 [mesh-audit 测量核心](../../.dependency-mesh-audit/references/mesh-measure.md) 执行；本工作流保留旧字段、单位、面积阈值与通过条件。

文件 digest 与阶段起止复用 [run-tools 本地核心](../../.dependency-run-tools/references/local-runtime.md)，本入口保留历史字段、跳过和异常传播语义。内容校验不授权重新提交远端任务。

取景和投影由 [model-preview 展示原子](../../.dependency-model-preview/references/preview-atoms.md) 唯一维护；rendering 保留 min/max 数组报告适配，固定求值网格、严格深度检查与原比例留白，产品姿态和渲染输出仍由本工作流编排。

设备选择委托 [blender-tools](../../.dependency-blender-tools/references/cycles-device.md)，本工作流仅将渲染引擎设为 Cycles，并保留 AUTO 可回退/显式 GPU 不可回退策略和原设备报告。
