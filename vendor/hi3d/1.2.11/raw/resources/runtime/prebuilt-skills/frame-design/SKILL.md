---
name: frame-design
description: 从作品尺寸与展示场景设计艺术相框，将真实 Hi3D 局部纹样融入轮廓，制作可拆背板和支座、标准或打印 DIY 连接，交付尺寸检查、装配关键姿态、FDM 文件和展示网页；主动打开成果页，视频交付后按需追加。发光浮雕相框与混色/UV 照片板用 lithophane-lightbox。
---

# 艺术相框

发光浮雕相框、混色/UV 照片板与 V5.1 LED 背板灯箱用 [lithophane-lightbox](../lithophane-lightbox/SKILL.md)，不把本流程扩成透光照片板。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 frame-design 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


完整任务按 [成果网页与按需视频](references/delivery-policy.md) 交付：**主动打开最终成果页；视频默认不渲染，基础结果交付后再询问，未回复不渲染**。图片、真实 3D 与结构/运动检查照常完成；用户已有明确视频请求则直接沿用。

制造版本按 [全打印规则](references/print-diy-workflow.md) 和 [本品类路线](references/diy-printing.md) 执行：完整设计尽可能实际完成一套全打印机械方案，保留已有外购版；不能只有方案文案而缺连接件。

首次、新设计或续接先读 [用户入口](references/user-guidance.md) 与 [完整推进](references/full-workflow.md)。按 [阶段计时](references/timing.md) 记录业务运行，依赖和 Hi3D 调用/恢复见 [工具约定](references/tooling.md)。

1. 从真实作品净尺寸、可覆盖边、形状、厚度与桌面/墙挂场景建立尺寸简报。作品窗口、纸卡/玻璃、背板、槽和连接分别建模，不整体缩放配合。调研并实际看高规格相框/雕塑构图，保留图像留白与框的主次，不贴满重复纹样。
2. 根据作品选轮廓及局部装饰。新 Hi3D 输入只用已授权的独立 `hi3d-api`；多角度/剖面检查真实源。装饰顺曲率生长，控制叶/羽端厚度、连接切线与主脉，避免香蕉状厚叶和悬浮贴牌。程序基础轮廓与真实 Hi3D 装饰分别说明。
3. 按 [配置](references/configuration.md) 与 [代码契约](references/code-contract.md) 选或扩展配方：流动椭圆/枝叶或偏心圆口只是显式可选构型。保留作品槽、旋转压片和可拆支座的标准 M3 配方；另有 [110 mm 圆口全打印配方](references/diy-recipe.md)，以静止背衬、旋锁背环和双燕尾支座完成四件装配，附真实配对试片。固定机构不能任意缩放，其他尺寸或构型要按任务重设计。设计新连接先读 [连接研究](references/connector-research.md) 和 [DIY](references/diy-printing.md)，原版保留，配对件、保持与释放一并完成。
4. 连续承力框与支座不能只相切；先布尔实体，最后切精密孔/槽，独立回读每件。核对作品装入、压片/闩解锁、背板与支座全程，实际接地和重心假设；墙挂需保留墙体/锚固依赖，不能用桌面模型声称满足墙挂。
5. 按 [验证](references/validation.md) 看中性细节、前后/剖面、真实桌面场景与完整安装/换片动作检查。动画用真实枢轴和同步动作，不能拿父子关系证明机械连接。生成最终GLB/STL/native、BOM/装配说明及图片与3D网页，按 [制作包完整性](references/delivery-completeness.md) 解压最终下载并逐项核对主体、连接、试片与工具，标明数字检查与实物试制的区别。

同步片段合并复用 [glb-clips](../.dependency-glb-clips/REFERENCE.md)，具体时间/通道限制见其契约；本流程仅为已明确同时播放的动作选择全部 clips。

姿态/求值公共能力按 [motion-check 契约](../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

试片裁切、间隙系列与配对来源记录复用 [fit-coupon](../.dependency-fit-coupon/REFERENCE.md)；本入口保留专用机构、支撑和实际公差定义。

<!-- managed-by: sparc3d-runtime -->
