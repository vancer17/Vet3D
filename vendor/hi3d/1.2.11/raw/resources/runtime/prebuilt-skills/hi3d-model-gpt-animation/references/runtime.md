# 独立运行与依赖

按入口打包约定物化完整分发目录后，hi3d-model-gpt-animation 入口可明确提供给目标 AI，通过其入口调用。生成用独立 hi3d-api，绑定与动作适配由独立 rig-retarget 工作流编排，通用 Blender 操作与共享原子实现按各包清单提供，按 [交接契约](rigging.md)明确实际目录；不要求复制整个仓库，不读取相邻工具或作者配置。

SKILL_DIR 为本包，RIG_SKILL_DIR 为独立 rig-retarget，RUN_DIR 为包外任务目录。Blender 操作用 Blender 5.x/自带 NumPy；拼图用 Python/Pillow；不需 SciPy 或 Hi3D 凭据。若另行执行绑定图求解，其依赖由 rig-retarget 自身说明。

```bash
"$PYTHON" "$SKILL_DIR/scripts/run.py" --help
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" \
  stage_ops inspect --input "$RUN_DIR/animated.blend" --report "$RUN_DIR/inventory.json"
"$PYTHON" "$SKILL_DIR/scripts/run.py" --rig-skill "$RIG_SKILL_DIR" contact_sheet --help
```

全局 --rig-skill 必须在本包命令名之前；Blender 命令名位于 -- 之后。入口延迟加载所选模块，只有检查总帮助不需依赖；其他命令明确加载同一份共享库。直接函数调用时显式添加两包 scripts 路径，再从 character 导入本包模块。目录存在与 CLI 执行不等于宿主已自动发现；单独记录验证范围。

舞台/布料离线回归：

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" \
  self_test --work-dir "$RUN_DIR/stage-test"
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" \
  test_cloth_contacts --work-dir "$RUN_DIR/cloth-test"
```

测试使用小型合成场景及包外新目录，不改用户前台工程、不提交服务。绑定与重定向测试从 rig-retarget 运行，不在这里重复实现。
