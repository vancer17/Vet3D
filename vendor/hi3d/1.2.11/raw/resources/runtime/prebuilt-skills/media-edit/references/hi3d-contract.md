# 视频时间线剪辑契约

入口：[脚本](../scripts/hi3d-media-edit.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：FFmpeg/ffprobe、Python 3.10+、Pillow。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-video.mp4、hi3d-edit.json。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

将本地视频按入出点、变速和有理帧率裁切拼接，统一画幅并解码验证；不隐式保留音轨。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 配方与算法

必填：`width/height` 为 2..8192 偶数像素，`fps` 为正数或有理数字符串（≤240），`clips` 为 1..100 个片段。每项 `path,start,end`（秒）必填，`speed` 默认 1，范围 0.125..8。可选 `crop={x,y,width,height}` 为源像素区域；越界拒绝。`transitionFrames` 默认 0，表示与前段淡化重叠的输出帧数，必须短于两段，第一段必须为 0。输出帧数按每段时长/速度×帧率四舍五入后减去重叠帧数。

`watermark={path,x,y}` 可选，本地图像按左上像素坐标叠加；画幅以主视频为准。`crf` 默认19，整数0..51。`budgetSeconds` 默认120。`validate` 纯校验并返回帧率/帧数，`command` 只构造 argv，`execute` 负责素材探测、运行、完整解码与新文件交付。

只处理第一视频流，使用等比缩放+留边统一画幅、CFR、H.264/yuv420p MP4。音轨不隐式保留，以独立混音能力传入；HDR 输入拒绝，避免无声明地丢失动态范围。不做高保真 HDR、任意转场插件或视频语义剪辑。技术验收复用 media-check 的完整视频解码。
