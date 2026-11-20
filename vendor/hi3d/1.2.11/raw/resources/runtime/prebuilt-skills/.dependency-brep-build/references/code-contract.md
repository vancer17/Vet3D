# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。配方字段以 [配方契约](contract.md) 为准。墙钟杀进程复用 `package.json` 物化的 `process_run.py`，唯一源是 [run-tools 预算契约](../../.dependency-run-tools/references/budget-run.md)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/brep_spec.py](../scripts/brep_spec.py) | `validate_spec`, `parse_designation`, `estimate_budget`, `load_spec`, `spec_digest` |
| [scripts/brep_kernel.py](../scripts/brep_kernel.py) | `require_cadquery`, `build_spec`, `main` |
| [scripts/brep_build.py](../scripts/brep_build.py) | `prepare_output`, `run_kernel`, `build_output`, `main` |

建模需要 CadQuery。`--check` 与配方校验不导入 CadQuery。运行产物写包外路径。无网络、不导入 `bpy`。
