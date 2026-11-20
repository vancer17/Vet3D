# 独立 Hi3D 模型交接

新生成复杂自由外壳时显式调用 `$hi3d-api`；已有可用外壳直接继续本地工程。将仓库 `tools/hi3d-api/` 的完整目录另行提供到宿主技能发现位置，或由用户/宿主给出已安装工具的实际绝对路径。先读该工具 `SKILL.md`、`references/calling.md` 和参数契约；本包不含第二套客户端，不从相邻目录偷偷导入。

## 输入与依赖

- 工具需要 Python 3.9+，本地 lamp-design 工具需要 Python 3.10+。授权 API 进程只在内部消费 `HI3D_AK`、`HI3D_SK`。AI 不读取、回显或验证真实值，不查凭据文件、shell 配置或环境列表；未配置时用户在 AI 外配置。维护/迁移/测试不消费密钥、不执行收费生成。
- 输入为实际检查过的单视图 PNG/JPEG/WebP 或有真实方向标记的多视图；突出目标壳体，减少背景、底座、线缆干扰。纯文字先生成概念图。图版拼接不是多视图参数。
- 档位、格式、纹理与服务版本按本次目的和工具支持范围选择，不继承作者账户、固定面数、价格或个人参数。通常以实际 GLB 交接；先 dry-run，再同计划正式提交；`waiting_choice` 交给宿主全局弹窗。
- 保存原始产物、完整任务 ID、参数、源图及哈希到包外任务目录。签名 URL、鉴权头与秘密不进入记录；下游接收真实下载文件，不猜固定文件名。

## 调用示例

`HI3D_TOOL` 为独立工具实际目录，`LAMP_RUN` 为包外任务目录，`LAMP_IMAGE` 为本次已审查图，`LAMP_JOB` 为该计划唯一 job。变量先由执行者替换为实际路径，不包含密钥。

```sh
python3 "$HI3D_TOOL/scripts/hi3d_api.py" submit model --image "$LAMP_IMAGE" --set format=glb --job "$LAMP_JOB" --dry-run
# 与 dry-run 同一计划正式提交；waiting_choice 交给宿主全局弹窗。
python3 "$HI3D_TOOL/scripts/hi3d_api.py" submit model --image "$LAMP_IMAGE" --set format=glb --job "$LAMP_JOB"
python3 "$HI3D_TOOL/scripts/hi3d_api.py" wait --job "$LAMP_JOB" --seconds 50 --interval 20
python3 "$HI3D_TOOL/scripts/hi3d_api.py" download --job "$LAMP_JOB" --out "$LAMP_RUN/raw-shell"
```

按工具实际状态判断业务结果：pending 时分段查询同一 job；成功后从下载记录的实际文件列表读取 GLB，再核对外观、孔洞、单位与尺度。下载成功不等于可打印壳体。

## 恢复边界

`submitting`、`submission_uncertain`、没有 ID 或提交后本地异常时，按工具恢复流程找回原任务；禁止删 job、换路径或新 POST 来探测。完整 ID 可能有点号，不拆分或重构。旧客户端 job 保留，使用其已有非敏感任务 ID，通过 `adopt model TASK_ID --job 新记录.json` 接管，关联旧记录，不重新生成。

下载中断或地址过期先查询/恢复同一任务。确认服务失败后才按授权做有限重试。工具缺失时继续已有模型、本地适用形体和其他独立阶段；用户明确指定 Hi3D 来源时不把程序外壳冒充 Hi3D。计时按 [阶段统计](timing.md) 记录，本地等待与服务计算耗时分开。
