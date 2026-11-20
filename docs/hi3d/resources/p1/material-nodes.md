# 基础 Principled 材质 material_nodes.py

## 资源身份与模型可见性

`material_nodes.py` 是 Hi3D Agent 1.2.11（Windows x64）随 `.dependency-blender-tools` 交付的 Blender Python 模块。模型可在包的参考入口找到基础线性颜色材质用法，由可信后台脚本导入 `principled_material`。随包参考路径未声明独立的 LLM Tool 或模型可见 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/material_nodes.py) · [随包材质节点契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/references/material-nodes.md>)

## 参数、结果与副作用

| 参数 | 作用 |
| --- | --- |
| `name`、`color` | 必填。新材质名称和已线性化的 RGB 或 RGBA 序列。RGB 补 `alpha=1`。颜色转换由调用方完成。 |
| `metallic=0`、`roughness=.5` | Principled BSDF 金属度与粗糙度。数值由 Blender 的 socket 属性解释。 |
| `inputs=None` | 可选映射。键为该 Blender 版本的 socket 名，值写入 `default_value`。映射最后合并，可覆盖 `Base Color`、`Metallic` 和 `Roughness`。 |

返回新建的 Blender `Material`。先设置 `use_nodes` 和取自原始 `color` 的 `diffuse_color`，再向 Principled 节点写入合并后的值。因此 `inputs["Base Color"]` 只覆盖节点值。材质分配、持久化和导出由调用方完成。颜色维度错误抛出 `ValueError`，查找或写入 socket 失败时删除本次新建材质并重新抛出异常。资源作用于进程的材质数据。

## 依赖与执行权限

脚本只直接导入 Blender `bpy`。材质和 socket 的实际可用性由 Blender 版本与运行环境决定。经 `exec_command` 启动 Blender 时，前置 Hook 和有效权限发生在外层命令，材质模块由后台进程执行。 [后台 Blender 包装器](../blender-execute.md) · [执行权限与 Hook](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例与核查

**根据归档源码编写的 Python 示例。** 在独立 Blender 的调用方脚本中运行，令归档的 `.dependency-blender-tools/scripts` 可导入。

```python
from material_nodes import principled_material

material = principled_material(
    "mat-sample",
    (0.22, 0.36, 0.42),
    metallic=0.1,
    roughness=0.65,
    inputs={"Coat Weight": 0.2},
)
print(material.name)
```

已在 Blender 4.5.16 LTS 调用归档副本，核对 RGB 补全、`Coat Weight` 写入及未知 socket 失败后的材质清理。真实犬猫毛发、眼睛和皮肤的材质配方、颜色管理及导出后多材质绑定仍需样本验证。 [P1 核查与摘要](../../upstream/1.2.11/extraction/p1/priority.json)
