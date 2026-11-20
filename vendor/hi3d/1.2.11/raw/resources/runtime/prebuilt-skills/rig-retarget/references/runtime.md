# 运行与独立使用

按入口打包约定在仓库外物化完整分发目录，再显式提供 rig-retarget 入口；脚本与必要资源随包提供，无需原仓库或原动画工作流。保留分发目录内的文档与依赖布局。宿主支持的技能目录以当前环境为准；目录复制和 CLI 成功不证明宿主新会话已自动发现。显式路径读取入口与宿主自动发现分别验证，不为维护擅自覆盖用户已安装副本。

`SKILL_DIR` 为当前实际包路径，`RUN_DIR` 为包外任务目录。所有缓存、映射、模型、报告和计时存到任务目录；不同候选使用新路径，保留原文件。直接 Python 调用显式将本包 scripts 加入 sys.path，再按需 `from rigging.service_rig import inspect_skin`；已有输入无需执行上游工作流，也不依赖 cwd。

| 能力 | 依赖 |
| --- | --- |
| 比例种子 `make_profile` | Python 标准库 |
| 既有工程检查/骨轴/缓存/动作、服务权重回迁及修复 | Blender 5.x 的 Python/NumPy；适配器写 layered Action，需要 Action slots |
| BVH 输入 | Blender 的 BVH 导入器；安装/启用可用导入器，不推断所有版本自带 |
| VMD/MMD 输入 | 单独提供可信的 MMD 导入能力和匹配的源参考骨架；先让 Blender 正确求值，再走通用 cache；本包不带 VMD 下载器、参考角色或 MMD 插件 |
| 外部图权重 | Python + NumPy/SciPy；可在独立环境计算 NPZ |
| Blender 内图权重测试 | 与 Blender Python ABI/系统/架构一致的 SciPy，通过 --python-packages 显式提供 |
| 请求 auto-rig/mesh-lod | 完整独立 mdf-call 和可达部署；本地已有输入不需要网络依赖 |

```bash
"$PYTHON" "$SKILL_DIR/scripts/run.py" --help
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- \
  --timing-log "$RUN_DIR/timings.jsonl" --task-id "$TASK_ID" \
  rig_adapter inspect --input "$RUN_DIR/character.blend" \
  --rig "$RIG_OBJECT" --report "$RUN_DIR/inventory.json"
```

全局选项在命令名之前，Blender 参数分隔符之后；`--timing-log` 用于自动计量此命令阶段，其他编排阶段按 [计时](timing.md)补齐。CLI 只加载该命令的依赖；普通 Python 查看总帮助不导入 bpy。`rig_adapter` 子命令为 inspect/cache/calibrate/retarget，保存完整 JSON，终端只输出报告路径。其他既有 CLI 保留各自输出契约。

本地回归均使用包外新目录，不调用真实服务：

```bash
"$PYTHON" "$SKILL_DIR/scripts/run.py" test_skin_weights
"$PYTHON" "$SKILL_DIR/scripts/run.py" test_weight_graph -v
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- test_service_rig --work "$RUN_DIR/service-test"
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- test_retarget --work "$RUN_DIR/retarget-test"
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- test_pipeline \
  --work-dir "$RUN_DIR/pipeline-test" --python-packages "$BLENDER_COMPATIBLE_PACKAGES"
```

这些测试验证合成几何上的计算、数据保护和组件交接，不证明任意生产角色视觉质量。实际验证环境和结果随维护任务存放，不写入本包执行日志。
