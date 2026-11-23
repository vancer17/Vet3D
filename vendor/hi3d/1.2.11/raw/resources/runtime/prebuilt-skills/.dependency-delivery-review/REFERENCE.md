---
name: delivery-review
description: "核对已有模型、图片、制作文件与成果页是否同版且可打开下载，输出交付清单和实际检查范围。"
---

# 交付验收

核对已有模型、图片、制作文件与成果页是否同版且可打开下载，输出交付清单和实际检查范围。

## 输入与完成结果

- 输入：当前版本的真实资产、网页入口、制造版本与视频请求状态。
- 输出：同版资源清单、网页/交互/下载检查记录和缺项；按 references/delivery-policy.md 执行，网页结构见 references/web-delivery.md。

## 调用与边界

不重新生成模型；基础交付不以未请求的视频为缺项。网页打开与公开发布是不同动作，完整规则仅在引用文档维护。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
