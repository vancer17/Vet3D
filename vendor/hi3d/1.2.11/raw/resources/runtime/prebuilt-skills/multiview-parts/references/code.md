# 脚本接口

## 任务配置

`scripts/run.py` 是统一 CLI，委托 `parts_pipeline.py` 的唯一实现；直接 Python 调用仍使用 `parts_pipeline`。脚本读取 JSON，顺序执行已审阅的本地 Python 模块，再按 `parts` 的顺序排列。相对路径以 JSON 所在目录为基准。先将 [job.json](../assets/example/job.json) 和 [model.py](../assets/example/model.py) 一起复制到包外任务目录；它们只演示接口，不是用户参考图的建模结果。

| 字段 | 契约 |
| --- | --- |
| `name` | 必填，1–64 位字母、数字、下划线或连字符，首位是字母或数字；用于场景与文件命名 |
| `modules` | 必填，非空 `.py` 路径数组；按顺序加载，每个模块导出 `build(ctx)` |
| `parts` | 必填，非空有序数组；每项恰好为 `{ "id": "标识", "label": "显示名" }`；id 唯一，命名限制同 name |
| `palette` | 必填，将材质键映射到六位 sRGB 十六进制色，允许前导 `#` |
| `axis` | 可选，`X`（默认）或 `Y`；此 runner 固定 Z 向上 |
| `gap` | 可选，部件求值包围盒间距，有限非负数，默认 `0.5` 个场景单位；按任务尺度覆盖 |
| `output_dir` | 可选，默认 JSON 同级 `outputs/`；必须位于 skill 包外，每次新建 `name-attempt前10位/`，不覆盖已有结果 |
| `exports` | 可选，`whole` 和 `parts` 两个布尔字段，均默认 false；只在 `deliver` 模式生效 |

其余顶层字段会被拒绝；把参考路径、尺寸判断、角度与造型说明保存在任务规格中。类别与实体部件不同：左臂、右臂可同属“手臂”，但 `parts` 中是两个 id。需要组内相邻时，在数组中连续列出。

普通 Python 可仅检查配置、文件存在与模块语法：

```bash
python3 "$SKILL_DIR/scripts/run.py" "$TASK_DIR/job.json" --check
```

`--check` 不导入 `bpy`，不执行模块，不创建场景或输出目录。`config_valid` 只表示配置和语法通过，不表示建模已执行或 `build` 运行成功。

`--describe` 无需任务配置，输出本工作流的入口、模式、报告版本及真实函数签名，便于调用分析；这不是对其他 skills 格式的推断。`--help` 也无需 Blender。位置参数与旧 `--job` 二选一；`--mode preview|deliver` 保持兼容。`--task-id` 显式指定任务标识，缺省按 job 的绝对路径生成稳定 UUID；每次新建 attempt_id。重跑时传 `--previous-attempt-id` 关联上次报告，沿用 task_id；这些标识不提供几何缓存或阶段断点恢复。

Blender 中的直接调用：

```python
import importlib.util
from pathlib import Path

script = Path(SKILL_DIR) / 'scripts' / 'parts_pipeline.py'
spec = importlib.util.spec_from_file_location('parts_pipeline', script)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
report = pipeline.run_job(Path(TASK_DIR) / 'job.json', mode='preview')
```

`SKILL_DIR`、`TASK_DIR` 由当前任务显式设置。GUI 桥接时将 `run_job` 放入返回 `None` 的一次性 timer 回调即可；命令行见 [运行说明](runtime.md)。

## 建模模块

每个模块定义 `build(ctx)`，返回值忽略。模块用 `ctx.part(id, label)` 登记部件集合，通过共享 helper 创建对象；配置 id 与登记 id 必须完全一致。左右件分开登记。模块不保存、不导出、不渲染、不改偏好，不操作其他场景。文件加载本身会执行 Python 代码，因此只运行本任务编写并检查过的模块；此 runner 不是不可信代码沙箱。

所有部件在统一建模坐标中创建；建议各部件自身 X/Y 居中、底部 Z≈0，由规格定义精确原点。不要在模块中把部件预先摆成整排。根对象由 runner 创建，初始在世界原点；单件 GLB 使用该原点，保留模块的局部坐标，不再次按几何自动居中。

