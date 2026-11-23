# Blender 视频序列契约

入口：[脚本](../scripts/hi3d-video-sequence.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+、Blender 4.3+；实际版本逐一验收。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-project.blend、assets、frames、hi3d-review.json。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

创建或按命名条带修订 Blender VSE 的图片、视频、声音、文字和颜色轨道，另存 BLEND、重开并渲染序列帧。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 时间线与软件版本

配方必填 width/height/fps/frames/strips。时间线从帧1开始，fps可为有理数字符串。可选 source 指向已有 BLEND；指定 id 的旧条带被替换，未指定条带保留并复制资源。strips项包含 id,type,start,duration,channel；type为 image/movie/sound/text/color。媒体类型给path，text给text/fontSize，color给RGB；opacity默认1，sound.volume默认1，offset默认0个源帧。禁止同通道重叠、非正时长、媒体不足和条带越界。

`validate` 校验配方；`execute` 创建任务/规范化路径并启动专用内核；`hi3d-vse-kernel.py` 在 Blender 内构建/编辑、复制图片/电影/声音到 assets、另存 BLEND、重开验证名称/起点/时长/文字/音量并渲染 PNG。Blender 新旧条带集合与 new_effect length/frame_end 按实际 RNA 适配。render默认true；false仅交付工程。budgetSeconds默认180。原生工程使用相对资产路径，需要工程和 assets 一起移动。

仅包含声明的五种条带，不覆盖全部 VSE 效果、任意源工程插件或嵌套 scene strip；复杂已有工程须额外资源审计。新建合成使用 Standard 视图。序列帧不含声音，音轨保存在 BLEND；要成片时显式编码和混音。Python侧需要 Pillow 解码验证实际帧尺寸和数量。
