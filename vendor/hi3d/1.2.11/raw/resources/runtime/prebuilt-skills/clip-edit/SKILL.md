---
name: clip-edit
description: 将本地图片或视频按排序、入出点与画幅剪成横屏或竖屏成片；可选用户配乐与字幕；先生成低分辨率预览再导出 MP4、封面、存在字幕时的 SRT 与配置清单。
---

# 视频剪辑

把用户提供的图片或视频剪成一条成片。字幕、片头和配乐均为可选；配乐只使用用户提供的本地文件。初版画幅为单一固定规格：竖屏 1080×1920 或横屏 1920×1080，30 fps。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D；剪辑与混音走独立原子能力。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 物化后，通过 `$clip-edit` 或显式读取本文件调用。Python 3.10+、FFmpeg/ffprobe、Pillow。运行目录在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。返回上一步保留时间线；重新导出保留上一版成片。失败和取消后不自动启动新付费任务。取消停止后续本地步骤，保留已生成预览；无远端任务可取消。

交互顺序：添加素材 → 排序 → 设置裁切与每段时长 → 填写字幕 → 生成低分辨率预览 → 修改 → 导出成片。音轨缺失不阻塞无声导出。无法解码的素材必须指出，允许替换或由用户移除。输出编码失败保留配置与中间成果。

## 时间线

必要输入为至少一个可解码的图片或视频。初版 `preset` 仅为 `portrait` 或 `landscape`，不能把推荐竖屏当成未确认的用户事实。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_edit.py" \
  --timeline "$RUN_DIR/timeline.json" --preview \
  --output "$RUN_DIR/plan-preview.json"
```

静帧图片先用 `scripts/still_clip.py` 按该段时长做成定帧视频，再进入剪辑。探测失败时停止并列出无法解码的路径。

画面剪辑显式调用独立 [media-edit](../media-edit/SKILL.md)，传入本次 `mediaEdit` 配方（预览为半分辨率偶数像素），接收 `hi3d-video.mp4`；音轨不隐式保留。字幕时间合法后，字幕轨道显式调用独立 [subtitle-track](../subtitle-track/SKILL.md)，传入 cues，接收 UTF-8 SRT/ASS。用户配乐或需要保留素材声时，音轨混音显式调用独立 [audio-mix](../audio-mix/SKILL.md)，传入成片视频、音轨与可选字幕，接收带声 MP4；无音轨则跳过混音，无声导出不算失败。

尺寸、帧率、时长与完整解码显式调用独立 [media-check](../.dependency-media-check/REFERENCE.md)。封面用 `scripts/extract_cover.py` 从实际成片抽帧，不另造图。

## 预览与交付

预览必须可播放；说明素材声与配乐音量来自 mix 配方的 gainDb。修改排序、入出点或字幕时只重跑受影响阶段。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)；交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)。

交付：成片 MP4、封面 PNG、存在字幕时的 SRT、timeline/plan JSON 与所需素材清单。仅提供真实文件。

最小验收：实际解码首尾画面、时长符合配置、字幕时间合法、带音轨样例实际可播放。

<!-- managed-by: sparc3d-runtime -->
