# `tool_result.py` 短结果

## 资源名称、来源与模型可见性

该 Python 模块随 Hi3D Agent 1.2.11（Windows x64）的 `.dependency-run-tools` 交付，构建来源为 `tools/run-tools/scripts/tool_result.py`。它提供 `pcg.tool_result.v1` 构造和校验。调用方可通过受管依赖文档发现该协议，并选择是否将结果放入模型上下文。未发现同名 LLM Tool 注册或独立 CLI。以下是模块 docstring 原文。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/tool_result.py) · [安装包受管依赖说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>)

```text
Short tool result returned into the agent loop. Logs stay in the task directory.
```

## 参数、结果与错误

`tool_result` 返回字典并调用 `validate_tool_result`。直接校验返回传入的字典。构造参数全部以关键字传入。

| 字段 | 类型、默认值与校验 |
| --- | --- |
| `status` | 必填，使用 `ok`、`failed`、`skipped`。 |
| `summary` | 必填非空字符串。构造限制长度为 1 至 240 字符，直接校验仅检查类型与非空。 |
| `artifacts` | 可选，默认空列表。成员为非空路径字符串，或含非空 `path` 的映射。映射内 `task` 与 `output` 成对提供，`href` 如提供需为非空字符串。 |
| `next_checkpoint` | 可选字符串，默认 `None`。 |
| `irreversible` | 可选，构造默认空元组，写入结果时转为列表。直接校验把缺省或假值按空列表判断。 |
| `error` | 可选。构造只接受字符串，未提供时省略该键。直接校验不校验此字段。 |

构造结果填入固定 `schema='pcg.tool_result.v1'`。无效参数或结构通常抛 `ValueError`，构造中不可转成列表的参数还会触发 Python 类型错误。没有磁盘、进程、网络或日志副作用。调用方自行负责序列化、持久化和结果投递。

## 执行与权限

模块使用 Python 内置类型和 `__future__`。调用方负责产物文件、路径边界和访问权限的检查。`session_schema.apply_tool_result` 可显式接收产物列表，schema 校验、状态判定与交付条件由调用方处理。隔离夹具以 `tool_result(status="failed", summary="Partial output", artifacts=["partial.png"])` 构造合法失败结果，`apply_tool_result` 将该路径登记到会话。经宿主命令启动 Python 时仍适用该命令的权限和 Hook。 [会话文档契约](session-schema.md#参数与结果) · [本地执行权限与 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 中性示例与核查依据

**Python 导入示例。** 在可导入归档脚本的解释器中构造结果。此例不访问文件系统。

```python
from tool_result import tool_result

result = tool_result(
    status="ok",
    summary="Preview prepared",
    artifacts=[{"path": "exports/preview.png", "task": "review", "output": "preview"}],
    next_checkpoint="review",
)
assert result["schema"] == "pcg.tool_result.v1"
```

已静态核对构造、校验及会话侧的产物回填接口，并用归档模块实测构造示例与失败结果回填。发行清单还记录了 `.dependency-head-hair-split` 和 `taubin-smooth` 下同源同摘要的物化副本。真实宿主的短结果传递、失败产物验收、回包持久化及错误展示仍待核对。 [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
