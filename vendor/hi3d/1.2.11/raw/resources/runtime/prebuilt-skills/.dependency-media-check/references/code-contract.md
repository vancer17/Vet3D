# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/check_media.py](../scripts/check_media.py) | `positive_rate`, `validate_spec`, `check_image`, `run_tool`, `check_video`, `audit`, `main` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

`check_media.decode_video(path, ffmpeg, timeout=600, run=subprocess.run)` 完整解码首视频流，以 ffmpeg progress=end、实测帧数和媒体时长返回记录；错误输出/失败/空帧拒绝。无需 ffprobe，但不检查标称帧率、尺寸或编解码器。`check_video` 保留 ffprobe 完整指标检查，并复用此解码器；帧数不一致列入 errors。
