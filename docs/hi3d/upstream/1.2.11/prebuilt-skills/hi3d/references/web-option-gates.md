# 网页 option 门禁

网页 C 端（2026-09-21）把**带钻**标成会员能力，不是积分档。本页是唯一目录源；PCG 仍用同一套 `waiting_choice` option 弹窗，不另做第二套 UI。

## 表面与身份

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `identity` | `standard` / `member` | 当前账号是否会员 |
| `surface` | `agent`（默认）/ `web` | Agent 生模阶段 vs 网页表单 |

- **钻石 = 会员**，积分不能解锁。
- **生模弹窗**：不写普通/会员身份提示，统一「请选择您要使用的 Hi3D 生成参数」。
- 生模、浮雕与拆件的明确参数可以预填 `selected`；缺少参数时保持 `waiting_choice`，参数齐全后直接提交。
- Desktop Agent 直接使用返回的 `user_interaction`：参数面板使用 `kind=preference`、`timeoutSeconds=60`，每题都有与 option label 匹配的 `defaultAnswer`。超时使用面板里的推荐参数。

`submit_choice_gate` / `gate_parameter_overrides` 对文生图和图生图直接返回 `ready`，不返回 `user_interaction`；生模、浮雕与拆件在参数不完整时让 CLI 返回 `waiting_choice` 且不 POST。`--session` 可读取任务目录已选参数；`native_display_overrides` 把弹窗 id 换成 Runtime native `--set`。用户已明确要求生成时，参数齐全即返回 `ready`，不再增加计费授权阶段。

## 目录（与 C 端对照）

| kind | 普通可用 | 带钻（网页锁定；Agent 可选用） |
| --- | --- | --- |
| text-to-image | Seedream V4.5；关多视图 | Nano-Banana-Pro / Nano-Banana 2 / GPT Image 2；多视图 |
| model | v3.0 高质/大师，v2.1 极速/高质，v2.0 均衡/高质；几何+风格化贴图（推荐）、几何或仅贴纹理 | 无。弹窗不标积分，扣分以实际 API 参数为准 |
| relief | 去背景、CC BY | 私有许可 |
| split | 角色/通用、模板 a（6 件）、CC BY | 模板 b–f；私有许可 |
| multicolor | CC BY | 私有许可 |

生模弹窗不区分普通/会员提示，统一为「请选择您要使用的 Hi3D 生成参数」。模型版本与子型号拉平为一个 `model_type` 单选，共 6 项，option `label` 仍是提交 id，说明写在 `description`：`v3.0:quality`（v3.0 极致细节 · 高质 | 品质增强，推荐）、`v3.0:master`（大师 | 极致细节）、`v2.1:fast`（v2.1 极速生成 · 极速 | 最快出稿，推荐）、`v2.1:quality`（高质 | 品质增强）、`v2.0:1536`（v2.0 均衡全能 · 均衡）、`v2.0:1536pro`（高质）。不提供 v1.5。生成类型依次列 `both`（几何+风格化贴图（推荐））、`mesh`（几何）、`texture`（仅贴纹理（需已有 GLB）），默认 `both`，不显示积分和估时。扣除的积分以提交时 API 对所选参数的实际计费为准。

`generation_type=texture` 映射为公共 API `request_type=2`，Runtime 则同时输出 `scene=texture` 与 `generationType=texture`（`both`/`mesh` 不改 scene）。该选项要求同时提供参考图和已有 GLB（`--mesh` / `--mesh-url`），且 `model_type` 为 v3.0 档位；`submit_choice_gate` / `gate_parameter_overrides` 接受调用方传入的 `has_mesh`，已知无 GLB 或选了 v2.0/v2.1 时在上传前抛 `ValueError`。`has_mesh=None`（如 Runtime 带 `--request`、GLB 可能来自 `meshUrl`）时跳过该检查，由 `build_plan` 的 scene 校验兜底。

Runtime v2.0 均衡档 `model_type=v2.0:1536` 显式传 `otherParam.modelType=balanced`，高质档 `model_type=v2.0:1536pro` 显式传 `otherParam.modelType=quality`，两档均传 `version=v2.0` 和 `voxelResolution=1536`；面板 id 与公共 API 的 resolution 代号保持不变。

Runtime v2.1 档位为 `fast` / `quality`：`model_type=v2.1:quality` 展开为 `version=v2.1`、`otherParam.modelType=quality`。旧面板值 `v2.1:pro` 不再接受；公共 API 的高质分辨率代号仍为 `1536pro`，不作为 Runtime 的 modelType。

前端 v3.0 档位与 Runtime 原生值分开：`v3.0:quality`（高质，默认推荐）→ `otherParam.modelType=standard`，`v3.0:master`（大师）→ `otherParam.modelType=quality`。公共 API 的 `resolution` 分别保持 `2048quality`、`2048master`；显示名称不直接用作后端模型类型。

Runtime 文生图和图生图不弹窗，默认使用 `gpt-image-2`，比例由 AI 根据内容、用途和参考图推荐并显式传入，用户明确指定的参数优先。图片数继续使用入口默认的 1 张；`model`、`aspect_ratio` 的可选 settings 映射保留，网页目录不变。模型面板使用 `model_type`、`generation_type`，两题在同一个 `user_interaction` 中展示。浮雕使用 `rmbg`，拆件使用 `scene`、`template`。`project_parameter_interaction` 对图片返回 `None`，对其他需要选择的任务生成以上宿主 payload；调用方复用返回对象，不手抄另一份 schema。

## 接口

[scripts/web_option_gates.py](../scripts/web_option_gates.py)：

- `project_web_options(kind, identity='standard', selected=None, surface='agent')` → 分组、`gem_ids`、`locked_ids`、`selectable_ids`、`clamped`。
- `reject_gated_request(...)`：仅 `identity=standard` 且 `surface=web` 时拒绝带钻字段。
- `display_overrides` / `native_display_overrides` / `submit_choice_gate(kind, overrides, selected, has_mesh=None)` / `gate_parameter_overrides(kind, overrides, session, native, has_mesh=None)` / `project_parameter_interaction` / `validate_generation_selection(selected, has_mesh=None)`。

session 可选 `hi3d_options: {identity, surface, kind, selected, selected_by_kind, stage}` 与顶层 `waiting_context`。投影见 pcg-view `compose_view` 的 `option_popup.web_options`。`selected` 的键必须是入口 [SKILL.md](../SKILL.md) 里的弹窗 id。
