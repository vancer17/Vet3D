# Hi3D Quality 与独立工具交接

## 依赖与输入

高模生成显式组合独立 `$hi3d-api`。将其完整目录另行复制到目标环境的技能发现位置并读取入口；本流程通过 `--hi3d-tool-dir` 指向实际工具目录，不依赖相邻目录或作者机器。需要 Python 3.9+；Blender和图像生成由宿主提供。已有合格GLB时直接继续配准，缺少生成工具不阻断其他本地阶段。

Hi3D AK/SK仅使用 `HI3D_AK`、`HI3D_SK`。AI不读取、打印、复制或验证值，也不读取凭据文件或shell配置；只有授权实际API进程内部消费。用户在AI外配置；维护测试仅用模拟客户端。此业务包不维护鉴权、HTTP、查询或下载客户端。

参数依据[官方创建接口](https://docs.hi3d.ai/zh/api/api-reference/list/create-task)；调用前由独立工具核对当前契约与权限。[随包配置](../assets/hi3d-quality-fourview.json)指定Hi3D3.0/2048quality、几何+纹理、PBR与GLB，200万面是起始值，明确用户要求优先。运行费用按实际结果，不固化案例扣费。

多视图为同一部件的2–4张独立正向PNG/JPEG/WebP、每张不超过20MB且含front；API顺序front/back/left/right，四图1111，前+右1001，前+左1010。单图用独立工具的 `submit model --image`；不能用四格拼图。官网标签、API槽和物体自身侧别按[视图约定](view-conventions.md)分别核对。

## 多视图执行

先真实看图并填好[方向清单](../assets/views-manifest.example.json)。以下变量为实际包和包外任务路径；每个唯一部件/获准重试版本使用独立job。生成授权沿用当前会话，不通过预检或余额查询扩大。

提交前确认两件事，缺一不可：该件视图审查已通过，且[生成前环绕关卡](proxy-segmentation.md#生成前环绕关卡)已通过。视图里的隐藏面若是 `inferred`，任务记录继续带着这个标记。下载完成后按[生成中在位环绕](registration.md#生成中在位环绕)审查该件，再决定依赖它的下一件能否提交。

```bash
python3 "$ASSEMBLY_SKILL/scripts/reviewed_submit.py" \
  --hi3d-tool-dir "$HI3D_TOOL" --views-manifest "$PART/views-manifest.json" \
  --params "$PART/quality.json" --job "$PART/generation/job.json" --dry-run
# 同一组参数去掉 --dry-run；waiting_choice 交给宿主全局弹窗。
python3 "$HI3D_TOOL/scripts/hi3d_api.py" wait --job "$PART/generation/job.json" --seconds 50 --interval 20
python3 "$HI3D_TOOL/scripts/hi3d_api.py" download --job "$PART/generation/job.json" --out "$PART/generation/download"
```

`quality.json`从随包配置复制，部分视图同步其位图。轮询pending继续同一job，attention/failed按工具恢复说明处理；分段等待并保持用户沟通。下载清单 `artifact.files` 中实际GLB作为后续原件，不能假设固定文件名或把下载目录当GLB。

## 适配器契约

随包 [view_contract.py](../scripts/view_contract.py) 提供相机表、`load_views`和`audit_multipart`：读取清单与图片，返回固定槽顺序、位图、非敏感审计；方向声明、审查、摘要、请求体文件数/顺序/字节不一致即失败。它不自动理解图像内容。

[reviewed_submit.py](../scripts/reviewed_submit.py)只编排业务校验和显式工具交接：`load_tool`验证完整外部包与模块来源；`reviewed_plan`先校验方向，再调用工具的`build_plan`/`multipart`并回读计划请求体，尚不创建客户端或鉴权。`ReviewedClient`把实际即将发出的同一流再次回读并复位，审计以 `job.json.views.json` 排他保存后才转交工具HTTP。`execute`复用工具的`submit_job`及状态语义，不复制任务生命周期。

兼容契约要求外部工具提供 `hi3d_parameters.build_plan/multipart`、`hi3d_jobs.submit_job/job_outcome`、`hi3d_client.Client/CREATE`、`hi3d_storage.save/public_record`；模块来源冲突或接口不兼容时停止交接，不能绕过校验改用裸文件提交。工具自身在提交前根据计划摘要复核文件，防止预检后字节变化。dry-run不联网、不读密钥、不写job；预览请求体与真实POST边界串可能不同，真实审计以提交时记录为准。

方向适配器不自动采集完整业务阶段耗时，执行者按[计时契约](contracts.md#阶段耗时与可选-token)覆盖生成与等待。跨部件全局去重由任务索引负责，单job幂等不阻止人为换路径重复生成。

## 恢复与原件

- 已有task ID只查询该任务；完整ID作为不透明字符串保存，允许点号。
- `submitting/submission_uncertain`或提交后本地异常时保留job与审计，先查控制台/服务记录；不能换job路径或自动重提。明确拒绝也要确认实际任务状态后才按授权处理。
- 旧任务记录不直接改成新job；保留原记录，从中取已有非秘密ID，通过工具的 `adopt model TASK_ID --job 新文件.json` 接管，再查询下载。
- 公共工具下载保持原始产物与摘要，失败保留中间文件，在新输出目录下载同一task；当前交接不承诺旧助手的Range续传。临时URL过期先重新查询同一任务，不另行生成，不在报告保存签名URL。
- 成功状态、下载或GLB结构检查不证明几何/贴图/装配正确，仍须Blender重开和业务验收。

## 离线验证

按入口打包约定生成业务工作流与工具的完整分发目录，并显式指定两个包的位置，运行 `python3 "$ASSEMBLY_SKILL/scripts/test_handoff.py" --hi3d-tool-dir "$HI3D_TOOL"`。测试使用合成图片、模拟客户端，覆盖方向拒绝、字节变更、两/四图顺序、真实流审计、重复和未知提交；不消费真实密钥或调用服务。公共工具生命周期与下载测试由其独立测试集维护。

## Runtime 审查后交接

`reviewed_submit.py --backend runtime --views-manifest FILE --params FILE --job FILE --output-dir DIR` 只返回宿主调用参数；desktop 分发默认 runtime。它验证真实视图方向、输入哈希及 bitmap，一份 arguments 先 dryRun 再提交。交接审查不等于已经审查网络 multipart；账号工具再次核验发送文件哈希。公共模式仍用 --backend public --hi3d-tool-dir DIR，并保留 ReviewedClient 的实际 multipart 审计。
