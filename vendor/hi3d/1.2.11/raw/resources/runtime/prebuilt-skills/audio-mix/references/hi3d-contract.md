# 音轨混音契约

入口：[脚本](../scripts/hi3d-audio-mix.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：FFmpeg/ffprobe、Python 3.10+。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-mixed.wav/MP4、hi3d-mix.json。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

按裁切、偏移、增益及淡入淡出混合本地音轨，输出 WAV 或搭配视频/字幕输出 MP4；验证解码和采样率。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 配方与混音规则

`duration` 为输出秒数。`tracks` 长度1..32，每项包含 `path,end`，可选 `start=0,offset=0,gainDb=0,fadeIn=0,fadeOut=0`。裁切端点相对源秒数，offset 为时间线延迟秒；gainDb 范围 -60..24，淡入/淡出不能超过该轨裁切长度。源越界、无音轨、输出范围外延迟拒绝。

可选 `video`、`subtitles`（须搭配 video）、`fontDir`（显式本地字体目录）、`loudness=-16`（-70..-5 LUFS）、`budgetSeconds=120`。先裁切/重置时间、48kHz立体声/增益/淡变/延迟，再混合、补静音或截断至目标时长，单遍 loudnorm，输出 PCM16 WAV 或 H.264/AAC MP4。不会保留输入视频的旧音轨，需显式列入 tracks。

`validate` 纯检查；`escape_filter_path` 处理滤镜路径，不走 shell；`execute` 探测音轨/视频长度、运行混音、全流解码、验证采样率及音视频时长差≤0.1秒。响度是单遍目标，非广播规范测量认证；不提供降噪/声源分离。输入和文件路径允许空格，滤镜复杂特殊字符需按测试支持范围使用。
