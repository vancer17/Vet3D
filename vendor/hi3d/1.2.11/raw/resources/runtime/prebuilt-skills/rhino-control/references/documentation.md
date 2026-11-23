# Rhino 官方参考文档

本包按版本保存官方帮助、API 与手册全文，供离线检索和脚本兼容性核对。正文版权归 McNeel / 对应上游；保留原 HTML、PDF 的版权信息。英语为跨版本共同资料。`official/` 的 ZIP 用于按需解压/读取，不应一次全部放入模型上下文。

先按[两级版本索引](versions.md)查询接口与 Python/MCP 约束；本页仅在需要来源、完整实现/示例、命令帮助或缺项核对时读取。衍生 catalog.zip 的正文按共同契约与版本差异组织；原始归档保留许可、原始注释和完整实现，供定向回查。

## 帮助正文范围

以每代官方 MadCap `Data/SearchUrl_Chunk*.js` 的全部索引主题为边界，保存每页原 HTML 与完整提取文本。来源为 `https://docs.mcneel.com/rhino/<代>/help/en-us/`；Rhino 5 Mac 的官方路径是 `mac`。镜像不包含网页图片、视频、搜索 UI 运行库；这些资源需按 index.json 中的原 URL 到官网查看。不能将正文归档称为整个网站的离线克隆。

| Rhino | Windows 归档 | 主题页/索引 | Mac 归档 | 主题页/索引 |
| --- | --- | --- | --- | --- |
| 5 | [rhino-5-en-us.zip](official/rhino-5-en-us.zip) | 1226 / 1232 | [rhino-mac-en-us.zip](official/rhino-mac-en-us.zip) | 1117 / 1117 |
| 6 | [rhino-6-en-us.zip](official/rhino-6-en-us.zip) | 1325 / 1325 | [rhino-6mac-en-us.zip](official/rhino-6mac-en-us.zip) | 1275 / 1275 |
| 7 | [rhino-7-en-us.zip](official/rhino-7-en-us.zip) | 1450 / 1450 | [rhino-7mac-en-us.zip](official/rhino-7mac-en-us.zip) | 1409 / 1409 |
| 8 | [rhino-8-en-us.zip](official/rhino-8-en-us.zip) | 1554 / 1554 | [rhino-8mac-en-us.zip](official/rhino-8mac-en-us.zip) | 1513 / 1513 |

共 10,869 个帮助主题页，其中 4,073 个是指向正文的重定向入口，不能把它们算成同等数量的独立教程。`docs.py read` 自动跟随归档内的 HTML meta 跳转，处理官方路径大小写差异；目标缺失、循环或深度超过 32 时明确报错，不返回占位页冒充正文。Rhino 5 Windows 的以下 6 个官方索引项不可获取，记录在该 ZIP 的 `missing.json`；没有用其它版本页面冒充补齐：`selmeshedges`、`selmeshfacesbyaspectratio`、`selmeshfacesbyarea`、`selmeshfacesbydraftangle`、`selmeshfacesbyedgelength`、`zoomends`（均在 `commands/*.htm`）。因此不能宣称整个官网 100% 齐全。

另有 18 个跳转入口指向 14 个未收录且官网不可取得的目标，按目标归档列出如下；读取器的错误会给出准确原 URL。不能拿其它版本或平台的同名页代替。

| 归档 | 未收录跳转目标（相对该代帮助根） |
| --- | --- |
| 5 Windows | `commands/ngonulatemesh.htm`、`commands/select-mesh-faces-commands.htm`、`macpreferencesandsettings/tool_palette.htm`、`commands/showdir.htm`、`commands/showends.htm` |
| 5 Mac | `commands/calc.htm`、`commands/commandprompt.htm`、`documentproperties/dimensions_style.htm`、`commands/meshfromlines.htm`、`commands/worksession.htm` |
| 6 Mac | `commands/commandprompt.htm`、`commands/worksession.htm` |
| 7 Mac | `commands/commandprompt.htm`、`options/alerter.htm` |

每份 ZIP 包含 `index.json`（path/url/title）、`html/`、`text/`、原搜索索引；有缺项时还包含 `missing.json`。旁边同名 JSON 声明来源、篇数、缺项及范围。归档为文档快照，官网可能在同一大版本 URL 下更新。

