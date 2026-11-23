# 截图替换简报契约

本页维护 `replace-brief.v1` 字段、坐标、素材种类和缺口计算。入口与调用边界见 [SKILL.md](../REFERENCE.md)；函数表见 [代码契约](code-contract.md)。

## 坐标

截图左上角为原点，X 向右、Y 向下。每个替换目标同时记录：

| 字段 | 含义 |
| --- | --- |
| `bbox_px_xyxy` | 像素整数 `[x0, y0, x1, y1]`，`x0 < x1`、`y0 < y1`，右/下为开区间上界，须落在截图宽高内 |
| `bbox_norm_xyxy` | 除以宽、高后的 `0..1` 值，与像素框在 0.5 像素内互推 |

只认框选，不把像素框宽高当成三维尺寸。遮挡、背面和截图外结构标为推定，不能写成已观测。

## 简报对象

顶层 `schema` 必须为 `replace-brief.v1`。`intent` 是用户原话或已确认的替换意图字符串，可为空但不能缺字段。

`screenshots` 至少一项：稳定 `id`、调用方给出的可读路径、像素 `width`/`height`。多张图须先确认是否同一画面版本；一个目标只绑定一个 `screenshot_id`。

`targets` 至少一项。每项：

| 字段 | 约束 |
| --- | --- |
| `id` | 简报内唯一、非空字符串 |
| `label` | 给人看的名称 |
| `role` | `replace` 需要素材；`keep` 或 `context` 只记录位置，不进入索取列表 |
| `screenshot_id` | 指向 `screenshots` |
| `bbox_px_xyxy` / `bbox_norm_xyxy` | 见上 |
| `evidence` | 截图中实际看见的轮廓、接触或遮挡 |
| `inferred` | 数组；看不见的部分。可为空数组 |
| `material_needed` | 仅 `role=replace` 必填：`minimum` 与 `preferred` 均为下面种类的非空子集，`notes` 为字符串可空 |
| `provided` | 已交给本任务的素材记录数组，缺省 `[]` |

素材种类只允许：`single_photo`、`multi_view_photos`、`existing_glb`、`measured_size`、`clean_cutout`。`preferred` 可以比 `minimum` 更完整，但不能出现种类表以外的值。

`provided` 每项含 `kind`、已存在的本地 `path`，以及写入产物时补上的 `sha256` 与字节数。脚本只核对文件存在和种类，不打开模型、不解码凭据。

## 缺口与索取

`request_gaps` 只处理 `role=replace`：若 `provided` 已覆盖该目标 `minimum` 中每一类，则 `status=ready` 且不生成索取项；否则 `status=awaiting_material`，生成一条 `requests` 记录。

索取记录字段：`target_id`、`label`、`ask`、`accepts`、`missing`。`ask` 由脚本按缺口种类套固定中文模板，不调用网络或模型。`accepts` 按种类给出期望扩展名提示（照片 `.png/.jpg/.jpeg/.webp`，模型 `.glb`，尺寸说明 `.txt/.json`，抠图 `.png`），不是 MIME 探测。

重叠框允许：两个目标可以共享像素。空框、越界、重复 `id`、未知 `screenshot_id` 或归一化与像素互推失败则整份简报失败。

## 产物

新建输出目录。成功时写入：

| 文件 | 内容 |
| --- | --- |
| `brief.json` | 补全尺寸、哈希、裁切路径、`status` 与 `requests` 后的简报 |
| `overlay.png` | 源截图副本上的框选与 id 标注，不改源文件 |
| `crops/<id>.png` | 每个 `role=replace` 目标的像素裁切 |
| `requests.json` | 仅 `awaiting_material` 的索取列表；全部就绪时为 `[]` |

源截图只读。输出目录必须原先不存在；失败时保留未完成目录供检查，不覆盖来源。
