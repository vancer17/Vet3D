---
name: exhibition-tour
description: 将展品模型、图片和文字做成单展厅网页，支持热点说明、自由查看与可暂停的固定路线导览；虚拟展厅不充当测绘或 BIM。
---

# 展览导览

把本次提供的展品做成一个可进入的单展厅：点热点看说明，可自由看，也可按顺序自动导览。缺少介绍时用文件名并标待补，不编造展品历史。虚拟展厅只按展品数量布置，不是建筑测绘或 BIM。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$exhibition-tour` 或显式读取本文件调用。Python 3.10+、Node 22+。运行目录必须在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。文件用附件；缺展品文件时该展位显示占位，不阻断其他展位。取消保留已生成页面。公开发布另行确认。

## 输入与规划

导览模式说明见 [modes.json](references/modes.json)。默认两者兼有；用户未确认前不是已核实事实。已有空间必须提供真实文件；虚拟展厅自动布置。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_tour.py" \
  --brief "$RUN_DIR/brief.json" --modes "$SKILL_DIR/references/modes.json" \
  --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/inspect_models.py" \
  --plan "$RUN_DIR/plan.json" --media "$RUN_DIR/media" \
  --output "$RUN_DIR/models.json"
"$PYTHON" "$SKILL_DIR/scripts/build_hall.py" \
  --plan "$RUN_DIR/plan.json" --media "$RUN_DIR/media" \
  --skill-dir "$SKILL_DIR" --output "$RUN_DIR/hall"
```

展品 GLB 容器显式调用独立 [glb-clips](../.dependency-glb-clips/REFERENCE.md) 的 `read_glb` 校验；本包不复制解析器。展品图片尺寸与完整解码显式调用独立 [media-check](../.dependency-media-check/REFERENCE.md)；缺失图片不调用，展位保留占位。导览进度显式调用独立 [game-save](../game-save/SKILL.md) 的 `encode`/`decode`/`writeSave`。`tour.mjs` 只编排热点、暂停、继续、返回起点和走完路线。

## 预览、修改与交付

用户进入展厅、点击热点、开始/暂停/继续导览、返回起点。手动点热点时自动导览暂停，避免抢镜头。替换单个展品只重拷该文件。只有实际写出的三维文件才列入下载，不把虚拟平面布置当成 BLEND 工程。

资源加载用 `scripts/check_http.py` 对页面、模块及已复制展品/空间文件做 loopback GET。交互步骤显式调用独立 [game-browser-check](../game-browser-check/SKILL.md)，传入本次 URL 与热点/暂停/返回起点步骤；缺少 Playwright 时记录未做浏览器交互。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 HTML 与展品文件，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：展览网页、资源包、布局与导览 plan JSON、操作说明。

最小验收：完整走完路线、热点与展品 id 匹配、暂停后可继续、可返回起点；HTTP 下验证全部已复制展品及按需模块。

<!-- managed-by: sparc3d-runtime -->
