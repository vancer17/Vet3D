# 本地接口与验证边界

实现唯一源为 [hi3d-roblox-api.py](../scripts/hi3d-roblox-api.py)，Python 3.10+ 标准库。CLI 只解析参数、调用核心和输出受限结果。

| 函数 | 输入 → 输出；副作用与失败 |
| --- | --- |
| positive_id(value) | 正十进制 int64 ID → 规范字符串；拒绝布尔、符号、URL、空白、前导零和超出 int64 范围 |
| parse_place(bytes) | UTF-8 Roblox XML v4 → Element；拒绝空/超预算、DTD/实体和其他编码；不执行脚本 |
| inspect_place(bytes) | → 类计数、有限 BasePart 类计数、脚本路径/大小、内容引用 scheme、重复 referent、云端限制类；不保存 URL 正文，不检查实时权限/几何/帧率 |
| publish_plan(bytes,suffix,universe_id,place_id) | → 不带凭据的固定 HTTPS 请求计划、原始字节指纹与媒体类型；XML 中本地路径、重复引用或已知受限类阻断；binary 仅识别头，不解码内部实例 |
| save_new_json(path,value) | 独占创建 JSON，0600、flush/fsync；父目录须已存在且解析后无跳转；不覆盖 |
| replace_record(path,value) | 原子替换当前调用的常规单硬链接意图文件；失败保留旧记录；不接受符号链接 |
| upload_once(plan,bytes,job_path,transport,authorized=False,studio_reviewed=False) | → 回执；核对完整规范计划/字节、已有账本只读复用；新意图先持久化再单次 transport；无重试，未知结果保留 |
| api_key_transport(key,timeout=30) | 已授权进程传入内存密钥 → 单次 send 闭包；固定 API 源、拒绝重定向、不使用环境代理、不记录错误正文 |
| NoRedirect.redirect_request(...) | → None；阻止带鉴权请求跨来源跳转 |
| main(argv=None) | inspect-place 或 publish-place CLI；默认发布 dry-run 零鉴权/网络/账本，正式分支只内部消费 ROBLOX_API_KEY；退出 0 为指定操作成功，1 为输入问题，2 为未取得已上传结果 |

Luau [Guard](../templates/hi3d-remote-guard.luau)：finite(value) 返回有限数判断；direction(Vector3,maxMagnitude) 返回单位向量或 nil；allow(buckets,key,now,rate,burst) 修改调用方显式桶并返回许可。now 使用服务器单调时钟秒，rate 为每秒令牌，burst 为容量；项目决定速率，不固化玩法常量。不是分布式限流或完整反作弊。

聊天模板只输出元数据，服务端以 pcall 调用平台资格检查；默认 Studio-only。客户端接收事件不等于有人工确认的 UI 送达。双方都须安装到入口声明的正确运行侧。

维护验证使用 [合成测试](../tests/hi3d-test-api.py)，只注入假的 transport/opener，覆盖未知提交不重发、计划篡改、错误响应、记录保护和 dry-run。运行 `python3 "$SKILL_DIR/tests/hi3d-test-api.py"`；带连字符文件名不能依赖 unittest discover 自动发现。

Luau 模板编译使用官方 `luau-compile`；再运行 `luau "$SKILL_DIR/tests/hi3d-test-guard.luau"` 检查有限数、独立限流桶、时钟回退与突发上限。该测试不模拟 Vector3 和 Roblox 服务；方向单位化/非法向量须在 Studio 另测。Roblox 容器/权限/复制与实际界面必须在 Studio 中验收，Python 和 Luau CLI 不提供这些平台服务证明。
