---
name: taubin-smooth
description: 使用 Blender 原生邻域算子对任意形状的三角网格做 Taubin λ/μ 光顺，支持固定边界与顶点、保持拓扑并另存工程。适用于几何去噪与减轻收缩，不是仅改变法线的平滑着色。
---

# Taubin 网格光顺

将已有三角网格按正 λ、负 μ 成对迭代，输出新模型和数值检查。直接调用 Blender 的 `bmesh.ops.smooth_vert`，不另写邻接矩阵或 Laplacian 数值内核。Blender 5.2 的普通 Smooth/Laplacian Smooth 不是一个完整 Taubin 步骤；每轮必须交替运行两次，第二次使用第一次更新后的坐标。依据与版本边界见 [算法和接口](references/contract.md)。

## 输入与输出

- 输入：Blender 可读的有限坐标三角网格，CLI 支持 BLEND、GLB/GLTF、OBJ、PLY；或已有 Blender Mesh/Object 供 Python 函数直接调用。无封闭、流形或单连通分量限制。多网格文件须明确对象集合。
- 输出：新版本目录中的 `smoothed.blend`、`report.json`，以及 `pcg.tool_result.v1` 短回写 `tool_result.json`；保留原文件和全部场景对象。报告包含参数、局部位移、固定/边界顶点数、拓扑保持与保存重开结果。
- 环境：Blender 自带 Python、bpy、bmesh 和 NumPy；无需另装数值库。先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，`SKILL_DIR` 指实际分发目录中的本 skill。

## 光顺倍数

用户可直接声明“几倍光顺”。**默认 10 轮为 1 倍光顺，20 轮为 2 倍光顺**；按 `实际轮数 = floor(10 × 倍数 + 0.5)` 换算，非整数轮数四舍五入（恰好 0.5 时向上取整）。倍数须为有限非负数；未指定倍数或轮数时使用 1 倍，即 10 轮。

| 用户声明 | 实际轮数 / CLI 参数 |
| --- | --- |
| 0.5 倍光顺 | 5 轮，`--iterations 5` |
| 1 倍光顺（默认） | 10 轮，`--iterations 10` |
| 1.5 倍光顺 | 15 轮，`--iterations 15` |
| 2 倍光顺 | 20 轮，`--iterations 20` |
| 3 倍光顺 | 30 轮，`--iterations 30` |

例如 1.25 倍换算为 13 轮；0 倍或取整为 0 轮时不移动顶点。执行者在调用前说明换算后的实际轮数，并将整数传给现有 `--iterations` 或 Python 的 `iterations`；CLI 不直接接收倍数。用户明确给出轮数时以该轮数为准；与倍数不一致时说明采用的轮数。

倍数只调整 λ/μ 成对迭代的轮数，不乘大 λ、μ，也不自动改变边界策略。一轮包含一次正 λ 和一次负 μ 更新。此约定用于估计计算轮数，不保证视觉光顺程度、位移或体积变化呈线性。比较不同倍数时默认从同一原始模型分别运行；只有用户明确要求追加光顺时才在已有结果上继续，并说明本次新增轮数。

## 执行

### 宿主执行模式

按顺序读本入口、[检查点与选项](pcg/routes.yaml)、[执行架构与产物槽](pcg/architecture.yaml)，再读 [PCG 交接](references/pcg.md)。宿主采用 [统一编排提示](../.dependency-pcg-view/references/host-orchestration.md)，在包外任务目录保留一份 session；本 skill 不实现 Agent 循环，也不自动 spawn。

| 阶段 | 操作与出口证据 |
| --- | --- |
| `input` | 明确源模型、对象、轮数、固定策略和新版本目录；记录现有用户授权。已有合格报告走 `review_only`，跳过光顺。 |
| `smooth` | 独立 Blender 调用 λ/μ、另存并重开；只在成功后回写 `smooth.mesh` / `smooth.report` 两个 keep 槽和实际哈希，转到 `review`。 |
| `review` | 核对当前文件与报告哈希，实际查看轮廓、边界和细节后才完成；数值通过时仍为待视觉验收。调整回到 `input`，保留旧版及 traces，从原始源写新版。 |

`smooth` 保存工程属于 `blender.write`，routes 标记 `confirm_required`；宿主记录已有请求对该操作的授权，范围已明确时不重复询问。原文件覆盖、删除、发布均不在本 skill 范围内。每轮结束、option/回退及 compact 后从持久化 session 重投影两张图；仅新产物或新版追加留痕，具体接口和失败恢复见 PCG 交接。

### Blender 调用

先读取 [接口、约束和验收](references/contract.md)，确认对象、原始拓扑、边界策略与新输出位置；按上面的倍数约定确定实际轮数。默认 λ=0.5、μ=-0.53、10 轮（1 倍）是可调整起点；用户已有参数优先，并通过脚本校验。开口形状需要保持接口时加 `--pin-boundary`；不能推断所有开边都必须固定。

在独立后台进程运行：

```bash
"$BLENDER" --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/execute.py" -- \
  --script "$SKILL_DIR/scripts/taubin_smooth.py" -- \
  --input "$INPUT" --output-dir "$RUN_DIR/smooth-v1" \
  --iterations 10 --lambda 0.5 --mu -0.53
```

单网格自动选择；多网格用重复 `--object "对象名"` 或明确 `--all-meshes`。CLI `--help` 查看参数；任意固定顶点索引通过 `taubin_positions` / `smooth_object` 的 `fixed_vertices` 提供。已有 Mesh 不必导出再导入。

检查报告与模型轮廓、边界、薄片和局部细节。数值校验不等于视觉通过；需要调整时从原始输入写新版本，避免不知情地累计光顺。已有合格输出可只读验收而跳过运行。

CLI 成功在标准输出打印短回写，详细指标读取 `report.json`；Blender 自身日志可能混在标准输出中，宿主优先读取 `tool_result.json`。`run_asset` 的 Python 返回值仍是完整报告。文件回写不等于已经更新宿主会话，调用者须完成 [产物绑定与重投影](references/pcg.md)。

## 关键边界

- 只移动原始网格顶点，保留索引、面序、UV、材质、顶点组和对象变换。只在副本上写坐标；未选共享网格实例不受影响。已有修改器保持原样，不将求值结果烘焙到基础网格。
- 多边形不自动三角化；需要时由调用者明确准备三角输入。Shape Keys 拒绝自动处理，先明确静态副本或全形态键处理策略。
- 均匀边邻域、Blender float32 精度；孤立顶点不动，松散边参与邻域，非流形边不自动修复。固定顶点仍作为邻居影响活动顶点。
- Taubin 减轻 Laplacian 收缩，但不保证体积严格不变、不自交、不翻面或棱边保持；不额外缩放补偿体积。报告位移单位为对象局部坐标单位。
- 输出目录必须全新，失败后保留已有源及可能产生的未完成输出；没有成功报告不能作为验收通过。脚本不安装到宿主技能目录，也不修改前台未保存工程。

<!-- managed-by: sparc3d-runtime -->
