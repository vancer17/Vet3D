# 阶段计时与局部修订

首次执行时读取本文件，在包外任务目录保存 brief、plan、展厅网页和运行记录；不写回能力包。计时口径唯一维护于 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)，由执行者落实；本包脚本不自动采集全流程耗时。

## 业务阶段

记录 `exhibits`、`space`、`prefer`、`layout`、`run`、`revise`、`deliver`。已有空间文件时 `space` 拷贝该文件；虚拟展厅不写三维工程。局部修改只记录实际重跑阶段。复用 `records/stages.jsonl` 与 `records/timing-summary.json`。Token 仅在宿主提供真实 usage 时可选记录。

## 修订

改顺序、停留时间或说明时先读上一版 plan 与资源哈希，只重拷变更展品。新页面写入新输出目录。
