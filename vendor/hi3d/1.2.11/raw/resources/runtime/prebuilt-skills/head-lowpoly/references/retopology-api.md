# Runtime 重拓扑与本地烘焙

本流程使用随包 `$mdf-api` 的 Runtime `mdf_api`，能力 `retopology`，参数为 `face=remesh_face_goal`、`face_type="quads"`、`topology_method="standard"`。接口接受 GLB，公开契约没有纹理/法线烘焙步骤；不能按 mesh-lod 的减面烘焙能力解释。保留 prepare 阶段的完整原高模，后续本地 Blender bake 仍生成 albedo、normal 和需要的 PBR 通道。

## 执行与恢复

1. 运行 `scripts/run.py`，本地 prepare 保留完整源工程，working_surface 导出单个头部的 `working_surface.glb`。减密副本仅用于 API 输入，不替换原始烘焙源。
2. 没有已完成结果时脚本退出 3，状态为 `waiting_retopology`；读取输出目录的 `retopology-request.json`。其中 `arguments` 就是 Runtime `mdf_api` 参数。先添加 `dryRun=true` 离线校验，再用相同参数正式执行；`waiting_choice` 交给宿主全局弹窗。用下载结果重跑脚本或 download 恢复不新建请求，不再弹窗。不要通过 shell 调用联网 Python。
3. 工具使用稳定的 jobPath 和 outputDir，保存原始响应及下载哈希。仅 SUCCEEDED / HTTP 200 / code=0 可继续。下载缺失用 Runtime `mdf_api(action="download")` 和原 job/outputDir 恢复。UNKNOWN 保留 job/requestId 核对，不轮询 MDF，不换路径重提。
4. 下载结束后，用原配置再次运行 `scripts/run.py`。无需手工填入结果路径：脚本从原始 MDF 记录的 downloads.model_obj 取下载文件，校验请求指纹、输入字节、参数、输出目录与下载 SHA-256。不要用工具摘要替代完整 job 文件。
5. 缓存复用已完成的本地准备。修改纹理尺寸只重做 bake 及其下游；工作网格或重拓扑参数变更导致原请求不匹配时停止，只有明确的新处理意图才设置新的 retopology_job。`--fresh` 仅重做本地阶段，不授权重复远程提交；等待服务期间不要使用它。

账号和环境由 Runtime/桌面代理检查，本地脚本只检查产物来源，不读取或验证登录密钥。服务耗时以 Runtime/job 的真实记录为准，不能把两次本地调用之间的间隔说成实测算法耗时。

## 四边面 OBJ 交接

服务端新增 `data.model_obj` 和 `data.files.model_obj.{key,url}`，指向 OBJ ZIP；原有 `model_glb` 保留。请求参数、登录鉴权均不变。Runtime 下载 ZIP 并保存哈希，head-lowpoly 只读取其中唯一的 OBJ 几何，不解压任意路径、不加载材质引用。

按输入 GLB 的 Y-up 坐标解释 OBJ，再转换到 Blender 工作坐标；这是当前导入约定，服务端回复尚未明确坐标轴。通过与工作模型包围盒比较进行检查，偏差超限即停止，不自动对齐。导入还要求单个网格、有限坐标、全部为非退化原生四边面；不配对 GLB 三角面。旧记录仅有 GLB 时停止，保留记录，不自动重提交；有 OBJ 描述但未下载时可用原记录执行 download。

通过检查后继续现有眼口修订、绑定、验证及本地 bake。烘焙来源始终是 source.blend 的完整原高模，服务响应新增 OBJ 不代表包含烘焙。
