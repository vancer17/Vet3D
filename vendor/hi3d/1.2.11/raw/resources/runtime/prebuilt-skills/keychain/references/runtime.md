# 参数与独立调用

本包只依赖本地 Blender 及其 Python 库；无需网络、凭据或相邻 skill。普通 Python 预检需要安装随包 `requirements.txt` 的 NumPy；Blender 通常自带 NumPy。测试用例使用合成网格，不调用生成服务。选择明确支持所选布尔求解器的 Blender；不以版本字符串代替实际能力检查。

## CLI

从任意工作目录调用。以下路径均为占位的调用参数，应换成当前包和当前任务的真实路径：

```sh
python3 /path/to/keychain/scripts/run.py --describe
python3 /path/to/keychain/scripts/run.py --check --input /task/source.glb --input-unit-mm 1000 --spec /task/attachment.json --out /task/candidate-01
blender --background --factory-startup --python-exit-code 1 --python /path/to/keychain/scripts/run.py -- --input /task/source.glb --input-unit-mm 1000 --spec /task/attachment.json --out /task/candidate-01 --task-id job-name
```

`--input-unit-mm` 必填，表示**导入后世界坐标的一单位对应多少毫米**，不是文件 UI 中显示的单位名。GLB 通常按米导入，因而通常为 1000；STL 没有单位，须据已知尺寸核实，不能按扩展名猜测。脚本先烘焙来源的世界变换，再缩放到 Blender 的米。输入必须已经具有本次需要的实体尺寸；若需缩小角色，显式按目标尺寸调整此比例或另存工作副本。

支持 `.blend/.glb/.gltf/.obj/.stl`，外部贴图和缓冲文件必须可解析。导入后只有一个候选网格时可省略 `--target`；否则明确给导入后的对象名。`.blend` 的隐藏渲染网格不作为候选。源对象存在修改器、约束、动画数据或形态键时拒绝继续，先由执行者另存求值后的静态网格副本。输入需闭合、绕序一致且朝外；断面、开放曲面、负体积、非有限坐标必须先显式处理。

`--out` 必须是包外尚不存在的目录，不覆盖来源或旧结果。`--check` 只读文件及参数，不导入场景、不检查拓扑、不创建目录。运行会修改独立后台 Blender 场景、创建输出目录；不会保存回输入路径。已有任务通过新输出目录重试，用相同 `--task-id` 和上次报告的 `--previous-attempt-id` 关联；它不是恢复已完成布尔的缓存开关。

## JSON 参数

下面仅是合成测试球体上的弯道示例，**不是角色尺寸、挂点或打印默认值**：

```json
{
  "mode": "tunnel",
  "frame": {"center_mm": [10, 30.5, 32], "normal": [1, 0, 0], "up": [0, 0, 1]},
  "major_radius_mm": 4,
  "tube_radius_mm": 1.6,
  "solver": "MANIFOLD",
  "connector": {"major_radius_mm": 4, "wire_radius_mm": 0.3, "pitch_mm": 0.7, "turns": 2.02}
}
```

| 字段 | 含义与范围 |
| --- | --- |
| `mode` | 必填：`tunnel` 环面差集形成弯道；`lug` 环面并集形成吊耳候选。 |
| `frame.center_mm` | 必填，世界毫米坐标的环面中心。 |
| `frame.normal / up` | 必填三维方向。法线非零；up 投影到环面后非零。局部轴见 [设计说明](design.md)。 |
| `major_radius_mm / tube_radius_mm` | 必填，中心线半径与管半径，有限且 `major > tube > 0`。 |
| `segments / sides` | 环面周向段数默认 160、截面段数默认 40；整数范围分别 24–1024、8–128，仅为网格精度默认值。 |
| `solver` | 默认 `MANIFOLD`；可显式指定 `EXACT`，不静默降级。两者都须验证实际结果。 |
| `audit_padding_mm` | 局部交叉检查包围盒外扩量，默认 1，非负。不是安全壁厚。 |
| `connector` | 可省略，仅生成一个带端盖的螺旋开口连接环。不是完整弹簧锁扣或链条生成器。 |
| `connector.frame` | 可显式独立设置；弯道可继承主体 frame。吊耳必须提供独立 frame，执行者需使金属环实际穿孔，通常与吊耳平面垂直。代码不自动求交点。 |
| `connector.major_radius_mm / wire_radius_mm` | 必填有限正数，中心线半径大于线材半径。 |
| `connector.pitch_mm / turns` | 必填轴向每圈螺距与圈数；螺距非负，圈数 1–4；超过一圈时螺距必须大于线径。 |
| `connector.phase_deg` | 起始角度，默认 90°；影响端头位置和穿入方向。 |

所有长度使用毫米，数值不得是布尔值、NaN 或无穷。未知顶层及 connector 字段拒绝。缺少必填字段、非法类型、无效坐标架会失败。完整金属环轴向包络包含螺距、圈数和线径；不能仅比较单根线材和孔径。闭合一圈、无间隙的模型不能作为无需变形即可装入的开口五金。

## 产物与状态

