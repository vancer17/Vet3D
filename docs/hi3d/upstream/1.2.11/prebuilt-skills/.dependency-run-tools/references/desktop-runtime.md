
# Desktop Runtime 执行约定

本模式只在宿主实际提供相应 dynamic tool 时生效。普通独立包继续使用各入口声明的公共 API、内部服务或本地工具；不要从工具名称推断部署可用性。

- 新图片交给宿主 `hi3d_api(action="generate_image")`，图像编辑把实际主图、参考图和意图交接；新 3D 交给 `hi3d_api(action="generate_3d")`。读取 [账号生成契约](../../hi3d/SKILL.md)，先 dryRun，把返回的 `consent.user_interaction` 交给宿主 preference 面板，参数齐后再同样参数正式提交。下载/等待恢复原任务，不重复提交。不使用其他图像生成工具替代用户选择的账号生成链路。
- 图像、网格处理交给 `mdf_api`；读取 [公开处理契约](../../mdf-api/SKILL.md)，dryRun 后同样参数正式调用，`waiting_choice` 交给宿主。仅公开 capability 可调用，不能将内部 worker/service/options 字段发送给公开入口。UNKNOWN 无查询端点，不重发；成功但下载失败只恢复下载。
- 普通 Agent shell 不调用账号联网脚本，不读取 Cookie、代理 token、AK/SK 或真实环境值。宿主只向受管工具子进程注入代理能力；原型中公共 CLI/内部 MDF 示例仅在明确的非 Runtime 模式下适用。已有合格本地文件直接继续本地阶段。
- 使用宿主提供的明确 Python、Blender 和媒体工具路径。普通 Python 没有 bpy；Blender 内置 Python 的 ABI 与独立 Python 分开。媒体定位不下载安装器；缺少依赖时由宿主安装流程提供。
- 用户可见的新文件名遵守宿主 `hi3d-` 前缀；输入文件、隐藏任务账本和第三方压缩包内部结构保留原名。新 GLB 下载或修改后，按宿主要求先做 `image_classification(tag=4)`，再用 `workspace_commit_model` 登记；分类失败保留同一 GLB 重试登记，不重做生成。
- HTML 的资源放在同目录或子目录并用相对 URL；通过宿主 loopback HTTP 地址打开实际最终 HTML，检查图片、模型、视频、交互与下载。不要以 file:// 页面或源码检查代替浏览器验收。
- 计费提交（Hi3D 新任务、`mdf_api` 正式调用）与其他 `confirm_required` 不可逆动作，只走 [宿主编排注入](../../.dependency-pcg-view/references/host-orchestration.md) §5b 的全局 `waiting_choice`。Agent 不另做授权。
- 长任务进度由状态卡呈现；只补充等待、失败、需要决策等有意义变化。用户明确要求更高频率时遵从。未知进度不编百分比，不把已耗时当 ETA。
- 业务阶段耗时仍按 [阶段记录](stage-records.md) 保存于任务目录；外部生成等待与本地阶段计算分别说明，续跑间隔不算实测算法时间。
