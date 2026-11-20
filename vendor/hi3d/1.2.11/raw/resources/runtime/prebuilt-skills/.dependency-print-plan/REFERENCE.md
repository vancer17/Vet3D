---
name: print-plan
description: "把既定产品结构转换为制造版本、全打印可行性、BOM、配对试片与验证计划。"
---

# 打印方案规划

把既定产品结构转换为制造版本、全打印可行性、BOM、配对试片与验证计划。

## 输入与完成结果

- 输入：当前产品结构、外购版本、打印机/材料约束和需保持的功能。
- 输出：按 [通用制造规则](references/print-diy-workflow.md) 输出实际可执行的制造方案与缺口；其他补充页只用于对应的品类条件。

## 调用与边界

不把外购版改名为全打印版；功能电气件、密封等依赖明列。计划本身不是成品；建模、验收与交付由工作流完成。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
