# `config_runtime.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）内置 `run-tools` 的 Python 参数与路径模块。物化在 `.dependency-run-tools/scripts/`，同一源码也以 `frame_runtime.py` 等名称投放到调用包。它由选定脚本导入。模型可通过本地文件读取看到源码，或在宿主允许执行时通过 `exec_command` 运行消费脚本。安装包证据为模块和上游使用说明，无独立的 LLM Tool 注册或模型可见 `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/config_runtime.py) · [执行工具](../tools/exec-command.md)

**源码模块说明原文**

```text
Argument/path boundaries; importing this module never starts work.
```

## 参数、结果与副作用

| 接口 | 参数与返回 | 校验和副作用 |
| --- | --- | --- |
| `cli_arguments(argv=None)` | 提供序列时返回列表副本。默认从 `sys.argv` 取第一个 `--` 之后的参数，否则跳过程序名。 | 仅读参数。 |
| `validate_paths(options)` | 接收可修改的 `Namespace` 或同类对象，就地替换值非 `None` 的 `source`、`scene`、`library`、`heightfield`、`heightfields`、`config`、`artwork`、`input`、`model` 和 `output` 属性。返回 `None`。 | 对这些属性展开 `~` 并解析路径。输入要求路径存在，缺失抛 `FileNotFoundError`。`output` 在当前模块所属包根内或与包根相同时抛 `ValueError`。输入允许目录。失败前已处理的属性可能已经替换。 |
| `load_config(path, *, required=())` | 读取指定文件，默认不要求键，返回 Python `dict`。 | 使用进程默认文本编码。顶层不是对象或缺少指定键时抛 `ValueError`。JSON 解码、文本解码和文件读取错误向上传播。 |
| `resolve_file_request(inputs, write_roots, *, package_root)` | 接收命名输入文件映射、命名写入根映射和调用包根，返回 `(resolved_inputs, resolved_write_roots)`，值均为解析后的 `Path`。 | 全部输入须为现有文件，缺失或传入目录时抛 `FileNotFoundError`。将全部解析出的输入作为受保护路径交给 `validate_write_roots`，冲突时抛 `ValueError`。允许既存的安全输出目录和写入根相互重叠。 |

`validate_paths` 使用模块自身的包根限制其 `output` 属性。`resolve_file_request` 使用调用者提供的 `package_root`，并同时检查该根与所有显式输入。两者都不创建目录。除读取路径、配置和参数外，模块唯一的主动修改是 `validate_paths` 替换调用对象的属性。 [安装包中的上游本地执行说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>)

## 依赖、权限与 Hook

需使用 Python 标准库。调用 `resolve_file_request` 时还需从模块搜索路径导入同目录的 `path_safety.py`。模块读取文件与路径元数据的权限由执行进程和宿主沙箱决定。随包实现未声明独立 Hook。借助宿主本地执行工具时，以该轮工具的有效权限及前置 Hook 为准。 [路径校验资源](path-safety.md) · [执行工具](../tools/exec-command.md)

## 中性调用示例

**调用示例。** 假定归档脚本目录在 Python 模块搜索路径上，`fixtures/mesh.glb` 和 `fixtures/process.json` 已存在。示例读取配置和路径，`runs/check-01` 无需预先存在。

```python
from config_runtime import load_config, resolve_file_request

inputs, outputs = resolve_file_request(
    {"model": "fixtures/mesh.glb", "settings": "fixtures/process.json"},
    {"result": "runs/check-01"},
    package_root="vendor/tool-package",
)
settings = load_config(inputs["settings"], required=("format",))
print(outputs["result"], settings["format"])
```

## 核查依据

已核对 1.2.11 安装副本的大小、SHA-256、参数分支及对 `path_safety` 的本地导入。归档模块实测可解析现有输入和独立输出根，预检后输出目录仍待调用方创建。安装包内 `motion-base/scripts/run.py` 和 `earbud-case-cover/scripts/run.py` 的导入可复核实际消费路径。单文件写入、并发路径稳定性与失败回滚仍需按所选调用方核查。 [P0 清单](../upstream/1.2.11/extraction/priority.json) · [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
