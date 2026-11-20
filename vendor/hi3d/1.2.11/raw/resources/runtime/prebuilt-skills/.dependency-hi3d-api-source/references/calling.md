# 调用、安装与恢复

按 [打包约定](../../.dependency-package-tools/references/usage.md) 生成完整分发目录，保留其中工具与文档的相对位置，再显式读取入口或按宿主机制安装并调用 `$hi3d-api`。仓库中的目录存在不代表当前会话已加载；不覆盖同名已安装版本而不检查差异。`SKILL_DIR` 指向本次提供的工具包目录，`RUN_DIR` 为独立任务目录；不向工具包写入用户数据或输出。API 脚本自身使用标准库，入口引用的说明仍须随分发目录完整提供，无需原分享包。

API CLI 使用 Python 3.9+ 标准库。Blender 检查需要可运行导入算子的 Blender 与其内置 NumPy；本次离线验证版本为 Blender 5.2。鉴权仅由实际 API 进程内部消费 `HI3D_AK`、`HI3D_SK`；AI 不检查环境值、配置文件或 shell 启动文件，不使用密钥命令行参数。认证缺失时停止，由用户在 AI 外配置运行环境。

## 最小流程

以下变量均为当前任务指定的非密钥路径。先设置 `SKILL_DIR`、`RUN_DIR`、`IMAGE`；`PYTHON` 为可用解释器。job 路径必须未被其他任务占用。

```bash
"$PYTHON" "$SKILL_DIR/scripts/hi3d_api.py" submit model --image "$IMAGE" --job "$RUN_DIR/model.json" --dry-run
# 参数选择之后直接提交：
"$PYTHON" "$SKILL_DIR/scripts/hi3d_api.py" submit model --image "$IMAGE" --job "$RUN_DIR/model.json" \
  --set model_type=v3.0:quality --set generation_type=both
"$PYTHON" "$SKILL_DIR/scripts/hi3d_api.py" wait --job "$RUN_DIR/model.json" --seconds 50 --interval 20
"$PYTHON" "$SKILL_DIR/scripts/hi3d_api.py" download --job "$RUN_DIR/model.json" --out "$RUN_DIR/model"
```

多视图用重复 `--image` 和对应 `--views front,left`；只传真实视图，不把旋转后的同一照片冒充多视图。贴纹理用 `submit model --image … --mesh … --set request_type=2`。浮雕用 `submit relief --image …` 或 `--image-url …`；拆件/多色用 `submit split` / `submit multicolor --mesh …` 或 `--mesh-url …`。每种操作指定独立 `--job`；所有 submit 都可先加 `--dry-run`。

`--set key=value` 可重复，按 [参数契约](parameters.md) 校验。例：`--set resolution=2048master --set face=5000000` 只在任务需要该档位时使用。网页带钻字段在 `surface=web` 且普通身份时不得用 API 改写，见 [网页 option 门禁](../../hi3d/references/web-option-gates.md)。URL 只允许无内嵌用户名/密码的 HTTPS；签名 URL 由任务提供，输出中隐藏 query/fragment，日志无法用于重建签名。

`balance [--out 新文件.json]` 只返回时间、`totalBalance` 和单位未确认标记，不推断现金或单任务扣费。`defaults` 只展示本地起始配置。dry-run/defaults/adopt 不访问网络或密钥。

## 任务状态与恢复

job 保存输入路径、大小、SHA-256、参数脱敏视图、完整计划指纹及 task ID；URL 签名和 API 响应正文不保存。文件首次以独占方式创建，后续 JSON 原子替换。一个 job 同时只由一个查询/下载进程维护；不同 job 不提供全局去重。

| 结果 | 处理 |
| --- | --- |
| `created / queueing / processing` | pending，继续查询同一 job |
| `success` 且无 `last_query_error` | 可下载；仍需验收产物 |
| `failed / submission_rejected` | CLI 退出 1，保留记录并处理失败 |
| `submitting / submission_uncertain` 或查询错误 | attention / 退出 2，保留原记录并核对服务端任务；不自动重提 |

