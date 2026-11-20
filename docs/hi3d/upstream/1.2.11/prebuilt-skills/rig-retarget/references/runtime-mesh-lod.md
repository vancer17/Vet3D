# Runtime 模式

仅在宿主提供公开 mdf_api 时使用；内部模式继续本入口原约定。

# LOD 减面与动画交接

已有合格 LOD 直接复用；需要减面、展 UV 和法线重烘时读取 mdf-api skill，通过 Runtime mdf_api 调用。输入为单个自包含 GLB，最大 200 MiB。有 baseColorTexture 时可携带颜色/PBR；按 [验收](validation.md) 检查动作与材质，不以调用成功保证无穿模。

## 输入、调用与产物

保留原始 GLB，使用单角色休止姿态，不上传整座舞台或舞蹈姿态。参数示例，先 dryRun，再移除 dryRun 正式执行；`waiting_choice` 交给宿主全局弹窗：

```json
{"action":"invoke","capability":"mesh-lod","file":"exports/hi3d-original.glb","params":{"target_face_num_list":[500000,200000]},"jobPath":".hi3d/mdf/lod.json","outputDir":"exports/hi3d-lod","dryRun":true}
```

唯一公开参数 target_face_num_list：非空正整数列表、严格降序、不重复、允许单档。不传旧内部自交或烘焙分辨率参数。Runtime 同步等待 7500 秒，没有轮询接口。

成功必须同时满足 HTTP 200、code=0、status=SUCCEEDED。工具 lods 按 targetFaces 降序提供档位，用其 field 查 files 获得本地路径。原响应 data.mesh_lod_glbs 的值是顶层字段名指针，不是 URL 或 key。不假设默认三档、JSON 枚举顺序或实际面数等于目标值。核实 GLB 可解析、档位完整、贴图/法线真实存在。

UNKNOWN/断线保留原 jobPath/requestId，不重提。下载失败用同一 jobPath/outputDir 的 download 恢复。用户选择本地预览时可用 Blender Decimate，但它不提供远端重烘效果，不能静默替换。

## 后续本地阶段

按 [准备、替换、权重和验收](mesh-lod.md#准备与替换网格) 继续；新骨架走 [公开绑定](runtime-service-rig.md)，已有绑定保留。
