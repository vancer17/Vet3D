---
name: glb-clips
description: 将已有 GLB 中明确同时播放的动画片段合并为一个 clip，校验目标冲突和采样时间，保持非动画 JSON 与二进制数据。
---

# GLB 同步片段

输入为已有 GLB 2.0、显式片段索引或已确认全部同步的选择、输出路径和片段名。输出为合并后的 GLB 与选择、通道数、时间范围和保持项报告。不创作动作、不重定时、不按前后顺序拼接。

先确认所选动作原本处于同一时间坐标；不同起止时间允许保留，不能据此认定它们适合同播。读取 [契约](references/contract.md) 选择 preserve 或 shared_accessor；后者要求引用同一个时间 accessor，weights-only 用于同步形态键。

按 [打包约定](../.dependency-package-tools/references/usage.md) 与 [清单](package.json) 生成完整包后，可显式 `$glb-clips` 或使用 Python 3 标准库 CLI：

```sh
python scripts/glb_clips.py --input source.glb --output merged.glb --clips 0 1 --name 'Assembly' --report merge.json
```

只有明确所有片段同播时才用 `--all-simultaneous`。默认保留源文件且不覆盖输出；原地改写必须相同输入/输出并显式 `--in-place`。校验失败不写 GLB。完成时复读输出，核对未选动作、非动画 JSON、全部 BIN 保持，并在目标查看器实际播放；静态报告不等于视觉/机械验收。

<!-- managed-by: sparc3d-runtime -->
