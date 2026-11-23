# 推荐：auto-rig 身体绑定与局部蒙皮修复

适用于需要新骨架的人形静止网格。已有合格绑定直接复用；头部表情、MetaHuman DNA 或必须保持既定骨架时沿用其专用流程。自动绑定只是起点，保体积修改器和归一化权重不能证明动作质量。

## 身体输入与服务交接

1. 保留原始工程，在副本确认静止姿态、轴向与单位。优先只提交代表人体结构的身体网格；衣服、护甲、头发和武器按语义分别处理。多个连续身体对象可在工作副本中合并；不同衣物层不按距离焊接。
2. 已有合格 LOD 直接用；需要最终减面/重烘时先完成 [LOD 交接](mesh-lod.md)。仅为调用制作代理时，可按输入限制减面、缩小副本纹理，回迁后仍交付原高模；代理预算和贴图尺寸由当前角色决定。
3. 显式提供独立 `mdf-call` 工具的实际目录 `MDF_DIR`，读取其 `SKILL.md`。推荐从用户指定的调用主机走默认 HTTP 中控；中控负责与 worker 往返。SDK 直连仅在 worker 能回连调用方时显式选择。队列已接受而输入未取回时先区分回调网络与算法失败，不迁移执行主机、不在超时后自动切换传输重提。
4. 保存返回原始 GLB，按 `invocation.json.files` 的 `field_path=["rigged_mesh"]` 找产物。检查 skin、关节索引、权重、材质、坐标和尺度，再回迁；无需重写客户端，也不为本地修复重复调用。

本工作流的本地命令只需 Blender/NumPy；网络调用才需独立 mdf-call。完整服务参数可由另行提供的 `service-select` 的 auto-rig 服务页确认。下面是已确认的人形 GLB 最小交接，不要求额外安装 service-select 才能使用。

```bash
# BODY 是当前已确认的身体对象名。导出基础网格的静止坐标，不烘焙修改器或动作。
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- service_rig export \
  --input "$RUN_DIR/source.blend" --body "$BODY" \
  --output "$RUN_DIR/body.glb" --report "$RUN_DIR/export.json"
```

`export` 只导出所选对象的独立副本，保留材质；原文件和对象不改。`--faces N` 可选，仅对提交副本做本地 Decimate，不提供严格自交保护或纹理重烘。需要静态修改器、shape key 或多对象装配效果时先显式准备工作网格，不能把基础网格导出当作完整场景烘焙。

在 `RUN_DIR/request.json` 保存：

```json
{"mesh":{"$file":"body.glb"},"options":{"use_skeleton":false,"use_transfer":true}}
```

```bash
"$PYTHON" "$MDF_DIR/scripts/mdf_call.py" --service auto-rig \
  --input "$RUN_DIR/request.json" --run-dir "$RUN_DIR/call" --timeout 1800
```

`mesh` 是单个非空文件；需贴图时优先自包含 GLB，默认输入上限 256 MiB。`use_transfer:true` 推荐保留原尺度与材质，但不保证拓扑逐点一致。`use_skeleton:true` 不保证既有骨名和层级精确保留。示例超时按任务调整；超时保留原 trace/state，沿 mdf-call 恢复规则处理。

## 回迁到认可的高模

服务 GLB、身体高模与骨架必须在同一静止空间。核对包围盒、轮廓、左右方向、关节头位置与层级；包围盒相近只是初筛。glTF 导入器补出的骨尾可能只用于显示，不据此修改骨骼静止矩阵或判断关节位置。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- service_rig bind \
  --input "$RUN_DIR/source.blend" --body "$BODY" --rigged-glb "$RIGGED_GLB" \
  --targets "$BODY" "$SOFT_GARMENT" --alignment-tolerance "$TOLERANCE_UNITS" \
  --output "$RUN_DIR/bound.blend" --report "$RUN_DIR/bind.json"
