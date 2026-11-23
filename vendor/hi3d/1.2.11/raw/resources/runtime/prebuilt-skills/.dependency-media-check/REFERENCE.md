---
name: media-check
description: "检查已有图片或视频的尺寸、帧率、帧数、时长及完整解码，输出可机读媒体验收报告。"
---

# 媒体检查

检查已有图片或视频的尺寸、帧率、帧数、时长及完整解码，输出可机读媒体验收报告。

## 输入与完成结果

- 输入：显式媒体文件、预期尺寸/帧率/时长或帧数，以及 ffmpeg/ffprobe 路径。
- 输出：scripts/check_media.py 的 CLI 和 check_video 等函数；完整视频解码及检查报告。

## 调用与边界

Python、Pillow、ffmpeg/ffprobe。技术检查不证明内容正确、来源同版或视觉质量；关键帧仍须实际查看。不会渲染或重编码输入。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

Runtime 的工具定位与 --ffmpeg/--ffprobe 参数见 [媒体契约](references/contract.md#宿主媒体工具)。

<!-- managed-by: sparc3d-runtime -->
