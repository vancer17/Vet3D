# 阶段计时与局部修订

首次执行时读取本文件，在包外任务目录保存 brief、plan、演示目录和运行记录；不写回能力包。计时口径唯一维护于 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)，由执行者落实；本包脚本不自动采集全流程耗时。

## 业务阶段

记录 `algorithm`、`contract`、`prefer`、`limits`、`run`、`revise`、`deliver`。局部修改只记录实际重跑阶段。复用 `records/stages.jsonl` 与 `records/timing-summary.json`。Token 仅在宿主提供真实 usage 时可选记录。

## 修订

改字段或限额时先读上一版 plan，新服务写入新输出目录。不自动重跑用户算法的收费依赖。
