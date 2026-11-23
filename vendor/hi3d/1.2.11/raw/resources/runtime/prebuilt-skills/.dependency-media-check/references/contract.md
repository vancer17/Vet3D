
## 宿主媒体工具

`media_tools.find_ffmpeg(explicit)` 优先显式路径，其次 imageio_ffmpeg，再 PATH；`find_ffprobe(explicit)` 优先显式路径，其次当前 Python sys.prefix/media-tools 下的 ffprobe 或 ffprobe.exe，再 PATH。无安装/下载副作用。audit 与 CLI --ffmpeg/--ffprobe 接受覆盖，保留完整解码、实际帧数、时长和尺寸验证。
