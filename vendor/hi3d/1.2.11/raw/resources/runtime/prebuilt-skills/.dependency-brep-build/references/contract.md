# 配方契约

schema 必须为 `brep-build.v1`，`units` 必须为 `mm`。禁止出现 `mesh`、`glb`、`stl`、`fit`、`sew`、`screenshot`、`from_mesh` 等反求字段。

## 实体 `kind`

| kind | 必填 | 说明 |
| --- | --- | --- |
| `box` | `length_mm` `width_mm` `height_mm` | 中心在 origin 的盒 |
| `cylinder` | `diameter_mm` `height_mm` | 底面在 origin、沿 +Z |
| `cone` | `diameter_bottom_mm` `diameter_top_mm` `height_mm` | 顶径可为 0 |
| `shell` | `source` `thickness_mm` | 对已有实体向内抽壳 |
| `iso_metric_thread` | `role` `designation` `length_mm` | `external`/`internal`；`ends` 为 `none` 或 `chamfer` |
| `iso_clearance_hole` | `designation` `depth_mm` | 中等配合通孔圆柱，作切刀 |
| `iso_tapped_hole` | `designation` `depth_mm` | 内螺纹切刀 |
| `import_step` | `path` | 已有 `.step`/`.stp` 操作数，不把网格 CAD 化 |

`origin` 可选 `[x,y,z]`，缺省原点。`id` 符合 `[A-Za-z][A-Za-z0-9_]{0,63}`。最多 16 个实体、20 次 ops。螺纹长度 ≤ 80 mm。

`designation` 为 `M12x1.5` 或粗牙 `M12`。配对公母螺纹须同一 designation；径向间隙由调用方用切刀尺寸表达，本入口不给“能拧上”的默认间隙。

## 布尔与倒角

`union` / `cut` / `intersect` 需要 `a` `b` `out`。`fillet` / `chamfer` 需要已有 `solid`、`radius_mm` 和 nonempty `edges`（`*` 表示全部边）。找不到边或结果空实体则失败。

`export` 为要落盘的 id 列表。`tessellation_mm` 默认 0.2，范围 (0.05, 2]。

## 预算

可选 `budget.max_wall_s`、`heartbeat_s`、`extend_used`。档位由实体/布尔分值估算：低 30s 可直接跑，中 60s / 高 120s 需确认。分值过高直接拒绝。`extend_used` 必须伴随显式 `max_wall_s`，并由 `--confirm-budget` 启动。
