---
name: hi3d-api
description: 调用 Hi3D API 进行单图或多视图建模、独立贴纹理、浮雕、拆件和多色处理，恢复已有任务、查询余额、下载并检查产物。适用于通用 Hi3D 服务调用；绑定与动画由下游工作流负责。
---

# Hi3D API

提供通用 Hi3D 工具入口，使用随包 Python 标准库脚本完成参数预检、单次提交、状态查询、3D 免费重试和原始产物交付。按 [打包约定](../.dependency-package-tools/references/usage.md) 提供完整分发目录，保留文档与依赖布局，再显式读取本入口或按宿主发现机制调用 `$hi3d-api`；运行时无需源仓库。

## 必要约束

- Hi3D 密钥仅使用全大写环境变量 `HI3D_AK`、`HI3D_SK`。**AI 禁止读取、打印、复制或验证其实际值**；禁止读取凭据文件、`.env`、shell 配置或枚举环境寻找密钥。仅已授权的实际 API 鉴权进程可在内部消费这两个变量，不回显、不落盘。未配置时请用户在 AI 外配置；创建、维护和测试 skill 均使用模拟鉴权，不消费真实密钥。
- 仅上传用户指定的输入，沿用已明确的生成范围和授权。先完成本地 dry-run；未授权生成时停留在计划阶段。图片检查、余额查询和测试不隐含收费任务授权。只执行所需能力，不默认跑全套。
- 文生图、图生图调用前必须使用 Python 检查最终 prompt 字符数，一个中文字或英文字母算一个字符，空格、换行及标点也计入；超过 4000 时先保留必要约束等义精简到 4000 字符以下，复查通过后再生成。计数命令、原生 request/settings 覆盖优先级和追加修订规则见 [图片生成必读策略](../hi3d/SKILL.md#图片生成与编辑)。
- 一个生成计划使用一个新 job 文件；相同 job 的重复命令只复用记录。`submitting`、`submission_uncertain` 或无 task ID 时先找回原任务，禁止删除 job、更换 job 路径或自动重提来绕过阻断。API 错误正文、鉴权头和带签名 URL 不进入日志或报告。
- task ID 按服务返回的完整字符串保存；官方建模 ID 可含点号，不拆分、不截断或重构。`ValueError` 等本地异常不代表服务端未创建任务；检查固定错误阶段与 job，再按 [恢复规则](references/calling.md#提交后本地失败的恢复) 查回原任务。有效 ID 先持久化，再更新排队状态。
- 文生图或图生图调用失败后立即停止当前图像生成流程，报告脱敏原因并保留 task ID、job 和已有产物；不更换参数、模型、路径或工具自动重提。只有用户明确要求重试或恢复时才继续；正常 pending 可继续查询同一任务。该规则覆盖账号模式与调用方的图片阶段，不以当前生成授权推导失败后的自动重试授权。
- 调用成功且取得图片后，效果不佳、视角错误或质量验收不通过属于质量迭代，可按已有授权和调用方原有次数限制继续修图或重新生成，无需逐轮重新确认，不因此暂停整项任务。质量新版本使用新的 job/输出目录，保留成功任务及产物；这不允许绕过调用失败或提交不确定的原 job。质量验收状态不得写成服务任务的 failed；最终验收门槛照常执行。
- 保存原始产物与哈希，派生编辑使用新路径。成功状态、GLB 头校验和 Blender 保存均不代表视觉、装配或打印质量通过。

## 调用流程

首次调用读取 [调用、安装与恢复](references/calling.md)，确定实际 `SKILL_DIR`、任务目录和 Python 3.9+。生成或修改参数时读取 [参数契约](references/parameters.md)；`defaults.json` 是可覆盖的起始配置，不是用户偏好或已验证的最优设置。网页带钻项与 Agent/网页表面差异读取 [网页 option 门禁](../hi3d/references/web-option-gates.md)。

| 任务 | 入口 |
| --- | --- |
| 单图、多视图建模或 GLB 独立贴纹理 | `scripts/hi3d_api.py submit model` |
| 图片浮雕、模型拆件、多色处理 | `submit relief / split / multicolor` |
| 本地参数预检 | `submit … --dry-run`；不联网、不读取密钥、不创建 job |
| 余额、查询、有限轮询、恢复、下载 | `balance / query / wait / adopt / download` |
| 账号 Runtime：3D 免费重试次数与提交 | `scripts/runtime/hi3d_api.py retry-quota` / `retry`；只接受原任务 ID，不写计费字段 |
| Blender 原始网格、材质、贴图与拓扑指标；顶点色显示副本 | `scripts/blender_review.py`；使用前读 [检查边界](references/review.md) |

提交生模、浮雕或拆件前，用宿主 `user_interaction` 展示参数面板，不要另做一套弹窗，也不要在参数未齐时直接提交。参数面板使用 `kind=preference`，每题的 option `label` 直接使用下表 id，网页短文案写在 `description`，提供匹配的 `defaultAnswer` 和 `timeoutSeconds=60`。模型在同一个面板里询问扁平的 `model_type` 与 `generation_type`；模型选项共 6 项，不先询问版本。文生图和图生图不展示参数面板，默认使用 `gpt-image-2`，比例由 AI 根据内容和用途推荐并显式传入；用户明确指定的参数优先，图片数量继续使用调用入口默认的 1 张。超时采用面板中的参数默认值。

用户明确要求生成或处理即表示执行该任务；参数齐全后直接提交，不再展示额外的计费授权面板。目录和可直接转交宿主的合法 payload 由 [网页 option 门禁](../hi3d/references/web-option-gates.md) 与 `scripts/web_option_gates.py` 维护。`scripts/hi3d_api.py submit` 用同名 `--set` 接收弹窗 id，再换成公共 API 字段。许可（`license`）只在弹窗里显示，不进入 submit。`model_type` 的值已经同时编码版本和子型号。

| 弹窗 id | 可见取值 | `--set` 之后的提交字段 |
| --- | --- | --- |
| `model_type` | `v3.0:quality` v3.0 极致细节 · 高质 \| 品质增强（推荐）、`v3.0:master` 大师 \| 极致细节；`v2.1:fast` v2.1 极速生成 · 极速 \| 最快出稿（推荐）、`v2.1:quality` 高质 \| 品质增强；`v2.0:1536` v2.0 均衡全能 · 均衡、`v2.0:1536pro` 高质 | `model` + `resolution`；Runtime 的 v2.0 均衡/高质分别传 `modelType=balanced/quality`；v3.0 前端 `quality` → `modelType=standard`，前端 `master` → `modelType=quality`，同时展开 `version` 与分辨率 |
| `generation_type` | `both` 几何+风格化贴图（推荐）、`mesh` 几何、`texture` 仅贴纹理（需已有 GLB） | `request_type=3` / `1` / `2`；Runtime 的 `texture` 同时传 `scene=texture`。选 `texture` 必须带 `--mesh` 或 `--mesh-url`，且 `model_type` 只能是 v3.0 档位；缺 GLB 或选 v2.0/v2.1 时门禁直接报错，不提交 |
| `rmbg` | `on` 去除背景、`off` 保留背景 | 浮雕 `rmbg=1` 或 `0` |
| `scene` | `character` 角色、`general` 通用 | 拆件 `model` |
| `template` | `a`–`f` | 拆件 `part` |

例如：`--set model_type=v3.0:quality --set generation_type=both`；为已有 GLB 单独贴纹理：`--image ref.png --mesh model.glb --set model_type=v3.0:quality --set generation_type=texture`。

先核对本地计划与输入来源，再提交；记录 task ID，分段查询，任务成功后下载。轮询返回 pending 时继续查询同一 job；attention 或 failed 时依据记录处理，不能把非成功状态当作生成完成。所有命令的参数见对应 `--help`。

交付原始产物、job、文件哈希与必要检查报告；说明实际验证和未验证部分。下游绑定/动画接收已下载的 GLB 与生成参数，无需接触密钥或重复实现 API 客户端。

人形身体需要新绑定时，推荐显式交给独立 `rig-retarget`，由其组合独立 `mdf-call` 经 HTTP 调用 auto-rig，再回迁高模、检查并修复手指等局部拉伸。已有合格绑定直接复用；本工具不因此重新生成模型或新增绑定客户端。

## 账号 Runtime 模式

宿主提供 `hi3d_api` 时，必须完整读取 [账号模式](../hi3d/SKILL.md)，遵守其中的图片默认模型和 prompt 预算，并按需读取参数、图像、免费重试与恢复参考。它与本文公共 API 的认证、参数和任务账本分开；`scripts/runtime/hi3d_api.py` 的网络任务只由受管宿主执行，普通 shell 不注入代理能力，离线 `check-image-prompt` 可在普通 shell 中执行。公共模式继续使用本入口原 CLI。账号 3D 免费重试走 `retry-quota` / `retry`，次数由服务端返回，客户端不得填写 `retryType`。

<!-- managed-by: sparc3d-runtime -->
