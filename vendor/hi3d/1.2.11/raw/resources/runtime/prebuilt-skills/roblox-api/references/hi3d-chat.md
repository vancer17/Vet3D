# 默认聊天的诊断顺序

1. 新工程使用 TextChatService 默认聊天，不强写 ChatVersion。官方文档说明该属性在新体验弃用，写入还有安全级别限制。
2. 编辑期核对 CreateDefaultTextChannels/CreateDefaultCommands，以及 ChatWindowConfiguration、ChatInputBarConfiguration、BubbleChatConfiguration 的 Enabled。运行后确认 TextChannels 下有 RBXGeneral，输入目标是 General；不要重复创建同名默认频道。
3. 先用 Studio 的 Server & Clients 启动两个客户端，确认角色和共享交互同步。模拟账号可能为负 UserId；资格判断为 UNKNOWN 不能当作允许或拒绝的真实平台结论。
4. 需要诊断时分别安装 [客户端模板](../templates/hi3d-chat-probe.client.luau) 到 StarterPlayerScripts、[服务端模板](../templates/hi3d-chat-probe.server.luau) 到 ServerScriptService。默认只在 Studio 运行；受控线上调试须显式将 EnableInPublished 属性设为 true，测试后关闭并发布更新。
5. 由测试者使用两个符合平台通信条件的真实账号，在 Roblox 客户端加入**同一服务器实例**。体验链接相同不等于同服；通过加入好友或服务器列表加入。人工发送普通测试文字，不由 Agent 自动给他人发送消息。
6. 双向接收端出现处理后的消息才是送达证据。SendingMessage 可能只是本地回显；`DisplaySystemMessage()` 仅本地系统提示；CanUserChatAsync/CanUsersChatAsync 为资格诊断，均不能代替实际收发。
7. 验证静音/屏蔽、重生、离开重进和不同设备。账号资格、年龄检查、家长控制、屏蔽关系及当前平台规则可限制互通；不保证所有账号彼此可聊天。

诊断仅记录频道、状态、消息 ID 和必要的测试账号标识，不打印正文、不保存未过滤文本、不复制私聊。不用自定义 RemoteEvent 绕过 TextChatService 过滤或通信资格。当前默认聊天是同服聊天，不是所有服务器共享的世界频道；“能发送聊天”也不是 MMO 容量验收。

| 症状 | 定位顺序 |
| --- | --- |
| 找不到输入框 | 默认 UI 开关→其他脚本是否隐藏→账号通信资格 |
| 只有自己看到 | 是否同服→是否 General→接收端结果→双方屏蔽与通信条件 |
| 默认频道缺失 | 初始化错误与有限等待→配置→是否为旧聊天工程 |
| 两账号各自能发但互相不通 | CanUsersChatAsync 成对资格→账号设置→平台当前规则 |
| 重生后重复显示 | 重复事件连接、GUI ResetOnSpawn、旧对象清理 |
| 消息被修改或拒绝 | 正常过滤/限流/权限原因，不尝试绕过 |

记录测试环境、发布版本、同服证据、两个方向的结果与限制。未真实执行写“待验证”，不以模板存在或客户端 Output 无异常替代验收。