CLI 退出 0 也可能表示 pending、计划成功或本地操作成功，必须读取状态。`wait` 的轮询调度窗口为 0–50 秒，间隔 5–50 秒；HTTP timeout 是单次网络操作超时，含鉴权/刷新时总耗时可能超过调度窗口。查询错误立即返回 attention。API POST 从不自动重试；GET 仅显式 401 时刷新鉴权一次。

已知 task ID 可以 `adopt model TASK_ID --job 新文件.json` 后 query/download；其他 kind 同理。ID 支持 1–200 个 ASCII 字母、数字、点号、连字符和下划线，作为不透明字符串原样保存并通过 `urlencode` 传入查询，不推断或拆分其组成。旧动画工作流的 state 不能直接当作新 job：保留原文件，提取其中已有的非密钥 task ID，使用 adopt，**不重新生成**。

### 提交后本地失败的恢复

远端创建与本地保存是两个步骤。HTTP/API 成功之后仍可能出现 ID 校验、字段处理或磁盘异常；看到本地 `ValueError`、非零退出或没有 ID，不能认定生成失败或未扣费。[官方查询说明](https://docs.hi3d.ai/zh/api/api-reference/list/query-task)中的建模 ID 包含点号，仅覆盖简短合成 ID 的测试不足以验证兼容性。

1. 保留原 job、输入哈希、参数与带时区的提交时间。先读取 `state`、`task_id` 和固定 `error.phase`；`request` 表示请求阶段未确认，`task_id_validation` 表示成功响应的 ID 本地校验失败，`task_id_persistence` 表示保存 ID 失败，`state_update` 表示更新状态失败。阶段只是本地定位，不是服务端结果。旧记录可能只有异常类型，不能把推断说成已证实原因。
2. 有完整 ID 时直接 query 同一个 job；有效 ID 在后续状态处理前已单独保存，即便状态仍为 submitting 也优先查询恢复。
3. 没有 ID 时使用已授权的 Hi3D 控制台“使用详情”或服务端记录找回。按提交时间（注意 UTC 与本地时区）、输入图片及参数交叉匹配；多任务并行时不可仅按列表顺序归属。不要进入密钥页面、读取凭据、猜 ID 或发新 POST 探测。
4. 找到唯一匹配的完整 ID 后，使用 adopt 创建关联原 job 的恢复记录，再 query/download；原 job 与恢复依据保存在任务目录。匹配不唯一或无法查回时，请用户提供原任务 ID/服务端确认，不能删除状态或换路径重新生成。
5. 修复兼容问题使用模拟客户端，覆盖官方格式的合成 ID 从 submit→落盘→query→download、adopt、同 job 复用及未知响应的单次提交边界。不得为验证修复再运行收费任务。

只记录必要 ID、固定阶段、状态及安全的 HTTP/code 信息；不保存完整 API 响应、鉴权内容或签名 URL。认证失败发生在 intent 之前；提交后磁盘完全不可写仍无法保证 ID 落盘，应保留旧 intent 并走控制台恢复。不得仅据异常类型判断密钥缺失或服务拒绝。

download 使用独立无鉴权下载器，仅允许 HTTPS 重定向。保存 `api-result.*`、必要时解压到 `extracted/`；保留原 ZIP、可选封面及各文件大小/哈希。拒绝覆盖、危险 ZIP 路径、符号链接、重复成员或解压总量超过 8 GiB。缓存需所有记录文件哈希一致；文件被编辑、缺失或输出目录改变即停止，不覆盖修复。下载/解压中断保留已写文件供检查，尚无完整 manifest 时用新的输出目录重下同一 task，勿重提生成。

交付动画时取 artifact.files 中实际 GLB 路径，保持原件；下载后缀或 GLB 头通过不能替代 Blender 实际导入与视觉检查。
