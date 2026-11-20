# 实现与资源契约

输入、输出和边界以 [入口](../SKILL.md) 为准。任务字段见 [契约](contract.md)。墙钟杀进程复用 `package.json` 物化的 `process_run.py`，唯一源是 [预算契约](../../.dependency-run-tools/references/budget-run.md)。

| 维护文件 | 函数或类型 |
| --- | --- |
| [scripts/task.py](../scripts/task.py) | `validate_task`, `load_task`, `digest_file`, `fingerprint` |
| [scripts/readers.py](../scripts/readers.py) | `identify`, `read_static` |
| [scripts/snapshot.py](../scripts/snapshot.py) | `select_checks`, `overall_status`, `profile_for` |
| [scripts/workspace.py](../scripts/workspace.py) | `prepare_workspace`, `unchanged`, `external_reference_paths` |
| [scripts/freecad_kernel.py](../scripts/freecad_kernel.py) | `assert_workspace_write`, `run` |
| [scripts/compare.py](../scripts/compare.py) | `build_checks` |
| [scripts/registry.py](../scripts/registry.py) | `append_record`, `load_records`, `build_view` |
| [scripts/report.py](../scripts/report.py) | `render_report` |
| [scripts/adapter.py](../scripts/adapter.py) | `FreecadAdapter`, `MockAdapter` |
| [scripts/verify.py](../scripts/verify.py) | `execute`, `main` |

`freecad_kernel.run` 只在 FreeCAD 进程内打开文档。普通 Python 可以导入写入边界检查，不会因此加载 FreeCAD。运行产物写在调用者给出的输出目录。无网络，不读取密钥。
