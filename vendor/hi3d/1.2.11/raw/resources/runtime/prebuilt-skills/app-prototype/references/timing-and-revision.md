# 阶段计时与局部修订

首次执行时读取本文件，在包外任务目录保存 brief、plan、网页和运行记录；不写回能力包。计时口径唯一维护于 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)，由执行者落实；本包脚本不自动采集全流程耗时。

## 业务阶段

记录 `business`、`data`、`prefer`、`flow`、`run`、`revise`、`deliver`。局部修改只记录实际重跑阶段，其余 `skipped` 并说明原因。复用 `records/stages.jsonl` 与 `records/timing-summary.json`。失败、取消保留已有文件，不自动开新目录重提。Token 仅在宿主提供真实 usage 时可选记录。

## 修订

更换字段或流程时先读上一版 plan 与产物哈希，只重跑受影响页面。新版本写入新输出目录，确认后再更新交付引用。导入失败保留旧存档并记录原因。
