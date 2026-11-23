# Runtime 模式

仅在宿主提供公开 mdf_api 时使用；内部模式继续本入口原约定。

# 推荐：auto-rig 身体绑定与局部蒙皮修复

适用于需要新骨架的人形静止网格。已有合格绑定直接复用；头部表情、MetaHuman DNA 或必须保持既定骨架时沿用其专用流程。自动绑定只是起点，保体积修改器和归一化权重不能证明动作质量。

## 身体输入与服务交接

1. 保留原始工程，在副本确认静止姿态、轴向与单位。优先只提交代表人体结构的身体网格；衣服、护甲、头发和武器按语义分别处理。多个连续身体对象可在工作副本中合并；不同衣物层不按距离焊接。
2. 已有合格 LOD 直接用；需要最终减面/重烘时先完成 [LOD 交接](runtime-mesh-lod.md)。仅为调用制作代理时，可按输入限制减面、缩小副本纹理，回迁后仍交付原高模；代理预算和贴图尺寸由当前角色决定。
3. 读取 mdf-api skill，通过 Runtime `mdf_api` 使用当前桌面登录态，不需要 SDK、中控地址或回调网络。
4. 从工具 `files.rigged_mesh` 取得本地 GLB，检查 skin、权重、关节、材质、尺度后再回迁。参数契约见 mdf-api/references/mesh-invoke-api.md 的 auto-rig 节。

```bash
# BODY 是当前已确认的身体对象名。导出基础网格的静止坐标，不烘焙修改器或动作。
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- service_rig export \
  --input "$RUN_DIR/source.blend" --body "$BODY" \
  --output "$RUN_DIR/body.glb" --report "$RUN_DIR/export.json"
```

`export` 只导出所选对象的独立副本，保留材质；原文件和对象不改。`--faces N` 可选，仅对提交副本做本地 Decimate，不提供严格自交保护或纹理重烘。需要静态修改器、shape key 或多对象装配效果时先显式准备工作网格，不能把基础网格导出当作完整场景烘焙。

通过 Runtime mdf_api 调用（路径相对工作区）：

```json
{"action":"invoke","capability":"auto-rig","file":"exports/hi3d-body.glb","params":{"use_skeleton":false,"use_transfer":true,"num_beams":10},"jobPath":".hi3d/mdf/body-rig.json","outputDir":"exports/hi3d-body-rig","dryRun":true}
```

先 dryRun，再移除 dryRun 用相同参数正式调用；`waiting_choice` 交给宿主全局弹窗。上限 256 MiB，优先自包含 GLB；参数扁平，不传 options 或 $file。use_transfer 不保证逐点拓扑一致，use_skeleton 不保证骨名和层级精确保留。普通调用等待 2100 秒。UNKNOWN/断线不重提，保留原记录及 requestId；下载失败只用 download 恢复。

## 后续本地阶段

按 [现有回迁、局部修复与完整验收](service-rig.md#回迁到认可的高模) 继续；此后不再调用内部服务。公开 LOD 见 [Runtime LOD](runtime-mesh-lod.md)。
