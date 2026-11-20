---
name: ue5-exploration-demo
description: 根据文字或参考图制作紧凑、可编辑的 UE5 展示场景，组织概念、高精资产交接、人物绑定交接、样板区、天气与外围，并在真实虚幻画面中验收。支持已有工程的局部修改；未安装引擎时不把脚本或空目录称为可打开工程。
---

# UE5 展示场景

把文字、参考图或用户指定的已有工程做成可编辑的 UE5 展示场景。场景主题、镜头、资产和交互由本次需求决定。通用三维探索或网页游戏使用 [build-explorable-3d-game](../build-explorable-3d-game/SKILL.md)。Unity 桌面治愈系探索使用 [unity-cozy-exploration-game](../unity-cozy-exploration-game/SKILL.md)，不在本入口改写成 Unity 工程。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。新图和生模经 Runtime `hi3d_api` 完成；人物新绑定经 Runtime `mdf_api` 或已确认的公开 mesh/invoke，由下游入口执行。已有工程、导入和本地构建留在任务目录。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。

## 独立工作流

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 提供本目录后，通过 `$ue5-exploration-demo` 或显式读取本文件调用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者把真实起止、状态和耗时写到包外任务目录；本包没有自动计时脚本，token 无采集时标 unavailable。虚幻编辑器、Cook 和打包是外部进程，不套用本地无界 CPU 的 kill。

本机迁入时未安装虚幻引擎，未打开编辑器，也未 Cook 或打包。环境探测、导入和验收只规定要检查的事实，不能把文件存在写成工程已通过。

来源包中的 `hi3d-credentials.json` 不迁入，也不要在本目录重建。生成密钥只使用 `HI3D_AK`、`HI3D_SK`，由已授权的 `hi3d-api` 进程内部消费；AI 不读取、打印或验证其值，不读取凭据文件。绑骨 Cookie 由宿主账号通道附加，不写入本包、日志或 UE 工程。

## 目标与适用范围

默认交付适合较短漫游展示的完整场景：相邻的活动区域、明确入口和主视觉、可通行的地面，以及近景、光照和可见背景。用户明确要求辽阔、留白或指定面积时按该目标设计。未指定风格时采用高保真自然表现；用户要求风格化时保持该完成度。

新场景重新设计可见美术，不默认复制其他项目的地图、建筑、人物或贴图。可以复用引擎、已有 API 客户端和通用导入方法。同一委托里已经合格的概念图、模型和绑定继续使用，保留原任务标识。局部修改只处理受影响的地图、资产和逻辑。

仅要场景时交付可编辑工程、启动方式和验证记录。用户要求独立运行包时才 Cook 和打包。没有目标平台的工具链时，不把只改 `-platform` 写成跨平台包已经可构建。

## 执行入口与必要输入

1. 从实际执行机器探测 `host_os` 和 CPU 架构。远程机、容器、WSL 与桌面分开记录，不从截图或示例路径推断。
2. `target_platform` 以用户指定为准。未指定时交付当前宿主能打开的可编辑工程，不自动做双平台包。
3. `asset_mode` 分开记录：`hi3d` 生成所需外观，`existing` 只用用户指定的续作或素材，`procedural` 做地形、散布、碰撞和结构装配，`auto` 按资产组合。新场景的 `auto` 不自动允许其他项目的美术资源。是否绑骨单独判断。
4. 用户已经给出目标时直接制作，不另开需求访谈。收费提交、覆盖已有交付和宿主不可逆检查仍走宿主编排，不在本入口再做一套确认弹窗。
5. 用 [制作记录](assets/production-record.md) 记下视觉目标、资产、任务标识和验收。记录放在包外任务目录，路径尽量相对工程。

## 阶段

| 阶段 | 要得到的结果 | 何时读取 |
| --- | --- | --- |
| 视觉目标 | 风格、空间、路线、色彩、光照和可玩/可视范围 | 新场景读 [视觉目标](references/art-direction.md) |
| 资产 | 可编辑母版、单体图和高精模型 | 制作或替换可见资产时读 [资产](references/assets.md) |
| 环境 | 真实引擎路径、平台分支和工程骨架 | 建工程或导入前读 [环境](references/ue-environment.md) |
| 场景 | 样板区、天气、外围和交互 | 装配关卡时读 [场景](references/scene.md) |
| 验收与交付 | 工程、画面、运行和可选打包分开记录 | 放行前读 [验收](references/acceptance.md) |

