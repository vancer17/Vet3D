---
name: stream-scene
description: "从参考视频、截图或已有模型编排可编辑溪流场景。按宿主调用 dcc-preset 打开 UE 5.7 及以上水体插件、Houdini 海洋谱或 Blender 流体域，再装配岸线与可选网页。可装泵的水景和通用 UE 展示不在本入口。"
---

# 可编辑溪流场景

把参考、已有模型或已有工程编排成可编辑的溪流场景。水体入口只调用 [dcc-preset](../dcc-preset/SKILL.md)；本入口保留宿主选择、资产交接、岸线装配、画面摆放和按需离线包。可步行的虚幻展示场景继续用 [ue5-exploration-demo](../ue5-exploration-demo/SKILL.md)。可装泵的循环水景使用 [water-feature](../water-feature/SKILL.md)。本入口使用实时美术水面和有限流场近似，不输出工程水力学。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。新图和生模经 Runtime `hi3d_api` 完成。已有模型和本地工程留在任务目录。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。

## 独立工作流

按 [打包约定](../.dependency-package-tools/references/usage.md) 提供本目录后，通过 `$stream-scene` 或显式读取本文件调用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者写入包外任务目录；本包没有自动计时脚本，token 无采集时标 unavailable。dcc-preset、Hi3D 查询和虚幻编辑器都不套用本地无界 CPU 的 kill。

来源草稿里的参考页没有随包提供可执行的网页着色器。本入口不把基础 BLEND、HIP 或已启用的插件说成包含细波、白沫和网页交互。

## 输入与完成

输入可以是视频、参考图、标注、GLB、BLEND、HIP、UE 工程、已有网页，或导出的布局 JSON。先确认新建、接续还是局部修订，以及目标是 Blender、Houdini、虚幻、网页，还是其中的组合。

视频只能支撑可见效果，不能据此断言原作者源码、引擎、着色器或真实物理参数。把「参考中观察到」「用户明确指定」「实现时合理假设」分开写。标注若是在描述当前错误，不沿错误方向生成新流场。

成功是目标宿主里的场景或交互满足最新要求，并在对应打开方式下看过。文件存在、插件已启用或控件出现，都不能单独代表水流、编辑或离线使用成功。

## 阶段

| 阶段 | 何时做 | 读取 |
| --- | --- | --- |
| 目标 | 每次新建或接续 | [任务判断](references/brief.md) |
| 水体预制 | 目标宿主还没有对应的水体入口 | [预制调用](references/preset.md) |
| 资产 | 缺少复杂外观，或要替换植物、桥、石 | [资产](references/assets.md) |
| 装配 | 要岸线、落差、树木贴地或河道修订 | [装配](references/scene.md) |
| 画面 | 用户要网页调色、摆放或默认参数 | [画面与编辑](references/art.md) |
| 减面 | 重复高模造成卡顿，或目标设备有预算 | [性能](references/optimize.md) |
| 验收 | 交付任何场景或网页前 | [验收](references/accept.md) |
| 离线包 | 用户要求解压后直接打开 | [离线交付](references/offline.md) |

已有合格结果直接续接。只改参数、树木、河道或打包时，不重开预制、不重新生成资产。

## 条件交接

| 阶段 | 交接 |
| --- | --- |
| 水体预制 | 目标是虚幻且工程为 5.7 或更高时，调用 [dcc-preset](../dcc-preset/SKILL.md) 的 `unreal.water`，把 `Water` 与 `Landmass` 写入 `.uproject`。用户要示例或浅水模拟时改用 `unreal.water-samples`、`unreal.water-simulation`。目标是 Houdini 20.5 或更高时调用 `houdini.ocean-spectrum`。目标是 Blender 4.2 或更高时调用 `blender.fluid-domain`。低于对应版本不套用，也不改用另一套几何假装预制已打开。 |
| 复杂资产 | 缺少合格的复杂外观资产时，显式交接 [hi3d-api](../hi3d/SKILL.md)，交参考图、规格和任务目录，取回原始 GLB 与任务记录。已有合格模型不生成。图片调用失败不自动重提。 |
| Blender 工程 | 需要后台打开、导入或另存 BLEND 时，交接 [blender-tools](../.dependency-blender-tools/REFERENCE.md)，不另写 Blender 启动器。 |

这些依赖需另行完整提供。写入 `.uproject`、HIP 或 BLEND 前，由宿主按本入口 `preset` 检查点确认；确认之后才给 dcc-preset 加 `--write`，不在对话里再问一遍。

## 停止与恢复

生成或处理失败时保留原任务和结果，继续不依赖该失败输出的阶段。缺少任务 ID 本身不是重新提交的理由。无法实际打开最终网页或离线副本时标明未验证，不以静态文件检查代替。

不默认生成视频、发布公网、安装软件、制作多人服务或打印文件。

<!-- managed-by: sparc3d-runtime -->
