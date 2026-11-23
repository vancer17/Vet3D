# 契约解析与 RunSpec

## 事实来源

按以下顺序寻找当前契约，找到足够事实后停止：

1. 仓库内官方客户端、SDK、调用方或集成测试；
2. OpenAPI、protobuf、IDL、schema 或服务入口；
3. 当前环境的部署清单、服务发现或受保护配置；
4. 运维文档和最近的已知成功调用。

只读取调用所需配置，不打印整份配置或环境。外部仓库只有私有方法时，可以在任务侧写薄适配层；不要把“方便本次调用”变成重构外部库的理由。

## 硬性事实与可标记未知项

写操作前必须确认：

- 目标环境、租户或命名空间；
- endpoint、协议、路由或方法；
- 必需输入、序列化方式和认证机制；
- 同步或异步语义，以及合理超时；
- trace/request/task ID 的生成和传递规则；
- 幂等保证或明确的零自动重试策略；
- 成功、失败和终态判定；
- 必需输出和最低验收条件。

大小上限、可选字段默认值、状态查询接口等如果没有权威声明，可以记为 `unknown`，再采用保守输入校验或零重试策略。不存在的信息不是继续搜索到无限期的理由；但相互冲突的硬性事实必须阻止写操作。

## RunSpec

一次运行只维护一个事实源。建议从 `assets/run_spec.template.json` 创建 RunSpec，至少包含：

- `run_id`、`case_id`、`environment`；
- `endpoint_alias`、`protocol`、`operation`；
- `trace_id`，以及契约支持时的 `idempotency_key`；
- `timeout_sec` 和自动重试策略；
- `input_digest`、契约摘要与可复查但脱敏的输入摘要；
- 显式成功谓词名称；
- 验证器列表；
- required/optional/disabled/reused 副作用；
- runtime provenance 文件引用。

`input_digest`、契约摘要和参数摘要使用完整确定性序列化数据的 `sha256_bytes` 或文件的 `sha256_file`；`stable_digest` 只反映截断脱敏摘要，不能用作精确缓存键。

RunSpec 不保存 token、Cookie、AK/SK、签名 URL、私钥或原始敏感请求体。实际 endpoint 如果敏感，只写入权限受控的本地运行目录；普通审计与用户报告记录 `endpoint_alias`。

## 运行时来源预检

容器镜像、挂载源码和登录 shell 可能加载不同代码。提交前至少记录：

- Python 或实际运行时版本及可执行文件；
- 入口模块的 `__file__`、文件摘要和可用版本字段；
- 有关仓库的 commit 与 dirty 状态；
- 当前目录和必要的模块搜索路径；
- 镜像或部署版本标识（如果当前环境提供）。

可使用：

```bash
"$PYTHON" "$SKILL_DIR/scripts/inspect_runtime.py" \
  --module package.service_entry \
  --repo /path/to/repository \
  --output /protected/run/runtime_provenance.json
```

脚本自身不发送网络请求，但 `--module` 会实际 import 并执行模块初始化；仅选择已确认无线上副作用的入口模块，未知模块先静态检查。
