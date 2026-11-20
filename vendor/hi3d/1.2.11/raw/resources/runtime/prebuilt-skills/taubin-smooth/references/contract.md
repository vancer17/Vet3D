# 原生算子、接口与验收

## 算法与 Blender 依据

对原网格边的一环邻居使用均匀权重，定义 `L(x)i = mean(xj, j∈N(i)) - xi`，每轮为：

```text
x'  = x  + λ L(x)
x'' = x' + μ L(x')
```

λ 为正，μ 为负；一轮是两次同步更新，不能先做 N 次正步再做 N 次负步，不能在负步复用旧 L(x)。固定顶点在两步中都不更新，仍参与邻居平均。没有邻居的顶点保持原值。

[Blender v5.2.0 源码的 bmo_smooth_vert_exec](https://github.com/blender/blender/blob/v5.2.0/source/blender/bmesh/operators/bmo_utils.cc) 先计算所有目标顶点的邻居均值与 factor 插值，再统一写回；有符号 factor 可直接用于两步。[BMesh API](https://docs.blender.org/api/current/bmesh.ops.html#bmesh.ops.smooth_vert) 是调用入口。脚本只编排该原生算子和副本/文件操作，没有 Python Laplacian 内核。

[官方 Smooth 手册](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/smooth.html) 描述单步邻居平均与负 factor；普通 Smooth 或带体积修正的 Laplacian Smooth 不应直接标为 Taubin。[GSoC 开发记录](https://devtalk.blender.org/t/gsoc-2026-improve-mesh-smoothing-in-blender/45189) 提到独立 Taubin/HC 选项，但开发分支记录不证明某个安装版本具有该接口。本 skill 的兼容基线是 Blender 5.2 的 `smooth_vert`，不依赖尚未核实的 modifier 属性，也不按未来版本号猜测属性。

参数限制 `0 < λ < -μ <= 1`，并拒绝 `abs((1-2λ)(1-2μ)) > 1`，避免归一化均匀图 Laplacian 最高频率 k=2 被放大。Taubin 的低频通带仍可能略有增益，大迭代数或异常网格仍可能产生过冲。默认 0.5/-0.53、10 轮是起始值，不是全模型通用最优参数。0 轮返回不变坐标。

用户声明“几倍光顺”时，执行者按 [光顺倍数约定](../SKILL.md#光顺倍数) 换算成整数 `iterations` 后调用；CLI 继续使用 `--iterations`，例如 2 倍传 `--iterations 20`，不另传倍数参数。`report.json` 中的 `iterations` 始终记录本次实际执行轮数；倍数换算不改变 λ/μ、固定范围或数值内核。

## Python 接口

从已物化包的 scripts 路径导入 `taubin_smooth`，在 Blender Python 中调用：

```python
from taubin_smooth import taubin_positions, smooth_object

# 只计算，不修改 Mesh，也不写文件。
positions, metrics = taubin_positions(
    obj.data, iterations=10, lambda_=0.5, mu=-0.53,
    pin_boundary=True, fixed_vertices=[0, 4],
)
# 在当前隔离场景中为该对象创建坐标副本；调用方负责另存。
metrics = smooth_object(obj, iterations=10, pin_boundary=True)
```

| 接口 | 契约 |
| --- | --- |
| `validate_parameters(iterations, lambda_, mu)` | 校验非负整数轮数、有限系数与上述约束；无副作用。 |
| `mesh_positions(mesh)` | 独立 float32 `(N,3)` 局部坐标；不读取修改器求值。 |
| `mesh_topology(mesh)` | 原边、角点、面起点/长度的精确字节快照，用于同版本前后验证。 |
| `taubin_positions(mesh, *, iterations=10, lambda_=0.5, mu=-0.53, pin_boundary=False, fixed_vertices=())` | 返回新坐标和报告；临时 BMesh 成功/失败均释放。非空三角面、有限坐标、合法固定索引；同面重复索引拒绝。允许退化面积、非流形、断开分量和孤立顶点，但不修复这些情况。 |
| `smooth_object(obj, **parameters)` | 只支持本地 Object Mode 网格、无 Shape Keys。复制 Mesh 后只回写坐标，核对拓扑；共享实例与原 Mesh 不动，其他数据保持。失败传播；无文件写入。 |
| `select_meshes(objects, *, object_names=(), all_meshes=False)` | 明确目标集合；多个网格不自动全选，重复/未知名或空输入拒绝。 |
| `file_digest(path)` | 兼容接口，直接复用 run-tools 的 `checkpoints.digest`；流式 SHA-256 只读文件，用于源保持和产物身份。 |
| `run_asset(source, output_dir, *, object_names=(), all_meshes=False, **parameters)` | 参数与路径预检后替换后台场景，选定对象光顺，写新 BLEND，重开核对坐标/拓扑/世界变换与源哈希，再原子写报告及 PCG 短回写；返回完整报告。新目录不可与包或输入重叠；失败可能留下不完整输出，不自动续写/覆盖。 |
| `main(argv=None)` | 解析 CLI，成功打印 `pcg.tool_result.v1` 短 JSON；运行异常打印 failed 回写并保留原异常，经 Blender 的 `--python-exit-code 1` 返回非零，不覆盖旧版回写。参数解析失败由 argparse 报错。 |

包内的 `execute.py`、`asset_scene.py`、`scene_io.py` 与 `path_safety.py` 按 manifest 从唯一工具源物化。载入 BLEND 保留完整场景并禁用内嵌脚本；其他格式沿用 Blender 导入器。OBJ/PLY/GLTF 的单位、拆点和属性受导入器约束；不承诺文件导入前后的顶点编号一致，拓扑保持从已载入 Mesh 开始。BLEND 保存重映射相对依赖路径，但不打包外部库或贴图；交付可搬运工程时另核对这些资源。

PCG 短回写、会话、哈希、原子 JSON 写入、YAML 解析和两种投影均复用 manifest 所列共享工具，不在本 skill 复制协议实现。`pcg_handoff.py` 只处理本能力报告到产物槽的交接；接口与宿主责任见 [PCG 交接](pcg.md)。纯计算与 `smooth_object` 不创建文件或会话，嵌入工作流时由调用方保存和登记产物。

既有的人像语义去噪具有 float64 权重、来源绑定、位移上限和定向面积约束；本能力采用 Blender 原生 float32、无权均匀邻域，不能无条件替换那些业务约束，也未改变其维护源或调用方。

## 验收

`report.json` 使用 `taubin-smooth.v1`；每对象列出参数、边界/固定/孤立/非流形计数、移动顶点数和局部位移 max/RMS。`topology_unchanged` 来自写回检查，`saved_mesh_readback` 来自保存重开比较，`source_unchanged` 对比原文件字节。0 轮、全部固定或已经平衡的网格允许位移为零。哈希仅覆盖主输入文件，不覆盖 GLTF/BLEND 的外部依赖。

自动检查不会判断光顺强度是否合适；实际任务查看同视角前后轮廓与细节，必要时做同拓扑基线的自交/翻面检查。通过参数检查不证明几何无缺陷，非流形或开放输入不能因保持拓扑便称为水密。

可复用回归入口（只在隔离后台场景运行，产物置于临时目录）：

```bash
"$BLENDER" --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/execute.py" -- \
  --script "$SKILL_DIR/tests/test_blender.py" -- --scripts "$SKILL_DIR/scripts"
```

覆盖解析三角形滤波响应、噪声球与收缩对比、边界/固定/孤立与非流形输入、源和属性保持、非法参数及保存重开；同时验证 CLI 短回写、真实文件的 PCG 槽位、版本 traces、重复绑定/compact 重投影、回退选项、keep 保护、丢失/篡改文件与失败不覆盖。真实模型的视觉验收仍按本次输入执行。
