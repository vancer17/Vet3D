# 基础材质节点

`material_nodes.principled_material(name,color,metallic=0,roughness=.5,inputs=None)` 接收已经线性化的 RGB/RGBA，建立 Principled BSDF 节点和 diffuse_color；可通过 inputs 显式设置 Coat Weight、Transmission Weight、IOR 等当前 Blender socket。不会把十六进制色值或 sRGB 隐式当线性值，也不设置特殊粉体/透光节点。

返回新材质，修改 bpy.data.materials；节点参数按 Blender 原规则接收/限幅，未知 socket 抛错并清理新材质。该函数不把材质分配给对象；分配和名称由调用方负责。无文件/网络副作用，需 Blender；合成材质检查 diffuse_color、每个指定节点值及失败清理。
