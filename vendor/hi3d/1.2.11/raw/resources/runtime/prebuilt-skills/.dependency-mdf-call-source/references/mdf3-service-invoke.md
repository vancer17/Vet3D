# MDF3 ServiceInvoke 适配器

CLI 通过 `--transport sdk` 显式选择本适配器；默认入口是 [HTTP 中控](mdf3-generic-forward.md)。worker 必须能连接调用端的临时 TCP 地址；单向访问队列不证明回连成立。

使用官方 `mdf3.service_invoke_tool.ServiceInvokeSession` 调已在线子服务。适配器处理：

- 配置路径与队列地址校验（非 test 环境必须提供配置）；
- 单次 `session.invoke(service_name, input_data)`；
- BinaryFile 的脱敏摘要；
- 传输失败、业务失败与契约错误分类；
- 提交前和终态 JSONL 审计；
- 严格单次调用，不做自动重试。

配置按显式 `config_path` → `MDF3_CONFIG_PATH` → 随包 test 配置解析。部署确认、覆盖方式和逐服务检查见 [部署与诊断](deployment-and-probes.md)。调用方仍须注入符合目标服务契约的成功谓词：

```python
# 运行调用脚本时，将本 skill 的 scripts 目录加入模块搜索路径。
from mdf3_service_invoke import MDF3ServiceInvokeCaller
from online_service_atoms import AuditWriter

audit = AuditWriter("/protected/run/invocation_audit.jsonl")
caller = MDF3ServiceInvokeCaller(
    # 可省略 config_path，使用环境变量或随包 test 配置。
    # config_path="/path/to/config.test.yaml",
    endpoint_alias="mdf3-service-invoke",
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

Python 适配器的 `success_predicate` 是业务契约，示例中的 `project_is_success` 必须由当前调用方定义；业务成功后仍需验收产物。离线测试注入 `session_factory`，不访问队列。默认工厂在 SDK 启动部分失败时也会停止会话，清理本地 TCP 资源。

超时、断连和 SDK 抛出的 `ServiceCallTimeout` / `ServiceCallFailed` 按 `AMBIGUOUS` 保留；返回非 dict 或成功谓词异常为契约错误；谓词非 True 为业务失败。产物、required 副作用由后续验证器处理，返回结果不自动成为 VALIDATED。

适配器没有内置异步查询循环或跨进程去重锁；调用方负责按原 ID 恢复并避免重复执行。默认审计只保存字段名和脱敏摘要指纹，hook 必须选择允许公开的字段。
