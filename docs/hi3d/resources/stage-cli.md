# stage_cli.py

## 资源身份与模型可见性

`stage_cli.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `run-tools` 的 Python 入口辅助模块。上游参考入口列出它承担命令行适配。实际参数来自调用脚本，模型可按该脚本的说明经本地命令入口执行。模块没有独立 LLM Tool 注册、模型可见工具 `description` 或可直接处理业务的 CLI。 [归档源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_cli.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>)

## 参数、结果与副作用

| 接口 | 参数和结果 |
| --- | --- |
| `cli_arguments(argv=None)` | 省略时复制 `sys.argv[1:]`，否则将给定可迭代参数转换为列表。遇到第一个独立 `--` 时只返回其后的元素，否则返回列表原内容。结果不解析参数含义，不验证业务输入。 |
| `StageFinished(code=0)` | 携带 `code` 属性的异常对象。构造函数保存给定值，调用者决定何时以及怎样把它转成进程退出码。 |
| `_finish_stage(code=0)` | 本地辅助函数，直接抛出 `StageFinished(code)`，由外层入口捕获。若未处理，异常沿调用栈传播。 |

导入会解析模块自己的目录，在该目录未出现在 `sys.path` 时把它插到首位。入口如何处理阶段结束信号由消费脚本决定。随包一个实际消费入口在 `main` 捕获异常并返回它，在顶层再抛 `SystemExit(result.code)`。该调用关系来自安装包源码，未据此推定具体会话执行。 [消费入口实例](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/earbud-case-cover/scripts/build_scene.py:129>)

## 依赖与权限

仅使用 Python 标准库。脚本自身只处理参数、导入路径及异常，业务读取、写入、启动行为与权限由外层入口管理。通过 Codex shell 执行时，前置 Hook 和沙箱在命令工具调用前判定。模块没有单独的 Hook，普通 Python 与 Blender 调用时均须按上层入口约定传参。 [执行工具的权限与前置 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**根据归档源码编写的示例。** 模块目录已加入导入路径。这里显式提供一组参数，用来展示 Blender 风格的分隔符与外层退出码转换。

```python
from stage_cli import StageFinished, _finish_stage, cli_arguments

arguments = cli_arguments(["--background", "--", "sample.json"])
try:
    if arguments == ["sample.json"]:
        _finish_stage(0)
except StageFinished as finished:
    raise SystemExit(finished.code)
```

## 核查依据与待验证项

源码映射为 `tools/run-tools/scripts/stage_cli.py`。已核对归档摘要并在普通 Python 中执行示例，确认示例的参数切片和退出码。具体消费入口的结束码传播与 Blender 启动参数需按实际入口联测。 [资源选择与摘要](../upstream/1.2.11/extraction/priority.json)
