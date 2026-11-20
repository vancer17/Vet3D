# 运行与交付

## 路径与依赖

按入口打包约定提供完整分发目录；`scripts/`、`references/`、示例资源及引用的依赖文档保持有效。将实际安装位置记为 `SKILL_DIR`，本次任务目录记为 `TASK_DIR`，均在运行时解析为绝对路径。业务输入与输出放任务目录，避免写入 skill 安装目录。

普通 Python 3.9+ 用于配置、接口发现、计时和文件检查；涉及 `bpy` 的操作必须在 Blender Python 中执行。参考路线使用 Blender 4.3.2，其他版本按实际结果判断兼容性。未因格式对齐将它改为其他 skill 使用的 Blender 5.x。JSON 任务与原子函数见 [脚本接口](code.md)。所有样例先复制到包外任务目录；配置预检会拒绝包内 output_dir。

```bash
python3 "$SKILL_DIR/scripts/run.py" --help
python3 "$SKILL_DIR/scripts/run.py" --describe
python3 "$SKILL_DIR/scripts/run.py" "$TASK_DIR/job.json" --check
```

以上命令不启动 Blender、不执行造型模块；正式执行另用下面的 Blender 入口。宿主需要更多依赖时按当前操作提供，本包不自动安装软件或启动服务。

## 命令行与 GUI

优先使用可用的 Blender 命令行入口。先核实工具存在和已有工程状态，不要假定作者机器的安装路径适用于新环境。调用形式如下，变量使用当前任务实际值：

```bash
"$BLENDER_BIN" --background --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- "$TASK_DIR/job.json" --mode preview
```

`preview` 构建并保存工程，跳过 GLB 导出；用户要求导出时选 `deliver` 并在任务配置中指定整排或逐件输出。脚本不自动生成相机、标签、地台或渲染图；需要这些交付时，由 GPT 在任务专属脚本中完成并核对结果。

`run.py --job ...` 与旧 `parts_pipeline.py --job ...` 继续可用，均调用唯一流水线。Blender 自身可能向终端输出日志，机器分析读取产物目录的 `report.json`，不要假定 Blender 整个 stdout 只有一个 JSON。失败既看外层非零退出，也看报告的阶段和质量检查。

若命令行因已诊断的图形初始化等环境问题失败，可通过受支持的电脑控制工具进入已打开 Blender 的 Python Console。先确认光标位于空白提示符，再执行任务桥接脚本：

```python
exec(open('/实际任务目录/run_in_blender.py', encoding='utf-8').read())
```

桥接脚本显式加载本工作流的 runner 并调用 `run_job`；GUI 中如需切换场景或编辑器，使用一次性 `bpy.app.timers.register` 回调，待当前 Console 调用结束再执行。后台脚本应直接调用，不能注册 timer 后立即退出。发生粘贴超时先检查界面，文字可能已经粘入，避免重复执行。

不因某次机器故障默认所有环境都走 GUI，不反复重试相同的已诊断崩溃。不要工厂重置、重载用户偏好或全局删除对象来获得空场景。

## Blender 上下文

- 在任务场景与视图层操作，明确所需模式与选择；primitive operator 完成后从 `bpy.context.view_layer.objects.active` 读取并检查活动对象。
- 按 `node.type == 'BSDF_PRINCIPLED'` 寻找材质节点，避免界面语言改变名称导致失败。
- 如需调整视图，只修改目标编辑器。切换 `area.type` 后不要沿用旧 `spaces.active`；查找类型为 `VIEW_3D` 的 space。
- 创建独立任务场景，保留用户工程。保存、临时副本及选择等副作用以 [脚本接口](code.md) 为准；模块不得任意修改其他场景。

## 验收与状态

检查部件数量、集合归属、根对象、坐标、非空几何和排列边界，再观察造型。有导出时，核对导出对象列表，逐件输出应在约定的原点，整排应保留布局；重新载入 GLB，确认轮廓、材质、部件和坐标未丢失。仅需 `.blend` 的预览任务跳过导出检查。

报告区分构建、保存、导出、跳过与失败；渲染只有在图像实际写入并检查后才算完成。文件存在和非零大小是第一层检查，不能替代重开与视觉 QA。失败时保留可用工程、日志和配置，修正具体失败阶段；不要覆盖已认可产物或将旧文件当新结果。

使用此 skill 建模时仍需执行相应输出验证，不能引用之前另一角色的成功记录代替本次检查。

## 离线维护检查

普通 Python 可在任意工作目录执行 `python3 -m unittest discover -s "$SKILL_DIR/tests" -v`。这些测试验证纯计算、配置、调用适配、模拟阶段编排和计时；不启动 Blender，不生成实际 3D 模型，不等于真实保存/导出/回读已验证。按入口打包约定在仓库外物化完整分发目录，另复制示例到任务目录，再做 `--check`，避免同仓库文件掩盖缺失依赖。
