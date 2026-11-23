# 依赖与显式调用

本工作流由宿主加载 `$relief-brush`，或读取完整物化包中的实际 SKILL.md 后按路径调用。安装与发现按 [打包契约](../../.dependency-package-tools/references/usage.md) 验证；输入、输出和模块定位按 [本地执行边界](../../.dependency-run-tools/references/runtime.md#显式本地执行) 处理。

| 当前步骤 | 本品类条件、交接与必读契约 |
| --- | --- |
| 建模、Brush、渲染或动画 | 需要 Blender 5.2 兼容 API，含 MANIFOLD 布尔及所用 glTF 导出器；其他版本先实际验证。后台命令与 ABI 隔离见 [Blender 运行契约](../../.dependency-blender-tools/references/code-contract.md#后台环境与-python-依赖)。 |
| 普通数组、STL 或截面检查 | 独立 Python 3.10+，按本包 requirements.txt 提供依赖；实际输入及输出类型见 [代码契约](code-contract.md)。 |
| 需要新 Hi3D 几何 | 独立提供 [hi3d-api](../../hi3d/SKILL.md) 完整分发目录；先读入口的凭据边界、[调用/恢复](../../hi3d/references/calling.md) 和 [参数](../../hi3d/references/parameters.md)，通过已解析的 `<HI3D_API_DIR>/scripts/hi3d_api.py` 将本次图像/参数交为真实原件及 job。dry-run、提交授权、不确定状态恢复、下载与脱敏按该工具执行；已有合格原件直接续接，不因上游缺失重新生成。 |
| 明确请求视频 | 最终有序帧交给 [media-encode](../../.dependency-media-encode/REFERENCE.md)，提供实际 FFmpeg、帧率/起始编号及任务输出目录；核对帧数、首中末画面并全片解码。编码参数沿用本次已确认动画，不把编码器的 profile 默认值反套入场景。 |
| 新概念图或网页 | 按 [产品工作流的工具选择](full-workflow.md#概念图与网页工具) 使用当前宿主能力；实际同版图、模型、页面与下载按 [交付审查](delivery-policy.md) 核对。 |

此页只维护步骤的触发条件与品类运行前提；工具完整协议由上列唯一来源维护。实际函数的覆盖、失败和验收范围继续以本包代码契约为准。
