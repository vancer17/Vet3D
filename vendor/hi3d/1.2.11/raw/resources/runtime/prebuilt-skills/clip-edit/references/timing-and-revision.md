# 阶段计时与局部修订

记录写在包外任务目录。口径见 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)。阶段为 `intake`、`prefer`、`review_plan`、`preview_cut`、`produce`、`preview`、`deliver`。低分辨率预览与成片导出分开计时；字幕与混音仅在实际调用时记录。无法解码的素材记 `failed` 并列出路径，不自动丢掉中间段。Token 可选且仅记录真实 usage。
