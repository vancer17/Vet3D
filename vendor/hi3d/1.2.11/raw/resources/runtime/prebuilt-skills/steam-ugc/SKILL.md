---
name: steam-ugc
description: 核对 Steam ISteamUGC 物品接口、调用侧和提交字段，执行离线提交前检查；单次真实调用仅在目标应用支持且已有授权与可信 SDK 连接时进行，不制作内容或代替发布验收。
---

# Steam 创意工坊物品接口

可独立调用 `$steam-ugc`，或显式提供本文件。输入：一项明确操作、调用侧、目标 App 的支持证据、已有内容目录及物品字段、包外报告位置；真实写入还需要账号已有权限、新建/更新目标与本次授权。输出：接口选择和离线检查结果；真实提交时只输出实际回执，不能据此声称物品已经公开或第三方能够订阅。没有可用 Steam 会话或 SDK 客户端时只做检查，不要求密码、密钥、验证码，也不假装提交。

执行前读取 [接口字段与检查](references/contract.md)、[来源与使用证据](references/sources.md)，核对目标应用本身是否启用了所需的 Workshop 集成及内容加载器。`ISteamUGC` 是 Steamworks SDK 中供集成应用调用的接口；静态创作文件本身不会执行该接口。要从已有应用的命令或官方游戏内上传器发布，先确认该应用真实提供该路径，不从 API 名称推断游戏支持。文档可能更新；正式提交前以目标应用已安装 SDK 和当前官方接口为准。

纯检查只处理物品字段、路径和已有证据，不触网、不调用 SDK、不重新制作内容；通用文件字节/哈希清单可另由 [game-package](../game-package/SKILL.md) 校验，不能拿其清单通过代替游戏内可加载或 Workshop 已发布。`content_folder` 是要提交的实际文件夹，`preview` 是实际图片，`app_id` 与 `published_file_id` 必须来自目标平台的真实值。缺少目标 App 支持、合法内容目录或新建/更新归属时保留 `prepared/blocked` 状态，不编造 ID。

单次调用的顺序：`CreateItem(app_id, k_EWorkshopFileTypeCommunity)` 只用于经确认的新建；已经存在目标物品时复用其真实 ID。对确认的 ID 执行 `StartItemUpdate`，按输入调用 `SetItemTitle`、`SetItemDescription`、`SetItemContent`、`SetItemPreview`，按需 `SetItemTags`、`SetItemMetadata`、`SetItemVisibility`，然后仅一次 `SubmitItemUpdate`。需先设置内容文件夹、可用预览、物品字段与授权可见范围；检查返回的 `EResult`、实际 `PublishedFileId_t`、提交/更新的回调和法律协议标志。上传不明时查原 ID 和平台状态，不能更换 ID 或重复提交。字段和失败停止点由 [接口契约](references/contract.md) 唯一维护；本入口不实现网络客户端，也不自建隐藏登录。

回执只证明已经观测到对应 SDK 提交结果。公开可见性和独立账号订阅下载的真实验收交给 [pub-steam-mod](../pub-steam-mod/SKILL.md)；它是独立交接，不能由回执推断。无用户发布请求时不执行任何写入。steamcmd、创意工坊网页及游戏内上传器的可用性只按其各自官方契约判断，不作为此接口的默认替代路线。

<!-- managed-by: sparc3d-runtime -->
