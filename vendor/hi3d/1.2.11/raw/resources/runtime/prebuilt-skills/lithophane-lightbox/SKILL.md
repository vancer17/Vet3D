---
name: lithophane-lightbox
description: 根据照片或已有浮雕制作发光浮雕相框，先选择外框尺寸及混色打印或 UV 打印工艺，复用 V5.1 参数化框体，生成制造文件，并在实际切片软件中配置、检查和打开项目。也支持只做尺寸评审、照片板适配或已有项目修改；不用于通用艺术相框或透光灯罩，也不默认启动实体打印。
---

# 发光浮雕相框

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D，生成图案的条件见 inputs 阶段。加载本入口后把 [宿主编排提示](../.dependency-pcg-view/references/host-orchestration.md) 注入编排 agent。通用艺术相框仍用 [frame-design](../frame-design/SKILL.md)；筒形透光浮雕灯仍用 [relief-lamp](../relief-lamp/SKILL.md)。本流程只做带 LED 背板的发光浮雕相框。

## 独立工作流与依赖

执行 lithophane-lightbox 前，按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。V5 接口、UV 制版与 V5.1 框体生成器随本包提供；混色 3MF 没有随包一键算法，必须使用当前可用的兼容工艺。[统一计时规则](../.dependency-run-tools/references/stage-records.md) 与下文阶段一起使用；已有合格接口、框体、照片板或切片工程可从对应阶段继续。

来源与修改见 [来源说明](references/hi3d-source-and-validation.md)。包内 `assets/frame-v5/checks/` 的历史 PASS 不是当前任务证据。

以 `$lithophane-lightbox` 或显式读取本文件调用。完整制作持续到“最终工程已在所选切片软件中打开，参数已写入并经真实切片检查”。尺寸评审、仅照片板或已有项目修改按用户范围执行。调用完整制作已包含本地切片与打开工程；不重复问“是否开始切片”。不发送到打印机、不启动实体打印，也不向 UV 店上传照片。

## 输入与完成结果

输入为照片附件、已有浮雕/高度场、已有框体工程，或仅尺寸咨询。第一次使用时一句话说明：采用已有参数化框体控制尺寸和装配，按所选工艺制作照片板，最后配置并打开切片工程。不要把此次选择变成付费生成授权。

成功时：

1. 外框尺寸与工艺均来自用户明确选择；推荐尺寸不是可视照片英寸规格，也不是超时默认。
2. 接口 JSON 给出可视画面、成品板、槽轮廓与安装边；不要再次从成品板减余量。
3. 完整制作含 12 件打印框体、真实照片板、制造包与原生切片工程；LED/金属五金只作包络，不混入打印件。
4. 数字检查不等于切片、实物装配、UV 附着或背光显色通过。

## 执行顺序

PCG 路径：`main` 从尺寸与工艺做到切片打开；`panel_only` 复用已有合格框体只做照片板；`size_review` 只计算接口；`reuse_project` 在已有项目上做尺寸或工艺修订。面板例子见 [交互与尺寸](references/hi3d-inputs-and-sizes.md)。机械尺寸见 [机械规范](references/hi3d-v5-mechanical-interface.md)。

1. **inputs**：区分新建、修改、恢复、仅咨询。复用附件与已确认参数。必选外框尺寸与工艺，使用 `kind=input`，不设超时默认。缺照片时保留接口方案，暂停依赖照片的制版；只有用户明确希望生成图案时才调用独立 [hi3d-api](../hi3d/SKILL.md)。不得擅自重画人脸。切片前收集真实打印机、喷嘴、材料与切片器版本。
2. **interface**：复用 [接口脚本](scripts/hi3d-frame-interface-1.py) 生成 `hi3d-frame-interface.json`。共用 `B=10 mm`、`O=3.5 mm`；可视画面 `(W−20)×(H−20)`，成品板 `(W−13)×(H−13)`，槽内轮廓再各加 0.4 mm。自定义 100–500 mm 是接口限制，不是床面范围。
3. **frame**：仅需照片板时复用已有合格框体。整框按 [整框复用](references/hi3d-frame-generation.md) 把生成器、检查脚本与配置复制到独立工作副本，用宿主 Blender 在 factory-startup 后台生成。后台打开、导入、另存交接 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。V5.1 为 12 个打印件：四根 45° 框条、四枚蝶形键、两根浮动压条、一块带一体铰座的 LED 背板、一副活动 U 支架。
4. **panel**：按所选工艺只走一条路线。混色读 [混色照片板](references/hi3d-mixed-workflow.md)；UV 读 [UV 照片板](references/hi3d-uv-workflow.md)，用已配准 0–1 高度场调用 [UV 制版脚本](scripts/hi3d-make-uv-panel-1.py)。从已有浮雕提取高度时交接 [relief-map](../.dependency-relief-map/REFERENCE.md)；脚本不会自动理解任意 GLB。缺必要数据时停止该依赖，不用占位板充当成品。
5. **validate**：按 [验证与交付](references/hi3d-validation-and-delivery.md) 做最少必要检查。闭合、法线、正体积调用 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md)。毫米 STL 调用 [print-export](../.dependency-print-export/REFERENCE.md)；UV 脚本自写的毫米 STL 回读后可跳过重复导出。支架开合与螺丝路径交接 [motion-check](../.dependency-motion-check/REFERENCE.md)。槽口/安装边试片需要成对裁切时交接 [fit-coupon](../.dependency-fit-coupon/REFERENCE.md)；透光阶梯片留在本流程。
6. **slicer**：完整制作按 [切片配置与打开](references/hi3d-slicer-workflow.md) 执行到打开最终工程。真实切片并回读首层、层序、支撑、料槽与床面；没有加载证据时明确尚未完成打开验收。用户明确只要尺寸或不要切片时标 skipped。
7. **deliver**：整理实际文件与检查记录。装配对照交接 [model-preview](../.dependency-model-preview/REFERENCE.md)。需要成果页时交接 [asset-page](../.dependency-asset-page/REFERENCE.md)，打开下载检查交接 [delivery-review](../.dependency-delivery-review/REFERENCE.md)；HTML 仅在用户要求或展示确有必要时新增。推荐测试任务见 [测试用例](references/hi3d-acceptance-cases.md)。迁入时未执行业务脚本、切片或实物测试。

图像调用失败立即停止相应流程，报告脱敏原因并保留记录；用户明确要求恢复前不自动重试。生成成功后的质量修改遵守当前宿主限制。

## 本地长任务预算

框体布尔/导出、UV 高度场网格和离线装配预览可能长时间占用 CPU。进入这些步骤前，任务目录必须已有预算和心跳；后台 Blender 由 [run-tools](../.dependency-run-tools/references/budget-run.md) 的 `process_run.run_budgeted` 启动。建议低档 120 秒、中档 600 秒、高档 1800 秒。低档可直接跑；中高档由宿主 `waiting_choice` 使用本入口 `choices_example` 确认后再启动。超时记 `interrupted`，不写半截 BLEND。Hi3D 远端等待继续走原 job。

UV 制版需要 Python 3.9+、numpy 与 Pillow，见 [scripts/hi3d-requirements.txt](scripts/hi3d-requirements.txt)。框体生成器只需 Blender 4.3+ 的 `bpy`。

## 恢复与记录

阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者把真实起止、状态和耗时写到包外任务目录，不要写入安装包。本包没有自动计时脚本，token 无采集时标 unavailable。尺寸变动时更新接口、裁切、几何和切片；仅改切片参数不重生成照片。授权配置切片不等于授权实体打印。

<!-- managed-by: sparc3d-runtime -->
