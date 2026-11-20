---
name: relief-brush
description: 从纹样文字、图片或已有 Hi3D 几何制作线性高度图、原生雕刻笔刷、几何印章和路径边饰，验证平面及曲面应用，交付工具文件、图片和展示网页；支持按实际需求设计可打印附件；主动打开成果页，视频交付后按需追加。
---

# 浮雕笔刷

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 relief-brush 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


完整任务按 [成果网页与按需视频](references/delivery-policy.md) 交付：**主动打开最终成果页；视频默认不渲染，基础结果交付后再询问，未回复不渲染**。图片、真实 3D 与结构/运动检查照常完成；用户已有明确视频请求则直接沿用。

制造版本按 [全打印规则](references/print-diy-workflow.md) 和 [本品类路线](references/diy-printing.md) 执行：完整设计尽可能实际完成一套全打印机械方案，保留已有外购版；不能只有方案文案而缺连接件。

首次、新设计或续接先读 [用户入口](references/user-guidance.md) 和 [完整推进](references/full-workflow.md)。用户明确只要 PNG/某阶段时遵从范围。业务运行按 [阶段计时](references/timing.md) 记录；依赖、Hi3D 授权/恢复及安装见 [工具约定](references/tooling.md)。维护 Skill 不执行其中的生成任务。

1. 明确目标软件/版本、资产类型、纹样来源、目标表面与毫米覆盖/深度。先实际查看样本及官方/作者资料，区别文字意图、概念图与真实几何。已有输入复用；需新网格时显式调用独立 `hi3d-api`，保留原件和脱敏任务记录。
2. 查看多角度和剖面，确定投射方向、遮挡、连通性与有效裁区。首击高度图不能保留倒扣，必要时改几何印章或分方向提取并说明。按 [配置](references/configuration.md) 显式指定采样轴、分辨率、裁区和模式，调用提取器；不套历史花纹区域。
3. 检查源射线缺失、原始/修补/掩膜、16位线性 PNG 与凹凸方向。孤立孔点的局部低谷修复须区分设计负空间，不能全局磨平。平铺同时核对边缘值、一阶差分、2×2实际几何和镜像汇合；周期连续不等于自然随机。
4. 根据目标格式创建原生 Brush、带底厚的几何印章和路径边饰。明确物理覆盖与深度，平面、圆柱和双曲面按弧长/法线应用；新会话实际导入并施加，不能只检查文件存在。见 [代码契约](references/code-contract.md) 和 [数字验证](references/validation.md)。未运行的目标软件格式标未验证，不能默换目标。
5. 打印试片可单件输出，不强造连接。用户选择拼板/握套才按 [连接研究](references/connector-research.md) 和 [DIY](references/diy-printing.md) 审计依赖、设计真实配合双方。实体任务无偏好先完成可行的全打印版本，已有方案保留，只有 PLA 不暗加 TPU/胶/磁铁。源代码没有完整拼接/锁环分支，需本次适配实跑。
6. 完成实际应用前后、从无纹到有纹的对照图与交互动作、可交互3D和说明网页；提供原生库、线性 PNG/元数据、源/配置、选中的制造件及下载。结束前打开网页与下载核对同一修订。纯高度图明确缩减范围时，以可读线性文件、方向/尺度元数据和检查说明为终点。

高度场测量和修补复用 [relief-map 核心](../.dependency-relief-map/references/heightfield-core.md)，本工作流保留来源读取、基线/尺度 profile 和业务后处理。

同步片段合并复用 [glb-clips](../.dependency-glb-clips/REFERENCE.md)，具体时间/通道限制见其契约；本流程仅为已明确同时播放的动作选择全部 clips。

<!-- managed-by: sparc3d-runtime -->
