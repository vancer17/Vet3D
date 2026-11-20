# 原子操作命令

以下对象名、路径、帧号仅为示例。用 inspect 输出替换选择器。`blender_bin`、`skill_dir`、`run_dir` 是调用方自己的变量；不要将脚本绑定到某个用户名、缓存目录或 Blender 版本路径。

## 共同调用形式

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" stage_ops inspect \
  --input "$run_dir/source.blend" --report "$run_dir/inventory.json"
```

修改命令必须指定新的 `--output`；输入保持完整，可作为回退文件。默认报告写到候选旁的 `.report.json`。可加 `--pack` 打包已有贴图。最终发布到已使用的文件名由调用方在验收之后处理，并保留回退路径。

所有命令可以 `--help` 查看参数。不要因为工具名包含 `clip` 就默认用户允许删除未选中的角色或舞台动画。

## 检查朝向

```bash
# 正面轴是该模型在 armature 休止空间中真实的面部向前方向。
# 本例模型正面 -Y；不是所有 BVH、FBX、glTF 都符合这个约定。
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" stage_ops inspect \
  --input "$run_dir/source.blend" --report "$run_dir/facing.json" \
  --rigs RigA RigB --head-bone head --forward 0 -1 0 --frames 0 90 180 270
```

计算 `world_forward = rig_world_rotation × pose_head_rotation × inverse(rest_head_rotation) × rest_forward`。工具报告世界向量；与相机/舞台的观众方向比较，投影到水平面判断 yaw，俯身不应被误判为整体朝向错误。

## 动作区间裁剪及重排

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" stage_ops clip \
  --input "$run_dir/source.blend" --output "$run_dir/clip.blend" \
  --rigs RigA RigB --source-start 181 --source-end 540 --start 0 \
  --rebase-markers --pack
```

181–540 **包含两端**，共有 360 个整数帧，输出 0–359。保持当前 fps；脚本不负责改变采样率。骨架动作先在原 NLA 状态全部求值缓存，然后移除所选 rig 的旧动画引用；生成每人一个 Action/strip。它会删除失去真实使用者的旧动作，保留仍被其他对象使用的共享动作。

- 支持已绑定、无约束/驱动、仅含骨骼姿态变换通道的动画。IK、骨约束、rig 对象动画、自定义属性驱动会提前拒绝，交给有视觉烘焙支持的专门流程。
- 逐帧烘焙保留整数帧的求值姿态，并改用 quaternion/LINEAR；不是原 Bezier 曲线的无损平移器，也不保证子帧插值完全相同。
- 时间轴是全场景设置。未选中的动作不删除；报告会列出剩余 Action。只有确认任务要求的所有角色/额外轨道都被处理后，才能声称“场景只剩这段舞蹈”。
- `--rebase-markers` 只保留源区间内标记并平移；默认不动标记。

需要将舞台灯效整段压入新时间区间时，显式指定已检查的 Action：

```text
--stage-actions LED_Pulse Moving_Spot \
--stage-source-start 1 --stage-source-end 480
```

灯效按原 source 区间函数求值，均匀采样到新整数帧；不复制原 modifiers 和 Bezier handles。共享于多个真实使用者的灯效 Action 会拒绝，防止扩大修改范围。

## 整体朝向

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" stage_ops orient \
  --input "$run_dir/clip.blend" --output "$run_dir/facing.blend" \
  --rigs RigA RigB --degrees 90
```

`90` 是计算结果的示例，必须根据 inspect 和画面确定。以每人自己的世界站位为旋转中心，整体旋转世界 Z；不围绕舞台中心旋转整支队伍。角色位移自然随父级旋转，保持局部曲线。

脚本限定 rig 无 parent、对象约束/驱动或对象动画，蒙皮网格位于该 rig 的后代层级。其他结构需明确设计一个 group pivot，同时纳入对象动画和独立蒙皮网格；不能硬套脚本或重复旋转骨架及其子网格。

## 精确舞台文本

先 inspect，再创建 UTF-8 JSON，例如：

```json
{
  "set": [{"object": "Main title", "text": "Hi3D 3.0 x GPT6 Astra", "max_width": 6.65}],
  "remove": ["Nameplate 01", "Nameplate 02"]
}
```

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" stage_ops text \
  --input "$run_dir/facing.blend" --output "$run_dir/titled.blend" \
  --spec "$run_dir/text.json"
```

`max_width` 可省略，单位与场景一致；只有超过上限才缩小字号。它不是透视排版器，仍需检查镜头中的留白。只修改/删除指定 FONT 对象；不会自动删除所有文本、改角色 mesh/rig 技术标识或重命名工程。未匹配、重复或冲突的选择器都会提前拒绝。

## 按秒渲染与拼图

仅在用户要求预览/渲染时运行，沿用已有 engine、相机、雾和灯光配置，不暗自重做美术。

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" render_samples \
  --input "$run_dir/titled.blend" --out-dir "$run_dir/renders" \
  --interval-seconds 1 --width 1920 --height 1080 --samples 64

"$python_bin" "$skill_dir/scripts/run.py" --rig-skill "$RIG_SKILL_DIR" contact_sheet \
  --manifest "$run_dir/renders/render_manifest.json" \
  --output "$run_dir/overview.jpg" --zip "$run_dir/originals.zip"
```

0–359 @ 30 fps → 0、30……330，共 12 张，不能再生成范围外的第 360 帧。非整数帧率按 `fps/fps_base` 换算并取整。支持 `--start/--end`（包含端点）、`--camera`；默认禁用运动模糊以观察姿态。

`--resume` 只接受相同源文件哈希、相同设置和完好的已有图像。若中断留下未登记 PNG，先检查再决定移动或复用，不能把混合版本图像当同一次结果。修改 `.blend` 后应使用新渲染目录。拼图按清单核对图像哈希与分辨率，拒绝混入已修改的图片。拼图要求 Pillow；不要求固定系统字体，`--font` 可显式指定字体文件。

## 修改脚本后的回归检查

```bash
"$blender_bin" --background --factory-startup --python-exit-code 1 \
  --python "$skill_dir/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" self_test --work-dir "$run_dir/new-self-test"
```

测试只生成小型合成场景，验证源/目标姿态矩阵、共享 Action、站位中心、世界顶点旋转、共享文字隔离和采样端点，不读取生产工程、不调用 Hi3D、不渲染。修改渲染脚本时再用测试生成的 `text.blend` 进行小分辨率采样及 `--resume` 检查。

RIG_SKILL_DIR 指另行提供的 rig-retarget 包，见 [依赖交接](rigging.md)。
