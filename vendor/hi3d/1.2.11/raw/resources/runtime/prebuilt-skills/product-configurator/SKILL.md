---
name: product-configurator
description: 为已有产品模型制作颜色、材质显示和部件显隐的交互配置页；互斥规则生效；无报价时不显示虚构总价；默认不含支付库存订单。
---

# 产品配置器

为**已经存在**的产品模型做可操作配置页：改显示颜色、显隐已有部件、恢复初始状态、导出配置。不把配置页当成产品设计、制造或变现收银。颜色切换只改变显示，不是物理材质验证。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF；需要新模型时由用户另行提供已有 GLB。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$product-configurator` 或显式读取本文件调用。Python 3.10+、Node 22+。运行目录必须在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。缺模型时提示用聊天附件提供。取消保留已生成页面。公开发布另行确认。

## 输入与规划

版式说明见 [styles.json](references/styles.json)。默认简洁展示，用户未确认前不是已核实事实。报价仅在用户要求时收集币种、基础价和选项价；缺失时页面不显示总价。

```bash
"$PYTHON" "$SKILL_DIR/scripts/inspect_parts.py" \
  --model "$RUN_DIR/model.glb" --output "$RUN_DIR/inventory.json"
"$PYTHON" "$SKILL_DIR/scripts/plan_config.py" \
  --brief "$RUN_DIR/brief.json" --inventory "$RUN_DIR/inventory.json" \
  --styles "$SKILL_DIR/references/styles.json" --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/build_page.py" \
  --plan "$RUN_DIR/plan.json" --model "$RUN_DIR/model.glb" \
  --skill-dir "$SKILL_DIR" --output "$RUN_DIR/configurator"
```

部件清单显式调用独立 [glb-clips](../.dependency-glb-clips/REFERENCE.md) 的 `read_glb` 读取容器 JSON，列出节点、材质与外部纹理；本包不复制 GLB 解析器。先展示识别结果，不要求用户抄写已读到的名称。模型不能独立选择目标部位时说明，并收集 `splitDecision`：`continue-as-whole` 或 `need-split`（后者停止，不假装已拆件）。

配置状态显式调用独立 [game-save](../game-save/SKILL.md) 的 `encode`/`decode`/`writeSave`：导入先 decode，失败不覆盖。`rules.mjs` 只编排色板、显隐、互斥与可选合计。

## 预览、修改与交付

用户切换选项、恢复初始、切换预设视角；非法组合禁用并解释原因。模型加载失败显示重试和下载入口。支付、库存、订单标为未实现，不提供能点击却无结果的按钮。

资源加载用 `scripts/check_http.py` 对页面、JS 模块、模型及已复制纹理做 loopback GET。交互步骤显式调用独立 [game-browser-check](../game-browser-check/SKILL.md)，传入本次 URL 与改色/显隐/恢复/导入步骤；缺少 Playwright 时记录未做浏览器交互。需要静帧截图时显式调用独立 [model-preview](../.dependency-model-preview/REFERENCE.md)，按当前姿态出图；未调用则不列出截图下载。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 HTML、GLB 与 plan JSON，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：交互网页、模型与实际复制的纹理、配置 JSON、运行说明；截图仅在实际写出后提供。

最小验收：各选项影响指定材质或节点、互斥有效、恢复默认一致、导出配置可再导入；HTTP 下检查模型、纹理和页面模块。

<!-- managed-by: sparc3d-runtime -->
