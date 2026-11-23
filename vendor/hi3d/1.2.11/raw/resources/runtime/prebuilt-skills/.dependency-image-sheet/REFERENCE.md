---
name: image-sheet
description: 将有序图片与标签拼成检查图并输出格位映射，支持等比缩略或明确拉伸、字体留白及可选来源哈希校验。
---

# 图片检查拼版

接收明确排序的图片与标签、列数、图片格尺寸和标签高度，输出 PNG/JPEG 检查图及每格到来源的映射。标签默认在图片上方，可显式放在下方；业务标题、列名和文件排序由调用方组合。只需 Python 3.9+ 与 Pillow；可独立处理磁盘图片，也可由 Python 调用方交接已经解码的 PIL 图片。

使用 `$image-sheet` 或显式读取本入口。先按 [打包约定](../.dependency-package-tools/references/usage.md) 提供完整包，再读取 [接口与清单](references/contract.md)：

```sh
python "$SKILL_DIR/scripts/image_sheet.py" --manifest "$MANIFEST" --output "$SHEET" --mapping "$MAPPING"
```

图片顺序和标签来自调用方，不自动按文件名排序。不把等比缩略、拉伸或裁切互换；本入口只提供前两种，裁切需调用方先明确准备图片。默认拒绝覆盖，不能覆盖任何来源图片。哈希不符、坏图、空输入或非法尺寸时失败。

拼版用于定位与对照，不能证明完整视频解码、未抽样帧质量或模型几何通过。抽帧、业务 manifest 验收、ZIP 和交付由调用方保留。

<!-- managed-by: sparc3d-runtime -->
