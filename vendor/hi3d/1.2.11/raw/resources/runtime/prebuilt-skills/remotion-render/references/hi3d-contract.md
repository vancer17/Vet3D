# 参数化动效渲染契约

入口：[脚本](../scripts/hi3d-remotion.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+、Node、React、同版本 Remotion/bundler/renderer、兼容 Chromium；商业许可由使用方核对。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-video.mp4、hi3d-props.json、public 素材。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

使用本地 Remotion 模板组合文字、矩形、图片、音轨及平移/淡入关键帧，渲染视频并验证帧数。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 模板配方、工程与队列

必填 `width,height,fps,frames,layers`；尺寸为正偶数≤8192，fps 为整数1..120，frames为正整数。`background` 默认深色。图层 `id` 唯一，`type=text/rect/image/audio`；text 使用文字，image/audio 使用本地 path。可选 x/y,width/height,color,fontSize,start,duration,fromX,toX,fadeFrames；时间单位是整数帧，start默认0，duration默认全片，必须落在总帧范围。平移使用线性插值，fadeFrames为淡入长度；不是任意 AE 动效插件。

`validate` 纯配方检查；`execute` 将资源复制至 public，保存渲染 props 和可重新提交的 `hi3d-project.json`（素材相对它的 public 子目录），调用随包 JS 模板。`hi3d-remotion.mjs` 用显式 `--runtime` 下的 Node 依赖进行 bundle/selectComposition/renderMedia；模板源码 `hi3d-template.jsx` 是 JSX 唯一维护源。Node 依赖由使用者提供：同版本 remotion/@remotion/bundler/@remotion/renderer，加 react/react-dom；不在运行入口隐式 npm install。明确 `--browser` 可避免自动下载浏览器。

`--queue` 与 `--spec` 互斥；队列为 `{schemaVersion:1,specs:[本地配方路径...]}`，顺序执行并写 `hi3d-queue.json`，首个失败停止。再次提交同队列可跳过哈希仍匹配的已完成子任务；失败子任务须新尝试目录，不自动收费、不自动加时。队列输入次序/内容改变会在子任务指纹校验时拒绝旧缓存。`budgetSeconds` 默认180，限制每次渲染子进程。

工程重新渲染仍需本技能安装包及声明依赖，不把 props JSON 称为独立桌面剪辑器工程。浏览器/字体版本会影响画面；完成条件含整片解码、帧数、帧率与尺寸检查，视觉内容仍需查看。
