# Rhino 5–8 两级文档索引

先确定目标大版本；安装元数据用于选探针，执行前仍须核对进程内版本/SR、平台、引擎和文档。每次只读取本版索引命中项，不加载整份索引、XML、Python 模块或其它版本正文。

## 第一级：版本到路径

`catalog.zip!路径` 表示随包[文档目录归档](catalog.zip)中的 UTF-8 文件；索引的 `start/end` 是对应正文 **1 起点、两端包含**的物理行号。`references/…` 路径相对于完整 rhino-control 包，其他路径相对于 catalog.zip。原始资料与许可保留在[来源索引](documentation.md)，不作为默认读取入口。

| Rhino | 第二级接口索引 | 共用 API 正文 | 本版差异正文与运行约束 |
| --- | --- | --- | --- |
| 5 | `catalog.zip!5/index.jsonl` | `common/rs.md`、`common/rc.md` | `5/rs.md`、`5/rc.md`；[Rhino 5](versions/5.md)。Python：`rhino-5`（Windows）/ `mac-rhino-5.0`；XML：`net35` |
| 6 | `catalog.zip!6/index.jsonl` | 同上 | `6/rs.md`、`6/rc.md`；[Rhino 6](versions/6.md)。Python：`rhino-6.0`；XML：`net45` |
| 7 | `catalog.zip!7/index.jsonl` | 同上 | `7/rs.md`、`7/rc.md`；[Rhino 7](versions/7.md)。Python：`rhino-7.0`；XML：`net48` |
| 8 | `catalog.zip!8/index.jsonl` | 同上 | `8/rs.md`、`8/rc.md`、`8/mcp.md`；[Rhino 8](versions/8.md)、[本版 MCP](versions/8-mcp.md)。Python：`rhino-8.0` / `rhino-8.30`；XML：`net48` / `net7.0` |

第二级每项记录精确 `id`、`kind`、`variant`、正文 `path/start/end`、简短功能 `summary`（异常长首句以 … 明示截断，完整约束在正文）；API 同时记录原归档 `source/source_start/source_end`。`rs` 为公开 RhinoScriptSyntax 函数，`rc` 为完整 RhinoCommon XML member（含重载签名），`mcp` 为本版 RhinoMCP 工具用途及上游语义章节，`guide` 为脚本、MCP、桌面操作和验收约束；[API 注意事项](api-notes.md)的 guide 行另以 `apis` 列出准确关联接口，正文仍只维护一份。MCP 工具的实际入参仍须核对本次 tools/list；文档快照不是在线 schema。

## 只读取需要的行段

```sh
# 写脚本只列本版与共用 Python 规则；每组默认最多 12 条，不输出正文。
python3 "$SKILL_DIR/scripts/docs.py" lookup --major 7 --kind guide --query guide:7: --query guide:python: --format text
# 已知精确 ID，内部按本版索引一次定位契约和对应注意事项，无需先输出 API 目录。
python3 "$SKILL_DIR/scripts/docs.py" section --major 7 --with-notes --id rs.AddBox --id rs.SurfaceVolume
# 未知名称先查询；不指定 kind 时也能找到关联注意事项。
python3 "$SKILL_DIR/scripts/docs.py" lookup --major 7 --query AddBox --format text
# Python 分支与 XML 框架分别选择；也可在同批 section 中混合 rs/rc/guide。
python3 "$SKILL_DIR/scripts/docs.py" lookup --major 8 --rs-variant rhino-8.30 --rc-variant net7.0 --query rs.AddPictureFrame --query RhinoDoc.WriteFile --format text
# Rhino 5 Mac 示例；Windows 改为 rhino-5，不能为绕过缺项选择另一平台。
python3 "$SKILL_DIR/scripts/docs.py" section --major 5 --rs-variant mac-rhino-5.0 --rc-variant net35 --with-notes --id rs.DocumentPath --id rs.AddBox
```

写脚本先读取本版运行约束，再按 `guide` ID 读取“创建与提交”“一次提交的编写清单”“提交前检查顺序”；需要保存时加“保存与完整验收”。CPython 只读 Rhino 8 对应引擎/ScriptEditor 段；MCP 安装和调用以 guide:8-mcp: 查询本版 MCP 段；CUA 用 guide:computer-use:。20 项夹具与来源/维护目录仅在实际使用时查询读取。已读取且资料未变化的段无需重复加载。`lookup` 的 total/truncated 表示是否有更多匹配；`--format text` 用单行显示 `id | path:start-end | variants | summary`，保留 total/truncated；自动化解析仍用默认 JSON。`--query` 可重复以批量检索；用更准确的名称缩小范围，必要时 `--limit`（1–100）。批量 lookup/section 在一次命令内复用版本索引和所需正文，不跨命令缓存。`section --with-notes` 精确关联本版 `apis`，共享注意事项每批输出一次，不执行模糊名称猜测；不带该标志时保持原纯契约输出。lookup 不限定 kind 可同时发现接口与注意事项，--kind rs/rc 只查对应契约。默认合并指向同一正文的 variant，仅输出定位字段；需要原实现时加 `lookup --sources` 获得原归档的精确行号。

`lookup` 和 `section` 均可用 `--rs-variant` 选 Python 分支、`--rc-variant` 选 XML 框架；两个选项互不影响，也不筛掉 guide/MCP。只接受该大版本实际收录的标签；旧 `section --variant` 保留给单类读取，与不同的分类型选择冲突时拒绝。重载仍须使用完整 ID。

未明确分支时，只有本版所有已归档分支均有记录且契约相同才直接读取。正文不同、包装实现不同或部分分支缺项均要求选择。`Wrapper difference` 警示表示相同说明掩盖了实现变化，必须按其中的原源码范围核对所选分支的输入/返回规则；不能只读相同 docstring。归档缺记录不证明运行时没有 API，也不能借另一平台、框架或新版补齐。

按目标平台选择 Rhino 5 分支；Rhino 8 的 8.0/8.30 与 XML 标签是固定源码/包快照，不是 IronPython/CPython 引擎名或任意 SR 的自动匹配。未覆盖的 SR 需查 Since、同版原始资料与目标运行时，不向最近分支或新版静默回退。CPython 的 .NET 转换规则不能由共用 IronPython 包装代码推断。缺项、歧义、冲突或过期索引均非零退出且整批无部分正文，不重放 Rhino 操作。

索引未命中或需要完整实现/示例时，按[官方来源](documentation.md)用旧 search/read 定向回查；不得以其它版本代填。`read --start-line N --end-line M` 可读原归档指定正文行；HTML 示例用 `--code-blocks` 保留缩进。合并判定及维护流程见[来源与维护说明](documentation.md#目录合并与维护)。
