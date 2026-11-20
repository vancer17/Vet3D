---
name: game-save
description: "保存游戏进度、恢复旧版存档或处理损坏存档时，提供游戏存档迁移的独立规则与验证；输出可接入既有工程的模块及检查结果。"
---

# 游戏存档迁移

## 触发与输入

用户提出“保存游戏进度、恢复旧版存档或处理损坏存档”时可独立调用 `$game-save`。已有游戏优先局部接入，不替换其引擎或重做资产。
输入为已有工程及所需规则数据、单位、目标运行环境和保留项。先读取 [接口契约](references/contract.md)；示例不是用户偏好。

## 执行

1. 核对输入与适用边界；缺少引擎工程时仍可执行随包规则示例，不把规则示例当作完整游戏。
2. 先运行 `node "$SKILL_DIR/scripts/hi3d-example.mjs"`，再将 [核心模块](scripts/hi3d-core.mjs) 接入显式目标工程。纯计算和引擎/网络副作用分离。
3. 使用游戏命名空间与槽位键。先读原字节再迁移，先通过 validate，再写新槽位；校验成功后才更新活动槽位。不要用空档自动覆盖坏档。
4. 运行 `node --test "$SKILL_DIR/tests/hi3d-core.test.mjs"`，并在实际工程验证：不同游戏拒绝、未来版本拒绝、迁移缺失、非法 JSON 值、存储异常。
5. 交付本次模块改动与真实检查记录，分别说明规则单测、引擎内操作、设备/服务验收的完成范围。测试输出写包外任务目录；不把退出 0 当成全部游戏验收。

## 结果与边界

encode(game,version,data) → JSON；decode(text,{game,version,migrations,validate,maxBytes}) → 数据；writeSave(storage,key,text) → 无返回

JSON 数据与同步存储适配；不是云存档或加密防作弊。迁移函数由项目提供，版本步数上限 100。readback 失败不自动删除旧数据；调用者保留备份。

Node 22+；纯计算模块可由现代浏览器 ES module 导入。浏览器适配的依赖见契约。本包不加载凭据、不发布服务、不收费。已有输出仅复核时直接执行检查阶段；失败回到规则/集成阶段，不自动扩大任务。

分发声明见 [package.json](package.json)，支持显式路径调用；宿主自动发现由安装环境决定。不要依赖源仓库 cwd 或邻包隐式导入。

<!-- managed-by: sparc3d-runtime -->
