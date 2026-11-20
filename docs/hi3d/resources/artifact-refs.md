# `artifact_refs.py` 会话产物别名

## 资源名称、来源与模型可见性

该 Python 模块随 Hi3D Agent 1.2.11（Windows x64）的 `.dependency-run-tools` 交付，构建来源为 `tools/run-tools/scripts/artifact_refs.py`。它通过受管依赖的 `REFERENCE.md` 和引用约定供调用方按需读取。已核实 Python 函数和 CLI，没有发现本文件作为同名 LLM Tool 注册的证据。模型可在读取参考文档后得知用法，也可通过本地执行工具读取 CLI 帮助或结果。模块 docstring 同时是 `ArgumentParser` 的说明，原文如下。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/artifact_refs.py) · [安装包引用约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/artifact-refs.md>) · [本地执行工具](../tools/exec-command.md)

```text
Conversation artifact aliases on a package-external session. No network.
```

## 参数、结果与副作用

所有 CLI 动作均要求 `--session`，指向现有 UTF-8 `pcg.session.v1` JSON。模块从同目录导入 `session_schema.validate_session`。 [会话文档契约](session-schema.md)

| CLI 动作 | 参数与结果 |
| --- | --- |
| `mark` | 需要 `--name`，输入显式 `--path` 或配对的 `--task` 与 `--output`。显式路径也可附带配对的槽位元数据。可选 `--label` 默认为空。名称需匹配 `[A-Za-z][A-Za-z0-9_-]{0,63}`，其中 `last` 保留。更新或新增键后写回原会话，并输出该引用的 JSON。 |
| `list` | 输出引用记录列表的 JSON。 |
| `resolve` | 需要 `--ref`，可以传入 `name`、`@name`、`ref:name` 或 `@last`。可选 `--task-root` 加入 `exists` 与 `resolved`。 |
| `rewrite` | 需要 `--text`。先按 `TOKEN_RE` 识别 `@name`，再用相应记录的路径替换命中的文本。含空白或引号的路径使用 JSON 字符串的形式引用。未匹配的普通别名保持原样。空列表上的 `@last` 会报错。 |

`mark_ref` 用名称维护单条记录，默认用 UTC ISO 时间填 `at`。记录还含 `path`、`label`、可选的 `task`、`output`、`entry`。`mark_slot` 按 `task/output` 从会话产物中取得路径。`@last` 按记录中的 `at` 值及列表位置选取。参数缺失、未知槽位或别名、会话格式错误均可触发异常。`mark_ref` 拒绝 HTTP(S) 和脚本 URL。读取既有会话时，`validate_session` 针对脚本协议和常见签名标记检查路径，普通 HTTPS 引用在隔离夹具中通过了校验和解析。标记后可用 `resolve --task-root` 查询 `is_file()` 结果，文件缺失时仍返回记录并标记 `exists: false`。读取、序列化或写入失败会作为异常退出。

`NAME_RE` 接受尾随连字符，`TOKEN_RE` 以词边界 `\b` 结束。隔离夹具把 `demo-` 绑定到 `long.png` 后，`resolve @demo-` 找到该记录，`rewrite` 则保留 `@demo-`。再将 `demo` 绑定到 `short.png` 后，`rewrite` 将 `@demo-` 改成 `short.png-`。调用方若需要精确查找，应使用 `resolve` 的完整别名参数。

## 执行与权限

模块使用 Python 标准库并访问调用方明确提供的会话及文件。CLI 的 `mark` 直接覆盖会话文件，应由调用方控制写入时机。`resolve --task-root` 解析任务根，对拼接后的目标调用 `is_file()`，再比较目标的词法祖先。因此，含 `..` 的路径可穿过此检查。隔离夹具在同一临时目录内创建任务根和它的兄弟文件，`../outside-fixture.txt` 经归档脚本解析后返回 `exists: true`。`resolved` 是拼接得到的路径字符串，宿主须按最终真实路径判断文件是否位于任务根内。经 `exec_command` 执行时适用当前执行环境的审批与前置 Hook。 [本地执行权限与 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 中性示例与核查依据

**CLI 示例。** 在已存在 `session.json` 的任务目录运行，将 `$script` 设为归档脚本路径，并显式使用选定的 Python。首次命令会改写该会话文件。

```powershell
& $python $script mark --session session.json --name preview --path exports/preview.png --label '预览'
& $python $script resolve --session session.json --ref '@preview' --task-root .
& $python $script rewrite --session session.json --text 'Review @preview'
```

已静态核对安装脚本的 CLI、会话依赖和上游用法。用归档脚本和临时会话实测了标记、解析、改写及上述边界。真实宿主的补充路径校验、跨轮注入、并发写回及文件移除后的恢复仍待核对。 [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
