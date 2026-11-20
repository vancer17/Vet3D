# 绑定与动画适配交接

需要新身体绑定、高模权重回迁、局部拉伸修复、骨轴校准、BVH/MMD/VMD 等序列适配时，显式提供完整独立 `rig-retarget/` 包，安装到宿主发现目录或明确其实际路径并读取 SKILL.md。仓库源码位置 workflows/rig-retarget 是查找线索，脚本不自动寻找相邻目录。

`RIG_SKILL_DIR` 为该包实际位置，`SKILL_DIR` 仍是本动画编排包。交接原模型/工程、服务原始 GLB（有则提供）、目标动作/帧范围/fps、对象名单和保留项，以及包外任务目录。接收 `.blend`、Action/映射、来源/修复规则、检查范围/残留问题和计时，继续舞台、布料或交付；已有合格蒙皮不重绑。

按需读取 rig-retarget 的：

- references/service-rig.md：新身体 auto-rig 输入、服务返回到高模权重回迁、检查与局部修复。
- references/geometry-and-binding.md、dense-skinning.md：自建校准骨架、连续皮肤域、图权重和外部 NPZ 求解。
- references/existing-rig.md、motion-and-hands.md：已有骨架的 rest/T-A 对齐、手指、脚步与序列烘焙；原 BVH builder 的掌腕路径。
- references/mesh-lod.md、game-delivery.md：明确需要 LOD、游戏动作、挂点与导出时的交接。
- references/validation.md、timing.md、code.md：全段形变验收、阶段统计与原子接口。

原本属于本包的 prepare_mesh/make_profile/build_character/cache_bvh/service_rig/validate_blend/weight_graph 及其绑定测试，现从 rig-retarget 的 scripts/run.py 直接调用，命令参数保留；新已有骨架适配为 rig_adapter。旧 character.* 绑定模块不再维护兼容副本。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$RIG_SKILL_DIR/scripts/run.py" -- rig_adapter inspect \
  --input "$RUN_DIR/character.blend" --rig "$RIG_OBJECT" --report "$RUN_DIR/rig.json"
```

本包剩余舞台/接触/预览命令也复用该包的 io_utils、blend_common 和 mesh_digest 原子能力。通过全局参数显式加载，原子函数导入不执行绑定、不访问网络：

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" \
  stage_ops inspect --input "$RUN_DIR/animated.blend" --report "$RUN_DIR/stage.json"
```

函数级复用时先显式把 RIG_SKILL_DIR/scripts 和本包 scripts 加入 sys.path，再导入 rigging 与 character；不设置永久系统路径，也不复制共享函数。依赖缺失说明该脚本需要的包，可继续不依赖脚本的已有资产检查与编排。身体改动后向下游标记需重建的衣物/接触缓存；不要从静止或服务成功状态推断动画合格。
