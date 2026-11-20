---
name: media-encode
description: "将已完成的有序 PNG/JPEG 帧编码为 MP4，并全片解码、抽取检查图和记录文件哈希。"
---

# 媒体编码

将已完成的有序 PNG/JPEG 帧编码为 MP4，并全片解码、抽取检查图和记录文件哈希。

## 输入与完成结果

- 输入：显式 frames 根目录、输出目录、帧数量与 ffmpeg 运行时；使用 --help 查看现有目录契约。
- 输出：scripts/encode_review.py 生成视频、解码检查与 contact sheet，当前 profile 为 24 fps；[encode_sequence](references/sequence.md) 可独立指定起始帧、模式、帧率、CRF、补偶数和覆盖策略。

## 调用与边界

Python、Pillow、imageio-ffmpeg。已有帧即可执行，不启动 Blender 或收费生成；清楚标注实际检查帧与编码失败。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
