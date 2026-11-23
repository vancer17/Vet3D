# 执行、审计与恢复

## 结果分类

| 分类 | 含义 | 默认动作 |
|---|---|---|
| `REJECTED` | 有证据表明请求未被接受，例如当前契约确认的 4xx | 修正输入或权限后再决定是否新调用 |
| `FAILED` | 服务明确执行并返回业务失败 | 不自动重试，先定位确定性原因 |
| `AMBIGUOUS` | 超时、断连、重定向、模糊 5xx、成功响应无法解析等 | 使用原标识查状态、日志和产物 |
| `INVALID_OUTPUT` | 服务声称成功，但输出缺失或验收失败 | 不自动重试，保留证据并排障 |
| `VALIDATED` | 服务成功且输出及 required 副作用通过验收 | 可作为完成或后续 checkpoint |

限流只有在契约能证明请求未被接受时才属于可重试的拒绝。遵守 `Retry-After`，使用有限退避和相同幂等键。认证、权限、参数和确定性业务失败不自动重试。

## 标准审计事件

每行一个 JSON 对象，公共字段为：

```text
schema_version, time_utc, event, run_id, case_id,
trace_id, call_id, service/operation, environment, endpoint_alias
```

调用事件：

- `request_sent`：提交前写入，包含 timeout、retries=0、幂等键和脱敏输入摘要；
- `request_accepted`：仅用于异步接受，不是终态；
- `task_status`：状态变化时写入；
- `request_finished`：确定成功、失败或拒绝；
- `request_ambiguous`：不能确认是否执行；
- `artifact_validated`：记录解析器、大小、摘要和业务断言；
- `case_completed` / `case_failed`：case 的最终证据状态。

`CallIdFactory` 仅保证单个实例中的编号唯一；同一审计文件合并多个 caller 或多个进程时，必须传入全局唯一的 `call_id`，或使用独立 case/trace 与审计文件。

同一 `call_id` 必须恰好有一个 `request_sent`。完整调用必须恰好有一个终态事件：`request_finished` 或 `request_ambiguous`。审计摘要不得保存凭据或完整大二进制，只保存类型、字段名、文件名、大小和 SHA256。

独立核对：

```bash
"$PYTHON" "$SKILL_DIR/scripts/verify_audit.py" /path/to/invocation_audit.jsonl --trace-id TRACE_ID
```

`--allow-incomplete` 只允许仍在监控的请求保持 open；它不会把失败或歧义状态改成成功。

## 批任务与 checkpoint

从 `assets/batch_manifest.template.json` 创建批清单。每个 case 使用独立 `case_id`、trace ID、审计文件和输出目录，避免日志或旧失败污染当前运行。

复用某阶段前必须同时满足：

1. 输入摘要一致；
2. 操作、契约或服务版本指纹一致；
3. 参数摘要一致；
4. 输出文件存在且摘要一致；
5. 当前验证器重新验收成功。

产物记录必须同时包含正整数字节数和 64 位十六进制 SHA-256，缺失时拒绝复用。输入/契约/参数指纹由调用方对完整数据计算，不使用截断审计摘要。只看到文件存在不能跳过。写文件时先写同目录临时文件、flush/fsync，再原子替换。歧义调用不能靠 checkpoint 自动重发；应先查询服务端状态或由用户决定。

checkpoint 建议采用以下最小结构，并用 `evaluate_checkpoint(...)` 重新校验：

```json
{
  "status": "validated",
  "input_digest": "sha256:...",
  "contract_digest": "sha256:...",
  "parameter_digest": "sha256:...",
  "artifact": {
    "path": "/local/result.bin",
    "size": 123,
    "sha256": "..."
  }
}
```

批量并发必须服从服务容量、费用和用户授权。昂贵或未知容量的服务默认串行；并发是显式优化，不是通用默认值。

## 排障边界

确认环境和标识后，找到最后一个明确成功的边界：网关、服务入口、队列、worker、下游依赖、回调或产物。检查该边界之后的第一个消费者，不要反复验证已经成功的生产者。观测缺失标为“未验证”，并给出下一项最小验证动作。
