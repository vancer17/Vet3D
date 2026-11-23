# `rigging/__init__.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）的 `.dependency-skin-weights/scripts/rigging/__init__.py`。这是 `rigging` 的 Python 包初始化文件，保留子模块实际使用的命名空间。上游资源契约将其列为包命名空间及导入适配。模型可通过读取该契约获知包路径。安装包核查范围内没有此文件的独立 LLM Tool 定义。 [归档原件](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/__init__.py) · [安装包资源契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-skin-weights/references/code-contract.md>)

**源码模块说明原文**

```text
Pure numerical skin-weight APIs; no service submission.
```

## 输入、结果与副作用

调用方以归档的 `.dependency-skin-weights/scripts/` 作为模块搜索根，执行 `import rigging` 后取得 Python 包对象和上述文档字符串。该文件只包含文档字符串，导入时由解释器建立包命名空间及模块缓存。功能入口由调用方从实际子模块显式导入。解析不到包时使用 Python 自身的导入错误。 [P1 包结构与依赖](../../upstream/1.2.11/extraction/p1/priority.md)

## 依赖、权限与前置 Hook

初始化文件没有其他本地或第三方导入。执行只需要 Python 及归档路径的读取权限，可用 `-B` 避免解释器生成字节码缓存。包加载及子模块调用由实际宿主或本地命令授权，前置检查属于外层执行入口。不同供应包可能有同名 `rigging`，调用方应核对 `__file__` 对应的确切归档路径。 [本地执行工具](../../tools/exec-command.md)

## 调用示例与核查依据

**调用示例。** 在所选 `.dependency-skin-weights/scripts/` 已加入 Python 模块搜索路径时验证导入来源。

```python
import rigging

print(rigging.__file__)
print(rigging.__doc__)
```

安装包已核实初始化文件仅含说明字符串。已在独立 Python 进程中核对 `rigging.__file__` 确实指向 P1 归档，并从相应包路径导入数值子模块。后续仍需在目标进程复核搜索路径与同名包解析。 [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [安装包资源契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-skin-weights/references/code-contract.md>)