- `assembly.blend`：本体工作副本、可编辑隐藏布尔操作体及可选金属环；来源对象保留但隐藏。材质可打包时打包。不保证第三方修改器、绑定和动画可继续使用。
- `assembly.glb`：只导出本体与可选金属环；米制。
- `body_mm.stl`：只导出本体，坐标放大到毫米；STL 无材质、无单位元数据。
- `request.json / report.json`：源主文件哈希、显式参数、尝试标识、诊断与产物哈希；GLTF 外部依赖需执行者另记清单。
- `timings.jsonl / timing_summary.json`：自动处理阶段的计时，范围及人工阶段见 [统计规则](timing.md)。

退出 0 表示预检完成或候选执行完成；不是结构验收通过。脚本已检测几何失败时 `quality_status=fail`、退出 2（Blender 的 Python 退出包装可能将非零归并为 `--python-exit-code`）；其他异常退出非零。无已知失败仍为 `quality_status=not_tested`，必须完成 [验证](validation.md) 才可另写业务验收结论。已知失败也导出候选，便于检查；不得交作已通过版本。`execution_status` 独立记录运行是否完成。预检失败不创建日志；处理开始后的失败保留已完成阶段和跳过记录；强制终止可能只留下 running 事件。

## 可复用原子契约

将包内 `scripts` 的绝对路径显式加入 Python 导入路径，或从该目录导入；不依赖当前工作目录。纯函数不读写文件；Blender 适配函数只在独立后台进程使用。

| 模块/函数 | 输入 → 输出；副作用与失败 |
| --- | --- |
| `geometry.number/vector/frame/validate` | 数值、向量、参数字典 → 校验数值、右手正交坐标架或原参数；非法参数抛异常，不修改输入。 |
| `geometry.torus` | 已校验的环面参数 → 世界毫米顶点与多边形索引；无应用状态。 |
| `geometry.split_ring` | 已校验的 connector、备用 frame、采样数/截面数 → 带端盖螺旋网格；默认 512×20，采样至少 2、截面至少 3；不模拟弹性。 |
| `blender_ops.material/mesh_object` | 材质属性或毫米网格 → 新 Blender 数据/对象；当前场景中创建资源，毫米转换为米。 |
| `blender_ops.load_body` | 来源路径、目标名、毫米比例 → 烘焙世界变换的独立本体副本；打开/创建场景，隐藏来源。对象歧义、非静态输入或不支持格式失败。 |
| `blender_ops.weld_exact` | Mesh → 原位合并精确同位顶点；保留循环 UV。它会连接精确接触的独立壳，须在源体检时识别，不用近邻距离修补薄壁。 |
| `blender_ops.topology` | Mesh → 边界/非流形边、绕序不一致的流形边、分量、带符号体积及有限性；无修改，不检测全局自交。 |
| `blender_ops.apply_interface` | 工作副本、校验参数 → 隐藏操作体和可选金属环；原位布尔、三角化非三角面、加新表面材质。求解器不支持/布尔失败抛异常，原始输入文件不变。 |
| `blender_ops.world_mesh` | Object → 求值后的世界米坐标顶点/三角面；临时网格读取后释放。 |
| `blender_ops.connector_check` | 本体、可选金属环 → 表面候选碰撞、顶点距离、双方向内外抽样；无修改，缺失或歧义标为未测。 |
| `blender_ops.ray_intervals` | 本体、世界毫米起点、非零方向、最大命中数 → 顺序边界交点/法线及是否截断；不自动解释壁厚或起点内外。 |
| `blender_ops.save_exports` | 工作本体、可选环、已创建输出目录、参数 → 写 blend/GLB/STL；仅 CLI 预检保证新目录，原子调用者自行保证不覆盖。 |
| `audit.segment_hit/triangle_relation` | 毫米线段或三角形数组 → 交叉布尔或关系；浮点阈值有限，共面退化返回待查。 |
| `audit.local_crossings` | 本体、操作体、外扩毫米量 → 世界坐标局部非相邻三角面诊断；无几何修改。忽略共享顶点面对、未证全局无交叉。 |
| `run.prepare/execute/main` | 参数对象/命令行 → 预检结果或候选报告/退出码；编排以上原子能力，集中处理文件、日志与失败。`digest/write_json` 只负责哈希读取和 JSON 写入。 |

函数的“已校验参数”前提表示复用时先调用 `validate`；不能绕过后假定任何输入均安全。脚本不提供候选选址优化器、圆角自动构造、链条锁扣机构或自动渲染。执行者在业务流程中按模型实现这些部分，并记录其验证范围。

网格拓扑测量通过物化的 [mesh-audit 测量核心](../../.dependency-mesh-audit/references/mesh-measure.md) 执行；本工作流保留旧字段、单位、面积阈值与通过条件。

网格读取与临时资源统一复用物化的 [blender-tools 快照](../../.dependency-blender-tools/references/mesh-snapshot.md)。原坐标、精度、三角面前提与领域拒绝条件由此入口保留。

文件 digest 与阶段起止复用 [run-tools 本地核心](../../.dependency-run-tools/references/local-runtime.md)，本入口保留历史字段、跳过和异常传播语义。内容校验不授权重新提交远端任务。
