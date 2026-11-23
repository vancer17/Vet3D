# 对话产物引用

任务目录里的 `pcg.session.v1` 已有架构槽位（`task`/`output`）和 `catalog.artifacts` 定位。本页只补**对话别名**：给用户和后续指令一个稳定的 `@name`，指向上次或更早留下的本地文件。不另建 skill，也不替代画板槽位。

## 调用形式

后续指令把 `@statue-crop` 或 `ref:statue-crop` 当作路径占位；`@last` 固定表示**最近一次标记**的别名，不能当作用户起的名字。未知 `@词` 原样保留，避免误伤邮箱。中文说明写在 `label`，不进入 token。

```bash
"$PYTHON" "$SKILL_DIR/scripts/artifact_refs.py" mark \
  --session "$TASK/session.json" --name statue-crop \
  --path crops/statue.png --label "左侧雕像裁切"

"$PYTHON" "$SKILL_DIR/scripts/artifact_refs.py" list --session "$TASK/session.json"
"$PYTHON" "$SKILL_DIR/scripts/artifact_refs.py" resolve --session "$TASK/session.json" --ref @statue-crop --task-root "$TASK"
"$PYTHON" "$SKILL_DIR/scripts/artifact_refs.py" rewrite --session "$TASK/session.json" \
  --text 'python replace_brief.py --screenshot main @statue-crop'
```

已有槽位可 `--task locate --output crops` 而不再写 `--path`。同名再次 `mark` 覆盖路径。解析结果不是文件仍存在的证明；带 `--task-root` 时核对该路径落在任务根内且 `exists` 为布尔值。compact 或跨轮引用后、断言文件仍可用前必须带 `task-root` 再解析，缺文件按不存在处理，不把聊天里的旧绝对路径当权威。禁止把 URL 或签名地址标成 ref。

函数入口：`mark_ref`、`mark_slot`、`list_refs`、`resolve_ref`、`rewrite_instruction`。字段校验见 session 的 `refs` 数组；缺省旧会话没有该键时按空列表接收。
