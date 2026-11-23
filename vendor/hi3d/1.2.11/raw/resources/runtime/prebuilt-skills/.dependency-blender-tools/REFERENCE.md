---
name: blender-tools
description: "使用 Blender 的后台进程、场景读写、原生依赖检查和有检查点的帧渲染，为原子能力及工作流提供通用操作。"
---

# Blender 工具使用

使用 Blender 的后台进程、场景读写、原生依赖检查和有检查点的帧渲染，为原子能力及工作流提供通用操作。

## 输入与完成结果

- 输入：显式 Blender 可执行文件、独立场景、目标目录、帧或 render spec。
- 输出：native_dependencies.py 检查工程资源；scene_io 按明确策略导入/保留对象，head_io 提供单头选择与额外网格保留；render_frame_chunk / render_video_chunks / render_frames 执行明确的帧任务。

## 调用与边界

优先 factory-startup 或新后台进程；脚本按 --python-exit-code 1 传播失败。分块渲染 spec 为 [{tag,frames}]，场景是 case/<tag>.blend，现有 profile 为 864×768/24fps；缓存需来源 hash 匹配，显式 adopt 不等于来源证明。不操作未保存前台工程。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

## 运行另一个包的脚本

先物化依赖，然后显式传已安装脚本路径，包装器只加入该脚本目录：

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 --python "$BLENDER_TOOLS/scripts/execute.py" -- --script "$SKILL_DIR/scripts/project_sapiens2_landmarks.py" -- "$LANDMARK_CONFIG"
```

包含相对包导入的入口用 `--scripts "$SKILL_DIR/scripts" --module rigging.weight_graph`。这是运行已信任包代码的入口，不是执行陌生代码的沙箱；异常会传递给 Blender 退出码。

包装器后的额外 `--` 会原样传入目标脚本，供采用 Blender 参数分隔约定的入口使用；目标接受普通 Python argv 时按其自身 CLI 提供参数。

多对象导入、父级世界变换和删除策略见 [场景 IO](references/scene-io.md)。来源高度与单位归一化由 source-prepare 负责。

需要完整打开 BLEND 或全新载入 GLB 后检查时，读取 [完整资产载入](references/asset-scene.md)，显式选择保留或切换帧；该操作替换后台场景，返回对象供调用者测量。

原始/求值网格的独立坐标、索引与可选属性快照使用 [mesh snapshot](references/mesh-snapshot.md)，必须显式指定坐标系和求值模式。

按已有顶点/面在显式集合中创建对象使用 [scene IO](references/scene-io.md) 的 create_mesh_object；单位与法线策略由调用方指定。

基础线性颜色 Principled 材质见 [材质节点](references/material-nodes.md)，色彩转换和特殊节点由调用方显式处理。

当前进程的 Cycles 后端选择与临时恢复见 [设备契约](references/cycles-device.md)；渲染/烘焙配置和 CPU 回退策略由调用方决定，不保存用户偏好。

按显式引擎、帧列表和参数渲染已有工程时读取 [帧渲染契约](references/render-scene.md)；分块缓存必须同时匹配来源与渲染源码。

EEVEE 标识与样本控制按当前 Blender 实际暴露的属性解析；共用接口见 [渲染兼容](references/render-engine.md)。

<!-- managed-by: sparc3d-runtime -->
