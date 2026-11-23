# 已有 Place 的单次 Open Cloud 发布

唯一公共接口依据：[Place Publishing 指南](https://create.roblox.com/docs/cloud/guides/usage-place-publishing) 与 [Universes API v1](https://create.roblox.com/docs/reference/cloud/universes-api/v1)。先核对当前文档，兼容范围变化时更新本 skill，不在调用方复制客户端。

| 项 | 契约 |
| --- | --- |
| 方法 | `POST https://apis.roblox.com/universes/v1/{universeId}/places/{placeId}/versions?versionType=Published` |
| 输入 | 已存在的 Universe ID 与其所属 Place ID；ID 不互换，也不从本地文件名猜测 |
| 请求体 | 原始 `.rbxlx` XML bytes（`application/xml`）或 `.rbxl` binary bytes（`application/octet-stream`），不是 JSON、ZIP、FBX 或 multipart |
| 鉴权 | `x-api-key`，该目标的 `universe-places` Write；用户在 Creator Dashboard 外部配置最小权限与适当有效期/IP 限制 |
| 成功证据 | HTTP 成功且 JSON 含正整数 `versionNumber`；再从 Studio/Dashboard 核对本次版本 |
| 不提供 | 创建 Roblox 账号/新体验、年龄验证、内容问卷、设置 Audience、证明公网可加入 |
| 限制 | 官方指南列出的 EditableImage、EditableMesh、PartOperation、SurfaceAppearance、BaseWrap 及相关子类更新需用 Studio；静态检查可识别 XML 中已知类，二进制文件必须人工核查 |

首次发布通常直接用 Studio，无需先创建 API Key。已有 CI 环境、目标 IDs 和凭据时再使用本接口。资产导入/审核/所有者权限不由 Place 上传替代；API Key 权限不等于体验内脚本 API 权限。

## 运行

先执行入口中的 dry-run，对照 Universe、Place、文件字节与现有授权。当前脚本设置 100 MiB 的保守本地文件上限，不将这个值宣传为各类资产的统一平台硬限制。XML 检查不承诺发现 Lua 动态资源引用。

通过实际 Studio 验收且确认目标后，已授权调用进程在内存消费 `ROBLOX_API_KEY`。AI 不读取环境、凭据文件、Cookie 或浏览器存储；不要把值写到命令行、仓库、报告或聊天。宿主不允许账号鉴权脚本时不执行此分支，使用 Studio UI。

```sh
python3 "$SKILL_DIR/scripts/hi3d-roblox-api.py" publish-place \
  --place "$RUN_DIR/hi3d-game.rbxlx" --universe-id "$UNIVERSE_ID" --place-id "$PLACE_ID" \
  --job "$RUN_DIR/hi3d-publish.json" --execute --authorized --studio-reviewed
```

`--authorized` 记录已存在的授权，不创造授权；`--studio-reviewed` 仅在真实 Studio 复核后使用，不用来跳过未做的测试。父目录必须存在且使用解析后的绝对路径；不覆盖任何已有记录。纯函数和注入 transport 可用于其他工具集成，详见代码契约。

## 结果与恢复

- `uploaded`：记录版本号。重复同 job 只读返回，不发第二个 POST。公开可见性保持未知，不假设由 Published query 参数控制。
- `rejected`：明确 4xx（除 408），不自动重试。核对权限、归属和当前限制；用户要求修复后再发布时使用新的有说明的发布尝试，保留旧记录。
- `submitting` / `submission_uncertain`：进程中断、超时、5xx、重定向或无法验证的成功响应可能已经创建版本。先在 Studio/Dashboard 找回版本；不能仅换 job 自动重传。没有查询凭据时记录待核对。确实无法查回时，只有用户接受重复版本风险后才能创建新尝试。
- 本地回执写入失败：原 submitting 意图保留，远端结果未知，按上一项恢复。

一个 job 同时只允许一个执行者；同目录独占创建防止双提交，但不同 job 不提供跨进程/跨目录的全局幂等锁。错误正文和鉴权头永不输出；先用非敏感 HTTP 状态与 Studio 的错误界面排查。已有线上版本、Private/Public 状态和运行中的旧服务器可能不同；更新和重启服务器要各自确认实际范围。
