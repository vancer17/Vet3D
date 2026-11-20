# 原始场景网格测量

在物化 scripts 路径导入 [scene_measure](../scripts/scene_measure.py)。依赖 Blender、NumPy 与本包 mesh_measure；不读写资产文件，不切帧、不求值修改器、不改变网格/对象。调用者提供对象集合，并先更新依赖图；需重新载入文件时组合 [blender-tools 的完整资产载入](../../.dependency-blender-tools/references/asset-scene.md)。

| 原子函数 | 输入 → 输出与边界 |
| --- | --- |
| `object_bounds(obj, *, unit_mm, precision='float64')` | 非空原始 Mesh、每原坐标单位的毫米数、float32/float64 读入精度 → 世界坐标下毫米 min/max NumPy 数组。空/非 Mesh、非法精度或非正有限单位抛 ValueError。foreach_get 后以 NumPy 施加 matrix_world，保持原读入与矩阵运算精度。 |
| `measure_objects(objects, *, unit_mm, precision='float64', empty='error', topology_objects=())` | 显式对象列表及上述尺度/精度 → objects、bounds_mm、dimensions_mm。忽略非 Mesh；empty=error 拒绝空网格，skip 不记空对象，keep 保留零计数/bounds_mm=None 行；始终要求至少一个非空 Mesh。每行含 name、vertices、faces（多边形）、triangles（Σ面顶点数−2）和世界 bounds_mm。 |

只有 topology_objects 明确列出的对象追加 nonmanifold_edges 与 volume_mm3，复用 [measure_mesh](mesh-measure.md)。这里体积为**原始局部坐标的绝对体积**乘 unit_mm³，世界包围盒才施加对象变换；不将非单位缩放误写为世界体积，不隐式应用修改器、焊点或修网格。需世界体积时直接向 measure_mesh 传入明确变换。非有限几何可能产生非有限诊断，不能据文件存在或指标数量判通过。

独立组合示例（单位由调用者确认）：

```python
from asset_scene import open_asset
from scene_measure import measure_objects
objects = open_asset(source, frame=0)
metrics = measure_objects(objects, unit_mm=1000, precision='float64', empty='skip')
```

## 文件入口适配

共享测量不选择业务文件、报告位置、动作名键或通过条件。三个现有适配保留如下差异，哈希均物化 run-tools/checkpoints.digest：

| 适配 | 文件/帧与空对象 | 原报告保持 |
| --- | --- | --- |
| 护甲 validate_assets | 当前目录全部 BLEND，再全部 GLB；保留加载帧；float64，空 Mesh 失败 | object/vertices/faces/bounds_mm；BLEND printable 才测局部体积；animations、被使用图片的 image_dependencies、bytes；fresh-import.json。空目录仍写空列表。 |
| 笔刷 validate_assets | 单文件，或目录 scene.blend 再全部 GLB；保留加载帧；float64，跳过空 Mesh | object/vertices/faces/bounds_mm、BLEND printable 体积、animation_actions、bytes；显式 JSON 输出。无文件或无非空 Mesh 失败。 |
| 本包 fresh_review | 下一层目录的 GLB；第 0 帧；float32，保留空 Mesh 行 | name/triangles、actions、bounds_mm；边界转 Python 数值后相减得到 dimensions_mm，保留旧精度；fresh-import.json。无文件仍写空列表。 |

fresh_review 的位置参数为 `[case_id, root]`；例如在后台 Blender 运行 `scripts/fresh_review.py -- case_id /task/results`，只检查已有文件。护甲图片清单与工具 native_dependencies 的材质节点外部依赖检查是不同目标，不互换；图片/动作清单不证明已完整打包、动作正确或实物可制造。

上述回读阶段没有内容缓存，调用即重新载入测量；复用旧的上游几何不会跳过该检查。后续若增加阶段缓存，必须同时纳入资产、适配器、asset_scene/scene_io、scene_measure/mesh_measure 与 checkpoints 的实际源码指纹。

[test_scene_measure.py](../tests/test_scene_measure.py) 在真实 Blender 检查父级/非单位变换、原始/修改器边界、局部体积、空对象策略和源保持。跨适配器验证使用同版含动作 GLB、外部贴图 BLEND 与空对象，逐字段比较输出；不以公共函数能导入替代独立物化包或业务适配验收。
