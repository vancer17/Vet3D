# FreeCAD 适配器

第一个软件系列是 FreeCAD。STEP、DXF、FCStd 的静态读取属于这个适配器，不代表其他商业软件已经接入。接口未实现时保持关闭，不能返回空列表冒充一致。

| 能力 | 已实现 | 当前可执行 |
| --- | --- | --- |
| `identify` | 是。按 ISO-10303-21、DXF 组码或 FCStd 的 `Document.xml` 识别 | 不依赖 FreeCAD |
| `open_native` | 是。无头打开副本 | 仅当 `freecad` 指向可执行文件 |
| `read_layers` | 是。ASCII DXF 的 LAYER 表 | 不依赖 FreeCAD。STEP 不能表达图层 |
| `read_objects` | 是。DXF 句柄、FCStd 对象名和类型 | 静态读取不把 STEP 实体序号当成对象身份 |
| `read_features` | 是。FCStd 里 `PartDesign::` 与 `Sketcher::` 对象 | 不解析几何 |
| `read_parameters` | 否 | 否 |
| `read_assembly_relations` | 否 | 否 |
| `resolve_dependencies` | 是。任务声明的依赖，以及 DXF IMAGE 路径 | 工作区外的路径判为未闭合 |
| `save_copy` / `reopen_copy` | 是。只写隔离副本，再重新打开 | 需要可执行文件、`roundtrip` 模式和授权 |
| `rebuild_copy` | 否 | 否 |
| `edit_probe` | 否 | 否 |

二进制 DXF 只识别容器，不解析图层。压缩包成员含 `..` 或绝对路径时拒绝读取。原生打开达到 `budget_seconds` 后停止，不把半截结果当成通过。

目标软件不是 FreeCAD 时，即使本机存在可执行文件，`open_native`、`save_copy` 和 `reopen_copy` 也保持不可执行。ClassCAD 可以作为上游建模工具记在 `upstream_build.tool`，其会话引用只出现在报告里。本适配器不启动 ClassCAD，也不把源端几何、体积或渲染当成第三方原生工程的图层、特征或装配证据。被消费的中间实体和网格近似都不计入结构证明。

模拟适配器只用于程序流程。它的记录是 `mock`，不能计入实测通过。