```

`targets` 显式列出需要蒙皮的未绑定对象，至少包含身体；没有软衣物时省略其示例参数。刚性护甲可按实际运动整件跟随对应骨骼；剑等独立道具不混入身体权重。不要把布片跨两腿的最近面迁移视为最终衣物方案。

`bind` 接受单骨架、单蒙皮身体的静止 GLB，拒绝已有绑定或骨组重名的目标；用最近面插值按骨名迁移，保留非骨骼组（如衣物固定组）。只应用临时 Data Transfer，保留目标几何、UV、材质、shape key 坐标及其他修改器；添加保体积 Armature。原始返回值仍保留，导入参考网格在候选中隐藏。保存成功标记 `pose_qa_pending`，不代表动作通过。已有绑定的局部修订直接走下一节。

## 定位后修权重

先排除骨向、父子空间、错误姿态、缩放和关节位置，再对照原始服务权重与高模迁移结果。用包含弯臂、屈腕、屈指的实际测试动作定位异常三角面，读取其静止位置和各顶点骨权重；静止图看不出跨侧牵拉。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- service_rig inspect \
  --input "$RUN_DIR/bound.blend" --body "$BODY" --frames "$FRAMES" \
  --height "$HEIGHT_UNITS" --report "$RUN_DIR/skin-before.json"
```

先在工作副本中编排或复用本次测试动作；`FRAMES` 如 `1:60` 表示包含首末的全部整数帧，命令本身不生成动作。检测到拉伸时仍写报告并非零退出；输入或求值前提不满足时拒绝检查。报告给出网格/骨架摘要、骨名顺序、真实骨头位置、异常面的顶点与权重；不从 `bone_编号` 猜左右手或具体手指。

检查时启用身体、骨架及 Armature 修改器的视口求值，避免隐藏对象导致静止数据被误当成已验证动作。`motion_observed:false` 表示未观察到变形，不能据此宣称运动质量通过；静止姿态仍可用来读取校准身份。

确认出现解剖上不应存在的影响（如另一只手牵拉拇指）后，在任务目录写修复规则：从检查报告原样复制 `mesh_sha256`、`rig_sha256`、`bone_names`，增加 `regions` 数组。每项为 `{"bounds":[[最小x,最小y,最小z],[最大x,最大y,最大z]],"forbidden_bones":["已确认的错误骨名"]}`；边界使用身体网格局部静止坐标的实际单位，执行者按当前模型校准，不复用另一角色的范围或骨编号。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- service_rig repair \
  --input "$RUN_DIR/bound.blend" --body "$BODY" --rules "$RUN_DIR/repair.json" \
  --output "$RUN_DIR/repaired.blend" --report "$RUN_DIR/repair-result.json"
```

仅清除所选区域的禁用骨影响并归一化剩余权重；保留本侧掌骨和各指关节的混合。只回写发生变化的顶点，不改动作或骨架；共享 Mesh 先复制所选对象的数据，不影响其他实例；同一所选皮肤域的完全重合点使用一致权重。规则与网格、骨名顺序、静止骨矩阵不匹配，区域为空或清理后将无绑定时拒绝。独立壳体分别处理；近似重合点需额外公差/语义判断，不盲目焊接。无需平滑即可解决时就停止，不逐顶点 top-k、不把整只手变成单骨刚体。确有局部过渡不连续时，再按 [高面数蒙皮](dense-skinning.md)做受限图求解。

## 完成条件

重开新文件对同一完整测试帧范围再次 `inspect`，再按 [变形验收](validation.md)检查其他部件、接缝与接触。`inspect` 支持三角化读取多边形，但要求求值前后顶点和三角索引一致；Solidify 等改变拓扑的可见表面需建立单独的求值静止基准，不能直接套用基础网格索引。

严重拉伸同时看倍率与绝对增量：边长 >3 倍且增加 >H/120；面双面积 >8 倍且增加 >H²/81000。保留原始最大倍率，不能删面、细分或放宽阈值制造通过。数值零异常只覆盖已检查动作，不保证任意动作、无自交或自然握拳。

需要可视化时，以最终文件生成同姿态、机位、灯光的修前/修后手部近景和完整角色图；骨架覆盖图使用真实关节层级。检查对象的 `hide_render` Action/NLA/驱动是否会覆盖手动可见性，只在预览副本中处理确认属于展示切换的轨道。交付原始输入、服务结果、修正工程、规则和验证范围，阶段耗时沿用 skill 的业务统计要求；不把任务模型、骨编号或运行记录写入技能包。
