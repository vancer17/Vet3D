# 业务阶段耗时

记录实际执行的 `input_analysis`、`site_selection`、`interface_design`、可选 `hi3d_*`、`load_working_copy`、`model_interface`、`structural_diagnostics`、`assembly`、`save_exports`、`roundtrip`、`render`、`visual_review` 和 `delivery`。局部修订只执行必要阶段，其余标 `skipped` 并说明原因。

包外任务目录的 `timings.jsonl` 每项包含 task_id、attempt_id、previous_attempt_id、stage、状态、带时区起止时间及 elapsed_seconds。进程内用单调时钟；失败、中断和已授权重试保留并关联原尝试。硬终止只有起点时保留 null、缺失原因和覆盖范围，不补零。恢复创建新候选目录和新尝试 ID，关联旧尝试；不覆盖旧文件。

`run.py` 自动记录 CLI 预检之后的加载、建模、结构诊断和保存/导出，以及本次执行区间的 `timing_summary.json`；开始事件在动作前落盘，正常/异常结束追加。新进程的 `--check` 只作预检，不写文件，执行者若要统计该阶段需另记实际时间。输出路径不可写或预检失败的时间由调用方记录，不能声称 CLI 已覆盖。

输入分析、选点、研究、上游生成、装配、渲染、回读和视觉审查由执行者在同一任务报告区补记真实时间。若只有带时区的墙钟起止点，标明其方法和范围；没有可靠计时就明确缺失。总墙钟取业务开始到结束区间，不累加重叠阶段；CLI 与其子阶段、云端等待与本地工作分别注明包含或重叠。

Token 可选，仅记录宿主/API 的真实 usage 和来源、覆盖范围及包含关系；任务总量不分摊，缓存/推理细项不重复累计，不用耗时、额度或字符数推算，不为补统计读取凭据或重跑任务。
