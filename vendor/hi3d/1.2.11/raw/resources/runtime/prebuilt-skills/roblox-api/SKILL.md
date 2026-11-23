---
name: roblox-api
description: 查询并适配 Roblox Engine 与 Open Cloud 接口，检查已有 Place 的静态结构、接入服务器权威交互和聊天诊断，或向已明确的 Place 单次上传版本；不设计游戏、不创建账号或代替公开发布验收。
---

# Roblox 接口适配

单一目标：把明确的 Roblox 接口操作落实为可核对的调用或工程改动。通过 `$roblox-api` 或显式读取本入口独立使用，不要求先运行游戏制作 workflow。

输入：所需操作、已有 `.rbxlx/.rbxl` 或 Luau 工程、运行侧（编辑期/服务端/客户端）、包外 `RUN_DIR`。云端更新另需已核对的 Universe ID、Place ID、发布授权及已通过 Studio 验收的版本；凭据只能在调用环境外部配置，不在聊天中索取。

输出：API 选型与运行侧说明、所需 Luau 改动、静态检查 JSON，或单次上传回执。`uploaded` 只证明返回了版本号，不能证明 Audience 为 Public、玩家可加入或多人功能通过。

## 选择正确接口

先读 [接口地图](references/hi3d-api-map.md)，按需读 [工程与远程边界](references/hi3d-engine.md)、[聊天诊断](references/hi3d-chat.md) 或 [Open Cloud](references/hi3d-open-cloud.md)。[官方文档索引](references/hi3d-sources.md) 提供在线入口和带许可的完整相关文档快照。引擎 API 运行在 Roblox；Open Cloud 是外部 HTTPS API；本地 XML 生成/解析不是调用 Studio API。

已有资源优先复用；不把本地 FBX 路径写进 MeshId，不把浏览器游戏 JS 直接粘贴进 Luau。新模型上传和资产权限由 Studio 导入流程处理；不能冒用另一账号的 asset ID。

## 本机 Roblox Studio

要在 Studio 里运行、导入、试玩，或指引用户操作 Studio 时，先在这台电脑上查找**已经安装、可以启动的 Roblox Studio**。同一任务里已经找到、且该程序文件仍在，就不要再问。只离线解析 `.rbxlx`、不打开 Studio 时，不必做这次询问。

算已安装，必须看到应用程序本体里的可执行文件：

- macOS：`/Applications/RobloxStudio.app`、`/Applications/Roblox Studio.app`，或用户应用程序目录里的同名程序包，且 `Contents/MacOS/` 内有可执行文件。`mdfind 'kMDItemDisplayName == "Roblox Studio" && kMDItemKind == Application'` 只作辅助，结果仍须是这种程序包。
- Windows：`%LOCALAPPDATA%\Roblox\Versions\<版本目录>\RobloxStudioBeta.exe`。开始菜单快捷方式只有指向这个程序时才算。
- 其他系统：同样以找到可启动的 Studio 程序为准。

`.dmg`、`.pkg`、`.msi`、`RobloxStudioInstaller.exe`、下载目录里的安装包、浏览器页面和未下完的文件都不算。先搜索，再决定要不要问用户。

没找到时，用宿主 `user_interaction` 打开输入面板，`kind=input`。不要设置 `timeoutSeconds`、`defaultAnswer` 或选项按钮。只在聊天里提问不算完成。

- title：`安装 Roblox Studio`
- message：`这台电脑上还没有可启动的 Roblox Studio。安装包、dmg 或下载文件不算已经安装。请到 https://create.roblox.com/docs/studio 安装官方 Studio，直到能从应用程序里打开它。装好后在下面回复，例如：安装完成，请继续`
- question：`装好后请回复，例如「安装完成，请继续」`（id：`studio_ready`）

「安装完成，请继续」「继续」「好的」「下好了」都算用户要求再查一次，不按句子对错卡人。是否放行只看重新检索：找到可启动的程序才继续；仍然只有安装包或什么都没有时，用同一面板再问，并说明还没找到程序。取消或拒绝后，停掉依赖 Studio 的步骤；离线静态检查可以继续。搜到后记下实际路径，本任务不再问。

## 独立调用

Python 3.10+ 标准库；只检查 `.rbxlx` 不需要 Studio、网络或登录。实际运行 Luau 需要 Roblox Studio/客户端；Luau CLI 只能做语法和受限模拟。

```sh
python3 "$SKILL_DIR/scripts/hi3d-roblox-api.py" inspect-place \
  --place "$RUN_DIR/hi3d-game.rbxlx" --output "$RUN_DIR/hi3d-place-check.json"

# 默认 dry-run：不读取凭据、不联网、不创建发布账本。
python3 "$SKILL_DIR/scripts/hi3d-roblox-api.py" publish-place \
  --place "$RUN_DIR/hi3d-game.rbxlx" --universe-id "$UNIVERSE_ID" --place-id "$PLACE_ID"
```

正式云端调用只按 Open Cloud 页执行。SDK/插件操作不得用普通 Script 绕过安全级别。包内 [远程请求保护模块](templates/hi3d-remote-guard.luau) 只提供有限数值、方向和速率检查；所属权、距离、视线、装备/资源、生命周期等业务校验仍由当前项目实现。

## 完成与恢复

按 [检查点](pcg/routes.yaml) 与 [阶段产物](pcg/architecture.yaml) 执行：先确认运行侧和契约，后调用，再核对结果。已有有效结果可直接复核。写云端前沿用已有授权，不重复确认；目标缺失或覆盖范围不明才收集必要输入。

`submitting` 或 `submission_uncertain` 时保留原账本，通过 Dashboard/Studio 核对版本；不换 job 自动重发。没有适用的自动化连接时转给账号持有人执行官方 UI，说明实际缺口，不声称远程操作完成。

脚本与函数边界见 [代码契约](references/hi3d-code-contract.md)。用 `python3 "$SKILL_DIR/tests/hi3d-test-api.py"` 离线验证，不消费真实凭据或上传真实游戏。模板须在项目中安装到正确运行侧并编译/试玩，文件存在不是功能验收。

<!-- managed-by: sparc3d-runtime -->
