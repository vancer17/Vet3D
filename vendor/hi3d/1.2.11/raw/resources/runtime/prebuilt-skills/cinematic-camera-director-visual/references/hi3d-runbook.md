# 本地执行与恢复手册

## 执行前

这里的桥接脚本是本 Skill 新写的适配器，不是 GenDoP 或 CinemaTraj 本身。创建草稿、结构检查和安装都不自动执行它。真实镜头任务开始后才按宿主权限规则运行。

从宿主能力信息获取 Blender 绝对路径和当前工作区；不依赖作者电脑路径或假设 `blender` 已在 PATH。将 `<SKILL_DIR>` 解析为安装后本 Skill 包根目录；桥接脚本位于 `scripts/` 下。输入工程必须先安全复制到工作区，GLTF 的外部资源一起复制并保持引用；运行只读取输入，输出必须是新文件。

各命令中的路径占位符是说明，不是默认实际路径。命令用参数数组执行，特别是用户描述不得拼接进 shell。macOS 图形程序应从首次执行起遵守宿主沙箱外审批规则。

## 命令

```text
<BLENDER_EXECUTABLE> --background --python <SKILL_DIR>/scripts/hi3d-camera-bridge.py -- inspect --workspace <WORKSPACE> --input <WORKSPACE_SCENE> --output <WORKSPACE>/exports/camera/take01/hi3d-scene.json

<BLENDER_EXECUTABLE> --background --python <SKILL_DIR>/scripts/hi3d-camera-bridge.py -- compile --workspace <WORKSPACE> --plan <WORKSPACE>/exports/camera/take01/hi3d-shot-plan.json --output <WORKSPACE>/exports/camera/take01/hi3d-camera-trajectory.json

<BLENDER_EXECUTABLE> --background --python <SKILL_DIR>/scripts/hi3d-camera-bridge.py -- bake --workspace <WORKSPACE> --input <WORKSPACE_SCENE> --trajectory <WORKSPACE>/exports/camera/take01/hi3d-camera-trajectory.json --output <WORKSPACE>/exports/camera/take01/hi3d-camera-scene.blend --report <WORKSPACE>/exports/camera/take01/hi3d-camera-basic-checks.json
```

`inspect` 支持 `--scale-m-per-unit <POSITIVE_NUMBER>`，只用于已有可信尺度证据的情况；不传时 `.blend` 的 `unit_settings.system=NONE` 被标为 `unverified`，导入 glTF 的空间单位按规范解释为米。无物理尺度时可以规划相对布局，但不能在未知尺度上调用烘焙并假装间隙、速度是米制验证。

每次只生成一个新 take 目录，不覆盖已有版本。输出存在时脚本立即失败，恢复者判断是已经完成还是部分生成，再只补缺少阶段；不要为了重跑删除原计划或改写原模型。按宿主数据保护要求校验解析路径、符号链接和多硬链接，脚本还对其接收的输入输出做工作区边界检查。

## 脚本职责

- `inspect`：读取已复制场景；列出稳定对象名、包围盒、原相机、单位、fps 和帧范围；不是完整原生场景图、SDF 或碰撞检查器。
- `compile`：接受统一计划，产生连续采样的本地确定性轨迹。Agent 负责语言理解、真实对象解析、锚点和导演选择。编译器不自动调用 API、上传、下载或执行模型。
- `bake`：对统一轨迹做基础门禁，保存基础报告；新建独立相机、烘焙逐帧关键帧并另存工程。基础失败不写可交付工程。场景尺度必须与 inspect/计划一致；`.blend` 具体单位来源由执行者在完整报告中核实。相机所在场景的 fps/区间会按镜头计划配置；若原场景有动画，只改变播放窗口而不重定时关键帧，并在交付中说明。

脚本不会自动进行几何避障、渲染、资源打包或工程重开检查。执行者必须完成 [验收规则](hi3d-validation.md) 后才宣称业务完成。非中心主点、非方像素、正交/鱼眼镜头和偏移镜头不在桥接器第一版支持范围，不能默默丢弃。

## 产物和记录

基础产物名：`hi3d-scene.json`、`hi3d-shot-plan.json`、`hi3d-camera-trajectory.json`、`hi3d-camera-basic-checks.json`、`hi3d-camera-checks.json`、`hi3d-camera-scene.blend`。实际预览、附加转换脚本和说明也用 `hi3d-` 前缀。这里列出的名字不是已生成文件清单。

执行者在包外的当前工作区任务记录中，记录各阶段实际开始、结束、状态、后端和输入输出关联。阶段耗时缺失就注明未知，不虚构服务计算时间；不保存密钥和完整鉴权环境。桥接脚本报告的时间只覆盖该命令，不能代替全流程计时。

## 最小验收任务与恢复

1. 用用户拥有的米制房间场景或经授权生成的测试场景，完成 `inspect`；输入输出文件不相同，原相机和主体变换保持。
2. 先按视觉导演前置流程查看真实图像、拟稿、完成弹窗核对并记录当前描述版本，再使用契约示例格式编写本场景真实坐标计划，完成 `compile`。确认最终时间、动作顺序和焦距；这是首次业务验证，不是创建本 Skill 时的既有成功记录。
3. 做完整场景安全检查后 `bake`，基础报告和工程均实际生成；新进程重开核对并产出真实预览。
4. 故障时保留上游原始结果和本地报告。坐标未知则停止导入；门禁失败则只修对应计划；工程已经生成但预览中断则只继续重开/预览。不重新生成已经合格的候选或安装环境。
