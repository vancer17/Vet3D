# 整件连接与证据强制验收

默认交付防脱成品。只研究原理、诊断中间件或用户明确要求可旋散时，可以交付标明范围的研究产物；不能省略默认要求后仍宣称防脱成品完成。`build` 是中间件，`add-stops` 是实体端部检查，`validate` 是运动检查；最终出口是本文件的 `accept`，不存在默认通过或忽略缺项的开关。

## 顺序与失败条件

1. 在 stop-job 的 `retained_motions` 中声明所有保留玩法及各自总行程。加止挡前先测相邻相对位移；不能为通过验收删掉用户要求的玩法。
2. `add-stops` 先验证 N 个有序瓣形成完整环：每条相邻无向边（含末瓣—首瓣）恰好一次，所有瓣处于同一连接分量，无非相邻边。它随后为每条接口生成舌根/承压体积及两方向各三个接触状态。
3. 针对最终文件按 [捕获与配合](capture-and-fit.md) 运行 `measure-capture`，逐侧测量倒扣、游隙、舌根、头厚、唇边与后壁，声明制造损失预算；补测端壁与三维配合间隙，生成真实导轨试片。区间文件含 `assembly_sha256` 与每瓣 `intervals_mm`，不能只拿外皮高度作为捕获区间。
4. 对每个声明玩法运行默认 `validate`，至少包含闭合、中间、全开三个状态；实际采样密度仍按几何风险选择。生成动画、重导入报告、真实剖面与播放证据，再完成下述人工/执行者审查。
5. 按 [打印交付](print-delivery.md) 实测文件大小，完成整件3MF的几何/装配回读，将导出记录与实际打印入口纳入 `reviews.assembly.artifacts`。调整过打印网格密度时，先重做本版机械和视觉检查；不能以旧高密度网格的报告为减面后的打印文件背书。
6. 组装证据索引，运行 `accept`。它重读全部最终分件检查拓扑和摘要，检查整装 STL 摘要、连接关系、报告中的原始覆盖和数值、每种玩法以及审查证据的完整性。缺失、空文件、内容变化、失败/待审查、漏件或漏玩法均非零退出，保留 `acceptance.json` 的 `passed:false` 与失败原因。文件体积是否合理及3MF实际回读由执行者负责，脚本只验证所引用文件与摘要。

```sh
python "$SKILL_DIR/scripts/run.py" accept --assembly "$TASK_DIR/stopped-01/assembly.json" --evidence "$TASK_DIR/evidence.json" --out "$TASK_DIR/accept-01" --task-id toy
```

只有输出 `passed:true` 且当前交付文件仍与其中记录的摘要一致，才能表述为“本版数字防脱验收通过”。更换实体、止挡参数、玩法声明、区间、动画或审查证据后必须重新生成相应报告并验收。失败产物不可混入通过版本。

## evidence.json 契约

所有文件引用统一为 `{"file":"相对于 evidence.json 的路径","sha256":"文件实际 SHA-256"}`，也接受绝对路径；交付包推荐相对路径。路径存在、文件非空及摘要相符均为硬性条件。JSON 报告按下面的引用读取，审查图像、视频、测量原始数据等通过 artifacts 引用。不得用空文件或自拟通过文本冒充实际证据。

| 字段 | 必需内容 |
| --- | --- |
| `schema` | `twisty.evidence.v1` |
| `assembly_sha256` | 当前最终 assembly.json 的摘要；其本身绑定全部零件、整装 STL、参数和玩法 |
| `stop_contacts` | add-stops 生成的 stop_contacts.json 文件引用 |
| `intervals` | 绑定当前 assembly 的实测区间 JSON 文件引用，须与各 validate 使用的文件一致 |
| `capture_measurement` | measure-capture 生成的 capture.json 引用；全环每高度的原始区间、两侧余量、制造预算及最小搭接门槛均通过；不接受 captured=true 替代 |
| `motions` | 每个 retained_motions 对应一行，不能为空、重复或遗漏；字段见下表 |
| `reviews` | 包含 capture、walls、sections、assembly、fit 五项审查；字段见下文 |

每个 motions 元素：

| 字段 | 含义 |
| --- | --- |
| `mode`, `travel_mm` | 与 assembly 中一项保留玩法精确对应 |
| `validation` | 该玩法默认 validate 的 validation.json 引用，purpose 必须为 retention_motion |
| `reimport` | 本版 Blender 导出的 reimport.json 引用，须绑定该 GLB 的摘要 |
| `glb` | 实际交付的该玩法动画 GLB 引用 |
| `visual_review` | 该玩法实际播放后的审查记录，artifacts 指向实际视频/交互预览及观察证据 |

每项 review（含 visual_review）都必须含：

- `status`：实际审查完成且通过后才填 `passed`；pending、failed、缺省均失败。
- `reviewer`：实际执行者标识；`findings`：依据本版测量/观察得出的非空结论，说明方法、覆盖和限制。不能复制模板或虚构审查。
- `artifacts`：至少一个实际证据文件引用。几何证据需从当前最终 STL 获得；索引顶层摘要将审查绑定到本版。

