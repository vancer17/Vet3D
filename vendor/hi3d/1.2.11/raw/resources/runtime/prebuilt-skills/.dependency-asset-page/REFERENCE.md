---
name: asset-page
description: 将已有版本化本地图片、GLB、视频和下载文件生成静态成果页及资产清单，复用资产读取与模板处理，不生成模型或发布网站。
---

# 既有资产成果页

输入为明确 title/revision、已完成的资产及 image/model/video/download 角色；输出为 index.html 和含实际文件哈希的 asset-manifest.json。基础页面内嵌原始资产并提供下载，GLB 使用固定 model-viewer CDN，图片与下载无需该运行时。适用于已有结果的单版展示；打印摆盘、手机内外视角和灯具概念选型仍由专用界面提供。

按 [打包约定](../.dependency-package-tools/references/usage.md) 与 [清单](package.json) 物化后，可显式 `$asset-page`。Python 3.9+ 标准库：

```sh
python scripts/asset_page.py --manifest assets.json --output new-page
```

先读 [清单与组合契约](references/contract.md)。文件必须相对清单根目录并实际存在；不获取网络资产，不修改模型，不创建或消费发布凭据。可传期望 SHA-256 绑定已冻结版本；未提供时只记录当前字节，不能据 revision 文本证明资产同版。

输出目录必须新建，校验失败不写页面。完成后核对资产/角色/版本及下载内容，在目标浏览器查看模型、图片和所选视频；浏览器未测时保持 browser_interaction_tested=false。完整交付审查交 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，公开发布仍由用户已授权的工作流或宿主处理。

<!-- managed-by: sparc3d-runtime -->
