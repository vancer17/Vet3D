---
name: head-template
description: "解析有来源与许可的 Taro 头部拓扑、分区及关键点映射，为固定拓扑拟合提供一致几何先验。"
---

# 头部模板

解析有来源与许可的 Taro 头部拓扑、分区及关键点映射，为固定拓扑拟合提供一致几何先验。

## 输入与完成结果

- 输入：显式自定义 template 路径，或请求随包 Taro 几何；可另选随包原始眼睛/口腔/皮肤资源。
- 输出：scripts/template_defaults.py 的 resolve_template_config 返回配置副本；assets/taro 包含模板、映射、来源 manifest 与 UPSTREAM_LICENSE。

## 调用与边界

不自动给自定义模板套用 Taro 贴图。头部几何的解析不启动纹理生成；MetaHuman 工作流自身负责纹理默认值。先核对模板哈希、拓扑和映射版本。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

耳部注册复用 `assets/taro/sapiens2_ear_mapping.json`：49 个零基 Sapiens2 耳点，含固定 vertex_index、triangle 和 barycentric；模板哈希必须一致，运行时不检测模板。ID 238、243、264 位于不稳定的根部边缘，已从默认集合禁用；模板改版需离线重新校准。

<!-- managed-by: sparc3d-runtime -->