```sh
python3 "$SKILL_DIR/scripts/docs.py" search \
  "$SKILL_DIR/references/official/rhino-5-en-us.zip" Boolean
python3 "$SKILL_DIR/scripts/docs.py" read \
  "$SKILL_DIR/references/official/rhino-5-en-us.zip" commands/booleanunion.htm
# 标题未命中时再检索正文
python3 "$SKILL_DIR/scripts/docs.py" search \
  "$SKILL_DIR/references/official/rhino-8mac-en-us.zip" tolerance --full-text --limit 5
# 原 HTML pre 代码块，JSON 字符串保留缩进；不要复制普通提取文本中的 Python 示例
python3 "$SKILL_DIR/scripts/docs.py" read \
  "$SKILL_DIR/references/official/developer-docs.zip" pages/0021.html --code-blocks
```

## Python、RhinoCommon 与 MCP

- [developer-docs.zip](official/developer-docs.zip)：完整 RhinoScriptSyntax 单页 API、官方 RhinoPython / scripting / Yak 分类索引链接的指南正文，以及 McNeel rhino-python 说明。可用相同 `search/read` 命令，path 以归档 `index.json` 为准。详情见 [来源清单](official/developer-docs.json)。分类页中两个失效旧入口（安装排错、旧 Grasshopper 首个 Python 脚本）保留缺项记录；其余可获取内容完整保存。现代 Python 参考不能代替旧版本的 API 可用性核对。
- [RhinoCommon 5](official/rhinocommon-5.zip)、[6](official/rhinocommon-6.zip)、[7](official/rhinocommon-7.zip)、[8](official/rhinocommon-8.zip)：来自官方 NuGet RhinoCommon 包的**完整 XML API 文档**，不包含 DLL。各 ZIP 内 `source.json` 给出准确包版本与下载来源；8 包含 net48/net7.0 文档。旧 XML 对部分方法没有文字注释，查不到不代表方法不存在；必要时结合新版 `since` 标签、官方源码与目标进程验证。
- [RhinoScriptSyntax 5–7 源码文档](official/rhinoscriptsyntax-5-7.zip)：官方 `mcneel/rhinoscriptsyntax` 的 `rhino-5`、`mac-rhino-5.0`、`rhino-6.0`、`rhino-7.0` 分支，完整 Scripts Python 源码、docstring、README/可用许可证，共 199 份文本；每个分支修订及许可来源保留在 source.json/README 中。它是查签名、返回值与包装实现的离线参考，不安装/覆盖 Rhino 自带库，也不代表每个 SR 二进制都相同。`docs.py read` 路径如 `rhino-5/Scripts/rhinoscript/surface.py`；当前脚本的精简规则见 [Python](python.md)。
- [RhinoScriptSyntax 8 源码文档](official/rhinoscriptsyntax-8.zip)：同一官方仓库 `rhino-8.0` 与 `rhino-8.30` 分支的完整 Scripts Python 源码/docstring 和 README/许可证，共 111 份文本，source.json 固定修订；用于比较 8 的包装实现，不能据此假定其它 SR 或 Python.NET 自动转换完全一致。
- [rhinomcp-docs.zip](official/rhinomcp-docs.zip)：用户指定 RhinoMCP 仓库的英文/中文 README、服务 README、changelog、docs、内置操作指南及 MIT LICENSE；`source.json` 固定上游修订。以安装的发行版本和实际 `tools/list` / `describe_capabilities` 为执行依据。使用 `lookup --major 8 --kind mcp --query 工具名` 定位工具用途和约束章节；原文也可 `search/read` 直接按 README.md 等真实成员路径读取，无需 index.json。

先用 `docs.py lookup --major N --kind rc --query 成员名` 查精确重载和行段；需要原始 XML 时用 `lookup --sources` 的真实归档成员路径与行号交给 `read --start-line … --end-line …`，也可解压到任务目录按成员查阅；保留 `<summary>`、参数、返回值和版本标签，不仅截取命中行。不要运行文档中的示例修改用户模型。

帮助中的 `commands/runpythonscript.htm` 是重定向页；正文在同一归档的 `information/rhinoscripting.htm`，含 RunPythonScript/ResetEngine 及宏规则。读取重定向占位文本后应继续读取目标正文。

