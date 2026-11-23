# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/prepare_source.py](../scripts/prepare_source.py) | `execute`, `main` |
| [scripts/source_normalize.py](../scripts/source_normalize.py) | `normalize_source` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按职责维护的公共模块

- [product_source](../scripts/product_source.py)：`import_source`。
- [studio_source](../scripts/studio_source.py)：`source`。

共享模块先按 package.json 物化。纯几何复用选择 `*_core`；各职责显式导入，路径与 profile 见 [组合契约](../../.dependency-shape-build/references/composition.md)。不同 profile 保留毫米/米、渲染策略和导出清理差异。

## 来源规范化与可选预览

`source_normalize.normalize_source(source,out,height_mm,*,yaw_deg=None,weld_tolerance_mm=0.0001)` 返回 `(object, report)`，重置隔离场景、经 [场景导入](../../.dependency-blender-tools/references/scene-io.md) 合并明确来源内的全部网格，施加世界变换与可选 Z 轴 yaw，再按目标高度缩放、居中落地、有限焊接及重算法线。目标高度有限且为正，yaw 有限，焊接容差有限且非负；无网格或无正 Z 范围失败。容差和 NPZ 为毫米，Blender 为米；保留逐角 UV 与材质索引，写 source.npz/source.blend/source-inspection.json，打包 FILE 图片。显式 yaw 在施加来源变换后切换为 XYZ 旋转再应用，避免 glTF 四元数模式使 Euler 修改无效。源文件不改，派生同名文件可覆盖，调用方负责隔离输入与输出。异常会传播且可能留下部分派生产物。

yaw=None 保留旧通用报告字段；显式 yaw（包括 0）增加 source_yaw_deg。原件哈希、原始/焊后计数、包围盒与不重网格/不减面字段保持。函数不渲染、不读取环境、不提前结束进程。

CLI 保留位置参数与 ASTRA_SKIP_SOURCE_VIEWS=1 的 StageFinished(0) 语义；未跳过时调用 [model-preview 来源视图](../../.dependency-model-preview/references/source-views.md)。复用者按 package.json 一并物化 source_normalize、scene_io、source_views、preview_scene 与 stage_cli；不能只复制 CLI。Blender 回归见 [test_source_normalize.py](../tests/test_source_normalize.py)，覆盖父级变换、多 mesh/材质/UV、接缝焊接、yaw、单位、重开与失败边界。

## product 接口契约

| 模块/函数 | 输入 → 输出与副作用 | 失败及限制 |
|---|---|---|
| `product_source.import_source` | 本地 GLB/glTF/STL 或 vertices/faces NPZ，显式 height 或 width（米）、ratio、rotation_z（有限弧度，默认 0） → 当前场景中的派生和保留副本 | 缺文件、无网格、零尺寸、非法比例拒绝；统一底面Z=0和XY居中，原始磁盘文件不改。NPZ不是自动设备尺寸证据。 |

product_source 在已施加来源世界变换后切换为 XYZ 再应用 Z 旋转，避免 glTF 的 QUATERNION 模式忽略 rotation_z。非零角度现在会实际影响按宽缩放和派生朝向；重新生成相关候选再验收。该接口保留当前场景、按宽/高选择、可选减面及隐藏原副本，与重置场景并写毫米 NPZ 的 normalize_source 契约不同，不能直接替换。
