# 运行与原子契约

## 环境和入口

Python 3.10+，安装随包 `scripts/requirements.txt`。几何使用 NumPy、trimesh、manifold3d、Shapely、SciPy 与截面闭环所需 NetworkX；Blender 使用自身 Python。依赖范围是允许安装范围，不是每个组合的兼容性认证。Blender 适配器采用 `wm.stl_import`、锐边标记和场景动画导出选项；执行前确认当前版本支持，不能丢弃关键导出参数后假称兼容。

按入口打包约定生成的完整分发目录可整体移动，不依赖原仓库。下例 `SKILL_DIR` 为其实际绝对路径，`TASK_DIR` 为技能包之外的任务目录，`BLENDER_BIN` 为实际 Blender 可执行文件。新建未指定瓣数时工作流默认16瓣，其余建模参数由任务测量；例子只解释字段。

```sh
python -m pip install -r "$SKILL_DIR/scripts/requirements.txt"
python "$SKILL_DIR/scripts/run.py" --help
python "$SKILL_DIR/scripts/run.py" inspect --input "$TASK_DIR/reference.stl" --scale-to-mm 1 --sections 5 15 25 --out "$TASK_DIR/reference-review" --task-id toy
python "$SKILL_DIR/scripts/run.py" build --job "$TASK_DIR/job.json" --out "$TASK_DIR/build-01" --task-id toy
python "$SKILL_DIR/scripts/run.py" add-stops --assembly "$TASK_DIR/build-01/assembly.json" --spec "$TASK_DIR/stop-job.json" --contact-probe-mm 0.2 --overlap-tolerance-mm3 0.00001 --out "$TASK_DIR/stopped-01" --task-id toy
python "$SKILL_DIR/scripts/run.py" validate --assembly "$TASK_DIR/stopped-01/assembly.json" --intervals "$TASK_DIR/intervals.json" --travel-mm 12 --mode staircase --samples 9 --overlap-tolerance-mm3 0.00001 --out "$TASK_DIR/check-01" --task-id toy
"$BLENDER_BIN" --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/blender_scene.py" -- --assembly "$TASK_DIR/stopped-01/assembly.json" --travel-mm 12 --mode staircase --out "$TASK_DIR/animation-01" --task-id toy
python "$SKILL_DIR/scripts/run.py" accept --assembly "$TASK_DIR/stopped-01/assembly.json" --evidence "$TASK_DIR/evidence.json" --out "$TASK_DIR/accept-01" --task-id toy
```

每次 `--out` 必须是尚不存在的目录且位于技能包外，避免覆盖源模型和已接受的产物；失败时保留部分产物及记录，纠正后换新目录、沿用 task-id，并用 `--previous-attempt-id` 关联失败尝试。此参数只建立关联，不自动恢复几何或跳过检查。输入路径相对于 job/manifest 文件解析，不依赖执行时 cwd。输出路径相对于 cwd 或使用明确绝对路径。

已有模型继续本地流程，无网络调用及凭据读取。`inspect` 可以读包含场景变换的 GLB；`build` 不自动判定朝向或裁头，也不保留纹理，准备阶段若需要带纹理外观应保存原件并由执行者另作 UV/材质回迁，不能用单色 STL 冒充保留了贴图。

## 参数文件

`job.json` 所有字段必填：

```json
{
  "mesh": "prepared_target.ply",
  "scale_to_mm": 1,
  "profile": "measured_profile.json",
  "count": 16,
  "k_deg_per_mm": 2,
  "step_mm": 0.2,
  "radial_scale": 1,
  "inset_mm": 0.1,
  "profile_sample_mm": 0.5
}
```

- `mesh`：一个已准备、外形合格且封闭连通、绕序正确、正体积的目标，滑轨轴为世界 Z，轴心 XY=(0,0)。`scale_to_mm` 是输入数值乘到毫米的系数；GLB 原始米坐标通常需 1000，必须依据实际变换确认。
- `profile`：JSON，包含 `source_count`（测得的原瓣数，整数 ≥3）及 `points_xy_mm`（一个简单闭合二维轮廓的顶点列表，可省略重复终点）。不支持多孔、多轮廓或变螺距轮廓。该输入由执行者从实测截面编辑完成，不能直接把 inspect 的所有环整体塞入。
- `count`：目标瓣数，整数 ≥3。新建未指定时由执行者明确写入16；已有指定/认可的瓣数优先。CLI仍要求该字段，不自动改写输入。`k_deg_per_mm`：有限非零旋转率，可负；螺距长度为 `360/abs(k)`。`step_mm`：扫掠最大层距，为正，单步转角需小于 180°；按间隙、材料余量及表面误差预算选精度，并按 [打印交付](print-delivery.md) 避免冗余细分，参数合法不代表精度足够。
- `radial_scale`：正径向倍率；`inset_mm`：非负轮廓内缩，变化会影响舌槽；`profile_sample_mm`：极角变换前的正边界采样间距。