专属字段与审查责任：

| 审查 | 专属字段及必须实际完成的工作 |
| --- | --- |
| capture | `interfaces:[{parts:[a,b],captured:true},…]`；逐条覆盖完整环，确认真实径向倒扣、运动下有效捕获及与 intervals 的对应关系，不能把图论连通当作实体捕获 |
| walls | `interfaces:[{parts:[a,b],minimum_mm:实测值,required_mm:任务阈值},…]`；逐条覆盖完整环；两值均正有限且实测值不低于阈值。实测最薄值覆盖两端壁、舌根及槽与外皮/邻槽之间材料，并在 findings 或引用数据中交代测量方法、位置、误差与阈值依据 |
| sections | 引用最终实体的真实剖面，能看到限位舌、槽两端和关键材料厚度；说明剖切方式和比例，不拿理想示意图代替 |
| assembly | `method:print_in_place` 与当前实现一致；检查整体成形位置、缝隙、首层、桥接及支撑可清理性，明确切片/实物验证状态；若发现不可制造问题则审查失败，不能用“未试印”掩盖已知失败 |
| fit | `process_status:assumed/calibrated`、`basis`、`coupon_artifacts`；逐接口 `interfaces:[{parts:[a,b],minimum_gap_mm,maximum_gap_mm,required_range_mm:[lo,hi]},…]` 覆盖整环。引用真实三维间隙测点、方法、位置/姿态和匹配导轨试片；明确工艺是否已实测。标称参数、普通插销试片或另一版测量不能替代 |
| visual_review | 对其 motions 行的玩法实际播放，检查全部瓣、闭合回位、最大展开、内部保持连接及无越程；说明观察工具与覆盖，不能把存在视频文件等同于已经看过 |

## 机器检查与判断边界

- 接触报告不仅要求 all_passed：还需全部接口的舌根/承压体积为正，以及每个方向的 before/contact/overtravel 恰好齐全；核对实际位移等于几何限值与探测步距，前两态交叠在容差内，越程交叠超过容差。
- 运动报告必须绑定本版每件 STL 和区间文件；重新计算位移、每接口限位和真实区间搭接。要求所有零件对的抽样计数完整，闭合—中间—展开状态有序且无失败，不能提交 study_only、空 states 或仅一个汇总布尔值。
- 捕获报告必须覆盖规格的全部接口和高度，原始区间与派生尺寸一致，较弱侧扣除制造/槽增长/磨损弹性预算仍满足余量；所有玩法和独立止挡端点的搭接均超过任务门槛。配合审查要求每接口实测三维间隙处于声明范围，并绑定真实试片文件；assumed 只表示数字工艺假设，不是实际手感合格。
- 重导入报告必须与本版 assembly、GLB、玩法对应；全部声明采样帧包含全部 Petal 对象，位置/旋转/螺旋关系误差都符合适配器阈值。新版适配器记录 glb_sha256 与 sample_frames；旧报告缺字段需实际重导入补测，不手填通过。
- 几何报告中的布尔体积来自已绑定的计算证据，accept 不重复所有布尔计算。图像、壁厚测量和审查结论的物理真实性仍由执行者负责，脚本检查文件绑定、数值门槛、覆盖、状态和归属，不会自动读图推断结构。
- 数字验收不是连续运动的穷尽证明，也不是试印、摩擦、负载、疲劳寿命或无支撑制造认证。报告保留这些限制；尚未实测的项目不能写成已验证。

## 原子契约

`scripts/retention.py` 只做计算和资料判断；`run.accept` 负责读取、摘要比对、最终网格重读、计时与写报告。

| 函数 | 输入 → 输出/失败 |
| --- | --- |
| positive / ring_edges / pair | 有限正数、瓣数或接口编号 → 合法值/标准环边；非法类型或范围抛错 |
| connection_report | 瓣数、接口 → 连接分量、缺失/额外/重复边及 complete；不推断真实捕获 |
| motion_cases / require_stops | 玩法列表/assembly → 合法玩法键/完整连接报告；缺止挡、缺声明、断环或超限抛错 |
| check_contacts | 接触报告、assembly、摘要 → 核对全部舌根、方向与三态数值，不完整或失败抛错 |
| check_motion | 报告、assembly、玩法、实测区间及摘要 → 重新核对运动与搭接、原始抽样覆盖；不重复实体布尔 |
| check_review / check_interface_reviews | 审查记录、文件验证回调/接口条目 → 核对实际文件、状态、完整环覆盖及测厚阈值 |
| check_reimport | 重导入报告、assembly、玩法、GLB 摘要 → 检查每帧每瓣及变换误差，漏件或旧文件抛错 |
| check_evidence | assembly、摘要、证据索引、JSON 读取与文件验证适配器 → 完整验收摘要；缺项和失败抛错 |
