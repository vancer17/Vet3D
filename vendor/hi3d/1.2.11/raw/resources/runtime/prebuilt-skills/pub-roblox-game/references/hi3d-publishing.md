# 最少步骤、真实状态

## 首次发布（推荐）

1. 用 Roblox Studio 打开最终 Place，确认已登录正确账号、测试停止、当前工程版本正确。macOS 的 **File 在屏幕最上方的系统菜单栏**，未必在窗口工具条；先让 Studio 成为前台应用。Windows 通常在应用菜单。不要指引用户在 Hi3D 的模型视窗找 Roblox 发布按钮。
2. 选择 **File → Publish to Roblox**。首次弹窗填写 Name、Description、Creator 和 Devices，核对所有者后选 **Create**。名称/说明可按已确认项目生成草稿；Creator 不能猜，Devices 只声明已经验证的设备。没有默认要求付费或先创建 API Key。若按钮灰色，先 Stop 测试、确认登录/权限、打开的是 Place 而非只选中了一个模型；保存本地副本并按实际错误排查，不盲点多次发布。
3. 上传成功记录体验/Place，打开 [Creator Dashboard](https://create.roblox.com/dashboard/creations)。选择刚上传的体验，在 **Configure → Settings → Audience** 将范围设为 **Public** 并 **Save Changes**。界面名称变化时按“该体验的受众/可访问性”定位；以当前界面为准。首次上传通常为 Private，上传成功本身不允许陌生人游玩。
4. Dashboard 若提示资格、年龄验证或内容成熟度与合规问卷，由账号持有人如实完成，再保存公开设置。政策和面向不同年龄受众的条件会变化；不把历史日期、费用或某个账号条件写成永久要求。官方 [发布指南](https://create.roblox.com/docs/production/publishing/publish-games-and-places) 和 [内容成熟度](https://create.roblox.com/docs/production/promotion/content-maturity) 是核对源。不得凭空默认付费，或扩大用户已授权的操作范围。
5. 从 Dashboard 的实际体验页面复制游戏链接，用客户端进入；请第二个符合体验/聊天访问条件的账号加入同一服务器。完成真实测试后才标记公网多人已验证。Public 不承诺平台搜索推荐、流量或全龄访问。

## 更新既有游戏

确认当前 Studio 已绑定正确 Place 时，用 **File → Publish to Roblox** 更新它。需要把本地文件放进一个已存在的目标时，用 **Publish to Roblox As…** 明确选中体验及 Place；这是可能覆盖既有内容的操作，必须属于已授权目标。保留本地原文件与可恢复版本信息，不为避免询问而新建一堆重复体验。

玩家页面 URL 通常为 `https://www.roblox.com/games/<startPlaceId>`，其中是起始 Place ID，不是 Universe ID；优先复制平台提供的真实链接。一个体验可含多个 Place，子 Place 发布不自动改变起始场景。现有服务器可能仍运行旧版本；用新服务器验证发布版本。强制重启/关闭运行服务器有额外用户影响，只在已授权范围执行，不将它当成更新必须步骤。

## 可选 Open Cloud

适用条件：已有体验和 Place，已核对归属，已有自动化发布环境和最小权限凭据，文件通过 Studio 检查，宿主允许该调用。否则保持 Studio 路线。调用 roblox-api 的单次上传接口与持久账本；不实现第二份客户端。它不能完成首次账号/体验创建、内容问卷或 Audience 设置，也不保证包含受限实例类的 Place 可更新。

无法确认 HTTP 结果或本地回执丢失时，先核对 Dashboard/Studio 的版本历史；保留 intent，不换 job 自动提交。明确拒绝后按错误类型修复，用户要求继续再做新尝试。未能核回未知结果时须先说明重复版本风险并取得针对该风险的授权。

## 默认与必须问的边界

已有项目名、说明、目标、发布请求和账号无需重问。发布请求已明确“让公众联机玩”时，可以推进 Public 设置；仅请求制作游戏不能推定公开授权。首次小型演示优先单 Place、标准客户端和平台服务，不默认域名、外部服务器、支付、跨服聊天或 Open Cloud。

已登录账号可复用，个人/群组归属须从当前目标或会话事实确认。多个候选目标时必须确认目标；账号资格、付费决定、身份与合规事实不能靠经验估计。所有“默认推荐”只用于可逆技术选型，不替代这些事实与授权。
