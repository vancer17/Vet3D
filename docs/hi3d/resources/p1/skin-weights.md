# `skin_weights.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）的 `.dependency-skin-weights/scripts/rigging/skin_weights.py`。上游 `skin-weights` 资源入口将其列为权重归一检查、区域修复和形变筛查的 Python 实现。模型可通过已选 Skill 的资源引用获知这些接口，执行由相应的本地命令或 Python 调用方承担。安装包核查范围内未发现此文件的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/skin_weights.py) · [安装包资源入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-skin-weights/REFERENCE.md>)

**源码模块说明原文**

```text
Pure, local skin-weight repair. Bone semantics and regions are caller supplied.
```

## 参数、返回与副作用

| 入口 | 参数与校验 | 返回 |
| --- | --- | --- |
| `check_weights(weights, vertices=None)` | `weights` 必填；`vertices` 可选，默认 `None`。要求非空 `N×B` 浮点数组，元素有限且非负，逐行和在 1 的绝对公差 `2e-4` 内，`rtol=0`。给出 `vertices` 时必须为有限的 `N×3` 静止顶点。 | `np.asarray(weights)` 结果，不主动拷贝、转为另一浮点精度或归一化；适用数组可与输入共享内存，调用方改返回数组可能改到原数组。 |
| `repair_regions(vertices, weights, bone_names, rules)` | 四项均必填，无默认值。权重与顶点先经 `check_weights`；有序唯一骨名数量须匹配权重列，规则非空，每条键集合恰为 `bounds`、`forbidden_bones`。边界为有限且 min≤max 的 `2×3` 数组，禁用骨为非空唯一列表。 | `(repaired_weights, report)`。返回新权重数组和内存统计，不写模型或报告文件；完整控制流与字段见[局部数组修复](#repair_regions-局部数组修复)。 |
| `stretch_metrics(rest, posed, faces, height)` | 静止与变形顶点应为同拓扑、同坐标单位的有限 `N×3` 数组。`faces` 是非空、索引有效的整数三角面表。`height` 为有限正数。 | 返回显著拉伸和面积增长的面计数、坏面并集数量、最大边长比例、面积比例、边长增长，以及最多 20 个按最大边长比例倒排的坏面索引和指标。 |

规则采用含边界的坐标盒。区域未命中、骨名未知、移除影响后总权重不大于 `1e-12`，或命中源码中的输入校验失败分支时抛出 `ValueError`。NumPy 无法处理的输入类型也可能触发原生异常。修复返回新数组，调用方负责把结果应用到资产或持久化。筛查在调用方给出的三角面上同时比较相对变化与绝对增长。边长判定要求倍率大于 `3` 且增长大于 `height/120`。面积项使用三角面叉积模长，要求倍率大于 `8` 且增长大于 `height**2/81000`。静止边长和叉积模长作为倍率分母时，下限分别为 `height*5.56e-8` 和 `height**2*3.1e-11`。骨名、坐标空间、规则和姿态均来自调用方。 [归档实现](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/skin_weights.py)

`stretch_metrics` 返回 `significant_faces`、`large_area_faces`、`bad_face_count`、`max_edge_ratio`、`max_area_ratio`、`max_edge_growth`、`worst_faces` 和 `worst_face_metrics`。其中三角面索引以传入的 `faces` 为准，`worst_face_metrics` 每项含 `face`、`edge_ratio` 和 `area_ratio`。`worst_faces` 从坏面并集中按该面最大边长倍率降序取至多 20 项。零异常时计数为零，坏面列表为空，最大指标仍来自全体传入三角面。 [返回字段实现](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/skin_weights.py)

`check_weights` 对空矩阵、整数权重、非有限值、负值或行和不合格的输入抛出 `ValueError("Expected finite nonnegative normalized N x B weights")`。该函数返回数值矩阵，骨名列与实际关节、顶点区域的对应由调用方核对。交换左右骨骼的两列权重后，各行仍归一时可通过数值校验。`stretch_metrics` 对畸形表面、空或越界三角表和非正高度抛出 `ValueError`，它读取调用方给定的顶点与索引，实际蒙皮连接和跨帧动作需由 Blender 取证。 [权重校验实现](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/skin_weights.py) · [单身体求值与报告](../specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查)

### repair_regions 局部数组修复

此函数读取静止顶点、当前权重、有序骨名和区域规则，不接收 Blender 对象、帧、骨架或输入文件。规则采用调用方声明的同一局部空间和单位；函数没有模型语义识别，也没有自动判断何种影响应删除。`bone_names` 先转为 `list`，检查数量及唯一性，没有逐项强制字符串；它与实际骨名和权重列的对应由调用方保证。`rules` 通常由 JSON 数组传入，源码检查非空并逐项读取，未单独断言容器必须为列表；每项则严格要求两个键，拒绝额外键。 [实际参数与校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/skin_weights.py:26>)

规则按顺序作用于结果副本。每条先取含边界盒内的所有顶点，统计当前结果中禁用列的权重和，仅对移除了正影响的行清零和归一。后条规则的 `max_removed_weight` 因而基于前次规则归一后的权重。任一步将顶点剩余权重降至 `1e-12` 或以下时拒绝，不猜测替代骨，也不能用此函数补救原来无影响或未归一的输入。

全部规则结束后，对**全部命中区域并集**内精确同坐标的行统一为其平均权重，再检查最终权重。平均不识别连通域、衣层或独立壳体，也不使用近似位置公差。即使本条 `affected:0`，同坐标行的保留权重不同仍可发生变化；`changed_vertices` 不能用各条 `affected` 求和代替。区域非空但最终零变化可以正常返回。函数不做邻域平滑、top-k、几何编辑或图权重求解。 [顺序处理与共享点平均](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/skin_weights.py:60>)

| 返回位置 | 完整字段与含义 |
| --- | --- |
| `repaired_weights` | 从输入拷贝得到的独立数组，保持输入的形状和浮点 dtype，不与原权重共享数据；输入数组保持不变。共享位置平均使用 float64 累加，再写回该 dtype。是否写回 Blender 由外层决定。 |
| `report.changed_vertices` | 最终数组与原数组至少一列精确不同的顶点行数，包含共享位置平均产生的变化。 |
| `report.rules[].vertices` | 本条区域命中顶点数，重叠规则可以重复计数。 |
| `report.rules[].affected` | 本条处理时至少一个禁用列具有正影响的行数，不包括后续仅因共享点平均改变的行。 |
| `report.rules[].max_removed_weight` | 本条命中顶点中最大禁用影响总和；没有正影响时为 `0.0`。 |
| `report.shared_position_duplicates` | 命中并集的顶点数减去精确唯一位置数，统计重复顶点而不是重复位置组数。 |

统计没有 `pass`、`pose_qa_pending`、文件摘要或实际骨架归属；CLI 增加的字段属于其自身契约。函数本身也不核对 `mesh_sha256`、`rig_sha256` 或原权重版本，文件来源及绑定关系由调用方另验。 [本地修订 CLI](../specialized-mesh-scripts.md#service_rig-repair-局部权重修订)

| 失败条件 | 实际边界 |
| --- | --- |
| 权重或顶点不合格 | `check_weights` 在结果副本产生之前拒绝；整数权重不会自动转换成合法浮点权重。 |
| 骨名数量／唯一性不符、规则为空 | 抛 `ValueError`。骨列对应实际关节的语义由调用方负责。 |
| 规则键、边界、禁骨列表不合格 | 抛 `ValueError`。未知骨由 `names.index()` 抛 `ValueError`；不可哈希或不可转换的畸形值还可能触发原生异常。 |
| 区域没有顶点 | 抛 `ValueError("Region contains no vertices; check the coordinate space")`。 |
| 清理后将无绑定 | 抛 `ValueError("Repair would leave vertices unbound; calibrate retained influences")`。 |
| 后条规则或最终校验失败 | 丢弃局部结果，没有返回可用数组或部分报告；输入数组保持原样。模型／文件是否已变更由外层写回顺序决定。 |

**根据已核实源码重建的伪代码。** 返回内存结果，不包含模型写回或文件落盘。

```python
def repair_regions(vertices, weights, bone_names, rules):
    old = check_weights(weights, vertices)
    names = require_unique_ordered_names_matching_columns(bone_names, old)
    require_nonempty(rules)
    result = old.copy()
    selected = empty_vertex_mask(vertices)
    reports = []
    for rule in rules:
        require_exact_keys(rule, {"bounds", "forbidden_bones"})
        bounds, columns = validate_rule_and_find_columns(rule, names)
        ids = vertices_in_inclusive_box(vertices, bounds)
        require_nonempty(ids)
        selected[ids] = True
        removed = result[ids][:, columns].sum(axis=1)
        affected = ids[removed > 0]
        zero_columns(result, affected, columns)
        require_remaining_weight_above(result, affected, 1e-12)
        normalize_rows(result, affected)
        reports.append(summarize_rule(ids, affected, removed))
    average_exact_shared_positions(result, vertices, selected)
    check_weights(result)
    return result, summarize_final_changes(old, result, selected, reports)
```

## 依赖、权限与前置 Hook

导入 NumPy。按包路径使用时保留同目录 `rigging/__init__.py`。本文件的计算使用调用方提供的内存数据，应用结果到模型或写出记录由外层负责。整包中的稀疏图求解位于另一个模块，并按其入口选用自身依赖。经宿主启动本地脚本时适用该执行工具的审批、沙箱和前置 Hook。 [包初始化资源](rigging-package.md) · [本地执行工具](../../tools/exec-command.md)

专项发行 `rig-retarget` 内的 `scripts/rigging/skin_weights.py` 与本页归档原件 SHA-256 同为 `07668c30ed37172c5b0babf053eefc206a3fcc6077ff3ba901aee9b68a1c11e4`。其 `service_rig.py` 在模块加载时导入这三个数值入口。绑定时检查权重，检查分支计算拉伸，修订分支调用 `repair_regions`，全部数组计算成功后才由 `write_changed_weights` 写回。`export` 分支仅加载该依赖，实际使用 Blender Mesh 和同包文件工具。隔离试验把数值函数替换为触发即报错的桩，合成对象仍能完成导出。 [P1 收据](../../upstream/1.2.11/archived-p1/archive.lock.json) · [物化映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [包内导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:7>) · [权重与修订分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:395>) · [单身体检查](../specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [本地修订](../specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [写回函数](../specialized-mesh-scripts.md#service_rig-权重写回与保护函数)

本文件只依赖 NumPy；`service_rig` 另导入 `weight_graph.mesh_digest`，不因此运行 SciPy 图求解。P0 启动包装与预算、P1 `asset_scene`／`mesh_snapshot`／`scene_samples` 可由外层另行选用，并未因执行 `inspect/repair` 自动调用。实际数组计算、Blender 写回、候选保存、报告保存和动作验收各有独立结果。

## 调用示例与核查依据

**根据已核实接口重建的调用示例。** 将归档 `.dependency-skin-weights/scripts/` 加入模块搜索路径。为两个合成顶点按尺寸明确的局部区域移除一个影响。

```python
import numpy as np
from rigging.skin_weights import repair_regions

vertices = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
weights = np.array([[0.75, 0.25], [0.4, 0.6]])
rules = [{"bounds": [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
          "forbidden_bones": ["detail"]}]
repaired, report = repair_regions(vertices, weights, ["base", "detail"], rules)
print(repaired.tolist(), report["changed_vertices"])
```

**额外合成探针。** 禁用骨已有零权重时，精确同坐标的两行仍会平均。此例不是随包测试中的原始示例。

```python
import numpy as np
from rigging.skin_weights import repair_regions

vertices = np.zeros((2, 3), dtype=np.float32)
weights = np.array([[0.8, 0.2, 0.0], [0.3, 0.7, 0.0]], dtype=np.float32)
before = weights.copy()
rules = [{"bounds": [[-1, -1, -1], [1, 1, 1]],
          "forbidden_bones": ["excluded"]}]
repaired, report = repair_regions(
    vertices, weights, ["retained_a", "retained_b", "excluded"], rules
)
np.testing.assert_array_equal(weights, before)
np.testing.assert_allclose(repaired, [[0.55, 0.45, 0.0]] * 2, atol=1e-7)
print(report)
```

**上述额外探针的实际返回统计。**

```json
{
  "changed_vertices": 2,
  "rules": [{"vertices": 2, "affected": 0, "max_removed_weight": 0.0}],
  "shared_position_duplicates": 1
}
```

归档模块的第一例实测得到一处权重修复，范围外保持原值。使用随包 Python 3.12.14／NumPy 2.5.3 复跑 5 项安装包测试，覆盖共同坐标一致性、幂等、空区域／未知骨／清空影响拒绝、非法权重和尺度相关筛查。额外数值探针确认：禁用影响已零且坐标唯一时零改动；共享位置平均可产生上例统计；顺序重叠规则按前次归一结果计算后续移除量；输入全零权重在修复前拒绝。 [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [安装包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/test_skin_weights.py>)

专项发行的 `test_skin_weights.py` SHA-256 为 `919210871da0e7f9d774de90176f6b20bcefd0f2f010ae7c15f1501076356e9f`，可用独立 Python 的 `-B` 经 `rig-retarget/scripts/run.py test_skin_weights` 重跑。这些是数组函数和小型合成夹具的验证。真实四足的骨语义、跨侧影响、独立软层、接缝、完整步态及导出影响数待实测；数组通过不证明骨架关联或形变质量。写回中断、保存／报告故障和并发属于外层 CLI 的落盘边界，不能视为本函数已提供回滚或持久化能力。
