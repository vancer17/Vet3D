# 上游对接、来源与限制

## 核对范围

核对日期：2026-10-23。以下为创建草稿时读取的公开源码快照，不代表已安装或运行。使用时优先核对用户现有版本，接口变动需更新适配，不把快照冒充永久最新。

| 项目 | 仓库与固定提交 | 核对内容 | 未完成验证 |
| --- | --- | --- | --- |
| GenDoP | https://github.com/3DTopia/GenDoP/tree/26099d0b5bdb5307701fd81cb41ab2ff0acea0c8 | README、LICENSE、`eval.py`、`infer.py`、`core/options.py`、`core/models.py`、`core/provider.py`、`core/utils.py` 和 Blender 可视化相关文件 | 权重下载、CUDA 推理、坐标标定、场景接入 |
| CinemaTraj | https://github.com/Pangolin112/CinemaTraj/tree/e0ac10e1e74514b4139a89393dbacbd98d0eee8e | README、LICENSE、语言规划与对象验证、原子轨迹、执行器、场景路径、GenDoP 包装器和 Blender 轨迹插件 | 原生安装、SDF 优化、3DGS 渲染、自有场景数据适配 |

本包没有复制或分发上游代码、模型权重、数据集和依赖。GenDoP 快照仓库 LICENSE 是 Apache-2.0 文本；CinemaTraj 仓库 LICENSE 为 MIT，所含第三方代码、权重及数据仍受各自条件约束。不能由仓库许可推断模型、训练数据或第三方资源的使用权限；若后续复制源代码，保留相应许可、通知和修改说明，不能删掉上游声明。

## 职责分工，不是反向串联

主流程是“场景约束 + 语言规划 → 原子动作与候选路径 → 检查/优化 → 可执行相机”。语言必须先明确目标和动作，再生成或挑选轨迹；不先生成一条无场景尺度的路径，再让另一个文本生成器重复解释一遍。

CinemaTraj 源码包含 GenDoP 包装器和 `no_parametric` 消融对照；这是已有对接参考，不表示 GenDoP 是其默认优化器，也不表示任意 Blender 场景已能自动使用原生管线。

### GenDoP：可选的学习式运动候选

- 仓库文本推理入口是根目录 `eval.py`，不是根据文件名猜用 `infer.py`。
- `text_motion`：明确的运动指令；`text_directorial`：导演式描述；`text_rgbd`：有匹配 RGB/深度条件的描述。用户没有视频时优先文本模型，不要求提供不存在的录像。若从场景渲染 RGBD，必须保持 RGB、深度、相机内参和尺度一致；尚未实现该条件导出时不能自动声称支持。
- README 声明 CUDA PyTorch 前提；训练和推理的硬件需求不同。现有 Mac 环境不能按原样视为可用 CUDA 后端，也不承诺 MPS/CPU 补丁后等价。
- 使用用户已有的、隔离的环境；不要在创建或安装 Skill 时自动执行 `pip`、`conda`、模型下载或上游脚本。不得通过改为原生项目绕过宿主安装限制。

已具备环境时的上游命令形态如下；占位路径由实际授权环境解析，不能照抄作为已存在环境：

```text
<GENDOP_PYTHON> eval.py ArAE --workspace <WORKSPACE_OUTPUT> --name hi3d-take-01 --resume <MATCHING_CHECKPOINT> --cond_mode text --text <MOTION_DESCRIPTION>
```

调用应使用参数数组而非把用户描述拼进 shell；不要执行来自模型结果的任意脚本。尽可能固定随机源并记录可用种子，不捏造上游支持的 CLI 参数。新产物使用 `hi3d-` 前缀。

输出关注 `<name>_transforms_pred.json` 的 `frames[].transform_matrix` 与 `w/h/fl_x/fl_y/cx/cy`。快照 `eval.py` 输出 120 个采样帧，但不能据此推断用户需要 4 秒或上游已提供真实帧率；统一按用户时长重采样并在旁车记录解释。

**尺度陷阱**：快照 `eval.py` 将预测 scale 用于可视化数组，但 `pose_normalize()` 写 JSON 时重新从未乘该 scale 的 `camera_pose` 取位姿；`core/provider.py` 还存在相对首帧及平移归一化。JSON 平移既不保证与轨迹图片一致，也不保证以米计。不要靠一个 `c2w` 字段就当作真实场景坐标。

