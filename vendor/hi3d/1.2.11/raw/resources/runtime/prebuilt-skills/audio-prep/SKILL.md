---
name: audio-prep
description: 整理本地音频：按探测到的时长做首尾静音裁切、淡入淡出与目标响度，试听对照后导出 WAV 与实测响度；不默认裁切中间停顿，未实现降噪则不提供该选项。
---

# 音频整理

对用户提供的音频做可复核的整理。用途、首尾裁切、淡入淡出、目标响度和输出格式来自本次 brief。降噪仅在实现可用时展示；当前未实现，入口不提供降噪开关。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 物化后，通过 `$audio-prep` 或显式读取本文件调用。Python 3.10+、FFmpeg/ffprobe。运行目录在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。试听切换时保持播放位置；不通过自动增大试听音量制造改善感。静音、过短和无法解码文件给出明确提示。不对录音中间的停顿默认裁切。取消保留已有试听，不自动开新处理。

交互：添加音频 → 查看时长及基础信息 → 选择处理项 → 生成试听 → 原始与处理版切换 → 导出。

## 探测与配方

时长必须来自 ffprobe 实际探测，不能用文件名或估计秒数代替。过短（整段短于拟裁切+淡变）或全静音在探测阶段失败。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_mix.py" \
  --brief "$RUN_DIR/brief.json" --output "$RUN_DIR/mix-spec.json"
```

处理显式调用独立 [audio-mix](../audio-mix/SKILL.md)，传入单轨裁切/淡变/loudness 配方，接收 PCM16 WAV。不输出 MP3：该格式尚未实现，不展示 MP3 下载。处理后用 `scripts/measure_loudness.py` 对**真实输出 WAV** 测综合响度与峰值；测量失败不得用配方目标值冒充。

## 预览与交付

预览提供原始文件与处理版路径，切换时沿用当前播放秒数。显示测量得到的 LUFS 与峰值；峰值越界（≥0 dBFS）视为失败。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)；交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)。

交付：WAV、处理参数 JSON、实测响度 JSON。仅提供真实文件。

最小验收：输出可解码、首尾未误切语音（对照探测时长与 trim）、峰值未越界、响度测量基于真实输出。

<!-- managed-by: sparc3d-runtime -->
