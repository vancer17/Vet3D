---
name: pub-roblox-game
description: 将已有可玩 Roblox Place 发布到核对过的体验，处理首次 Studio 上传、公开受众与真实多人验收，记录实际账号手续和发布状态；已配置的既有 Place 可选 Open Cloud 更新，不负责游戏设计或账号代注册。
---

# 发布已有 Roblox 游戏

通过 `$pub-roblox-game` 或显式读取本入口独立调用。输入：最终 `.rbxlx/.rbxl` 或已打开的 Studio Place、实际测试结果、目标所有者及新建/更新范围、用户已有发布授权。输出：真实版本/体验链接、公开状态、多人验收结果及手续记录。没有账号连接时先交付全部可完成的检查，清楚指引账号持有人完成最后操作，不能声称代为发布。

`SKILL_DIR` 是完整分发目录，`RUN_DIR` 为包外本次输出。Python 不是 UI 发布的必要依赖；官方 Roblox Studio 和 Creator Dashboard、具有目标权限的账号是必要外部条件。安装契约见 [package.json](package.json) 与 [打包说明](../.dependency-package-tools/references/usage.md)。

## 最短路径与依赖

首次发布默认走 **Studio：File → Publish to Roblox → Create；Dashboard：Configure → Settings → Audience → Public → Save Changes；两账号进入同一服务器验收**。具体前提、菜单位置与更新分支见 [操作路线](references/hi3d-publishing.md)。上传后的默认 Private 和公开发布是两件事；`versionType=Published` 也不切换 Audience。

需要静态检查、聊天诊断或已配置的 Open Cloud 更新时调用独立 [roblox-api](../roblox-api/SKILL.md)，交接最终 Place、目标 IDs、授权和 Studio 验收结果，接收静态报告或版本回执；UI 首次发布不要求配置 API Key。本包不复制 API 客户端，必要依赖按分支显式提供。

## 本机 Roblox Studio

打开 Studio 或指引用户点击 Studio 菜单之前，先在这台电脑上查找**已经安装、可以启动的 Roblox Studio**。同一任务里已经找到、且该程序文件仍在，就不要再问。本次明确只做不打开 Studio 的 Open Cloud 更新时，可以不做这次询问。

算已安装，必须看到应用程序本体里的可执行文件：

- macOS：`/Applications/RobloxStudio.app`、`/Applications/Roblox Studio.app`，或用户应用程序目录里的同名程序包，且 `Contents/MacOS/` 内有可执行文件。`mdfind 'kMDItemDisplayName == "Roblox Studio" && kMDItemKind == Application'` 只作辅助，结果仍须是这种程序包。
- Windows：`%LOCALAPPDATA%\Roblox\Versions\<版本目录>\RobloxStudioBeta.exe`。开始菜单快捷方式只有指向这个程序时才算。
- 其他系统：同样以找到可启动的 Studio 程序为准。

`.dmg`、`.pkg`、`.msi`、`RobloxStudioInstaller.exe`、下载目录里的安装包、浏览器页面和未下完的文件都不算。先搜索，再决定要不要问用户。

没找到时，用宿主 `user_interaction` 打开输入面板，`kind=input`。不要设置 `timeoutSeconds`、`defaultAnswer` 或选项按钮。只在聊天里提问不算完成。

- title：`安装 Roblox Studio`
- message：`这台电脑上还没有可启动的 Roblox Studio。安装包、dmg 或下载文件不算已经安装。请到 https://create.roblox.com/docs/studio 安装官方 Studio，直到能从应用程序里打开它。装好后在下面回复，例如：安装完成，请继续`
- question：`装好后请回复，例如「安装完成，请继续」`（id：`studio_ready`）

「安装完成，请继续」「继续」「好的」「下好了」都算用户要求再查一次，不按句子对错卡人。是否放行只看重新检索：找到可启动的程序才继续；仍然只有安装包或什么都没有时，用同一面板再问，并说明还没找到程序。取消或拒绝后，停掉依赖 Studio 的步骤；不依赖 Studio 的核对可以继续。搜到后记下实际路径，本任务不再问。

## 执行

1. **核对目标**：若本路线要打开 Studio，先完成上面的本机检查。读取最新实际文件/Studio 项目和现有授权；确认创建新体验还是更新哪个既有 Place、个人或群组归属。能从当前选中体验可靠读取的事实不再询问；未知 IDs、群组归属和覆盖对象绝不猜测。更新前保留源文件及可恢复的旧版本记录。
2. **检查准备**：确保停止试玩，Studio 单人和多客户端验收通过，资产权限可用；核对账号发布资格和内容问卷。依据真实功能填问卷，不能为通过审核隐瞒内容。不要求默认注册新账号、开 API、购买会员或支付费用。
3. **上传版本**：已授权则直接按操作路线发布；复用已有上传回执时跳过。写下 Place/Universe 的实际 IDs、版本、所有者和操作者。未执行则保持 `prepared`；发生超时或未知上传时保留记录，先核对平台版本，不自动重发。
4. **设置可访问范围**：要求公网游玩且已获授权时，将该体验受众设为 Public 并保存；保留现有年龄/设备限制与平台审核的真实状态。用户只要私测时不得擅自公开。资格缺失时如实记 blocked，完成其他独立工作。
5. **验收与交付**：打开真实游戏页，使用 Roblox 客户端验收，按 [发布验收](references/hi3d-acceptance.md) 记录两账号同服加入、复制、重生/重连及聊天条件。给出真实链接与剩余缺口，不把 Studio 的模拟用户当作公网测试。

阶段见 [routes](pcg/routes.yaml) 和 [architecture](pcg/architecture.yaml)。按 [手续模板](templates/hi3d-publication-record.json) 在 `RUN_DIR/hi3d-publication-record.json` 填写实际动作；另交付 `hi3d-publish-review.md`，列出证据与未验证项。模板中的空值和 not_performed 不代表已批准。状态严格为 `prepared` / `uploaded` / `public` / `public-multiplayer-verified`，阻塞和未知记录在对应字段，不通过推进状态掩盖它们。

## 账号手续与授权

发布授权在同一明确目标内持续有效，不逐步重复问。仅缺少目标、发布授权、身份操作或新增费用时收集所需决定；可用宿主输入面板时使用面板，凭据/验证码/证件一律交给用户在官方界面操作。记录谁做了什么：登录不等于注册，发布体验不等于注册公司，生成代码不等于平台提交。

该 skill 不自动注册账号、签署协议、完成身份验证、购买资格或改动广告/付费设置；若平台要求额外手续，展示具体阻塞和官方入口，并等待账号持有人完成。沿用已有满足条件的账号。不保存敏感身份信息、聊天正文、Cookie 或密钥。当前平台政策可能变化，以 Dashboard 实际提示和 [官方发布文档](https://create.roblox.com/docs/production/publishing/publish-games-and-places) 为准。

<!-- managed-by: sparc3d-runtime -->
