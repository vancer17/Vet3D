# 业务验证与副作用

## 验证层次

从便宜到昂贵逐层验证，达到用户要求的业务强度后停止：

1. **存在性**：必需字段或文件存在且非空；
2. **完整性**：大小、摘要、数量、索引和关联关系一致；
3. **可解析性**：由目标 JSON/schema、图片、视频、压缩包、模型或项目解析器读取；
4. **业务不变量**：范围、均值、状态、版本、目标对象和上下游对应关系正确；
5. **端到端证据**：必要的回调、消息、上传或消费确实发生。

通用文件原子只负责存在性、大小和 SHA256。GLB、视频、数据库记录等验证器属于可注入 hook；本 skill 不要求项目移动或改写已有验证逻辑。

验收输出建议包含：

```text
validator, status, artifact_path/reference, size, sha256,
parser/schema, assertions, validated_at
```

## 副作用清单

调用前列出服务直接和间接产生的副作用，并为每项选择一种策略：

- `required`：未发生则任务不完成；
- `optional`：未发生记录 warning，但不否定主要结果；
- `disabled`：用户或 RunSpec 明确不执行；
- `reused`：使用已有产物，记录来源、摘要和复用依据。

常见副作用包括对象存储/metrics 上传、回调、队列消息、通知、索引写入、预览生成、计费任务和日志归档。不要把 optional 观测失败冒充算法失败，也不要把 required 副作用静默降级为 optional。

## 成功谓词

协议适配器不应猜测项目业务成功字段。成功谓词由当前服务契约或官方客户端提供，例如：

```python
def is_success(result):
    return result.get("success") is True and result.get("status") == "success"
```

如果不同版本存在兼容字段，兼容逻辑应来自当前项目事实，而不是扩散到通用 skill。

## 完成证据

只有以下条件同时成立才能记录 `VALIDATED`：

- 协议和业务结果明确成功；
- 所有必需输出通过当前验证器；
- required 副作用全部有证据；
- 审计中没有未解析的 open 或 ambiguous 调用；
- 保存路径、摘要和 trace/task ID 可复查。

最终报告单独列出 optional warning、reused 产物、未验证假设和人工决定，不用笼统的“全部成功”覆盖这些差异。
