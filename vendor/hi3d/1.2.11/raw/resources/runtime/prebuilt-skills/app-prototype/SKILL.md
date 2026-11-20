---
name: app-prototype
description: 把明确业务流程做成列表、详情、编辑三页网页并本地保存；示例数据必须标注；导入失败不覆盖；登录支付与多人同步显示为未实现。
---

# 业务 App 原型

把本次确认的业务流程做成可操作网页：列表、详情、编辑，以及本地持久化。不编造登录、支付或多人同步。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$app-prototype` 或显式读取本文件调用。Python 3.10+、Node 22+。运行目录必须在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。宿主按 [编排约定](../.dependency-pcg-view/references/host-orchestration.md) 维护会话。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。返回上一步保留输入；重新执行保留上一版产物。失败和取消后不自动启动新付费任务。取消只停止后续本地步骤，保留已生成文件。

1. 说明用途、必需输入（谁、场景、管理对象、最重要一次操作）和最终 HTML/源码。
2. 字段与状态用表单；缺项定位到对应字段。已有完整需求时跳过提问。
3. 展示表格、卡片、双端自适应及推荐理由，允许沿用；业务事实不能用默认值代替。
4. 检查页面关系、字段和示例操作；已有执行授权则继续。公开发布另行确认。
5. 执行时显示当前阶段并提供取消。
6. 用户实际完成新增、查看、编辑与筛选；错误定位到字段。
7. 按页面、字段或规则修改时只重跑受影响输出；迁移本地数据时先备份。
8. 逐项下载与打包；只提供真实存在的文件。网页交付前用本地 HTTP 打开，检查模块与页面。

## 输入与规划

预约、库存、作品管理示例见 [示例数据](references/examples.json)，选择示例时记录必须带 `example: true`，不能标成真实业务数据。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_app.py" \
  --brief "$RUN_DIR/brief.json" --examples "$SKILL_DIR/references/examples.json" \
  --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/build_app.py" \
  --plan "$RUN_DIR/plan.json" --skill-dir "$SKILL_DIR" --output "$RUN_DIR/app"
```

本地记录显式调用独立 [game-save](../game-save/SKILL.md) 的 `encode`/`decode`/`writeSave`：先 decode 备份，校验通过后再写入同一槽位；导入失败不覆盖旧数据。产物目录中的 `records.mjs` 只做字段校验、筛选与备份编排，不另写存档格式。

## 预览、修改与交付

用户须完成一次新增与编辑、必填校验、刷新后记录仍在、导出后再导入。登录、支付和多人同步在页面上标为未实现，不提供能点击却无结果的按钮。清空真实数据需明确授权。

资源加载用 `scripts/check_http.py` 对列表、详情、编辑页及 JS 模块做 loopback GET。交互步骤显式调用独立 [game-browser-check](../game-browser-check/SKILL.md)，传入本次页面 URL 与新增/编辑/筛选步骤；缺少 Playwright 时记录未做浏览器交互，不能把 HTTP 200 当成操作验收。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 HTML/JS 与 plan JSON，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：三页 HTML、`app.js`/`records.mjs`/`hi3d-core.mjs`、plan JSON、导入导出说明。仅在文件实际写出后提供下载。发布为独立可选步骤。

最小验收：完整新增与编辑一次、必填校验定位到字段、刷新恢复、导出后重新导入；最终页面及按需资源通过实际 HTTP 加载检查。

<!-- managed-by: sparc3d-runtime -->
