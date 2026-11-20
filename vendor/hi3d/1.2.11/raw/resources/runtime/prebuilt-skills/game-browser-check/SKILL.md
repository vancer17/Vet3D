---
name: game-browser-check
description: "验证游戏真实开局、交互按需资源或重开后报错时，提供浏览器玩法验收的独立规则与验证；输出可接入既有工程的模块及检查结果。"
---

# 浏览器玩法验收

## 触发与输入

用户提出“验证游戏真实开局、交互按需资源或重开后报错”时可独立调用 `$game-browser-check`。已有游戏优先局部接入，不替换其引擎或重做资产。
输入为已有工程及所需规则数据、单位、目标运行环境和保留项。先读取 [接口契约](references/contract.md)；示例不是用户偏好。

## 执行

1. 核对输入与适用边界；缺少引擎工程时仍可执行随包规则示例，不把规则示例当作完整游戏。
2. 先运行 `node "$SKILL_DIR/scripts/hi3d-example.mjs"` 查看场景输入示例（本命令不启动浏览器），再将 [核心模块](scripts/hi3d-core.mjs) 接入显式目标工程。纯计算和引擎/网络副作用分离。
3. 浏览器和 HTTP 服务沿用宿主权限及工程环境；steps 仅 click/fill/press/visible/text，最后必须断言已就绪状态。为开始/操作/暂停/恢复/结算/重开/按需资源分别提供序列；实际查看截图。
4. 运行 `node --test "$SKILL_DIR/tests/hi3d-core.test.mjs"`，并在实际工程验证：实际 HTTP 请求、资源缺失、断言失败、上下文 finally 清理。
5. 交付本次模块改动与真实检查记录，分别说明规则单测、引擎内操作、设备/服务验收的完成范围。测试输出写包外任务目录；不把退出 0 当成全部游戏验收。

## 结果与边界

checkBrowser(browser,{url,timeoutMs,allowedOrigins,viewport,steps}) → {passed,errors,requests}

需要调用方提供 Playwright Browser；新隔离上下文阻断 service worker，限制来源。仅覆盖显式 steps，不自动发现全部玩法或证明视觉质量。

Node 22+；纯计算模块可由现代浏览器 ES module 导入。浏览器适配的依赖见契约。本包不加载凭据、不发布服务、不收费。已有输出仅复核时直接执行检查阶段；失败回到规则/集成阶段，不自动扩大任务。

分发声明见 [package.json](package.json)，支持显式路径调用；宿主自动发现由安装环境决定。不要依赖源仓库 cwd 或邻包隐式导入。

<!-- managed-by: sparc3d-runtime -->
