# Cycles 设备操作

[cycles_device.py](../scripts/cycles_device.py) 只配置当前 Blender 进程，运行时需要 Cycles；不保存用户偏好、不启动渲染或烘焙、不设置 samples/engine。

- `select_cycles_device(scene,device='CPU',fallback_cpu=False)` 返回 backend、devices 名称和 fallback；回退时附 reason。CPU 直接选择 CPU，显式后端为 OPTIX/CUDA/METAL/HIP/ONEAPI，AUTO 按此前顺序尝试实际枚举到的设备。只启用所选后端，不混用 CPU；无可用设备且未显式允许 fallback_cpu 则 RuntimeError，未知名称在修改前 ValueError。失败可能保留本进程枚举过程中改变的 compute backend。
- `cycles_device_context(scene,device='CPU',fallback_cpu=False)` 临时选择并 yield 同一报告，成功、异常及中断都恢复原 scene.cycles.device、compute backend 与原设备 use。按设备 id/type 恢复，枚举新增设备退出后禁用；不删除 Blender 的设备清单，不恢复调用方自己的渲染设置。

渲染调用方可采用 AUTO + fallback_cpu=true；烘焙默认 CPU，具体工作流显式 GPU 的回退策略分别保留。返回 GPU 名称只证明枚举与选择，不证明 GPU 完成了实际渲染。离线测试覆盖后端选择、顺序、无设备、错误和设备对象重新枚举；实际运行另核对 CPU 烘焙与上下文恢复。
