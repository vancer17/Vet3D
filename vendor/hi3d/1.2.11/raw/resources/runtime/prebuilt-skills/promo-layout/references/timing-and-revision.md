# 阶段计时与局部修订

首次执行时读取本文件，在包外任务目录保存 brief、plan、报告和运行记录；不写回能力包。计时口径唯一维护于 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)，由执行者落实；本包脚本不自动采集全流程耗时。

## 业务阶段

记录 `intake`、`prefer`、`review_plan`、`produce`（含每个尺寸的 svg-edit/合成）、`preview`、`deliver`。局部修改只记录实际重跑阶段，其余 `skipped` 并说明原因。复用 `records/stages.jsonl` 与 `records/timing-summary.json`。失败、取消保留已有文件，不自动开新目录重提。Token 仅在宿主提供真实 usage 时可选记录。

## 修订

更换标题、正文、裁切、颜色或版式时先读上一版 plan 与产物哈希，只重跑受影响尺寸。新版本写入新输出目录，确认后再更新交付引用。溢出或解码失败记录字段与文件，不静默截断。
