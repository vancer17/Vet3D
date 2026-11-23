# `glb_bounds.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）的 `.dependency-mesh-audit` 随包脚本，源码映射为 `skills/mesh-audit/scripts/glb_bounds.py`。包内入口将它列为变换后包围盒检查实现。模型可通过已选 Skill 的资源引用发现脚本，实际运行使用宿主提供的本地命令或由 Python 调用方导入。在已核查安装材料中未找到此脚本的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_bounds.py) · [安装包入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/REFERENCE.md>)

**源码模块说明原文**

```text
Read actual GLB positions and node transforms; report default scene extents.
```

## 参数与结果

| 入口 | 参数 | 返回与写入 |
| --- | --- | --- |
| `inspect(path)` | 必填，无默认值，传入指向本地 GLB 的 `Path`。 | 读取文件，返回包围盒尺寸、顶点实例计数、动画名称和外部资源 URI 的字典；不写报告，也不返回文件摘要。 |
| `python glb_bounds.py <root>` | 必填位置参数，无默认值；从给定根目录按排序后的 `*/*.glb` 枚举文件，不递归任意深度。 | 为各文件附加相对 `file`、`sha256` 和 `bytes`，批次结束后写入 `root/glb-bounds-check.json`，可覆盖同名报告。标准输出打印处理计数。常规非优化 Python 执行下，遇到外部资源或文件大于等于 25 MiB 会触发断言。 |

`inspect` 用同目录 `read_glb` 读取容器，要求一个内嵌 `BIN\0` chunk，直接读取每个 primitive 的 `POSITION`。位置 accessor 限于非 sparse 的 little-endian float `VEC3`，支持符合范围与对齐约束的交错存储。遍历默认场景，按父子关系累积矩阵。节点有 `matrix` 时按 glTF 列主序解析，其他节点从平移、旋转和缩放计算变换。 [容器依赖](glb-clips.md) · [安装包实现契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/references/code-contract.md>)

- `scene_dimensions_xyz_m` 为世界坐标三个轴的包围盒跨度。按 glTF 米制解释。
- `width_depth_height_mm` 按 X、Z、Y 重排跨度后乘以 1000。调用方应先确认模型尺度与实际验收坐标。
- `mesh_vertex_instances` 按实际遍历到的节点与 primitive 累加 POSITION 条数，复用的几何可被重复计数。
- `animations` 为文档内动画名称，未命名时使用索引字符串。`external_resources` 罗列 buffer 与 image 中的非 data URI，函数不会读取这些 URI。

容器尺寸或对齐不符、BIN 数量不符、位置类型不支持、读取范围不合法或原始 POSITION 非有限时抛出 `ValueError`。文件读取错误与缺字段等原生异常向上传播。尺寸取自原始 POSITION 与静态节点变换。骨骼、形态键、动画时刻的求值和几何有效性需要专门检查。 [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/tests/test_glb_bounds.py>)

**静态源码边界。** 节点 matrix／TRS、累积 world 矩阵及变换后坐标没有全面的有限性、旋转规范或几何有效性门槛；原 POSITION 有限不等于世界尺寸有效。范围从正／负无穷初始化，未检查默认场景必须包含 Mesh，也没有最终非空／有限结果校验。默认场景无 Mesh 时可以得到 `mesh_vertex_instances:0` 及非有限尺寸，返回成功不能解释为存在有效资产。这些分支来自源码核对，本次未新增空场景或非法变换实测。 [遍历与返回](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_bounds.py:38>)

25 MiB 和无外部资源断言只属于批处理入口，不是 `inspect()` 的统一限制。批次中任一文件读取、解析或断言提前失败时，末尾报告尚未写入，旧报告可能保留；报告普通覆盖写入不具原子替换或回滚，写入中断也可能留下部分 JSON。枚举没有匹配文件时仍可写空列表。没有独立质量 `pass` 或持久任务 ID，调用方需核对实际文件集合、摘要、顶点实例数及有限尺寸，再决定是否采用结果。 [批量入口及写盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_bounds.py:62>)

## 实现伪代码

**根据已核实源码重建的伪代码。** 保留单文件检查和批处理的不同门槛；没有补入实现中不存在的最终非空验收。

```python
def inspect(path):
    doc, chunks = read_glb(path.read_bytes())
    binary = require_one_embedded_bin(chunks)
    bounds = initialize_infinite_bounds()
    for node in traverse_default_scene(doc):
        world = accumulate_static_node_transform(node)
        for primitive in node_mesh_primitives(node):
            positions = read_validated_float_positions(doc, binary, primitive)
            bounds.include(transform_positions(positions, world))
    return make_dimensions_instances_and_resource_report(doc, bounds)


def batch(root):
    rows = []
    for path in sorted(root.glob("*/*.glb")):
        result = inspect(path)
        result.update(file=str(path.relative_to(root)),
                      sha256=file_digest(path), bytes=path.stat().st_size)
        assert not result["external_resources"]
        assert result["bytes"] < 25 * 1024 * 1024
        rows.append(result)
    write_json_overwriting(root / "glb-bounds-check.json", rows)
```

## 依赖、权限与前置 Hook

直接依赖同目录 `glb_clips.py` 和 NumPy。脚本把自己的实际目录加入 Python 模块搜索路径。单文件检查只需受控输入的读取权限，批量入口额外需要报告写入权限。经宿主本地命令执行时，沿用该工具实例的审批、沙箱和前置 Hook。 [本地执行工具](../../tools/exec-command.md)

## 调用示例与核查依据

**调用示例。** 将归档 `.dependency-mesh-audit/scripts/` 加入 Python 模块搜索路径，使用含单个内嵌 BIN 的本地样件。

```python
from pathlib import Path

from glb_bounds import inspect

report = inspect(Path("fixtures/inspection.glb"))
print(report["scene_dimensions_xyz_m"], report["mesh_vertex_instances"])
```

以发行包的 Python 3.12.14 和 NumPy 2.5.3 复跑 3 项随包测试。带父变换、列主序矩阵和交错顶点的样件得到 [10, 21, 36] 的 XYZ 跨度与三个顶点实例。损坏容器、外置 buffer、sparse 位置和越界 accessor 均有失败用例。真实四足资产的尺度、压缩或量化存储及动画形变仍待验证。 [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/tests/test_glb_bounds.py>)

归档与安装副本 SHA-256 同为 `3431b26d8238ba6448b7efc28099f911b3f98e1fc7e6bb94fbb9b416a0b8a6b4`。批次中断、旧报告残留、报告写入故障、空场景及非有限节点变换未在本次逐项注入，不能扩大为已经验证所有失败恢复。 [P1 归档收据](../../upstream/1.2.11/archived-p1/archive.lock.json)