同一 Object 不得属于多个部件；父子关系必须局限于本部件。对象可共享 Mesh 数据，但需要独立编辑几何时复制 data。runner 拒绝未登记对象、跨部件父级、共享 Object 和空几何。支持普通 Mesh 与 Curve，不处理实例化 Geometry Nodes、骨骼动画、文字或体积；这些输入需任务专属适配并另行验证。

## 原子函数与副作用

| 入口 | 输入 → 输出；副作用与失败 |
| --- | --- |
| `load_job(path)` | JSON 路径 → 解析后的配置；读取 JSON 与模块源文件，AST 语法检查，不执行模块；不合法则抛错 |
| `layout_offsets(bounds, axis, gap)` | 按顺序的 `(min_xyz, max_xyz)` → 根平移数组；纯计算，底部对齐 Z=0、沿轴整排居中，非排列轴居中 |
| `import_file(path)` | 本地脚本 → 已执行模块；仅用于已审阅代码，异常传给调用方 |
| `build_modules(ctx, paths, records)` | 按顺序执行模块，在显式 records 列表保存已尝试模块的结果；异常或中断保留记录并继续抛出 |
| `validate_part_ownership(scene, collections, expected_ids)` | 检查部件 ID、对象归属与父级，返回 ID→集合；只读，不创建几何 |
| `create_part_roots(bpy, collections, ordered_parts)` | 为每个部件创建根并保持子物体世界变换，返回 `(集合, 根)` 列表 |
| `apply_layout(bpy, entries, ordered_parts, axis, gap)` | 计算求值边界、移动根、返回部件清单；只变换本次根对象 |
| `part_bounds(collection, depsgraph)` | 集合与依赖图 → 求值后世界包围盒；读取 Mesh/Curve，几何为空则失败 |
| `save_scene(bpy, scene, path)` | 保存一个任务场景并核对文件签名；不改用户当前工程路径 |
| `export_glb(bpy, path, entries, local)` | `(集合, 根)` 列表 → 文件签名记录；创建求值网格副本导出，Curve 在副本中转 Mesh，恢复场景并清理临时副本 |
| `export_part_files(bpy, directory, ordered_parts, entries)` | 逐件导出并逐个 yield 已验证文件；后件失败时已产出的记录可保留 |
| `restore_context(bpy, scene, view_layer)` | 恢复调用前场景与视图层，动作不依赖日志写入成功 |
| `verified_file(path, kind)` | 文件与 `blend/glb` → 路径、字节数与状态；验证文件签名，GLB 另检查长度、JSON 块与非空 meshes；不做视觉或完整加载验证 |
| `run_job(path, mode, *, task_id=None, previous_attempt_id=None)` | 编排上述阶段，返回报告；创建唯一输出目录、自动计时、恢复原场景，普通失败返回 failed；中断记日志后原样抛出 |
| `main(argv)`、`describe()` | 参数适配/接口发现；不实现几何算法，普通预检和帮助无需 `bpy` |

`run_job` 要求 Blender 的 window 上下文和 Object Mode；不擅自退出用户 Edit Mode。保留生成的任务场景以便检查，失败也保留已创建内容和报告，不做全局清场。通过 `bpy.data.libraries.write` 将任务场景另存为独立 `.blend`，不改变用户当前工程路径；它不自动在界面打开所存文件。用户原场景中的选择不参与建模或导出。

配置错误在创建产物目录前抛出，CLI 输出错误 JSON 并非零退出。缺少 `bpy`、Object Mode 不合适或运行阶段失败时，已创建的报告记录具体失败；不合适的环境不会创建模型场景。重跑使用新目录，需要对照原记录，不能把旧产物当新结果。`KeyboardInterrupt` 等中断在写入阶段/报告后继续抛给直接调用方，CLI 中键盘中断返回 130；普通失败为 1。Blender 外层还须设置 `--python-exit-code 1`。

### 报告 schema 2

