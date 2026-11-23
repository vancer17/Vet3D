# 阶段计时与局部修订

首次执行时读取本文件，在包外任务目录保存模型、inventory、plan、网页和运行记录；不写回能力包。计时口径唯一维护于 [统一阶段记录](../../.dependency-run-tools/references/stage-records.md)，由执行者落实；本包脚本不自动采集全流程耗时。

## 业务阶段

记录 `asset`、`options`、`prefer`、`price`、`preview`、`revise`、`deliver`。无报价请求时 `price` 记 `skipped`。局部修改只记录实际重跑阶段。复用 `records/stages.jsonl` 与 `records/timing-summary.json`。Token 仅在宿主提供真实 usage 时可选记录。

## 修订

改色板、互斥或镜头时先读上一版 plan 与模型哈希，不重新生成已有模型。新页面写入新输出目录。导入失败保留旧配置。
