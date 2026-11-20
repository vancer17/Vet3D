# 连续 PNG/JPEG 编码

物化包内 `from encode_sequence import encode_sequence`，传 ffmpeg、folder、fps、output；参数 `start=0`（None 按数字最小值推导）、`pattern="%04d.png"`、`crf=19`、`pad_even=False`、`overwrite=False`、`ffprobe=None`、`timeout=600`。依赖 Python/Pillow 和可用 libx264 的 ffmpeg。帧模式支持 %0Nd.png、%0Nd.jpg、%0Nd.jpeg，必须精确连续、同尺寸且没有额外图片；混合格式或扩展名与实际内容不符时拒绝；fps 支持正数/有理数字符串。奇数尺寸需显式 pad_even。失败可能留下部分 MP4，成功报告由调用者命名，不自动重试覆盖。

`sequence_names` 是纯序列校验；`encoder_command` 只组 argv；`encode_sequence` 编码后调用 media-check 验证实测帧数、时长和完整解码。显式 ffprobe 时还独立核对尺寸、标称/平均帧率；未提供时在 check_scope 明示这两项未独立探测，不能宣称完整技术验收。联系表只抽帧展示。

encode_review 保留 24fps/CRF19/可覆盖及 contact sheet/哈希 sidecar；从最小编号推导起始帧以接收既有 0000 或 0001 序列。lamp-design 保留 0000 开始、整数 fps/CRF18/补齐偶数、拒绝已有视频与 .json sidecar，以及文件大小门槛。两处均调用同一编码与独立解码实现。


独立 CLI：`python scripts/encode_sequence.py --ffmpeg "$FFMPEG" --frames "$FRAMES" --output "$VIDEO" --fps 24 --start 1 --crf 18`，`--pattern` 选择格式，按需显式 `--pad-even/--overwrite/--ffprobe`。仅成功后向 stdout 输出技术检查 JSON，不生成隐式 sidecar。函数/API 与 CLI 使用同一校验和编码路径；图片同时检查文件结构与实际像素解码。

头部表情适配保留 JPEG、8fps、CRF20 和覆盖已有目标视频；本次 JPEG 序列在新临时目录生成，避免恢复或缩短动作时混入旧帧，原始检查 PNG 与 frames.json 保留。成功才写 expressions.video.json 并纳入工作流输出/缓存；无视频分支不调用编码器。拼图不能替代全片解码，技术通过也不表示表情质量通过。