参考轮廓的外端必须伸出目标，原点附近与内部舌槽必须是正确的功能轮廓。程序检查副本是否重叠，但不会发现所有覆盖遗漏或自动判断有效倒扣；生成后比较外形、内侧和端部。

`validate` 的 `--travel-mm` 为非负最大累计位移；`--mode` 选择 staircase/wave；默认 `--samples` 至少 3，包含闭合、中间与全开；`--overlap-tolerance-mm3` 为非负相交体积判失败阈值，应按零件尺度与计算误差选择。报告保留原始最大相交体积，不能把低于阈值描述为严格零相交。成品按 stop-job 声明的每种正行程玩法分别运行。

默认必需 `--intervals` 指向含 `assembly_sha256` 和 `intervals_mm` 的 JSON，后者为每瓣 `[lo,hi]`，顺序对应 assembly；lo/hi 是未展开时已测量的真实互锁区间。来源及可靠性由执行者按 [搭接规则](validation.md#搭接区间来源)核实。明确做诊断时可加 `--study-only`，此时允许没有止挡、没有区间或只取两态；报告标为 study_only，不能用于成品通过。

## 产物与失败

| 命令 | 文件 | 判定 |
| --- | --- | --- |
| inspect | inspection.json、part_*.ply | 只输出连通件、度量和原始截面，不自动识别机构 |
| build | assembly.json、profile.json、assembled_mm.stl、parts/*.stl | 每瓣重读后必须封闭；profile 副本间隙必须为正；这是尚未加止挡的中间件 |
| validate | validation.json | 默认要求完整止挡和绑定区间；碰撞、无搭接、超限均失败；通过仅表示该玩法的运动检查 |
| accept | acceptance.json | [整件连接与证据齐全](acceptance.md) 强制出口；缺项、旧报告、失败或未审查均非零退出并写 passed:false |
| measure-capture | capture.json | 最终网格每接口/高度的实际区间、逐侧捕获余量与制造预算检查；失败保留明细，非零退出；契约见 [捕获与配合](capture-and-fit.md) |
| blender_scene | model.blend、animated.glb、reimport.json、closed/open 六视图 | 新场景导入，与源关键时刻逐件比较；脚本不做实体碰撞、真实受力或视频编码 |
| 以上执行 | timings.jsonl；run.py 另写 timing_summary.json | 记录实际覆盖阶段；完整业务统计见 [阶段统计](timing.md) |

Blender 动画入口要求正行程（仅闭合模型使用 build），并在独立后台进程执行，脚本拒绝操作前台 Blender。它新建工作和重导入场景，不依赖全局删除已有模型；生成的源场景保留全精度零件及动作，六视图从重新导入的实际 GLB 渲染。视频与交互页面由执行者按任务继续制作，不能在尚未生成时报告交付。

整件3MF封装、独立回读和文件体积检查由执行者按 [打印交付](print-delivery.md) 完成；它们不在上述CLI自动输出范围内。最终证据需绑定实际选作下载入口的打印文件，不能只审查STL后未经核对地推荐另一版3MF。

## 默认防脱与最终验收

`add-stops` 在已有 assembly 上新增实体止挡，输入、装配边界及原子函数见 [stops.md](stops.md)。build 不猜测止挡尺寸；默认工作流必须继续补齐或复核止挡。已有止挡输入不重复布尔。validate 默认拒绝无止挡及不完整环；Blender 中间预览不能代替验收。完成所有玩法的动画与审查后，按 [证据索引契约](acceptance.md) 运行 accept；旧版产物缺新增声明、文件绑定或审查时须实际补测，不能自行回填通过。

`measure-capture` 与 `rail.t_profile` 的规格、适用探线和原子契约见 [capture-and-fit.md](capture-and-fit.md)。最终 accept 同时要求数字捕获报告、真实三维配合审查及试片引用；旧 evidence 索引缺 capture_measurement 或 reviews.fit 会失败。没有自动三维距离或试印适配器，执行者需用实际最终网格补测，不以理想参数替代。

## 函数与副作用

脚本目录可作为明确的 Python 模块搜索路径加入；只导入本包兄弟模块，不导入其他 skill。入口只组织调用，核心运算可独立执行。

| 模块 / 原子函数 | 输入 → 输出；副作用 / 失败 |
| --- | --- |
| motion.offsets | count、travel、mode → 每瓣非负位移；支持奇偶瓣数，最大值归一至 travel，非法值抛 ValueError |
| motion.screw_pose | offset、progress、k → (轴向 mm, 角度 deg)；进度须在 [0,1]，无副作用 |
| motion.adjacent_overlap | 区间及位移 → 每条相邻边的位移差、重叠区间与长度，含首尾边；没有重叠返回零和 null |
| geometry.load_mesh | 文件、倍率 → 应用场景变换的毫米三角网格；读取文件，不修改原件 |
| geometry.metrics / require_solid | 网格 → 度量 / 一个有效闭合体的度量；require_solid 不满足时抛错，不自行修补 |
| geometry.to_solid / from_solid | trimesh ↔ manifold；检查状态、空体、连通性，from_solid 只清理浮点焊接后精确坍缩面 |
| geometry.section_loops | 网格、高度列表 → 每层原始 XY 环；无交线返回空列表 |
| geometry.adapt_profile | 单轮廓、原/新瓣数、倍率、内缩、采样 → 适配轮廓及所有旋转副本的最小平面间隙；分裂、折叠、接触均报错 |
| geometry.helical_parts | 准备网格、轮廓、瓣数、k、层距 → 独立闭合瓣；常螺距扫掠求交，空件或小岛不自动删除 |
| geometry.measure_states | 完整网格、位移、k、进度列表、体积阈值 → 全对相交、包围盒与状态；包含完全包容，无轻量代理 |
| run.read_json / write_json / digest / resolve_input | 文件读写、内容摘要、显式相对路径解析；写业务产物，不保存秘密 |
| run.inspect_input / build / validate | CLI 命名参数、输出目录、计时回调 → 阶段产物；文件与运行编排，核心计算委托同一份几何/运动函数 |
| timing.utc_now / append_event / stage | UTC 时间、追加 JSONL、计时上下文；成功/失败/可捕获中断均记录，异常继续抛出 |
| blender_scene.import_parts / animate | manifest 与 Blender 场景 / 零件、位移、k、fps → 零件 / 关键帧；只改本次后台场景 |
| blender_scene.sample_transforms / compare_transforms | 源/重导入对象与帧 → 变换快照 / 逐瓣位置旋转和螺旋关系误差；设置当前帧 |
| blender_scene.check_glb_layout | GLB、所需零件名 → 无返回值；直接检查节点与一个动画片段，夹带其他场景对象或漏件则抛错 |
| blender_scene.render_views | 场景、零件、输出、全开帧 → 真实六视图；建立相机，尺寸自适应，各状态放大比例可能不同 |

代表性回归通过 `python -m unittest discover -s "$SKILL_DIR/tests"` 执行；运行数据使用包外临时目录。新 Blender 适配参数还需在目标运行版本实际导出并重读，离线纯函数检查不覆盖宿主技能发现或云端服务。

文件 digest 与阶段起止复用 [run-tools 本地核心](../../.dependency-run-tools/references/local-runtime.md)，本入口保留历史字段、跳过和异常传播语义。内容校验不授权重新提交远端任务。

check_glb_layout 使用 [glb-clips 的 read_glb](../../.dependency-glb-clips/references/contract.md) 验证完整容器后，仍由本工作流核对精确花瓣节点名和单一同步片段；读取公共模块不自动合并或改写动画。

measure_states 保留螺旋姿态和原报告字段，完整实体相交复用 [motion-check](../../.dependency-motion-check/references/solid-samples.md)。不启用 AABB 排除，使用 abs(volume) 与严格大于指定公差；轨道/捕获/止挡继续独立验收。每次使用新输出目录，此阶段无可复用缓存。
