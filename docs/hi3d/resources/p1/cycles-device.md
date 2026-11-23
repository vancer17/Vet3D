# Cycles 后端选择 cycles_device.py

## 资源身份与模型可见性

`cycles_device.py` 是 Hi3D Agent 1.2.11（Windows x64）随 `.dependency-texture-bake` 物化的 Blender Python 模块，源映射为 `tools/blender-tools/scripts/cycles_device.py`。烘焙模块从同目录导入它。包文档记录设备选择和恢复行为，随包参考路径未声明独立的 LLM Tool 或模型可见 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/cycles_device.py) · [随包设备契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/references/cycles-device.md>)

## 参数、结果与副作用

| 接口 | 行为 |
| --- | --- |
| `select_cycles_device(scene, device="CPU", *, fallback_cpu=False)` | `scene` 必填。直接选择 CPU，或采集指定 GPU 后端的设备名。`AUTO` 按 `OPTIX → CUDA → METAL → HIP → ONEAPI` 尝试。`fallback_cpu=True` 允许所请求的 GPU 后端不可用时显式回退 CPU。 |
| 返回 | 字典含 `backend`、`devices`、`fallback`。CPU 的 `devices` 为空，显式回退时附 `reason`。GPU 选择启用对应后端的设备并关闭其他设备。 |
| `cycles_device_context(scene, device="CPU", *, fallback_cpu=False)` | 上下文内提供同一报告。退出时恢复原场景设备、计算后端和按 `(id, type)` 匹配的设备启用标记。退出时禁用枚举期间新增的设备。 |

未知设备名称抛出 `ValueError`。GPU 枚举中的 `RuntimeError` 或 `TypeError` 由选择器跳过，尝试耗尽且未允许回退时抛出 `RuntimeError`。直接调用选择器可能留下枚举途中修改的计算后端。上下文通过 `finally` 恢复捕获的状态。作用范围为当前 Blender 进程，渲染引擎、采样、实际渲染和偏好文件由调用方管理。

## 依赖与执行权限

仅依赖标准库和 Blender 自带 `bpy` 的 Cycles 偏好接口。GPU 还需要可用设备、驱动及支持该后端的 Blender 构建。直接选 CPU 可绕过设备枚举，上下文仍读取 Cycles 偏好以建立快照。经 Agent 的本地工具运行时，沙箱与前置 Hook 由外层启动命令处理。 [后台 Blender 包装器](../blender-execute.md) · [执行权限与 Hook](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例与核查

**根据归档源码编写的 Python 示例。** 令归档的 `.dependency-texture-bake/scripts` 在独立 Blender 进程中可导入。

```python
import bpy
from cycles_device import cycles_device_context

scene = bpy.context.scene
prior = scene.cycles.device
with cycles_device_context(scene, "CPU") as report:
    assert report == {"backend": "CPU", "devices": [], "fallback": False}
assert scene.cycles.device == prior
```

已在 Blender 4.5.16 LTS 调用归档副本验证 CPU 报告和退出后场景设备恢复。随包 CPU 烘焙夹具还核对了设备标记及上下文中故意抛出异常后的恢复。GPU 后端真实枚举、回退、恢复和烘焙成品仍待目标设备实测。 [CPU 烘焙隔离测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/tests/test_device_context.py>) · [P1 路径与摘要](../../upstream/1.2.11/extraction/p1/priority.json)
