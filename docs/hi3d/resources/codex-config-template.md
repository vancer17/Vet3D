# Codex `config.toml` 模板

## 资源名称、来源与模型可见性

`runtime/templates/config.toml` 随 Hi3D Agent 1.2.11（Windows x64）发布，模板内标记配置版本 `9`。Runtime 启动时由 `Ya` 渲染，写入 `CODEX_HOME/config.toml`，供随包 Codex 0.166.0 使用。模型从实际生效的工具集与上下文看到相关结果。这个配置文件没有独立的模型可见 Tool `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/templates/config.toml) · [随包 Codex 版本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json>)

## 输入、结果与副作用

| 模板变量或表项 | 内容与约束 |
| --- | --- |
| `MODEL`、`PROVIDER`、`BASE_URL` | 宿主提供模型名、提供方标识及服务入口。提供方声明 `wire_api = "responses"`。Runtime 对换行、反斜杠、引号等进行 TOML 转义。 |
| `ENV_KEY` | 提供方读取的环境变量名。模板保存变量名，凭据值由宿主单独注入 app-server 环境。 |
| `APPROVAL_POLICY` | Runtime 使用传入策略，环境默认值为 `on-failure`。模板设置 `workspace-write` 并允许该沙箱的网络访问。 |
| `[agents]`、`[features]`、`[skills]`、`[skills.bundled]` | 模板关闭 Codex 子 Agent 与随包 Skill，并关闭 Codex 自行附加 Skill 指令。Runtime 另行供应当前有效 Skill。 |
| `[shell_environment_policy]` | 继承核心环境，排除模型凭据变量和匹配 `*_SECRET*`、`*_TOKEN*`、`*_KEY*` 的 shell 环境变量。 |

常规启动读取现有目标。受管文件内容一致时直接复用，内容变化时在首次遇到相应备份名时保存备份，再写入新内容。受管内容用生成器标记识别，备份后缀随已有文件的配置版本标记决定。已有非空非受管文件在该常规分支保留。写入经同目录独占临时文件、同步、重命名和清理。读取、备份或写入失败会抛出异常。运行时还可通过命令行覆盖设置，例如桌面模型代理使用受校验的本机 Responses 入口。

## 权限、沙箱与前置 Hook

模板提供宿主启动配置基线。同版样本实际出现 `read-only/on-request` 和受限网络，核查单轮应读取该轮 `turn_context`。积分 Hook 由 Runtime 通过 app-server 启动参数启用，之后检查信任状态。模板渲染、命令审批和 Hook 的同意判断各有独立入口。 [本地执行权限与 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 中性示例与核查依据

**节选的渲染示例。** 以下示例只演示变量替换，完整表项见归档原件。

```toml
model = "demo-model"
model_provider = "demo"
approval_policy = "on-failure"
sandbox_mode = "workspace-write"

[model_providers."demo"]
base_url = "https://example.invalid/v1"
env_key = "DEMO_MODEL_TOKEN"
wire_api = "responses"
```

已静态核对 Runtime 的 `Ya` 渲染入口（零基字节偏移 `2471192` 附近）、启动调用（`3112158` 附近）及 app-server Hook 启动参数（`3115289`）。归档模板已通过标准 TOML 解析，保留 `{{MODEL}}` 等占位符。目标宿主的服务兼容性、变量注入、用户配置保留和权限覆盖仍需结合实际运行结果复核。 [安装包 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [发行锁](../upstream/1.2.11/inventory/inventory.lock.json)