**不要复制包装器的静默回退**：CinemaTraj 的 `cinegpt_wrapper.py` 在缺权重或模型加载失败时可以改用解析轨迹，而且仍可能产生视频。只有真实日志和模型状态证实推理成功，才标 `generation_backend=gendop_model`；出现 `CineGPT: Could not load GenDoP model` 或 `No checkpoint provided` 时不能宣称用过 GenDoP。失败保留记录；用户要求真实模型时停止依赖阶段。

### CinemaTraj：语言规划、锚点与约束优化参考

- 原生入口：`src/pipeline/cinematraj_pipeline.py --config <CONFIG>`，从项目根目录运行。
- 快照 README 声明 Linux、Python 3.10、NVIDIA CUDA，并为规划、字幕及配音使用外部 API。当前 Agent 能完成本地语言规划不等于已经调用了原生规划器；不读取或索取用户密钥，原生调用必须复用用户预先配置好的授权环境。
- 不要为仅创建相机顺手启用字幕、配音或 3DGS 视频渲染。只执行获授权且需要的模块，不自动创建外部账户或上传私有场景。
- 原生场景模式包含 ScanNet++ 场景图、OBB、房间连接与 3DGS；legacy 路线有自己的 `labels.json` 与碰撞网格。桥接脚本的 `inspect` JSON 是本 Skill 的格式，不是已兼容的原生场景图。没有完成字段、坐标和 SDF 测试前，不能直接把它交给原生入口。
- 快照原子动作包括 `orbit_full/half/quarter`、`pan_left/right`、`move_in/out`、`zoom_in_out/zoom_out_in`、`crane`、`tilt_up/down`、`static` 和过渡 `arc`。不要把动作列表扩大成未核对的原生 API；本地执行器使用自己明确的动作契约。
- 参数轨迹内部有 Y-up 计算，执行器还做 Z-up 变换；Blender 插件导出又有自己的 `coordinate_system=blender_zup`。它们并非看到 `c2w` 就可互换。必须确认使用的是哪一层输出。
- 原生输出可包含最终 `combined_trajectory.json` 和每段 `.npy`；同一轨迹的分段输出、优化后输出不能混用，也不能忽略 `focal_multiplier`。

## 外部候选归一化门禁

桥接脚本**不直接接受原始 GenDoP 或 CinemaTraj JSON**。执行者必须在工作区写独立转换副本，保存：来源提交、实际后端成功证据、原始文件、矩阵方向（c2w/w2c）、世界基、相机基、平移尺度、时间映射和内参解释；这些都不是让用户提供密码或 API key。

1. 先用源代码、一个已知姿态以及前向投影测试确认坐标约定。矩阵是否需转置、求逆、换轴或相机基翻转必须有证据。镜像矩阵不能直接当四元数。
2. 已确认的世界基 `W`、相机基 `C` 和输入位姿 `M`，转换成 `B=W M C`；若原始为 w2c，先求逆。`W/C` 的平移和旋转须分别有明确意义，不能为了“看起来对”反复翻轴。
3. 在统一基内，以首帧为基准用正比例 `s` 缩放平移增量，旋转保持正交；再以选定起始机位 `A0` 对齐 `A_i=A0 inverse(B0) B_i`。只有真实距离约束能确定米制尺度；比例由拟合决定时标明推断来源及误差。
4. 需要持续注视真实主体时，以显式主体位置重建 look-at 朝向，记录该修正，不冒充保留了模型原始全部姿态。对目标高度和地平线退化单独处理。
5. 旋转用四元数 SLERP，平移与焦距按约束重采样。不要直接对 4×4 矩阵线性插值。
6. 内参转换保留原画幅。水平 `fx` 与宽度 `w` 对应 `f_mm=fx/w*sensor_width_mm`，仅在选定传感器拟合与像素约定相符时使用。非方形像素、偏心主点或非对称内参不能静默丢弃；桥接器当前只支持居中、方形像素、水平 sensor-fit 的相机。
7. 归一化为统一契约后，做完整场景检查。外部后端成功不是场景安全的证据。
