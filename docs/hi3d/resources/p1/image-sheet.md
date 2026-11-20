# 图片检查拼版 image_sheet.py

## 资源身份与模型可见性

`image_sheet.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `.dependency-image-sheet` 的本地 Python 模块和命令行入口。Skill 可通过 `image-sheet` 参考入口公开拼版用途及脚本调用方法。模型获准执行本地命令时可按该入口调用脚本。运行时没有为此文件单独注册 LLM Tool，描述来自参考文档。安装入口的描述原文如下。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-image-sheet/scripts/image_sheet.py) · [安装包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-image-sheet/REFERENCE.md>)

```text
将有序图片与标签拼成检查图并输出格位映射，支持等比缩略或明确拉伸、字体留白及可选来源哈希校验。
```

## 参数、结果与副作用

| 接口 | 参数及结果 |
| --- | --- |
| `compose_sheet(items, *, columns, image_size, label_height, ...)` | 按输入顺序消费非空条目。每项提供磁盘 `path` 或已解码的 PIL `image`，可带 `label`。磁盘条目可附 `sha256`，脚本在解码前核验当前字节。列数和宽高为正整数，标签高度和 `gap` 为非负整数。返回独立 RGB 图像和有序格位列表。 |
| 排版选项 | `resize` 默认 `contain`，等比缩小、禁止放大并左上对齐，`stretch` 拉伸到格尺寸。`label_position` 默认为 `top`，也接受 `bottom`。`gap=0`，默认背景与前景分别为 `#101722` 和 `#dce8ef`，标签偏移 `(8, 4)`，采样器为 `Image.Resampling.LANCZOS`。可提供 PIL 字体或默认字体的字号。 |
| `write_sheet(items, output, *, overwrite=False, save_options=None, **layout)` | 接受 `.png`、`.jpg`、`.jpeg`，创建父目录并保存新图。返回 `output`、`size` 和 `cells`。`save_options` 传给 Pillow 编码器。每个格位记录索引、行列、标签、源路径、源尺寸、绘制后图像范围及整格范围。盒坐标为像素，右边界和下边界采用排他坐标。内存图的 `source` 为 `null`。 |
| CLI `--manifest`、`--output`、`--mapping` | 从 JSON 读取 `images` 与 `layout`。图片和可选字体支持相对清单目录的路径或绝对路径。输出图和映射必须是独立路径，映射写为 JSON，并将同一结果打印到标准输出。默认拒绝覆盖，可显式传 `--overwrite`。 |

尺寸、模式、条目形状、摘要或目标路径冲突会抛出 `ValueError`，已存在目标默认抛出 `FileExistsError`，文件读写与图像解码错误向上传播。CLI 先写图再写映射，后一步失败可留下已写的图。函数从源图转换出新的 RGB 数据，保留输入文件或内存图。调用方提供照片顺序和标签，并判断成图与照片的业务含义。 [清单及像素契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-image-sheet/references/contract.md>)

## 依赖、权限与前置 Hook

脚本导入 Python 标准库和 Pillow。Pillow 需提供 `Image.Resampling`，指定默认字体字号时还需支持 `ImageFont.load_default(size=...)`。自定义字体由调用方提供。脚本直接读取来源、字体及清单，并写入报告路径。文件访问受进程权限限制。经外层 `exec_command` 调用时，由外层处理适用的权限审批及前置 Hook。 [命令权限](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**调用方 JSON 示例。** 将两张照片置于清单同目录。

```json
{
  "images": [
    {"path": "front.png", "label": "Front"},
    {"path": "left.png", "label": "Left"}
  ],
  "layout": {"columns": 2, "image_size": [320, 240], "label_height": 24, "gap": 4}
}
```

**PowerShell 调用示例。** `$imageSheet` 指向归档文件。

```powershell
python -B $imageSheet --manifest './inputs/photos.json' --output './review/sheet.png' --mapping './review/sheet.json'
```

## 核查依据与待验证项

源码映射为 `skills/image-sheet/scripts/image_sheet.py`。隔离测试使用随包 Pillow 12.3.0 和两张合成 RGB 图片，核对了来源字节、逐项摘要、拼版像素与格位对应。归档脚本另已用上述清单复核 CLI 写图及映射位置。手机照片的 EXIF 朝向、ICC 色彩解释、非 ASCII 字体和大图资源占用仍需实测。写盘中断后的输出与映射恢复由调用方验证。 [P1 核查记录](../../upstream/1.2.11/extraction/p1/priority.md)
