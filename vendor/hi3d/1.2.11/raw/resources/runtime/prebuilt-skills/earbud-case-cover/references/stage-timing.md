# 业务阶段耗时记录

调用本业务工作流时必须记录：设备识别/来源研究、概念/Hi3D或已有源、源拟合/精密内腔/分盖/接口、固定与开盖/插线/装卸验证、渲染/编码/回读、网页与下载验收。按实际执行拆分，已有输入阶段标skipped并说明复用；维护/迁移Skill本身无需统计。

启用外形减薄时，在源拟合与精密建壳之间记录 `exterior-thinning` 阶段及其尝试状态；未启用标 skipped，恢复使用已有 thinned 源时记录复用来源。变换摘要不含完整业务计时，仍由执行者按统一契约补齐。

执行前读取 [统一阶段记录契约](../../.dependency-run-tools/references/stage-records.md)，按其事件身份、时钟、恢复、汇总与可选 token 规则记录。本工作流由执行者在包外任务产物目录保存 `stage-timing.jsonl` 和摘要，沿用 `task_id`、`stage_id`、`attempt`、`status`、`started_at`、`ended_at`、`elapsed_seconds` 字段，并表达统一契约要求的父阶段、恢复来源和缺失原因。

脚本已有的局部 `seconds`/log 只覆盖其实际调用；执行者负责补齐上述完整业务阶段，不能据此声称脚本自动采集了重试或网页阶段。
