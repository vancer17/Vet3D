---
name: replace-brief
description: 根据用户截图框出要分割替换的位置，生成裁切与标注，并列出仍需向用户索取的替换物件素材。适用于场景或产品图中替换单个或多个物件前的需求整理；不生成 3D、不调用分割服务、不代替下游装配。
---

# 截图替换简报

从已有截图标出要替换的区域，输出可核对的框选、裁切，以及向用户索取替换物件素材的缺口清单。

## 输入与完成结果

- 输入：一张或多张同一画面的截图、用户替换意图、执行者给出的目标框选；可选已经提供的照片/GLB/尺寸说明。
- 输出：包外新目录中的 `brief.json`、`overlay.png`、`crops/<id>.png` 和 `requests.json`。`requests.json` 为空表示替换目标的最低素材已齐，不是已经完成替换。

使用 `$replace-brief` 或显式读取本入口。先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，`SKILL_DIR` 为分发目录中的本 skill。Python 3.9+ 与 Pillow；无网络、不读取密钥。

```bash
"$PYTHON" "$SKILL_DIR/scripts/replace_brief.py" --check \
  --brief "$RUN_DIR/brief.json" --screenshot main "$SCREENSHOT"

"$PYTHON" "$SKILL_DIR/scripts/replace_brief.py" \
  --brief "$RUN_DIR/brief.json" --screenshot main "$SCREENSHOT" \
  --output "$RUN_DIR/replace-brief-v1"
```

`--screenshot` 可重复，值为截图 `id` 与本地路径。`--check` 只校验不写盘。字段、坐标和缺口规则读 [简报契约](references/contract.md)；函数入口读 [代码契约](references/code-contract.md)。`--help` 查看参数。

## 执行

按顺序读本入口、[检查点](pcg/routes.yaml) 与 [阶段产物](pcg/architecture.yaml)。框选由执行者对照截图填写；本包校验几何、裁切、标注并生成索取文本，不调用检测或分割模型。

| 阶段 | 操作与出口证据 |
| --- | --- |
| `input` | 确认截图文件可打开、意图、要替换/保留的对象，以及已交素材路径。已有合格产物走 `review_only`。 |
| `locate` | 为每个可独立替换的对象写稳定 id、像素框、可见证据与推定；脚本校验框在图内、写出 overlay 与 replace 裁切。 |
| `request` | 按每个 replace 目标的 `minimum` 核对 `provided`；缺项写入 `requests.json` 并原样向用户索取，不编造素材、不调用 Hi3D。 |

检查图拼版需要时由独立 [image-sheet](../.dependency-image-sheet/REFERENCE.md) 处理裁切序列，本入口不拼版。干净输入组装交给 [geometry-input](../.dependency-geometry-input/REFERENCE.md)；图生 3D 或网格拆件交给调用方另行提供的 [hi3d-api](../hi3d/SKILL.md)。人头分割不是本能力，见 [portrait-analysis](../.dependency-portrait-analysis/REFERENCE.md)。

## 关键边界

- 只定位和索取，不修改源截图，不生成网格、不提交收费任务、不把框选当真实尺寸或工程结构。
- `keep`/`context` 目标只帮助避免误换背景，不进入索取列表。一个可见对象不要拆成多个任务；不同对象不能共用一个 id。
- 输出目录必须新建。框越界、归一化与像素不一致、重复 id 或已交文件缺失时失败。文件存在不等于框选正确；须对照 overlay 与原图验收。
- 索取文本由缺口种类套模板生成。用户尚未提供素材时停在 `awaiting_material`，不能用截图局部冒充替换物件。

<!-- managed-by: sparc3d-runtime -->
