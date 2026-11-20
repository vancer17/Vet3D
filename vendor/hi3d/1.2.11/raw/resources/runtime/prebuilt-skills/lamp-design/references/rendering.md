# 双状态渲染与视频

图片和结构/动作检查照常执行；本页的连续视频渲染与编码仅在明确请求后执行，参见 [交付规则](delivery-policy.md)。不要在默认基础交付前渲染视频。
## 光效和几何一致性

真实腔体、壁厚、开孔与可见灯源构成光路。若艺术壳不透光，应从窗口/扩散件出光；不能把整块金属雕塑设置 emission 冒充透光。透光打印塑料可用透射/次表面等近似，但需试片校准，且仍属视觉预测。灯源几何 emission 与场景灯须同时切换，OFF 时二者都归零。

标准比较固定几何、材质、曝光、色彩管理、相机路径、背景与摄影辅助光。可另外做“夜景氛围片”，明确其摄影条件变化；不得用夜景变暗证明灯具输出变强。双状态的相同帧要有相同视角。

## 推荐分镜

视频已被明确请求但未指定镜头时，可交付 OFF、ON 各 6–10 秒转台，24 fps、1080p 或与工件适合的方形构图；先做 480–720 px 的完整低采样预览确认开关、背面、接缝和光孔，再输出所需终稿。额外的定机位 OFF→ON 演示可复用静帧作交叉淡变，但必须注明是状态转场，不是物理电路启动仿真。

检查：阴影接触、灯具轮廓、亮斑过曝、透光件是否实际遮住点光源、黑缝/漏光、背面功能件、转台全程裁切、噪点与编码闪烁。保留相同关键帧的 OFF/ON 对照。

## 基础图片与按需视频的脚本用法

`LAMP_SKILL` 是技能实际绝对目录，输入及输出路径按当前任务替换；完整契约见 [本地工具](tooling.md)。

`render_states.py` 默认每种状态只渲一张图片（`--frames 1`），不编码视频。基础交付省略 `--frames` 或设 1 即可；下面的 144 帧和编码命令只在视频明确请求后执行。

准备场景，命名灯具光源和发光材质，在 JSON 写明 exact names 与视觉强度；`render_states.py` 对缺失对象、错误能量和缺少相机报错。灯光外的几何保持不变，使用同一条相机轨迹。

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$LAMP_SKILL/scripts/render_states.py" -- \
  --input lamp.blend --config light-states.json --output renders \
  --frames 144 --fps 24 --resolution 1080 --samples 32
python3 "$LAMP_SKILL/scripts/encode_video.py" --ffmpeg /absolute/path/to/ffmpeg \
  --frames-dir renders/off --fps 24 --output off.mp4
python3 "$LAMP_SKILL/scripts/encode_video.py" --ffmpeg /absolute/path/to/ffmpeg \
  --frames-dir renders/on --fps 24 --output on.mp4
```

光效配置示例：`{"lights":{"Lamp LED":0.8},"emissions":{"LED surface":4.0},"target_m":[0,0,0.1],"orbit_degrees":360}`。光的数值为渲染参数，不代表电器额定功率。

脚本会输出可复用场景快照与 manifest；运行后打开 PNG 与视频/抽帧核验。默认 CPU 可复现，速度可按环境改用已验证 GPU。视频编码检查退出码、文件大小、连续帧号和 ffmpeg 解码；编码成功不能代替视觉检查。

原始 `.blend` 如带全局动画，先复制并冻结指定基准帧，以免相机/灯光在帧间被现有 F-curves 覆写。本脚本逐帧设定视角与灯光，渲染基准场景时钟；它是转台工具，不是机械装配动画工具。
