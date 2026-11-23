# Python 脚本编写与执行

外部 Python 只生成/传输脚本；实际建模由 Rhino 的内嵌运行时执行，不能在系统 Python 中直接 `import rhinoscriptsyntax` 控制 GUI。Rhino 5–7 使用 IronPython 2.7；Rhino 8 的 `RunPythonScript` 也保留这条兼容路径。

## 创建与提交：prepare / RunPythonScript / ResetEngine

```sh
python3 "$SKILL_DIR/scripts/rhino.py" prepare --kind probe --major 7 \
  --script "$RUN_DIR/probe7.py" --output "$RUN_DIR/probe7.json"
```

`prepare` 将 [共同版本探测](../scripts/runtime_compat.py) 内联到新文件，输出独立可运行的 `.py` 和宏，例如 `_-RunPythonScript "/absolute/probe7.py"`。输出和源码位于包外新路径；不依赖 cwd、包目录、`__file__` 或之前导入的模块。自定义业务脚本也应自包含，顶层明确调用一次主函数；只写 `def` 不会执行建模。

通过 computer use 提交分两步：先只输入 `_-RunPythonScript` 并回车；读界面确认出现 `Python Script` 路径提示后，输入完整带引号的绝对路径，核对后回车一次。不要逐字快速输入整个宏跨越命令切换；完整宏粘贴若已自动执行，不再按回车，以免重复 Paste 并插入剪贴板图片。等待新 JSON，回读实际版本、Python 实现及文档标识。

尚未运行的 Rhino 可按目标代 Starting Rhino 文档使用启动参数。macOS：`open -a "/Applications/Rhino 7.app" --args -runscript '...macro...'`；Windows：`Rhino.exe /runscript="...macro..."`。核对该代路径引用规则；已运行应用可能忽略启动参数，应使用现有进程的命令栏，避免另起进程接到错误模型。

