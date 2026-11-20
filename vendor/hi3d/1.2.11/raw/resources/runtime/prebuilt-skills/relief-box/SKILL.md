---
name: relief-box
description: 按收纳物和取放方式设计浮雕收纳盒或旅行首饰盒，将 Hi3D 纹样融入盒盖，完成分区、可拆内托、开合和保持结构，支持标准或打印 DIY 路线，交付模型、图片、制造包和网页；主动打开成果页，视频交付后按需追加。
---

# 浮雕收纳盒

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。


## 独立工作流与依赖

执行 relief-box 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录；下文脚本和资源路径均指物化后的工作流包，分发时保留依赖与文档布局。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文品类阶段一起使用；已有中间输入可从对应阶段继续。


完整任务按 [成果网页与按需视频](references/delivery-policy.md) 交付：**主动打开最终成果页；视频默认不渲染，基础结果交付后再询问，未回复不渲染**。图片、真实 3D 与结构/运动检查照常完成；用户已有明确视频请求则直接沿用。

制造版本按 [全打印规则](references/print-diy-workflow.md) 和 [本品类路线](references/diy-printing.md) 执行：完整设计尽可能实际完成一套全打印机械方案，保留已有外购版；不能只有方案文案而缺连接件。

首次、新设计或续接先读 [用户入口](references/user-guidance.md) 与 [完整推进](references/full-workflow.md)。业务阶段按 [计时](references/timing.md) 记录；外部依赖和 Hi3D 恢复见 [工具约定](references/tooling.md)。

1. 先定义收纳物的数量/包络、拿取方式、固定位置和携带场景，再选外轮廓。实际看高规格收纳与首饰盒图片/装配资料，区分照片可见分隔与未经证明的可拆能力。戒指、耳针、项链的逃逸/缠结路径分别设计，不把好看的空格当旅行保持。
2. 确定盖面纹样密度、留白和起伏。新 Hi3D 纹样通过独立 `hi3d-api`，检查真实多角度/剖面和源边界；盖面高度/曲率映射保留细节，装饰不穿内腔、不挡抓盖或锁位。按 [配置](references/configuration.md) 选显式配方，不能把特定三区旧布局当任意物品的通用解。
3. 建立真实壁厚/底厚、可用净高、定位裙、内托、分隔、取托边和软接触占位。标准件、泡棉/织物模板与实际打印件分开。开合连接先 [研究](references/connector-research.md) 再按 [DIY](references/diy-printing.md) 选型；原 M3 提盖版保留，打印路线生成双方锁座/闩/键等真实零件。
4. 确保物品、盖垫、裙边不互相硬穿；椭圆边界裁切内衬四角，计算盖落桌最低点。提盖结构只做真实提盖，不用旋转动画冒充铰链。检查内托、耳卡、绕线芯全路径与末帧重新合盖锁止。
5. 用 [代码契约](references/code-contract.md) 生成并独立回读文件，按 [验证](references/validation.md) 实际审查中性纹样、盖底与内区。交付同一版本GLB、STL、软衬模板或真实TPU件、native/配置、BOM和存取关键姿态，完成可交互网页与下载。数字闭合/无碰撞不等于防刮、运输保护或试印通过。

姿态/求值公共能力按 [motion-check 契约](../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

<!-- managed-by: sparc3d-runtime -->
