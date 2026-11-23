# `checkpoints.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）内置 `run-tools` 的本地产物验证模块，供已写入文件的阶段按摘要复核。调用脚本通过 Python 导入。模型可以读取上游使用说明或源码，宿主允许时可以执行导入该模块的脚本。安装包未提供该模块的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/checkpoints.py) · [执行工具](../tools/exec-command.md)

**源码模块说明原文**

```text
Local content verification only; never decides whether remote work can retry.
```

## 参数、结果与副作用

| 接口 | 参数与返回 | 校验与异常 |
| --- | --- | --- |
| `digest(path)` | 必填本地文件路径。以 1 MiB 块读取，返回 SHA-256 十六进制字符串。空文件也返回其完整摘要。 | 文件无法打开或读取时，错误向上传播。 |
| `artifacts_match(artifacts, *, base=None, expected=(), allow_empty=False)` | 必填 `artifacts` 字典，键为文件路径字符串，值为 SHA-256 字符串。`base` 可指定相对路径基准，省略时按进程当前路径解析相对名。`expected` 可传必有的文件键，默认空。`allow_empty` 默认 `False`。 | 传入类型错误、缺必有键、非字符串条目、缺文件或摘要变化时返回 `False`。全部条目核对成功时返回 `True`。设置 `allow_empty=True` 后，仅在 `expected` 同时为空时允许空字典通过。文件打开或读取错误仍可向上传播。 |

函数只读取本地文件及元数据，不写状态，也不启动进程。`base` 用于路径拼接。调用方需要独立处理绝对路径、`..`、符号链接及写入根限制，并验证记录 schema、输入及配置指纹。远端任务另用服务的任务标识和恢复协议。 [安装包中的上游本地执行说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>)

## 依赖、权限与 Hook

只依赖 Python 标准库 `pathlib` 和 `hashlib`。执行进程须拥有目标文件读取权限，工具层沙箱根据本轮环境生效。模块未声明独立 Hook。由宿主本地执行入口运行时，沿用该入口适用的前置 Hook。 [执行工具](../tools/exec-command.md)

## 中性调用示例

**调用示例。** 假定归档脚本目录在 Python 模块搜索路径上。`recorded_artifacts` 来自之前一次完成的本地任务记录，使用旧摘要检查现有文件。

```python
from checkpoints import artifacts_match

recorded_artifacts = {
    "notes.txt": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
}
print(artifacts_match(recorded_artifacts, base="runs/check-01", expected=("notes.txt",)))
```

此例中 `notes.txt` 的约定字节为 ASCII `hello`，末尾无换行。文件缺失或含额外换行时检查返回 `False`。

## 核查依据

已核对 1.2.11 安装副本的大小、SHA-256、布尔返回分支及只读实现。归档模块实测接受摘要匹配的本地文件，并在缺少指定记录名时返回 `False`。安装包 `head-lowpoly/scripts/run.py` 的导入可复核调用来源。具体业务记录、文件并发变化和端到端缓存决策仍需按实际调用方验证。 [P0 清单](../upstream/1.2.11/extraction/priority.json) · [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
