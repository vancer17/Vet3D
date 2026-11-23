# 检查配置

未指定 `required_preservation` 时，使用下表必须项。指定之后，表内其余项目视为未纳入本次要求，不记为通过。配置修订号为 `1`。

| 工程类型 | 配置 id | 必须项 |
| --- | --- | --- |
| `drawing` | `drawing-preservation` | 图层、对象、块、尺寸、文字样式、外部参照、布局 |
| `part` | `part-preservation` | 单位、实体、草图、约束、参数、特征、配置、自定义属性 |
| `assembly` | `assembly-preservation` | 零部件、实例、位置、配合、配置、抑制、外部引用 |
| `drawing_sheet` | `sheet-preservation` | 模型关联、视图、尺寸、标注、图框、字体、布局 |
| `exchange_solid` | `exchange-solid` | 实体类型、单位、位置、几何 |

内容识别为高可信且任务没有声明类型时：DXF 视为图纸，FCStd 视为零件，STEP 视为交换实体。交换实体不默认拥有特征树。格式不能表达某项硬性要求时，该项失败，而不是记成空集合一致。

静态读取尚未解析的字段保持缺失或不受支持。DXF 布局、FCStd 参数和约束、STEP 几何都属于这一类，不能因为对象数量相同而通过。

`file_readable` 与 `source_protected` 始终必须。`native_open` 在 `require_native` 且指定了目标软件时必须。`dependencies_closed` 在声明了依赖或读到外部路径时必须。`roundtrip` 只在该模式必须。编辑探针未约定时为不适用。
