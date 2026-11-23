# 字幕轨道排版契约

入口：[脚本](../scripts/hi3d-subtitle-track.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-subtitles.srt、hi3d-subtitles.ass。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

将明确时间戳文本排成 UTF-8 SRT/ASS 字幕，校验重叠、精度和行长；不做语音识别。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 配方与时间规则

必填 `cues=[{start,end,text}]`，时间单位秒，必须顺序不重叠、end>start；ASS 精度为1/100秒，SRT为1/1000秒。拒绝空文本、反斜杠及花括号控制码，避免用户文字被当作 ASS 样式执行。`font` 默认 Arial（字体名不能包含逗号/换行）；`fontSize=36,width=1280,height=720,margin=40,maxLineChars=24` 均为正整数。按字符数换行，不承诺字形实际测宽或复杂语言分词。

`validate` 纯校验；`timestamp` 处理进位；`render` 返回 SRT/ASS 文本；`execute` 写入新任务。输出底部居中、白字黑描边、安全区边距。字体存在性由最终渲染后端检查并实际看图；缺字体可能替换，不能宣称指定字体已加载。语音转写不属于本阶段。
