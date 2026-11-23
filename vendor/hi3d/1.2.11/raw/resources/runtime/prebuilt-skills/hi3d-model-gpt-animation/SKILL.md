---
name: hi3d-model-gpt-animation
description: 编排已有或 Hi3D 人形模型的 Blender 动画交付，显式复用 rig-retarget 完成绑骨、蒙皮修复与序列适配；自身处理模型交接、动作裁剪、多人舞台、披风/接触、按需预览及游戏资产组织。已有工程可增量修订，不重复生成或重绑。
---

# 模型到 Blender 动画交付

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 hi3d-model-gpt-animation 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


从已有模型或认可工程开始，组织本次需要的生成、绑定、动作、次级运动和交付。具体骨架与蒙皮实现由独立 rig-retarget 唯一维护，本包保留舞台、布料和展示编排。

## 独立入口与显式依赖

完整提供本文件夹，通过 `$hi3d-model-gpt-animation` 或明确路径读取入口。首次读 [运行说明](references/runtime.md)，确定本包 `SKILL_DIR`、包外 `RUN_DIR`、Python 和 Blender。依赖按任务提供，已有输入跳过上游工作：

| 阶段 | 依赖与产物交接 |
| --- | --- |
| 需要从图片生成/恢复模型 | 独立 `$hi3d-api`：图片与规格 → 原始 GLB/任务记录；见 [模型交接](references/model-generation.md) |
| 新绑定、服务高模回迁、已有骨架/手指修复、目标序列适配 | 独立 `$rig-retarget`：模型/工程、动作与保留项 → 已检查的绑定工程、Action/映射/报告；见 [绑定交接](references/rigging.md) |
| LOD 减面/重烘或 auto-rig 请求 | 由 rig-retarget 按需显式组合 `$mdf-call`；已有绑定/LOD 不重新请求 |
| 本包舞台、布料、接触与预览 CLI | Blender/Pillow 按需加载；共享场景读写、动作和摘要函数来自显式 `--rig-skill "$RIG_SKILL_DIR"`；只加载所需原子函数，不运行绑定阶段 |

依赖完整安装到宿主技能目录或由上下文提供实际路径并读取入口；源码相邻不构成安装或隐式导入契约。需要的输入已具备时不重跑生成、LOD 或绑骨。共享库是脚本运行依赖，与是否执行上游业务阶段分开。

## 选择工作

| 任务 | 操作 |
| --- | --- |
| 绑定、权重或按动作改 rig | 交接 rig-retarget，读取其对应参考，不在本包写第二套实现 |
| 裁剪、朝向、文字及舞台修订 | `stage_ops inspect / clip / orient / text`；读 [舞台命令](references/stage-commands.md)与必要的 [编排](references/stage-and-revisions.md) |
| 披风、尾巴、代理与接触 | 执行者按角色建立语义拆件/代理，`embed_cloth`、`contact_check`；读 [次级运动](references/garments-and-secondary-motion.md)与 [命令](references/cloth-and-contact-commands.md) |
| 请求预览或拼图 | `render_samples`、`contact_sheet`；读 [验收](references/validation-and-runtime.md) |
| 游戏 LOD、动作与挂点 | 由 rig-retarget 的 game-delivery 交接；本包组织最终资产与检查报告，不隐含引擎整合 |

本包原子接口见 [代码说明](references/code.md)。给定动作的下载/导入依来源与许可处理，不捆绑生产角色或动作数据。

## 保留与验收

保留原始工程、模型、贴图及用户认可结果，局部修改只处理指定对象/通道。不得把既有蒙皮工程送进清空场景的新建骨架流水线。用户面数、动作来源、时长、人数与渲染要求优先；说不渲染时只做数值与视口检查。

先完成身体 Action，再组织 NLA/舞台/布料；身体或代理改变后重建相关缓存。`clip` 限于已烘焙且无约束/驱动的姿态，`embed_cloth` 接已烘焙固定拓扑代理，`contact_check` 不自动修复或检测包含关系；边界按各命令说明执行。

仅上传已授权模型；Hi3D 的 `HI3D_AK`、`HI3D_SK` 只由独立工具鉴权进程内部消费，AI 不读取密钥。服务超时保留原身份，不自动重提；维护测试不调用收费服务。

重开最终保存文件，检查实际网格、材质/打包贴图、Action/NLA、fps/帧范围。新蒙皮/新动作由 rig-retarget 检查全段变形、掌腕和脚步；本包检查实际舞台、最终高模接触与布料可搬移。文字修订按对应不变量检查。数值、视口、连续时间接触和引擎验证分别报告，残留问题明确说明。

交付主 `.blend`、本次生成的原始模型/LOD、动作来源/映射和修订记录、必要验证与打开说明。只需目标动作时不额外增加检查段；没有视频请求不渲染视频。

## 阶段统计

执行者按实际模型生成、绑定/动作交接、衣物/舞台、验证/预览和交付阶段，在包外任务报告记录 task/attempt、status、带时区 start/end 和单调时钟 seconds。失败、中断、已授权重试追加并关联原任务，未执行标 skipped；缺失时间说明原因和覆盖范围，不填 0 或编造。计量工具等待，服务计算另列，父子调用注明包含关系，同一 rig-retarget 阶段不重复计量；总墙钟按业务起止区间计算，不累加重叠阶段。

Token 可选，只记录宿主/API 实测 usage 及来源/范围，不把总量分摊到阶段，不从额度、字符数或耗时推算。未采集不影响耗时与交付。现有舞台脚本不自动记录全业务计时，执行者补齐并交付摘要和记录位置；运行日志不写回 skill。

需要公开绑定或多档 LOD 时，将已生成 GLB 交给 [rig-retarget](../rig-retarget/SKILL.md)，使用其 Runtime 分支及现有原子动作/蒙皮实现。

<!-- managed-by: sparc3d-runtime -->
