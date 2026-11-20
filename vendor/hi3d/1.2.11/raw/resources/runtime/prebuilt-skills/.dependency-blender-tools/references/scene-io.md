# 场景导入与对象保留

在后台 Blender 的物化 scripts 路径导入 `scene_io`。`import_objects(path, reset=False)` 导入 GLB/GLTF/OBJ/PLY/BLEND 并返回新对象；reset=True 明确清空场景。缺文件/不支持后缀在清场前失败，其他导入错误原样传播。BLEND 加载完整对象层级，以便保留父级世界变换；不自动规范单位、合并或命名。

`retain_meshes(objects, remove_others=False, apply_transform=True)` 接收非空且不重复的当前场景网格，先快照全部世界矩阵再解除父子关系，可明确删除其他场景对象并逐件施加变换。返回原名→对象字典。网格/UV/材质保持；变换应用遵从 Blender 的 shape key/共享数据限制并传播失败。会改变选择和 active 对象，只在隔离场景调用。

`head_io.load_source(path, object_name=None, keep_objects=())` 保留单头选择与 Source_High 名称，附加网格按原名保留；head-lowpoly 的薄适配负责 hair_objects 和 Source_Hair_ 名称/来源属性。source-prepare 使用同一导入器后自行合并、按毫米目标高度规范化、有限焊接和保存。二者不能互换。

`create_mesh_object(name,vertices,faces,collection,material=None,recalculate_normals=False,smooth=False)` 只在显式 collection 中创建网格对象；坐标已经是场景单位，不自动缩放/焊点/转换。可选在临时 BMesh 重算法线，成功或异常都释放；创建后出错删除本次对象和网格。返回新对象，保持其他对象和当前选择，不推断产品标签。
