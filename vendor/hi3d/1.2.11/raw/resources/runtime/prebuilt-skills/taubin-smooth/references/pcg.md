# Taubin 的 PCG 交接

宿主读取 [routes](../pcg/routes.yaml)、[architecture](../pcg/architecture.yaml) 和 [编排提示](../../.dependency-pcg-view/references/host-orchestration.md)。会话、短回写、投影分别复用 [run-tools](../../.dependency-run-tools/REFERENCE.md) 与 [pcg-view](../../.dependency-pcg-view/REFERENCE.md) 的随包模块。调度、用户授权、视觉判断及 loop/compact 钩子属于宿主；文件存在不表示宿主已安装或执行这些钩子。

## 阶段与文件

一次业务任务只有一份 `pcg.session.v1`，在任务根保存 `session.json`；各次光顺另用 `smooth-v1/`、`smooth-v2/` 等全新目录。`board.json` 是执行画板，`view.json` 是选项决策页。三者是保留/可重建的控制资料，不作为业务产物递归追加。

| 槽 | 来源与判定 | 保留 |
| --- | --- | --- |
| `smooth.mesh` | 本版 `smoothed.blend`，保存重开检查成功，文件 SHA-256 与报告一致 | keep |
| `smooth.report` | 同目录 `report.json`，schema、源保持/重开/拓扑断言成功 | keep |

`tool_result.json` 是这两个槽的短回写信封，不是第三个交付槽。普通 Python API 返回完整报告不变；CLI 改为短回写，消费旧 stdout 报告的调用方应改读 `report.json`。成功回写的 `next_checkpoint=review` 仅表示进入人工/执行者视觉验收，不能立即标记 completed。

`smooth` 的 `blender.write` 包括另存新工程。执行前由宿主把用户已授权的源、对象、参数和目标范围记录在 session 的 `confirmations` 扩展字段中，含 checkpoint、权限名与授权依据；该字段是宿主说明，不改变共享 schema。明确请求光顺并另存即是对应授权，不需要重复确认。授权未覆盖具体写入范围时才走 option；不把 `confirm: true` 按钮误当已经收到确认。

## 可调用适配

[pcg_handoff.py](../scripts/pcg_handoff.py) 可在普通 Python 3.9+ 或 Blender Python 中导入；依赖从 [package.json](../package.json) 物化，无额外 YAML 库。

| 接口 | 行为 |
| --- | --- |
| `result_from_report(report_path)` | 只读验证成功报告与相邻 BLEND 当前哈希，生成标准短回写；用于新结果或 `review_only`。回写权限描述原光顺阶段，不表示本次验收重新写 BLEND；不验证外观，也不重跑光顺。 |
| `bind_report(session, report_path, task_root=...)` | 返回会话副本，绑定两个真实 keep 槽并通过共享 `apply_tool_result` 留痕。新版追加 sync、保留旧路径；相同 path/href/hash 不重复 append，也不重置已经完成的验收。新版进入 review/running，路由保留。拒绝任务根以外的产物或其他入口的 session。 |
| `project_session(session, task_root=...)` | 无写入、无 append，返回 `compose_board` + `locate_board` 和 `compose_view` 两张图；丢失的文件标 missing，最后路径与 traces 保留。 |
| `write_state(session, task_root=...)` | 先原子写 session，再写两份可重建投影；拒绝包内目录、不同任务覆盖、元数据符号链接。单写者，调用前读取磁盘最新 session；若投影写入中断，下次重投影即可。 |

独立调用本 skill 时，宿主在已物化 scripts 路径上使用这些接口：

```python
import json
from pathlib import Path
from session_schema import new_session
from pcg_handoff import bind_report, write_state

# task_root、task_id、authorization 来自当前任务，不能写回 skill 包。
root = Path(task_root).resolve()
session_path = root / "session.json"
session = (json.loads(session_path.read_text(encoding="utf-8"))
           if session_path.exists()
           else new_session("taubin-smooth", task_id=task_id, checkpoint="input"))
# 首次执行前持久化现有授权；未授权时不得伪造 authorization。
session.setdefault("confirmations", []).append({
    "checkpoint": "smooth", "irreversible": ["blender.write"],
    "evidence": authorization,
})
session.update(checkpoint="smooth", status="running")
write_state(session, task_root=root)

# 调用 SKILL 中的 Blender 命令，等待退出；退出 0 后核对真实报告再绑定。
# root / "smooth-v1" 必须是本次新目录，不可在失败后读取旧版成功回写。
session = json.loads(session_path.read_text(encoding="utf-8"))
session = bind_report(session, root / "smooth-v1/report.json", task_root=root)
write_state(session, task_root=root)
```

嵌入已有工作流时，使用父任务已有 session，把短回写的两个槽映射到父架构实际槽位，由父宿主调用共享 `apply_tool_result` 和父图投影；不另建第二个业务 session。本地适配只接受 `entry=taubin-smooth`，不会偷偷覆盖父任务。

## 验收、回退与恢复

- **视觉完成**：从 mesh/report 槽核对本版，实际打开模型查看轮廓、开边、薄片和细节。宿主在 session 记录实际检查范围与结论后设置 `checkpoint=review,status=completed` 并 `write_state`；未做视觉检查保持 running 或 waiting_choice，不填通过。
- **只验收已有结果**：采用 `route=review_only`，调用 `bind_report` 验证并登记已有报告；已经登记且未变的文件只重投影。原源可能不在本机，报告的 source_unchanged 仅是当时断言，不声称重新验证原文件。没有成功报告或哈希不符时不能冒充数值验收通过。
- **选项与回退**：设置 `status=waiting_choice` 时，`compose_view` 从 routes 提供 option；用户选择后更新 route/checkpoint/choices。调整参数回 input；review 回 smooth 只定位已有光顺阶段，不自动再次执行。回退不删除产物、不清 traces、不撤销已保存文件，新参数重跑使用新目录。
- **每轮与 compact**：重新读取磁盘 session，调用 `write_state`，无需新产物也重投影；不得为了重投影重放短回写。压缩残留保留任务根、当前检查点和 board 叶子的 path/href、traces 数。宿主必须实际接入循环与压缩触发点，本脚本不会注册 hooks。
- **失败与中断**：非零退出或捕获异常时，宿主将 session 标为 failed/interrupted 并重投影，保留当前阶段、旧产物及未知耗时；没有成功报告不能绑定 keep 槽。若实际出现未完成 BLEND，先核对文件存在，再以无 task/output 的诊断 artifact 登记真实路径，不冒充成功 mesh，且不得自动删除。未落盘回写但已有成功报告时，可在只验收路径核实后恢复，不能凭进程退出推断通过。
- **阶段计时**：纯原子能力由调用宿主按 [阶段记录契约](../../.dependency-run-tools/references/stage-records.md) 记录实际耗时，日志地址写 `session.timing_log`；本脚本不声称自动采集整个 Agent 流程或 token。

`keep` 不参与清理。缺文件、迁移目录或重开后的 hash 不符必须真实展示；不可为消除 missing 而自动重跑光顺。报告和 hash 是可信本地执行证据，不是签名证明，也不保证几何无自交或外部贴图已打包。
