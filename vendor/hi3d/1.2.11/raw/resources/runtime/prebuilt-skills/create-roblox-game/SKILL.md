---
name: create-roblox-game
description: 从需求或已有工程制作可编辑 Roblox 游戏，组织资产、Luau 服务器与客户端、多人测试和性能预算，并按已授权范围发布到 Roblox；已有工程可直接进入检查或发布，不预设类型、关卡或美术风格。
---

# Roblox 游戏制作与发布

通过 `$create-roblox-game` 或显式读取本入口调用。目标是交付能在 Roblox 中继续编辑、验证和运行的工程；需要公网多人时一直推进到发布与真实客户端验收，不能只交概念图、模型或教程。账号资格/操作连接缺失时先完成所有独立工作，准确交付工程与下一步，不把阻塞写成已上线。

## 输入、默认与边界

输入为用户的核心交互目标、已有工程/素材、明确保留项和交付范围。只有影响核心玩法、归属或不可逆操作的缺项需要询问；技术起始值采用 [默认与询问边界](references/hi3d-defaults.md)。不写入任何固定游戏类型、地图布局、审美、物品或战斗参数。

复用会话已给出的答案和授权。实际用户输入面板可用时，用它收集必要输入；没有时用简短明确问题。只有偏好可使用推荐值，超时采用推荐值不是用户授权。上传文件通过附件接收；登录、证件、密码、验证码和密钥只能在官方界面处理。

本包为执行者工作流，**不自动生成任意游戏**；执行者据本次需求编写场景和 Luau。Python/Luau CLI 用于离线检查，Roblox Studio 用于真实运行。首先明确现有自动化能否操作 Studio/账号，不能在最后才披露发布能力缺失。

## 独立依赖与交接

`SKILL_DIR` 指本工作流完整分发目录，`RUN_DIR` 指包外任务输出目录。依赖按 [package.json](package.json) 与 [打包说明](../.dependency-package-tools/references/usage.md) 显式物化，不隐式导入邻目录。

- 由 [roblox-api](../roblox-api/SKILL.md) 接收目标接口、当前 Place/Luau 与运行侧，返回 API 适配、静态检查及必要诊断；本工作流不复制客户端或完整接口文档。
- 用户要求上线时调用 [pub-roblox-game](../pub-roblox-game/SKILL.md)，交接最终 Place、已完成验收、所有者/目标及已有授权，接收发布版本、公开链接与公网验收状态。只要工程时跳过发布。
- 已有真实帧时间且可用 Node 22+ 时调用 [game-profile](../game-profile/SKILL.md)，传入毫秒样本与当前设备预算，取回 p50/p95/p99；未采样不调用、不伪造 FPS。
- 需要外部建模时调用当前任务提供的 [blender-tools](../.dependency-blender-tools/REFERENCE.md) 或已有资产生产入口，交接明确单位的源资产和导出文件；按用户指定路线执行。已具备资产的任务跳过，不为生成阶段补文件或重新付费。
- 阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者记录真实起止、状态和耗时；本包没有自动采集整个 Studio/UI 过程的脚本。

## 本机 Roblox Studio

依赖 Studio 的阶段开始前，先在这台电脑上查找**已经安装、可以启动的 Roblox Studio**。同一任务里已经找到、且该程序文件仍在，就不要再问。纯文字整理范围可以先做，但不能打开 Studio，也不能把未安装说成已经可用。

算已安装，必须看到应用程序本体里的可执行文件：

- macOS：`/Applications/RobloxStudio.app`、`/Applications/Roblox Studio.app`，或用户应用程序目录里的同名程序包，且 `Contents/MacOS/` 内有可执行文件。`mdfind 'kMDItemDisplayName == "Roblox Studio" && kMDItemKind == Application'` 只作辅助，结果仍须是这种程序包。
- Windows：`%LOCALAPPDATA%\Roblox\Versions\<版本目录>\RobloxStudioBeta.exe`。开始菜单快捷方式只有指向这个程序时才算。
- 其他系统：同样以找到可启动的 Studio 程序为准。

`.dmg`、`.pkg`、`.msi`、`RobloxStudioInstaller.exe`、下载目录里的安装包、浏览器页面和未下完的文件都不算。先搜索，再决定要不要问用户。

没找到时，用宿主 `user_interaction` 打开输入面板，`kind=input`。不要设置 `timeoutSeconds`、`defaultAnswer` 或选项按钮。只在聊天里提问不算完成。

- title：`安装 Roblox Studio`
- message：`这台电脑上还没有可启动的 Roblox Studio。安装包、dmg 或下载文件不算已经安装。请到 https://create.roblox.com/docs/studio 安装官方 Studio，直到能从应用程序里打开它。装好后在下面回复，例如：安装完成，请继续`
- question：`装好后请回复，例如「安装完成，请继续」`（id：`studio_ready`）

「安装完成，请继续」「继续」「好的」「下好了」都算用户要求再查一次，不按句子对错卡人。是否放行只看重新检索：找到可启动的程序才继续；仍然只有安装包或什么都没有时，用同一面板再问，并说明还没找到程序。取消或拒绝后，停掉依赖 Studio 的步骤。搜到后记下实际路径，本任务不再问。

## 执行阶段

1. **范围与能力预检**：先完成上面的本机 Studio 检查，再打开最新工程，核对现有版本和自动化能力；记录目标交互、平台、设备、资产来源、发布范围及测试证据。局部改动只更新差异，不重问整套偏好。
2. **工程与资产**：读取 [制作路线](references/hi3d-production.md)，先建立可进入、可操作、有反馈和恢复的最小闭环，再接真实资产。源资产、运行资产、碰撞与实例布局分开保存；模型成功生成不等于游戏已完成。
3. **规则与复制**：经 roblox-api 的运行侧契约接入服务端判定、客户端输入/UI、RemoteEvent 和生命周期；核心规则可单测，平台副作用显式适配。只实现用户需要的系统，不默认增加战斗、背包、经济或跨服服务。
4. **分层验收**：按 [验收矩阵](references/hi3d-validation.md) 依次进行静态/语法、纯规则/模拟、Studio 单客户端、Studio 多客户端、目标设备测试。几何更新重新检查依赖的碰撞、交互范围和路线；未改脚本复用有效的旧检查结果。
5. **发布与公网验证**：仅在发布已获授权时交接 pub-roblox-game；已有可玩 Place 可直接从本阶段开始。首次 Studio 发布是推荐最短路径，Open Cloud 仅适合已配置目标与自动化权限的更新。
6. **交付与缺口**：交付最新 Place、Luau、资产源文件与对应关系、版本说明、实际验收结果及阶段耗时；发布完成时给真实游戏链接和版本。以“已准备/已上传/已公开/公网多人已验证”分别报告，不混称完成。

执行结构与跳过关系见 [architecture](pcg/architecture.yaml)、[routes](pcg/routes.yaml)。每阶段记录至 `RUN_DIR/hi3d-stages.jsonl`，验收写 `hi3d-validation.md`，交付清单写 `hi3d-delivery.md`。实际输出路径绑定本任务，不把旧聊天路径当作当前文件存在证据。

历史问题抽象为 [问题—原因—恢复路线](references/hi3d-lessons.md)。每次失败先分类，修复受影响部分并验证；不为小修改重做模型或全部测试，不为服务失败拿占位资产冒充完成。

<!-- managed-by: sparc3d-runtime -->
