# 基线、版本关系和源码入口

## 已核实的最终组合（2026-11-06）

原工作区标识 `asset_4610c1f2`。来源桌面环境里它在 `packages/runtime/.data/environments/test/workspaces/asset_4610c1f2`。本仓库 `workflows/hex-terrain` 没有这份工作区，也没有贴图、BLEND、GLB 和脚本原件。下表是来源定位，不是新工程必须使用的路径；在目标工作区里从该工作区根解析相对路径。

| 角色 | 原工作区相对路径 |
| --- | --- |
| 当前通用配置 | config/hi3d-terrain-rules.json，version 2.1.2 |
| 最终地图JSON | exports/hi3d-hex-terrain-grid_48.json |
| 最终注册地形GLB | hi3d-hex-terrain-grid_37.glb |
| 对应未注册导出GLB | exports/hi3d-hex-terrain-grid_43.glb |
| 最终工程 | exports/hi3d-hex-terrain-grid_43.blend |
| 最终总览/水域近景 | exports/hi3d-hex-terrain-grid_43-overview.png / hi3d-hex-terrain-grid_43-water-detail.png |
| 自然库注册GLB | hi3d-hex-terrain-decorations_26.glb |
| 自然库工程/manifest | exports/hi3d-hex-terrain-decorations_28.blend / .json |
| 自然图集 | exports/hi3d-natural-decoration-atlas_1.png |
| 草坪注册GLB | hi3d-hex-terrain-grass-patches_2.glb |
| 草坪工程/manifest | exports/hi3d-hex-terrain-grass-patches_5.blend / .json |
| 草坪基础场 | exports/hi3d-grass-patch-edge-multiply_1.npz |
| 最终草坪SDF场/参数 | exports/hi3d-grass-patch-fields_4.npz / .json |
| 三档草坪自身纹理 | exports/hi3d-grass-patch-{dry,moderate,wet}-albedo_4.png |
| 文明库GLB/工程/manifest | hi3d-civilization-decorations_4.glb；exports/hi3d-civilization-decorations_4.blend / .json |
| 文明色块图 | exports/hi3d-civilization-decoration-palette_1.png |
| 已确认所有地表纹理 | exports/hi3d-approved-terrain-textures/ |

GLB注册序号、导出工程序号、JSON序号彼此不同；例如37/43/48属于同一最终状态。地图files可能只存basename，blend需在exports中解析，不能一律对所有files键都用地图所在目录或工作区根目录拼接。

## 原脚本职责

脚本位于原工作区scripts目录。下面是实现取材入口，不是建议按顺序无脑重跑；多数是单次迁移脚本，写死输入/输出/旧版本，还会检查目标不存在。复用前阅读依赖并改为新路径/参数，不运行旧脚本覆盖当前状态。

| 阶段 | 入口与用途 |
| --- | --- |
| 单格/拆分/地图/倒角 | hi3d-hex-terrain-tile_1.py、tile_2.py、grid_1.py、bevel_1.py（均带hi3d-hex-terrain-前缀） |
| JSON-only与环境 | hi3d-hex-terrain-json-only_1.py、values_1.py、frequency_1.py、sandiness_1.py |
| Top纹理/UV | hi3d-hex-terrain-textures_1.py、apply-json_1.py |
| 通用自然规则 | hi3d-terrain-apply-rules_1.py，含读取配置、路径、GLB、随机、普通装饰布局工具 |
| 草坪mask/预览 | hi3d-grass-patch-edge-multiply_1.py、hi3d-grass-patch-preview.py |
| 草坪最终资产/摆放 | hi3d-grass-patch-fields_4.py、hi3d-hex-terrain-grass-patches_4.py、hi3d-hex-terrain-grass-patches_5.py、hi3d-hex-terrain-place-grass-patches_1.py |
| 水面 | hi3d-hex-terrain-water_1.py、water-rotate_1.py、water-height_1.py |
| 河道与入水修订 | hi3d-hex-terrain-river_4.py、river-edit_2.py |
| 裁草 | hi3d-hex-terrain-clip-river-grass_1.py |
| 河纹/植物 | hi3d-river-texture-seamless_1.py、hi3d-hex-terrain-river-texture_2.py、river-plants-per-cell_3.py |
| 自然库合并/图集 | hi3d-natural-decoration-audit_1.py、hi3d-natural-decoration-atlas_1.py、hi3d-natural-decorations-merge_1.py |
| 文明建筑 | hi3d-village-decorations_2.py、hi3d-town-decorations_1.py、hi3d-fortress-decorations_3.py、hi3d-civilization-decorations_4.py |
| 文明贴图/资产入图 | hi3d-hex-terrain-civilization-assets_1.py |
| 文明布局与最终尺寸 | hi3d-hex-terrain-civilization-layout_2.py |
| 城墙 | hi3d-hex-terrain-civilization-walls_1.py、civilization-open-bottom-gate_1.py、civilization-corner-towers_1.py |

表内缩写后缀沿用同行完整前缀；可在[精确来源索引](11-source-inventory.json)中查全部真实文件名和sha256。

## 资源依赖与精确资产信息

[资源依赖索引](13-resource-dependencies.json)展开最终配置的36自然、3水下、9文明、1河水纹理（共49张），资产库，以及草坪基础场/SDF/独立albedo/图集；路径和SHA256取自原件。它按“加载现有成果”与“进一步编辑/重建”区分依赖，未把所有历史候选都列为当前必需输入。

[资产尺寸与替换契约](12-asset-catalog-and-transforms.md)保存自然22种、文明12种的中文身份、最终尺寸与原点/变换处理。不要把已确认缩放倍数再应用到最终库。

## 已知实现边界

这是一套经过逐步编辑得到的基础版本，尚不是单一命令即可完整重建所有层的统一生成器。`hi3d-terrain-apply-rules_1.py` 的主要执行流程仍是较早的自然贴图/装饰应用；后续草坪、河道、文明依赖专用脚本。不要因为它能解析最新配置就称它已支持完整文明系统；直接套到最终场景可能重置自然层，造成不同层不一致。

文明布局专用脚本假定存在第一道墙/第一个水口、至少有其他文明格；它包含level3逻辑，但原图没有堡垒格。这些需在新地图扩展时解除样例假定并补实摆验证。水域是显式7格测试，不含自动水流模拟、河道汇流网络、自动湖海判别或自动文明规划。

贴图和资产原件没有随本skill复制，快照不是可直接启动的完整工程包。本skill能指导复用/重建并保存规则，但不能在源资产不存在时承诺完全相同的画面。

旧 `exports/hi3d-terrain-rules-guide.md` 写的是规则1.2.1、水Alpha0.45和60–98株草；它已落后于2.1.2。草坪manifest摆放契约和预览标题也残留旧值，按本skill的最终对照处理。
