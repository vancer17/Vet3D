# 拼版契约

唯一实现为 `scripts/image_sheet.py`。`compose_sheet(items, *, columns, image_size, label_height, gap=0, background='#101722', foreground='#dce8ef', font=None, font_size=None, label_offset=(8,4), resize='contain', resample=PIL.Image.Resampling.LANCZOS, label_position='top')` 返回新的 RGB PIL 图片和有序 cells，不修改输入图片。每项必须且只能有 `path` 或内存 PIL `image`，可带 label 与可选 sha256；哈希只接受磁盘来源，逐文件核对后解码。字体可传 PIL font 对象；未给时使用默认字体，font_size=None 保留 Pillow 默认字号。

columns 必须正整数，image_size 是正整数宽高，label_height/gap 是非负整数像素；gap 包括外边框。列数按明确参数保留，末行空格不自动收缩。label_position 仅接受 top（默认，上方）或 bottom（下方）；label_offset 相对标签带左上角，底部标签的带起点在图片格高度之后。长标签由调用方缩短或选合适字号，本接口不自动改文案或截断。contain 等比缩小、不放大且左上对齐；stretch 明确拉伸到格尺寸，不隐式裁切。resample 可由 API 选择 Pillow 采样器，业务原参数保留。

`write_sheet(items, output, *, overwrite=False, save_options=None, **layout)` 调用 compose_sheet 后写 PNG/JPEG，返回 `{output,size,cells}`。每格记录 index、row、column、label、source（内存图为 null）、source_size、image_box 和 cell_box；box 为像素 `[left,top,right,bottom]`，右/下边界不包含。顺序和标签不排序；映射对应最终像素位置，不是任务执行证据。save_options 可传 JPEG quality 等编码参数。

CLI 的清单格式如下，路径与可选字体相对清单目录；也支持绝对路径。--mapping 保存函数返回值，两个目标必须与所有输入不同，默认均拒绝覆盖。

```json
{
  "images": [{"path":"front.png","label":"Front"}, {"path":"side.png","label":"Side"}],
  "layout": {"columns":2,"image_size":[400,276],"label_height":24,"resize":"contain","gap":0}
}
```

失败不会修改来源文件；写盘阶段失败可能留下部分输出，调用方不能把已有文件当作完整成功。API 不负责保存 mapping 文件，调用方自行决定返回值如何归档；CLI 固定写出 mapping。没有 Blender、ffmpeg 或网络依赖，Pillow 需支持 `ImageFont.load_default(size=...)`。

现有适配分别保留方形 BICUBIC 拉伸/顶部标签、BICUBIC 不放大缩略图/帧号、按原宽高比的 LANCZOS 检查图/时间标签，以及 LANCZOS 拉伸/底部标签。额外标题区由调用方在新画布中组合，格位映射默认仍相对本函数返回的图像。抽帧和 ZIP 不属于此原子。验收需检查混合比例、来源像素不变、坏图/哈希错误/覆盖、顺序与格位；拼版不代替完整媒体或运动检查。