Rhino 8 CPython 的分阶段提交与初始化约束见[本版说明](versions/8.md#scripteditor-提交)。

`-RunPythonScript` 的 `ResetEngine` 只用于确需清除多文件开发的旧模块状态，不能用它自动重跑失败修改；优先生成自包含文件，避免导入缓存。

## 写脚本前的版本检查

先查该代帮助，再查函数签名、返回值和 RhinoCommon `since`；当前网站示例不代表旧版本可用。[分版本源码与 XML](documentation.md#pythonrhinocommon-与-mcp) 可离线核对。RhinoScriptSyntax 的包装函数与其底层 RhinoCommon 方法都必须可用；新参数不能仅按函数同名推断兼容。帮助中的跳转入口要解析到实际正文；复制示例以原 HTML pre 或官方 Python 源码为准，不复制丢失缩进的提取文本。

主版本/SR、运行 build、文档标识、Objects.Find 和保存接口的差异按[目标版本索引](versions.md)读取，不能仅凭同名接口推断兼容。

旧 XML 中没有注释条目不证明接口不存在；交叉检查新版 `since`、对应分支的官方源码与实际运行时。无法确认的接口先做只读能力检查，再决定最低 SR 或替代路径；不要等修改了一半才发现缺方法。

## 一次提交的编写清单

1. **共同语法与路径**：首行 `# -*- coding: utf-8 -*-`（CPython 的 shebang 存在时在第二行）；`from __future__ import print_function` 放在普通 import 之前。5–8 共用文件不用 f-string、类型注解、dataclass、pathlib、Python 3 专属标准库或 CPython 的 NumPy/C 扩展。非 ASCII 名称/路径用 `u"..."`；生成器用 `u` 加 ASCII JSON 转义，避免 Windows 反斜杠变转义符。需要小数运算时用 `4.0 / 3`，避免 Python 2 整数除法。
2. **输入与文档**：`import Rhino`、`import rhinoscriptsyntax as rs`、`import scriptcontext as sc`。在 Rhino 文档上下文执行，固定本次 `sc.doc`，不在异步线程改文档，不借 Grasshopper 临时文档代替。先核验 GUID 存在、对象类型/锁定状态、尺寸有限且合理、输出目录可写；不调用 `GetObject`/`GetPoint`/`_Pause`。需要用户选取时先取得选择再运行。
3. **单位与坐标**：读取单位及绝对/角度容差，明确参数是在世界坐标还是指定平面；圆/圆弧传显式平面，变换传轴，避免活动 CPlane 影响。`rs.AddArc`、`rs.RotateObject`、`rs.AddRevSrf` 的角度为度；RhinoCommon 方法可能用弧度，逐签名核对。不要把 0.001 mm 当任意模型的通用容差；本夹具只在空模型设毫米与 0.001。已有模型不得无意改变单位或缩放几何。
4. **创建与返回值**：按接口契约区分 GUID、列表、bool、数值/元组；先判失败，再索引/测量。零数值、`t=0`、setter 返回的旧 False/空名称可能有效，不可一律 `if not value`。直接 RhinoCommon 添加对象还须拒绝 `System.Guid.Empty`。RhinoCommon 内存几何不会自动出现在文档：用相应 `doc.Objects.Add…` 写入；修改已有对象用对应 Replace/ModifyAttributes/CommitChanges，并验证返回值。图层/属性/视图 setter 多数返回旧值或修改数，不是新的值；用 getter 回读。
5. **状态与证据**：批处理保存 `prior = rs.EnableRedraw(False)`，`finally` 恢复原图层、选择（若有改变）、原 redraw 状态及临时上下文。记录任务 GUID；布尔删除输入后改用返回的新 GUID。验证有效性、闭合性和尺寸/面积/体积，再保存并回读；发生错误保留 traceback 与已有对象，不自动重发、不全选删除用户模型。

接口特有的几何前提与返回值经验在[按接口查询的注意事项](api-notes.md)，用 `section --with-notes --id rs.函数名` 随契约读取命中段；已读且资料未变化的段复用。仅 API 缺失需走命令回退时读取 rs.Command 对应段。

## 提交前检查顺序：compile

先固定目标主版本/SR、平台、引擎、文档标识、输入 GUID/单位和新输出路径；逐个 API 核对签名、最低版本及返回类型。再检查实际生成文件的编码、缩进、引号、顶层调用与所有退出路径。在**目标引擎**用 `compile(open(path, 'rb').read(), path, 'exec')` 做只编译预检，不 exec/import 候选文件；系统 Python 3 的编译不能证明 IronPython 2.7 可用。随后只读验证依赖和必要 API 存在，检查输入几何、容差及期望量，才单次提交建模。compile 通过不证明 API/几何正确；成功须由结果断言和文件回读确认。验证记录同时写明已覆盖的平台/引擎和未安装的版本，不把静态检查当实机结果。

## 保存与完整验收：WriteFile / File3dm.Read

区分对象类型：活动文档的 `RhinoObject.Id` 与文件回读的 `File3dmObject.Attributes.ObjectId` 都是 GUID；`ObjectAttributes` 没有 `Id`。只读预检同时覆盖保存/回读用到的属性，不能只检查建模函数是否存在。

原生保存采用 `FileWriteOptions`，设 `SuppressDialogBoxes=True`、`WriteSelectedObjectsOnly=False` 后调用 `WriteFile`；检查 bool，再 `File3dm.Read` 核对 GUID、有效几何与单位，最后 `Dispose()`。窗口标题/当前文档路径是否变化不能代替落盘验收。`compatibility_target=5` 不会把 Rhino 8 的输出自动变成 Rhino 5 文件；交付旧格式时需另选该版本保存设置并验收实际文件版本。

## smoke20：跨版本夹具验证

```sh
python3 "$SKILL_DIR/scripts/rhino.py" prepare --kind smoke20 --major 5 \
  --script "$RUN_DIR/rhino5-test.py" --output "$RUN_DIR/rhino5-test"
```

分别生成 major=5、6、7 的脚本，均来自同一 [smoke20.py](../scripts/smoke20.py)，只改变兼容目标。每份在新空白模型中原生 `RunPythonScript` 一次；不要用 MCP 代替原生验证。要求 [20 项断言](validation.md) 全通过、attempts=1、implementation=IronPython，并回读 3DM。修订后从唯一源重新生成，保留失败记录；在 Rhino 8 通过只能称旧脚本在 Rhino 8 的兼容测试。未知模型应先完成输入检查和几何预检；模板不能保证任意拓扑一次成功。

Rhino 8 同时生成 major=8 的 ironpython 与 cpython 两份 `smoke20`，分别走 RunPythonScript / ScriptEditor，检查 implementation 各自正确。`prepare` 生成的是探针或确定性验收夹具；业务脚本由 agent 按本清单编写，不能把夹具不加修改地当业务结果。

依据：[Rhino 5](https://docs.mcneel.com/rhino/5/help/en-us/information/rhinoscripting.htm#RunPythonScript)、[6](https://docs.mcneel.com/rhino/6/help/en-us/information/rhinoscripting.htm#RunPythonScript)、[7](https://docs.mcneel.com/rhino/7/help/en-us/information/rhinoscripting.htm#RunPythonScript) 的脚本说明；[官方 RhinoScriptSyntax 源码](https://github.com/mcneel/rhinoscriptsyntax)；各代完整 XML 及固定分支快照见[离线索引](documentation.md)。
