---
name: rig-retarget
description: 为 T/A-Pose 人形角色建立或修正骨架与蒙皮，并按指定动画序列校准骨轴、休止姿态、手指、根位移和脚步，烘焙可编辑 Blender 动作。适用于新绑骨、auto-rig 高模回迁、已有绑定适配 BVH/MMD/VMD 等动作及局部拉伸修复；不承担模型生成、面部 DNA、打印关节或舞台渲染。
---

# 骨骼绑定与动画适配

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 rig-retarget 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


从已有模型或已绑定工程开始，交付与本角色及目标动作匹配的骨架、蒙皮和原生动画。保留已认可几何与贴图，按任务选择新绑定、已有绑定适配或局部修复，不因动作困难重新生成角色。

## 独立入口与输入

整个 `rig-retarget/` 包可独立安装到宿主技能目录，或明确提供实际路径并读取本文件，通过 `$rig-retarget` 调用。首次读 [运行说明](references/runtime.md)，确定本包 `RIG_SKILL_DIR`（包内命令也记为 `SKILL_DIR`）、Blender 与包外 `RUN_DIR`。

输入：角色模型/工程、目标动作或动作需求、需要保留的几何/材质/骨架/动作、最终格式、fps/时长与渲染要求。骨架语义、比例、衣物域和接触点由执行者对当前角色校准，不要求用户预先提供技术映射表。只有未指定且无法从素材确定的关键需求才需澄清。

本地流程使用随包 `scripts/run.py`，不依赖其他业务工作流。实际请求 auto-rig 或 mesh-lod 时才另行提供独立 `$mdf-call` 及可达服务；已有服务结果不重新提交。纯动作适配不要求 Hi3D、MDF 或 SciPy；具体动作格式导入器按需提供。依赖不通过相邻目录自动导入。

## 选择路径

| 输入/问题 | 操作与按需阅读 |
| --- | --- |
| 未绑定 T/A-Pose 身体 | 优先 [service_rig export / bind](references/service-rig.md)，显式交接 mdf-call；不适用服务时按 [几何与绑定](references/geometry-and-binding.md)校准并本地求解 |
| 已绑定角色要适配给定舞蹈/动作 | 先 `rig_adapter inspect`，再按 [已有骨架与序列适配](references/existing-rig.md)检查骨尾/roll、缓存源动作并烘焙；不要重跑新建骨架流水线 |
| 动作中局部尖刺或跨侧牵拉 | 先检查骨轴、父子空间与动作，再 `service_rig inspect / repair`；依据异常面和真实骨权重局部修复 |
| 已准备网格需要自建骨架/图权重 | `make_profile` → 执行者校准 → `build_character`；高模或 Blender 缺 SciPy 时读 [外部图求解](references/dense-skinning.md) |
| BVH 配合已校准比例骨架 | `cache_bvh`、`motion.build_action`，见 [BVH 与掌腕](references/motion-and-hands.md)；该旧构建路径不自动识别任意服务骨架 |
| 明确需要 LOD、游戏动作和挂点 | [LOD 交接](references/mesh-lod.md)、[游戏角色交付](references/game-delivery.md)；默认保留原面数与贴图 |
| 最终动作检查 | [验收](references/validation.md)：全帧形变、接缝、手指、脚步及保存重开；数值和视觉分别报告 |

原子函数与副作用见 [代码接口](references/code.md)、[适配接口](references/retarget-api.md)。阶段耗时按 [计时](references/timing.md)随任务产物记录。

## 必须保持的条件

- 原文件和原始服务/动作文件保留；新结果另存。纯绑骨/适配不隐含减面、重拓扑、焊接全部壳体、缩贴图、重建模型或增加渲染。用户说不渲染时仅用数值检查和 Blender 视口。
- 根据真实关节头与层级识别左右、掌腕、指骨；导入器合成骨尾可能没有解剖含义。只在确有轴向问题时校准，保留关节头位置；改 rest 轴会影响已有动作，须在候选中明确重烘目标动作，不能声称旧曲线仍等价。
- 坐标对齐后处理 rest 差异，再转为目标父骨局部旋转。T/A 姿势差异、手指局部关节增量和身体整体转动分开处理；不复制源 Euler、骨编号或某次四元数偏移。
- 腿长来自对应关节头链，不用显示骨尾长度或全身包围盒猜比例。保持骨段 scale=1；超出可达范围时报告脚目标误差并校准骨盆/步幅，不拉长腿去追源脚点。鞋底高度修正不是完整脚锁。
- 权重仅修改已定位区域；保留非骨骼组、连续皮肤接缝与独立衣物语义。更新已有权重时保留成员顺序，避免双四元数混合次序改变；平滑恶化时回退有效版本，不无限扩大修复域。
- 动作先求值/烘焙，再组织 Action/NLA。源约束、IK 和对象运动须进入实际求值缓存；目标约束/驱动/特殊继承不能当普通 FK 直接套用。本包适配器会拒绝不支持的目标结构。
- 高模检查可分块或使用经过 Blender 对照验证的加速计算；不能换低模或稀疏帧却声称原高模全段通过。拉伸、碰撞、穿插、循环速度及艺术自然度是不同结论。
- 不内置在线客户端。已授权服务沿原任务身份恢复，超时不自动重提。Hi3D 的 `HI3D_AK`、`HI3D_SK` 仅由独立工具的获授权鉴权进程内部消费；本包不读取密钥，维护测试只用本地素材或合成夹具。

## 交付与下游交接

交付打包贴图的 `.blend`、实际 Action/NLA 与 fps/帧范围、角色绑定/动作映射、来源、局部修复规则、检查结果和阶段耗时。只请求目标动作时不额外附加检查段。重新打开最终文件核对非空动作、实际变形和保留项；待检查或残留缺陷明确标记，不把保存成功叫作绑定质量通过。

其他 skill 显式提供本包后，交接模型/工程、动作、保留项和任务目录；接收已保存工程与报告，继续游戏、舞台或模型制作。它们不复制本包实现或通过相邻目录偷导入。模型生成、舞台/布料和渲染可由另行提供的 hi3d-model-gpt-animation 编排；头部表情/DNA 和打印关节保留专用流程。

公开 Runtime 模式读取 [auto-rig 交接](references/runtime-service-rig.md) 与 [LOD 结果](references/runtime-mesh-lod.md)，服务结果继续接入本入口现有动作映射、权重回迁和局部修复。

<!-- managed-by: sparc3d-runtime -->
