---
name: hex-terrain
description: 在 Blender 中按 JSON 规则创建或修订 lowpoly 正六边形地形，处理分离地格、环境贴图、自然装饰与草坪、水域河流、文明建筑和边界城墙，并导出经过重导入检查的 GLB。适用于复用规则 2.1.2；不含贴图与模型原件，不能从本包直接跑出原工程画面。
---

# 正六边形地形

把地图尺寸、种子、海拔和显式河道/文明输入做成可编辑的 Blender 地形，并导出重导入后颜色、透明度和变换仍然正确的 GLB。地形语义留在 JSON；GLB 只保存可见几何、材质、变换和米制单位标记。基线规则版本是 `2.1.2`。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。已有地图、工程和贴图留在任务目录。询问现状或讨论方案本身不授权改模型。

## 独立工作流

按 [打包约定](../.dependency-package-tools/references/usage.md) 提供本目录后，通过 `$hex-terrain` 或显式读取本文件调用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者写入包外任务目录；本包没有自动计时脚本，token 无采集时标 unavailable。

本包保存规则、资产尺寸快照和来源索引。`assets/baseline/` 里的 JSON 仍按原工程 `config/` 的相对路径解释，不能从本目录直接执行。贴图、装饰网格、草坪场和完整地图不在包内。源资产不存在时，不能承诺画面与 `asset_4610c1f2` 完全相同。

## 先确定当前任务

- **继续原工程**：先读 [基线与文件索引](references/08-baseline-and-sources.md)。自然库、文明库、草坪和地图的序号各自独立，不能用相同后缀配成一套。
- **新建一张同类地图**：读 [地格与数据](references/01-grid-and-data.md)，复用规则和已绑定的资产，替换尺寸、种子、海拔及显式河道/文明输入。
- **改某一个模块**：只读下表对应细则，保留用户已确认的其他部分。目标改变什么就重算哪一层；资产造型已合格时不重新生成。

## 必须保持的设计边界

1. 随机场、海拔、水位、文明度、流向和实例记录保存在 JSON。改 JSON 属性与应用可视化是两个阶段。
2. 每格上表面 `Top` 与侧底部 `Body` 分离。底面 Z=0，顶面 `altitude×0.1m`。3cm 倒角属于 Body，不随柱高拉伸。
3. 自然陆地由温度×湿度×材质构成 36 种贴图。植被不是地表材质。普通陆地贴图不要求四方连续；河水纹理沿 V 方向连续。
4. 自然普通装饰、河流植物、文明建筑各款一个 mesh、一个材质，使用嵌入式图集。草坪保留 Turf/Blades，每格所有三角草合成一个草叶物体。
5. 草坪一格一个、不缩放、只旋转 60° 整数倍。自然普通装饰随机缩放 0.6–1.0。文明建筑使用最终资产原尺寸和确定性功能布局。
6. 水下判定为 `waterLevel > altitude`。最终水面高度是 `(waterLevel−0.25)×0.1m`。水域与河流 Alpha 均为 0.7。
7. 河流只沿相邻格流向更低或等高处，不重访格子；一条河一个连通 mesh。河道覆盖处移除普通装饰；草坪保留实例，但裁去覆盖到的 Turf 和 Blades。
8. 文明度是 0–3。水下强制 0。文明地格替换自然地表和陆地装饰，保留独立河流层。墙只在地图内部文明/自然的共享边生成；水口开到墙体最底部。

早期被推翻的规则见 [修改决策](references/09-decisions.md)。对话摘录只作历史证据，见 [需求摘录](references/10-conversation-requirements.md)；同一主题以最新决定和现行配置为准。

## 分模块细则

| 任务 | 阅读 |
| --- | --- |
| 六边形、坐标、海拔、JSON、三个环境场 | [01 地格与数据](references/01-grid-and-data.md) |
| 36 张自然贴图、水底和文明贴图、UV | [02 纹理](references/02-textures.md) |
| 22 种自然资产、密度、随机与碰撞 | [03 自然装饰](references/03-natural-decorations.md) |
| 草坪范围、三角草、摆放与河道裁剪 | [04 特殊草坪](references/04-grass-patches.md) |
| 水面、河流几何/UV/植物、入水衔接 | [05 水域与河流](references/05-water-and-rivers.md) |
| 12 种文明资产、功能布局、墙/水口/角楼 | [06 文明](references/06-civilization.md) |
| 导出、性能、验证、失败定位 | [07 实施与验收](references/07-workflow-and-validation.md) |
| 文件组合、脚本职责、实现局限 | [08 基线与来源](references/08-baseline-and-sources.md) |
| 资产尺寸、中文身份、图集和实例替换 | [12 资产契约](references/12-asset-catalog-and-transforms.md) |
| 49 张地表纹理与草坪场依赖 | [13 资源索引](references/13-resource-dependencies.json) |

原脚本是单次迁移脚本，写死旧路径。复用前改到新路径，不用旧脚本覆盖已有版本。`hi3d-terrain-apply-rules` 不能单独代表完整文明系统。

## 条件交接

| 阶段 | 交接 |
| --- | --- |
| Blender 工程 | 需要后台打开、导入或另存 BLEND 时，交接 [blender-tools](../.dependency-blender-tools/REFERENCE.md)，不另写 Blender 启动器。米制、`scale_length=1`。不操作未保存的前台工程。 |
| 缺失资产 | 缺少合格地表或装饰资产且用户明确要求生成时，显式交接 [hi3d-api](../hi3d/SKILL.md)。已有贴图和模型不生成。图片调用失败不自动重提。 |

这些依赖需另行完整提供。已有合格地格、贴图、装饰、河流或文明层时跳过对应阶段。

## 本地计算预算

地格生成、装饰散布、河流 mesh、文明墙和离线渲染可能长时间占用 CPU，且期间可以没有业务产物。进入这些步骤前，任务目录必须已有预算和心跳；后台 Blender 由 [run-tools](../.dependency-run-tools/references/budget-run.md) 的 `process_run.run_budgeted` 启动。建议低档 120 秒（单格或预览）、中档 600 秒（一层装饰或一条河）、高档 1800 秒（整张地图导出）。低档可直接跑；中高档由宿主 `waiting_choice` 使用本入口 `choices_example` 确认后再启动。超时记 `interrupted`，不写半截工程。加时只在用户确认后用新输出目录和新的 `max_wall_seconds` 再跑。Hi3D 远端等待不套用本地 kill。

## 完成条件

交付可编辑 blend、对应地图 JSON、当前规则，以及重导入后可见颜色、透明度和变换正确的 GLB。说明实际通过的检查、缺失的源资产，以及尚未登记到 Studio 的文件。JSON 里历史 `checks` 为 true 不等于这次重新通过。文件存在或导出成功不等于验收通过。

<!-- managed-by: sparc3d-runtime -->
