# 已有场景的显式帧渲染

物化工具后，在独立 Blender 后台进程中调用 `render_scene.render_scene(source, output, frames, *, engine, resolution, fps=None, threads=None, samples=None, device=None, denoise=None, prefix='', animation=False, overwrite=True)`。输入已有 BLEND、输出目录、非空无重复整数帧列表、引擎和正整数宽高；返回实际 PNG 路径。打开工程会替换当前场景，不重建模型、不写回源工程、不编码视频。

`fps=None` 同时保留源 fps/fps_base；指定整数 fps 时设 fps_base=1，保证有效整数帧率。threads/samples/device/denoise 未给时保留源设置，给定时显式更新；仅 Cycles 使用其采样/设备/降噪设置。设备可用性由运行环境保证，不隐式切换后端。

逐帧模式按列表顺序输出 `<prefix><frame:04d>.png`。animation 模式要求连续递增帧，设置起止和 step=1，以同样四位编号输出；可以保留 Blender animation 模式的处理方式。prefix 不允许目录分隔或 # 占位符。统一显式设置 PNG、100% 分辨率和扩展名，不依赖源工程的文件格式。`overwrite=False` 在打开工程前拒绝任何已有目标帧；默认覆盖与原适配相同。失败保留已完成帧、不报告整体成功，调用方负责恢复与检查点。

已有适配保留以下参数，不推广为通用默认：

| 入口 | 引擎/模式 | 分辨率、fps、命名 |
| --- | --- | --- |
| render_frame_chunk | EEVEE 逐帧、2 线程 | 864×768、24fps、0001.png |
| render_frames | EEVEE 逐帧 | 960×720、保留 fps、frame-0001.png |
| 工作流的 DIY 帧适配 | EEVEE 逐帧、2 线程 | 864×768、保留 fps、0001.png |
| 护甲已保存动画适配 | Cycles animation、CPU/降噪/2 线程 | 调用方宽高/采样、24fps、frame-0001.png |

分块恢复仍由 render_video_chunks 负责。检查点除来源 BLEND 哈希、帧数和 profile 外，记录 render_video_chunks、render_frame_chunk、render_scene、stage_cli 的源码摘要；任一变化隔离旧帧再渲染。缺少新摘要的旧检查点不能自动复用；显式 adopt 仅承认人工已检查的无记录帧，不证明来源。共享渲染源码变化不触发建模，建模产物不被此工具修改。

验证正常首尾帧、保留/指定 fps、两种引擎与命名、覆盖失败、无相机失败及原 BLEND 内容不变。完整多帧质量与后续编码验收由调用方另行完成。
