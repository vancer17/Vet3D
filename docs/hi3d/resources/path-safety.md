# `path_safety.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）随 `run-tools` 物化的 Python 路径预检模块。`config_runtime.py` 与 `hi3d-edit-job.py` 导入它。模型读取相关资源或消费脚本时可以看到这层约束，宿主允许执行后可随消费脚本运行。安装包中未发现独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/path_safety.py)

**源码模块说明原文**

```text
Preflight local write roots without creating or changing any files.
```

## 参数、结果与副作用

| 接口 | 参数与返回 | 失败条件 |
| --- | --- | --- |
| `paths_overlap(first, second)` | 两个参数均为必填路径。解析后路径相等，或其中一项位于另一项的祖先路径中，返回 `True`。其余情况返回 `False`。 | 路径类型或解析错误向上传播。 |
| `validate_write_roots(write_roots, *, package_root, protected_inputs=())` | `write_roots` 为命名路径映射，`package_root` 为调用包根，`protected_inputs` 为受保护路径的可迭代对象，默认为空。返回键相同、值为已解析 `Path` 的字典。 | 输出根与包根或任一个受保护输入相等或为其祖先或后代时抛 `ValueError`。文件系统路径解析异常向上传播。 |

预检采用 `Path.resolve()`，会解析既存的符号链接。允许尚未创建的写入根，也允许多个写入根相互重叠。预检只处理传入的根和显式保护项。调用方决定文件名、覆盖策略和后续写入。整个预检不创建或修改文件。 [安装包中的上游本地执行说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>)

## 依赖、权限与 Hook

只依赖 Python 标准库 `pathlib`。读取路径元数据和后续写入受运行进程、文件系统权限与宿主沙箱约束。文件系统在校验后发生变化、硬链接指向同一内容、派生文件另行越界，均需由调用方的执行边界处理。模块未声明独立 Hook。通过宿主执行时沿用本地执行入口及其实际前置 Hook。 [执行工具](../tools/exec-command.md)

## 中性调用示例

**调用示例。** 假定归档脚本目录在 Python 模块搜索路径上。输入和输出使用分开的目录，成功时只返回解析后的结果目录。

```python
from path_safety import validate_write_roots

roots = validate_write_roots(
    {"result": "runs/check-01"},
    package_root="vendor/tool-package",
    protected_inputs=("fixtures/mesh.glb",),
)
print(roots["result"])
```

## 核查依据

已核对 1.2.11 安装副本的大小、SHA-256、路径关系分支及实际导入点。归档模块在 Windows 临时目录接受独立输出路径，并拒绝将受保护输入的父目录设为写入根。并发文件系统变化、硬链接和具体宿主权限仍待实测。 [P0 清单](../upstream/1.2.11/extraction/priority.json) · [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
