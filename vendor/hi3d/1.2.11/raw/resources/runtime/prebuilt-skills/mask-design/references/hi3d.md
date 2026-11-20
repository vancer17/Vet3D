# 独立 Hi3D 工具交接

新生成头模或艺术外壳时显式调用 `$hi3d-api`；已有有效模型时直接进入本地适配，不要求重跑上游。将仓库 `tools/hi3d-api/` 的完整目录另行提供到目标宿主的技能发现位置，按宿主机制加载并核对其 `SKILL.md`、`references/calling.md` 和 `references/parameters.md`。不复制客户端到本包，不通过相邻目录导入。没有工具时说明缺少的具体能力，继续默认头型、已有模型和其他独立工作。

`MASK_SKILL`、`HI3D_TOOL`、`MASK_RUN` 分别指实际业务包、独立工具包和包外任务目录。Python 3.9+。授权 API 进程只从 `HI3D_AK`、`HI3D_SK` 内部取得鉴权值；AI 不读取、打印或验证真实值，也不查凭据文件、shell 配置、环境列表，不保存 token、鉴权头或签名 URL。缺失时用户在 AI 外配置；维护与测试不消费真实密钥或调用收费服务。

## 输入输出

- 头部任务：助手实际审查后的清晰头照或真实多视图，保留原图与处理记录。面具任务：独立的面具参考图；只有文字时先制作可看的概念图，再整理为符合接口的单图或视图。两个用途各用独立 job。
- 对工具传入非空 PNG/JPEG/WebP（当前工具每张最多 20 MiB）、输出 job 路径及经工具参数契约核对的参数。多视图按工具 `--views` 标记真实方向，不能把拼图当四张图或伪造侧脸。
- 参数来自本次任务及工具支持范围；不固化个人档位、面数或价格。指定 GLB 交接，是否纹理由任务决定。先 dry-run；本地预检不证明图像质量或服务可用。
- 下载后的 `artifact.files` 中实际 GLB 是下游输入，不能假设固定文件名。记录原始文件、完整 task ID、参数、尺度状态和哈希；在新路径加工。成功下载不等于合格头雕、可佩戴外壳或打印件。

## 调用与恢复

以下变量先替换为当前任务真实路径；`IMAGE` 为当前这一项已审查输入，`JOB` 为该生成计划唯一记录。读取工具说明后再执行。

```bash
python3 "$HI3D_TOOL/scripts/hi3d_api.py" submit model --image "$IMAGE" --set format=glb --job "$JOB" --dry-run
# 与 dry-run 同一参数正式提交；waiting_choice 交给宿主全局弹窗。
python3 "$HI3D_TOOL/scripts/hi3d_api.py" submit model --image "$IMAGE" --set format=glb --job "$JOB"
python3 "$HI3D_TOOL/scripts/hi3d_api.py" wait --job "$JOB" --seconds 50 --interval 20
python3 "$HI3D_TOOL/scripts/hi3d_api.py" download --job "$JOB" --out "$MASK_RUN/raw-model"
```

1. `created/queueing/processing` 是 pending，继续同一 job 的有限轮询；退出 0 不能单独判断成功。
2. `submitting/submission_uncertain`、提交后异常或没有 ID 时保留记录，按工具恢复规则找回任务；不得删 job、换路径或新 POST 探测。完整 task ID 允许点号，不拆分或猜测。
3. 旧客户端 job 不直接当新格式。保留原记录，从已有非敏感字段取完整 ID，通过 `adopt model TASK_ID --job 新文件.json` 接管，再查询/下载；关联原 job，不重新生成。
4. 已确认服务失败才根据本次授权规划重试；次数不继承历史案例。下载中断或临时 URL 过期先恢复同一任务，保留中间件，必要时新目录重新下载，不新建生成任务。
5. 全部服务调用与等待按 [计时契约](timing.md) 记录实际耗时，服务计算时间仅在有真实来源时单列。

本包通过 CLI 组合现有工具，无独立 HTTP/鉴权实现。迁移验证使用工具 dry-run 或模拟客户端；不把本地验证写成当前线上生成成功。
