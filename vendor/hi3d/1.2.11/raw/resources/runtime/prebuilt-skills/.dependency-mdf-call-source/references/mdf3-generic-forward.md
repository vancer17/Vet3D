# MDF3 Generic Forward 适配器

只在当前仓库的官方调用方或服务入口确认协议为 MDF3 `generic-forward` 时使用 `scripts/mdf3_generic_forward.py`。

适配器处理：

- MDF3 `dumps` / `loads`；
- base64 `pickle_payload` envelope；
- trace header；
- BinaryFile 的脱敏摘要；
- HTTP、业务失败、契约错误与歧义结果分类；
- 提交前和终态 JSONL 审计；
- 严格单次调用，禁用重定向、不做自动重试。

适配器按显式 `endpoint` → `MDF_ENDPOINT` → `http://172.31.192.135:7789/generate_model` 解析地址；只读取这一非敏感地址变量，不读取凭据。部署确认、覆盖方式和逐服务检查见 [部署与诊断](deployment-and-probes.md)。调用方仍须注入符合目标服务契约的成功谓词：

```python
# 运行调用脚本时，将本 skill 的 scripts 目录加入模块搜索路径。
from mdf3_generic_forward import MDF3GenericForwardCaller
from online_service_atoms import AuditWriter

audit = AuditWriter("/protected/run/invocation_audit.jsonl")
caller = MDF3GenericForwardCaller(
    # 可省略 endpoint 使用环境变量或随包内网地址。
    # endpoint="https://your-internal-gateway/generate_model",
    endpoint_alias="test-generic-forward",
    environment="test",
    audit=audit,
    success_predicate=project_is_success,
)
result = caller.call_once(
    service="target-service",
    input_data=request_data,
    trace_id=trace_id,
    timeout_sec=3600,
    run_id=run_id,
    case_id=case_id,
)
```

Python 适配器的 `success_predicate` 是业务契约，示例中的 `project_is_success` 必须由当前调用方定义；业务成功后仍需验收产物。

需要幂等 header 时，只有在服务契约声明其名称和语义后才配置 `idempotency_header`。提供幂等值但没有可确认的传递方式会直接报契约错误。

默认延迟加载随包通信子集和标准库 HTTP；文件型调用无需第三方包，数组需 NumPy。来源和兼容边界见 [通信运行时](wire-runtime.md)。仍可显式注入 HTTP、编解码函数和传输异常，不访问线上服务地完成测试。

仅解码当前已确认可信 MDF 服务的响应，序列化实现可能具备代码执行能力。不要把任意 URL 或第三方 pickle 当作本适配器的输入。非预期 2xx、3xx 以及缺少明确 success 布尔值的响应按 AMBIGUOUS 保留；HTTP 200 后还要通过 envelope 与注入的业务成功谓词；产物、required 副作用由后续验证器处理，返回结果不自动成为 VALIDATED。

适配器没有内置异步查询循环或跨进程去重锁；调用方负责按原 ID 恢复并避免重复执行。4xx 仅在当前部署能保证未受理时按拒绝处理，其他协议需使用项目适配器。默认审计只保存字段名和脱敏摘要指纹，hook 必须选择允许公开的字段。
