# 来源、时间与实际使用边界

查阅日：2026-10-12。Steamworks 网页为持续更新文档，没有从固定 SDK tag / 存档确认版本；正式提交必须重新对照当前文档和目标应用 SDK。本文只概括接口与操作边界；文档原文许可证未查实，不转载整页或镜像网站，也不编造过去的浏览/调用记录。

| 接口/渠道 | 官方入口 | 调用侧 | 本次对话的实际情况 |
| --- | --- | --- | --- |
| `ISteamUGC` | https://partner.steamgames.com/doc/api/ISteamUGC | 已集成 Steamworks SDK 的游戏/可信上传工具 | 用户提供文档链接，Agent 在聊天中分析接口；**没有调用 CreateItem、SubmitItemUpdate 或其他 SDK 方法**，也没有真实上传回执。上文接口均标记“通用必需”，不是本次实际执行。 |
| 创意工坊集成 | https://partner.steamgames.com/doc/features/workshop/implementation | 游戏开发方/Steamworks 应用管理员 | 分析启用与接入前提；没有替目标游戏配置 Steamworks。 |
| 创意工坊物品验收 | https://partner.steamgames.com/doc/features/workshop | 有权限的创建者及另一订阅账号 | 仅说明待完成的最短发布和订阅侧验收；没有物品 ID 或实际他人订阅。 |
| `steamcmd` | https://partner.steamgames.com/doc/sdk/uploading | 通用 Steam 应用部署命令行，具体 Workshop 游戏若支持需另查其官方入口 | 本次没有运行命令；不能把 Steam depot 构建上传混同为 ISteamUGC 物品上传，也不作为默认发布路线。 |
| 创意工坊网页 | https://steamcommunity.com/workshop/ | 浏览器访问；适用操作视 App 权限而定 | 本次仅讨论/查看页面支持情况，没有登录账号、创建物品或设置可见性。 |
| 游戏内上传器 | 目标游戏自身发布的操作说明，未知则待确认 | 目标游戏客户端/授权工具 | 没有观察到可用上传器，也没有实际调用；不能编造某款游戏菜单。 |

这次已完成的是**创意源资产、离线模型/动画/特效/音频检查以及接口分析**。未形成目标游戏资源映射、可直接安装的游戏内容目录、Steam 上传尝试、物品 ID 或订阅验收。资产案例与来源可在任务目录单独审计，不能在本原子技能固化它们。将来有实际 SDK 客户端、应用支持与当前授权时，以实时回调、用户/所有者证据及可恢复状态为验收依据；当前只为离线规范，不能写“已发布”。
