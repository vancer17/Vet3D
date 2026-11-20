---
name: promo-layout
description: 从品牌或产品名称、准确文案与可选产品图生成方图、横幅和竖版海报；文字与图像分层且禁止静默截断；交付 PNG、可编辑 SVG/HTML、素材参数包与阶段耗时。无产品图时必须明确纯文字版式。
---

# 宣传物料

按本次确认的品牌名称、准确文案和素材，生成三种固定版式的宣传图。文字保持独立图层，不写入生成背景；缺少产品图时必须明确选择纯文字版式，不能用示例图顶替。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF；本地文件编辑使用随包脚本与独立原子能力。

## 独立工作流与依赖

执行前按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$promo-layout` 或显式读取本文件调用。Python 3.10+、Pillow；矢量导出需要 Inkscape 1.2+。运行目录必须在包外。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。

先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。宿主按 [编排约定](../.dependency-pcg-view/references/host-orchestration.md) 维护会话；本包不实现 Agent 引擎。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。返回上一步保留输入；重新执行保留上一版产物。失败和取消后不自动启动新付费任务。取消只停止后续本地步骤，保留已生成文件；本入口无远端生成任务，不能把停止等待写成远端取消。

1. 说明用途、必需素材（品牌/产品名、准确文案；产品图或明确的纯文字版式）和最终 PNG/SVG/HTML。
2. 文件用附件；文案表单保留草稿。缺项定位到对应字段。
3. 展示推荐规格与配色效果，允许沿用；品牌名和准确文案不能用默认值代替。
4. 检查素材列表、输出规格和缺失项；已有执行授权则继续。本流程无对外发布和新增云端费用。
5. 执行时显示当前阶段并提供取消。
6. 预览真实 PNG/HTML；长文案溢出必须失败并指出字段，禁止静默截断。字体缺失时报告替代字体。
7. 修改标题、正文、主图裁切、颜色或版式时只重跑受影响尺寸；重试前检查已有任务目录，避免覆盖未知文件。
8. 逐项下载与打包；只提供真实存在的文件。网页交付前用本地 HTTP 打开，检查资源和文字图层仍可编辑。

## 输入与版式

推荐三种规格见 [版式坐标](references/layouts.json)：方图 1080×1080、横幅 1920×1080、竖版海报 1080×1920。用户确认前不得把推荐值当成已核实事实。配色、使用场景和裁切来自本次 brief。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_layouts.py" \
  --brief "$RUN_DIR/brief.json" --layouts "$SKILL_DIR/references/layouts.json" \
  --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/overflow_check.py" \
  --plan "$RUN_DIR/plan.json" --output "$RUN_DIR/overflow.json"
```

溢出检查失败时回到文案或字号，不缩小画布偷偷裁字。

## 生成与分层

版式与文字图层显式调用独立 [svg-edit](../svg-edit/SKILL.md)，传入本次 `plan.json` 中每个尺寸的 `svg` 配方，接收 `hi3d-artwork.svg` 与 PNG；输出目录必须新建。`svg-edit` 不嵌入本地位图，产品主图留在 HTML/PNG 合成层，文字不烘焙进生成背景。

有产品图时，用 `scripts/compose_png.py` 按 brief 裁切放入图像区，再叠独立文字；用 `scripts/write_html.py` 写出图像与文案分离的 HTML。纯文字版式跳过主图合成。

尺寸与完整解码显式调用独立 [media-check](../.dependency-media-check/REFERENCE.md)，核对每个 PNG 的宽高并完整载入像素。三尺寸对照可显式调用独立 [image-sheet](../.dependency-image-sheet/REFERENCE.md)，输入有序 PNG 与规格标签，接收检查图；对照不能代替逐张溢出结论。

## 预览、修改与交付

分别展示各尺寸真实文件。修改单项文案或裁切时保留其他已通过尺寸的上一版。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 PNG、SVG/HTML 与参数 JSON，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：各尺寸 PNG、可编辑 SVG、分层 HTML、brief/plan/overflow JSON。仅在对应文件实际写出后提供下载。HTML 须本地打开确认文字仍为 DOM 文本而非烘进图片。

最小验收：中文长标题仍可读或明确溢出失败、三种尺寸无溢出、编辑文案后新输出更新且旧版保留。

<!-- managed-by: sparc3d-runtime -->