开发指南是持续更新的跨版本资料，含 Rhino 9 内容；先看 New in 9、发布日期与具体最低 SR。原 HTML 保留代码缩进，普通 `text/` 仅适合阅读；`read --code-blocks` 返回实际目标 URL、跳转链及未去缩进的 pre 数组。官方 Python 源码归档的 `text/*.py.txt` 本身保留原始缩进，直接普通 read 即可。示例中的交互选择、隐含变量或笔误仍须按任务修正并在目标引擎编译检查。

## 完整 PDF 手册

[manuals.json](official/manuals.json) 保留官方每个下载 URL 与实际文件映射。包含 Rhino 5 Windows 用户手册，Rhino 6/7/8 Windows/Mac 用户手册，以及官方目前为 Rhino 6 及后续版本提供的 Level 1、Level 2 完整训练 PDF。同内容下载去重，所有来源仍可追溯；不同版本 URL 返回同一 PDF 时不宣称是分别冻结的历史版本。

| 内容 | 文件 |
| --- | --- |
| Rhino 5 Windows 用户手册 | [PDF](official/rhino-5-user-guide-windows.pdf) |
| Rhino 6/8 Windows 用户手册（相同内容） | [PDF](official/rhino-8-user-guide-windows.pdf) |
| Rhino 7 Windows 用户手册 | [PDF](official/rhino-7-user-guide-windows.pdf) |
| Rhino 6/7 Mac 用户手册（相同内容） | [PDF](official/rhino-7-user-guide-mac.pdf) |
| Rhino 8 Mac 用户手册 | [PDF](official/rhino-8-user-guide-mac.pdf) |
| Level 1 | [PDF](official/rhino-6-level1.pdf) |
| Level 2 | [PDF](official/rhino-6-level2.pdf) |

来源：[官方训练资料目录](https://wiki.mcneel.com/rhino/trainingguides/en)、[Rhino 5 用户手册](https://docs.mcneel.com/rhino/5/usersguide/en-us/windows_pdf_user_s_guide.pdf)、[Python 开发指南](https://developer.rhino3d.com/guides/rhinopython/)、[RhinoCommon NuGet](https://www.nuget.org/packages/RhinoCommon/)、[RhinoMCP](https://github.com/jingcheng-chen/rhinomcp)。

## 更新归档

`docs.py mirror --base <官方帮助根 URL> --output <任务目录/new.zip>` 复用同目录 `.cache`，最多 16 个下载线程；默认有任何缺页即失败，不发布完整 ZIP。只有核对缺页原因后才显式加 `--allow-missing`，并同步篇数和缺项说明。读取操作可以有限重试；此策略不用于 Rhino 建模命令。归档生成到包外，审核完再替换源码资源；不要将抓取缓存、诊断过程和本机测试报告提交进仓库。

## 目录合并与维护

共用判定要求所有已归档版本/平台/框架均有该接口：XML 契约相同才合并；Python 还比较签名、默认值、可执行包装代码和类型标注，已核对的纯说明差异使用含类型的统一说明。无法确认的差异保留在各版正文；同名但参数、返回、实现或前提改变不能仅凭文字相似合并；同一大版本中的分支也遵守此规则。相同说明下的包装差异在各版正文独立定位并标出原源码范围，编写时必须回查所选实现。共用表示资料契约一致，不是跨版本内核行为已实测。

人工核对的 Python 说明差异按完整原函数（含示例）、分支集合和抽取正文绑定指纹，不能只按函数名永久放行。来源或解析结果变化后，该例外自动失效并保留各版说明；重新逐项审阅后才能更新 REVIEWED_RS。说明中的引号/反引号字面量不压缩内部空白。抽取时只省略 Example/Examples/See Also 章节，后续 Notes、Returns 等约束仍保留；完整实现与示例按 source 行号回查。

维护资料后在包外 `catalog-build --output 新.zip`，审核替换 catalog.zip，再运行 `catalog-check`；索引由脚本生成，不手改行号。批量读取仅在一次命令内共享同一份版本索引及正文快照，下一命令重新读取资源；修改手写资料后仍须重建索引，不把本地复用当作宿主 token 缓存。
