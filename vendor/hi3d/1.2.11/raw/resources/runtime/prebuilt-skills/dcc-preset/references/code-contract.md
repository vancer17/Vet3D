# 代码契约

| 函数 | 输入 | 输出 | 失败 |
| --- | --- | --- | --- |
| `catalog.lookup` | 可选 app、topic、version、preset id | 公开字段和 `applicable` | 版本字符串无法解析时抛出 `ValueError` |
| `catalog.parse_version` | `5.7` 或 `5.7.1` | 三元整数；其他文本返回 `None` | 不猜测发行名 |
| `unreal_project.plan_enable` | 已解析工程、预制 id、可选引擎版本 | `ready`、`rejected` 和将要改动的插件名 | 未知预制、插件数组损坏、版本冲突 |
| `unreal_project.apply_enable` | `.uproject` 路径、是否 `--write` | 同上，并在有改动且 `write` 时替换文件 | 拒绝和空改动都不写文件 |
| `dcc_preset.main` | lookup 或 apply 参数 | 标准输出和可选 `result.json`；退出码 0 完成、2 拒绝、3 缺宿主程序 | 宿主命令非零时记 `rejected`，不把退出码 0 当成画面通过 |

`blender_fluid_domain.py` 与 `houdini_ocean_spectrum.py` 只在对应宿主进程里执行。前者保存域和流入，后者在类型存在时保存一个 SOP。两边都不启动模拟缓存。