| 字段 | 调用方解释 |
| --- | --- |
| `schema / skill / task_id / attempt_id / previous_attempt_id` | 版本、能力与任务/尝试关联；不要从文件名猜状态 |
| `execution_status` | `running / completed / failed / interrupted`，用于统一判断脚本执行 |
| `status` | 保留旧成功值 `preview_ready / delivered` 及中间 `saved`；失败/中断为 `failed / interrupted` |
| `modules / parts / artifacts / exports` | 实际模块结果、部件变换与边界、已确认文件、导出状态；早期失败可能没有 parts |
| `checks` | `structure`、`file_signatures`、`roundtrip`、`visual` 分开记录；自动流程不做回读或视觉验收 |
| `visual_review` | 保留旧 `not_performed` 字段；不能凭 completed 改成通过 |
| `timing / timings_path / timing_summary_path / timing_scope` | 阶段数据、日志位置、覆盖范围，详见 [计时契约](timing.md) |
| `error / error_type / cleanup_error / timing_error` | 实际错误；清理或统计失败记录阶段/类型，已生成文件仍保留 |
| `context_restore` | `completed / failed / not_required`，与统计写入结果分开；日志失败不阻止恢复动作 |

旧调用参数、`run_job` 名称与成功 status 保留；新增 schema、执行状态、检查与统计字段。之前没有统计的旧 report 不补造时间。文件签名通过不等于可重新打开、视觉或装配通过。

`preview` 即使配置启用 exports 也全部跳过。`deliver` 只导出为 true 的项目；两个标志均 false 时只保存。逐件导出根变换为单位矩阵，整排保留布局；两者都只包括登记部件，修改器烘焙到导出副本网格，原工程可编辑几何保留。无相机、灯光、标签或地台生成逻辑。

## 几何 helper

`scripts/geometry.py` 在 Blender 中加载，提供 `Context(scene, palette)`，颜色转为线性空间，材质节点按类型查找。默认材质 Roughness=0.5、Metallic=0；按图需要时通过 `ctx.mat` 调整，不能把该值当作参考物材质结论。以下位置、长度均为 Blender 场景单位，旋转为弧度。

| 方法 | 参数与结果 |
| --- | --- |
| `part(name, label)` | 新集合；记录稳定 `part_id` 与显示标签，同一 Context 禁止重复 id |
| `material(name, hex, rough=.5, metal=0)` | 新 Principled 材质；可注册到 `ctx.mat` |
| `add(object, name, material_key, collection, smooth=False)` | 将刚创建对象移到指定集合、赋材质；只对本任务新对象使用 |
| `box(name, pos, dims, mat, coll, bevel=.04, rotation=None)` | 立方体，应用尺寸缩放；按需倒角 |
| `ellipsoid(name, pos, scale, mat, coll, segments=40, rings=24)` | UV 球缩放为椭球，应用缩放 |
| `cylinder(name, pos, radius, depth, mat, coll, axis='Z', vertices=48, bevel=.02)` | 沿 X/Y/Z 的柱体 |
| `tube(name, a, b, radius, mat, coll, vertices=32)` | 两个不同端点间的柱体 |
| `mesh(name, vertices, faces, mat, coll, bevel=0)` | 按顶点/面创建网格并重算法线；输入需形成所需表面 |
| `poly(name, coords, y_front, depth, mat, coll, bevel=.02)` | 将 XZ 简单多边形沿 Y 挤出；复杂凹轮廓需检查拓扑 |
| `line(name, points, radius, mat, coll)` | 有厚度的折线 Curve；导出副本转 Mesh |
| `torus(name, pos, major_radius, minor_radius, mat, coll, axis='Y')` | 沿指定轴的圆环 |
| `bevel(object, width=.04, segments=3)` | 添加倒角与 Weighted Normal 修改器 |
| `apply_all(object)` | 应用对象的修改器；改变任务场景选择，失败抛错 |
| `boolean_difference(target, cutter)` | 应用修改器并做差集，删除本任务的 cutter；只用于本任务拥有的对象 |

所有 helper 是造型原语，不包含从像素推断几何的算法；倒角尺寸、分段数和曲线半径按任务尺度选取。一般输入需有限坐标、正尺寸、有效面索引和合法多边形；复杂几何仍需 Blender 实际执行与视觉检查。

基础形体复用物化的 [shape-build 原语](../../.dependency-shape-build/references/primitives.md)，网格链接委托 [blender-tools](../../.dependency-blender-tools/references/scene-io.md)。保留本入口毫米/场景单位换算、集合、曲线/网格类型、材质、倒角与法线 profile；品类形状仍由此工作流编排。