已有合格输入跳过对应阶段并写明原因。缺少虚幻引擎时，可以继续设计、清单和已授权的资产生成，并把 UE 导入与实机验收标为未完成。

## 条件交接

| 阶段 | 交接 |
| --- | --- |
| 概念图、单体图、新建模型 | 缺少合格参考图或模型时，显式交接 [hi3d-api](../hi3d/SKILL.md)：逐资产规格、参考图和任务目录交给它，取回原始 GLB 与任务记录；已有合格模型不生成。图片调用失败不自动重提。精细可见资产使用 `model_type=v3.0:quality` 与 `generation_type=both`，不升到 `v3.0:master`。 |
| 需要活动的人物 | 需要活动且没有合格绑定的人物，交接 [rig-retarget](../rig-retarget/SKILL.md)，取回已检查的骨架与蒙皮；已有合格绑定不重绑。新身体绑定由 rig-retarget 按需组合 [mdf-call](../mdf-api/SKILL.md) 的 mesh/invoke，本入口不另写 Cookie 客户端。 |
| Blender 工程 | 需要后台打开、导入或另存 BLEND 时，交接 [blender-tools](../.dependency-blender-tools/REFERENCE.md) 的场景读写，不另写 Blender 启动器。 |
| UE 导入与关卡 | 使用当前版本已核实的 Python、Blueprint 或 C++。不生成假 `.uasset`、假 `.umap`，也不假定第三方 UE 插件已经安装。 |
| 引擎水体 | 场景需要虚幻水体且工程为 5.7 或更高时，交接 [dcc-preset](../dcc-preset/SKILL.md) 的 `unreal.water`，在 `.uproject` 启用 `Water` 与 `Landmass`。样例或浅水模拟另选 `unreal.water-samples`、`unreal.water-simulation`。低于 5.7 不套用。插件启用后仍须在关卡里放置水体，本交接不创建 Actor。 |

这些依赖需另行完整提供。仓库路径只是查找线索。Hi3D 与绑骨的提交、查询、下载和未知结果恢复遵从各自入口，不在这里复制客户端或另定重试次数。

## 完成条件

- 可见内容达到 [验收](references/acceptance.md) 的适用检查。临时圆柱树干、三角叶片、多面体岩石、单色地面和椭球动物不能留在最终地图。
- 样板区在真实 UE 画面中看过并达到视觉目标后，才扩展同类布景。没有渲染环境时交付阶段工程，并标明视觉未验证。
- 概念图、API 预览和 UE 画面分开标注。工程能加载、角色能移动、画面合格、包能启动，各自记录，不能互相代替。
- 分享工程时排除密钥、Cookie、Token、临时下载 URL 和可再生缓存。

## 停止与恢复

从第一个未完成步骤继续：环境、生成、下载、绑定、导入、装配、运行、打包分开记录。模型生成使用 `hi3d-api` 的 task ID；绑定使用 `mdf-call` / `rig-retarget` 的调用记录。绑定失败不重生成合格模型，导入失败不重投已完成的绑定。

同一问题经过两轮有针对性的修复仍无改善时，重新检查结构、输入和原因，不追加相同收费请求。

## 无私有数据的测试任务

> 用一段“雨后石拱门与临溪茶棚”的文字，做一版可步行的紧凑 UE5 展示场景：一座可穿行的石拱、一座功能不同的茶棚、一棵近景树、一段湿润地面和轻微体积云。不要 NPC。已有合格模型不重做。本机没有虚幻引擎时，完成概念与资产交接，并把导入、样板区画面和打包标为未验证。

可观察结果：资产清单能区分拱门与茶棚；高精路由指向 `v3.0:quality`；没有凭据文件；未安装引擎时最终记录含未验证项，而不是一份自称可打开的空目录。

<!-- managed-by: sparc3d-runtime -->
