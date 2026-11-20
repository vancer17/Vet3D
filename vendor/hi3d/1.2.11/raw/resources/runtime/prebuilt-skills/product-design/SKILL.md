---
name: product-design
description: "从文字、图像或已有艺术模型完成通用产品设计、工程化、验证和图片/3D/制造包交付，供品类工作流组合。"
---

# 产品设计交付

从文字、图像或已有艺术模型完成通用产品设计、工程化、验证和图片/3D/制造包交付，供品类工作流组合。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口下述公共 API、内部 MDF、其他图像工具与 shell 联网示例只适用于明确的非 Runtime 环境；desktop 的新图/3D 和公开处理经 Runtime `hi3d_api`、`mdf_api` 完成，已有产物继续本地步骤。

任务拆解见 [architecture.yaml](pcg/architecture.yaml)。[routes.yaml](pcg/routes.yaml) 只描述用户检查点与 option，不是执行架构图。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。

## 输入与完成结果

- 输入：当前主题、明确品类输入契约、尺度/材料及已有资产；产品专属工作流提供造型、功能和验收条件。
- 输出：按 references/full-workflow.md 编排连接研究、概念与来源、结构、打印方案、图片/3D、网页/文件与阶段记录；最终输出真实可打开的文件。

## 调用与边界

本入口负责通用端到端顺序；具体几何和制造约束由所选品类合同明确，已有输入跳过对应上游。基础交付完成后仅在明确请求时追加视频。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
