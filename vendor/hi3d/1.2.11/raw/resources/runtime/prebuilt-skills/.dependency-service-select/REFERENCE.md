---
name: service-select
description: "根据已有输入和目标效果选择 Hi3D/MDF 原子服务，输出精确的服务契约、参数与产物交接方案。"
---

# 服务能力选择

根据已有输入和目标效果选择 Hi3D/MDF 原子服务，输出精确的服务契约、参数与产物交接方案。

## 输入与完成结果

- 输入：目标变化、保留特征、已有图像/网格及服务部署前提。
- 输出：先读 references/catalog.md，再按所选分支读取 geometry、texture、api 或 references/mdf 中的服务页；输出选择、必要字段、输出结构和验收边界。

## 调用与边界

选择不提交任务。实际调用显式交接 mdf-call / hi3d-api，图像/ZIP 组装交接 geometry-input。12 个已记录契约包含 8 个已确认露出服务及 4 个待确认露出服务，范围见 catalog；契约不等于当前可用性，成功码/非空文件不等于效果达成。已有合格输入跳过上游，未知状态复用原任务记录。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

宿主提供公开 mdf_api 时，按 [公开能力表](../mdf-api/references/mesh-invoke-api.md) 选择 capability 与扁平 params；与下述内部服务表分开。未公开的服务必须保留部署前提。

<!-- managed-by: sparc3d-runtime -->
