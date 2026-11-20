# 同步合并契约

[scripts/glb_clips.py](../scripts/glb_clips.py) 仅需 Python 标准库。

- `read_glb(bytes)` 校验版本、总长、对齐、完整 chunk 和唯一首个 JSON，返回字典和剩余 chunk；不写文件。
- `_index` 验证整数范围；`_times` 解出 embedded buffer 的非 sparse float SCALAR 时刻，校验 byte range、有限、非负和严格递增。外部 URI/sparse 时间数据不受支持，明确失败；这不是完整 glTF 合法性验证器。
- `merge_bytes(data,clips,name,timeline='preserve',allowed_paths=None)` 是纯转换，返回 bytes 与报告。clips 必须显式传索引集合或字符串 all；拒绝空选择、重复/越界索引、空动作、无效 sampler/input/output/node 引用和重复 `(node,path)`。只支持 translation/rotation/scale/weights。未选动作及顺序保留，合并动作置于最早选中位置。
- `preserve` 不改任何采样时刻，允许所选动作的采样密度/起止不同；调用者负责确认应同时播放。`shared_accessor` 额外要求全部 sampler.input 相同，不把数值恰好相等的不同 accessor 当作共享。allowed_paths 可限制 weights；无插值或重定时算法。
- `merge_file(source,output,...,overwrite=False,in_place=False)` 先完整转换，再同目录临时文件原子落盘；默认排斥已有目标，源和目标相同需 in_place。输入校验异常保留原文件，临时文件始终清理。`main` 解析 CLI 并打印/写 JSON 报告，report 不得覆盖 GLB。

报告包含 before/after SHA-256、片段数、selected_clips、channel_count、timeline_policy、time_accessor_ranges（开始/结束/数量）、可用时 shared_time_accessor，以及 retimed=false、binary_chunks_unchanged、non_animation_json_unchanged。保持指非动画 JSON 语义一致与 JSON 后全部 chunk 字节一致；JSON 排版可改变。合并后旧 animation 的 name/extras/extensions 不合并，新的名字由调用者提供；通道和 sampler 附加字段完整保留。

调用分支：relief-brush 只 weights 且共享时间；frame-design 接受一般节点通道；motion-base 保留完整手装/滚动名称；model-preview 仅在多个片段时合并，0/1 片段仍原样保留。它们的建模、减面、贴图、动画生成与导出仍各自负责。

相框/新月相框和旅行收纳盒旧配方也通过各自 `merge_scene_animation` 调用 merge_file；薄适配继续维护自己的动作名和报告键。它们明确选择 all，因此无动作会失败，不能套用预览副本的 0/1 原样保留策略。合并失败不改源仅指此函数，不承诺撤销调用方此前的导出或建模。

验收覆盖多片段/部分选择、不同时间策略、目标冲突、非法引用、损坏容器、失败不改源，以及独立复读 JSON/BIN 和查看器播放。未作完整 output accessor 元素布局、动画扩展或实际视觉验证时不得声称全部 glTF/动作正确。

read_glb 也可单独供网格范围、Blender 导入前检查和导出布局检查复用；这种代码物化关系不要求执行 merge_bytes 或合并动画。容器校验不解释位置、材料、对象角色或产品验收条件；未知 trailing chunk 保留，具体 BIN 数量和用途由消费方检查。

低模人头交付、MetaHuman 静态预览和运动底座导出检查复用此只读函数，各自的 morph/skin、纹理/附件、运动/部件验收继续独立；损坏尾块会比仅解析首段 JSON 更早失败。带阶段缓存的调用方将物化的 glb_clips.py 纳入真正消费它的阶段源码指纹。
