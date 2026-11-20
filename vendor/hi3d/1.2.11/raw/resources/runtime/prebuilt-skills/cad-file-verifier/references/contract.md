# 验收契约

输入、状态和结论以本文件为准。执行入口见 [SKILL.md](../SKILL.md)。

## 任务

| 字段 | 含义 |
| --- | --- |
| `mode` | `inspect` 单文件健康检查，`compare` 对照基线，`roundtrip` 在已授权副本上保存并重新打开 |
| `candidate` | 待验收文件 |
| `source` | 基线。`compare` 必须提供。没有基线时保留项为 `unknown` |
| `target` | 软件、版本、构建和平台。FreeCAD 适配器在软件名为空时填入 FreeCAD |
| `document_type` | `drawing`、`part`、`assembly`、`drawing_sheet`、`exchange_solid`。空则只在内容识别为高可信时推断 |
| `required_preservation` | 本次硬性保留项。空则使用该工程类型的默认检查配置 |
| `expected_changes` | `{path, value}`。路径如 `dimensions.D1.value`、`objects.10.layer`。命中的变化不算意外丢失 |
| `dependencies` | `{id, path}`。路径在工作区外或文件不存在时，依赖闭合失败 |
| `tolerances.absolute` | 数值比较阈值。未提供时，不相等的数字为 `unknown`，不编造公差 |
| `allowed_operations` | `read`、`copy`、`roundtrip`、`edit_probe`、`repair`、`convert`。默认 `read` 与 `copy` |
| `require_native` | 默认 true。为 false 时原生打开记为不适用，静态结果不能写成目标软件已验收 |
| `freecad` | 可执行文件。缺失时原生能力为不可执行 |
| `budget_seconds` | 原生子进程墙钟上限，默认 120。到点停止，不自动重试 |
| `repair` | true 时只记录是否授权。当前适配器不执行修复 |
| `upstream_build` | `{tool, version, session_evidence_refs}`。缺省 `tool` 为 `not-specified`。`classcad` 只记录源端会话，不连接该引擎，也不把源端通过写成目标软件原生验收 |

隔离复制始终发生，且不写回原始路径。`roundtrip`、`edit_probe`、`repair`、`convert` 需要出现在 `allowed_operations` 中才允许继续；其中编辑探针、修复和转换当前没有实现。

## 状态

| 状态 | 含义 |
| --- | --- |
| `pass` | 声明范围内的证据满足要求 |
| `fail` | 证据表明要求未满足 |
| `unknown` | 没有足够证据，包括没有基线、字段没读到、两侧都缺失 |
| `blocked` | 软件、许可、授权或预算使检查没有执行 |
| `not_applicable` | 本次工程或目标不适用，并写明理由 |

整体优先级：`fail`，然后 `blocked`，然后 `partial`，然后 `pass`。必须项出现 `unknown` 时整体为 `partial`。没有可评估的必须项时不能通过。被排除的项目写入范围说明，不记为通过。

打开成功、保存成功、对象数量相同、外观相近和进程退出码都不能单独证明兼容。目标软件没装好是执行受阻，不是文件不兼容。

## 记录

实测记录追加到注册表，不覆盖旧的通过或失败。每条记录带上 `upstream_build`。`record_kind: mock` 不进入通过统计。相同环境下一例通过、一例失败时，聚合视图同时保留并标出冲突。构建号不同、或上游工具不同的记录分列，旧结果仍可查询。`tool` 为 `classcad` 的样本在视图中单独限制定义：源端样本不证明目标软件的原生工程兼容。更正用新记录的 `supersedes` 指向旧记录，不删除旧行。

注册表写入失败时保留本地报告，并写明兼容记录未更新。
