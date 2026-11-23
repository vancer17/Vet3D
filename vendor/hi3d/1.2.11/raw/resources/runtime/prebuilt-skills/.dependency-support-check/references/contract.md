# 质量与支承契约

唯一计算源 [support_core.py](../scripts/support_core.py) 不读写文件、不导入 Blender、不修改传入数组。空、非有限、负密度/质量、零体积与退化支承域均失败。输入实体须闭合、绕序一致且不含相互重叠而重复计质的零件；核心不证明这些前提，开放面片不能用体积积分当实体。

| 函数 | 输入和输出 |
| --- | --- |
| `mass_properties(vertices, triangles, *, density_g_cm3, unit_mm=1, volume_epsilon_mm3=1e-8)` | N×3 顶点、M×3 整数索引；每坐标单位对应 unit_mm 毫米，密度 g/cm³。相对顶点均值作有向四面体积分，减轻远离原点的消减误差；返回 signed_volume_mm3、绝对 volume_mm3、center_mm、mass_g。反绕序改变有向体积符号，不改变正质量；绝对体积不大于 epsilon 拒绝。 |
| `combine_mass(parts)` | 非空 `{mass_g, center_mm}` 列表→合质量和密度/质量加权重心；允许已知载荷质量，不要求伪造网格。 |
| `support_polygon(points_xy, *, round_digits=None)` | 非空有限 N×2 点→去重后的 CCW 凸包；默认不量化。调用方可显式指定小数位；线/点支承失败。 |
| `signed_margins(hull, point_xy)` | 严格凸 CCW 多边形与有限二维点→各有向边的垂距；全部正值才在内部，0 在边界，负值在外部。 |
| `assess_support(parts, contacts_mm, *, gravity=(0,0,-1), round_digits=None)` | 质量记录、接触点 mm、非零重力方向→合重心、垂直重力的正交平面基/原点、凸包、投影中心、边距和严格内部布尔。平面原点为接触均值；不是世界 XY 多边形。重力只取方向；不模拟接触法线与摩擦。 |

CLI [check_support.py](../scripts/check_support.py) 的 `check(source, output)` 读取 JSON，返回上述结果并以独占创建写报告；禁止覆盖输入、已有报告或包内文件。`parts` 每项可为完整网格参数或明确 `{mass_g, center_mm}`，其他顶层必需键为 `contacts_mm`、`gravity`。例如：

```json
{"parts":[{"mass_g":100,"center_mm":[0,0,20]}],"contacts_mm":[[-10,-10,0],[10,-10,0],[10,10,0],[-10,10,0]],"gravity":[0,0,-1]}
```

该例裕量 10 mm。通过 [测试](../tests/test_support.py) 核对单位/密度、远原点、反绕序、已知载荷、边界/域外与旋转重力；材质密度和接触点须由本次任务提供。相对旧 float32 品类积分改为 float64 相对原点积分，报告字段和物理口径保持，最后数位可能不同。
