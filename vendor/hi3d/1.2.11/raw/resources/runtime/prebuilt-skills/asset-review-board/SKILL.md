---
name: asset-review-board
description: 将本地图片、视频和模型按资产分成版本，并排或单版对比并写下批注；批注绑定原版本，导入失败不覆盖，不提供协作账号云端。
---

# 资产审阅看板

把本次提供的图片、模型和视频按**同一资产的版本**做成可对比看板：默认并排，只有一版时单版切换。写下批注并绑定原版本；刷新后仍在。不要把不同作品当成前后版。批注模板不是质量结论。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$asset-review-board` 或显式读取本文件调用。Python 3.10+、Node 22+。运行目录必须在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。文件用附件。取消保留已生成页面。公开发布另行确认。存储失败时页面给出醒目提示并立刻提供导出。

## 输入与规划

审阅版式与可选维度见 [review.json](references/review.json)。默认并排对比；仅一版时强制单版。可选维度为外观、结构、运动或自由，默认自由，不作为质量裁决。文件名版本不明确时必须给出 `assetId`，不能把无关文件排成序列。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_review.py" \
  --brief "$RUN_DIR/brief.json" --review "$SKILL_DIR/references/review.json" \
  --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/inspect_models.py" \
  --plan "$RUN_DIR/plan.json" --media "$RUN_DIR/media" \
  --output "$RUN_DIR/models.json"
"$PYTHON" "$SKILL_DIR/scripts/build_board.py" \
  --plan "$RUN_DIR/plan.json" --media "$RUN_DIR/media" \
  --skill-dir "$SKILL_DIR" --output "$RUN_DIR/board"
```

模型版本显式调用独立 [glb-clips](../.dependency-glb-clips/REFERENCE.md) 的 `read_glb` 校验容器；本包不复制解析器。图片与视频尺寸、时长与完整解码显式调用独立 [media-check](../.dependency-media-check/REFERENCE.md)；缺失文件不调用。批注存档显式调用独立 [game-save](../game-save/SKILL.md) 的 `encode`/`decode`/`writeSave`：导入先 decode，失败不覆盖；覆盖导入需要授权并保留备份。`notes.mjs` 只编排添加、编辑、状态、版本绑定与合并导入。

## 预览、修改与交付

用户添加/编辑批注、切换 pending/done。图片批注用 0–1 的 uv，视频用时间 t，模型用部件加视角或整体。对比可同步相机与播放；视频时长不同时给出不能对齐的警告。批注不自动迁到新版本。刷新后从存档恢复。多人实时协作、账号、云端同步标为未实现，不提供能点击却无结果的按钮。

资源加载用 `scripts/check_http.py` 对页面、模块及已复制图片/视频/模型做 loopback GET。交互步骤显式调用独立 [game-browser-check](../game-browser-check/SKILL.md)，传入本次 URL 与添加批注/改状态/导入失败步骤；缺少 Playwright 时记录未做浏览器交互。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 HTML 与媒体文件，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：审阅网页、资源包、plan JSON、批注导出、操作说明。

最小验收：可添加、编辑、改状态；刷新后批注仍在且绑原版本；导入失败不覆盖；模型、视频和图片各用一个样例在 HTTP 下检查。

<!-- managed-by: sparc3d-runtime -->
