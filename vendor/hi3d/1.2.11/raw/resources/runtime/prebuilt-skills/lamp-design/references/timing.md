# 业务阶段耗时

执行者在用户实际调用 `$lamp-design` 开始设计、修复时计时；编写、迁移、安装或维护 skill 不适用。随包脚本只执行局部能力，**不会自动采集全流程耗时**。在包外任务目录建立 `timing.jsonl` 与交付摘要，并将位置写入 `lamp-manifest.json` 的 `timing` 字段。运行记录不写回技能或仓库。

## 阶段与记录

按实际工作划分 `intake`（需求与选择）、`research_concept`、`shell_model`（本地或 Hi3D 外壳）、`hardware_structure`、`fdm_validation`、`render_video`、`web_package`、`delivery`。已有模型复用、纯概念或修复范围内不需重做的阶段标 `skipped` 并说明理由。生成与等待可拆子阶段。不要为了填齐列表实际重跑服务。

事件身份、起止与缺失字段、崩溃恢复、墙钟和可选 token 的完整口径统一读取 [run-tools 阶段记录契约](../../.dependency-run-tools/references/stage-records.md)。本页只维护上述品类阶段、任务文件位置及人工覆盖范围；不另定义事件 schema，不把局部脚本改称自动计时。

放射竖片修订可在上述阶段中记录 `radial_constraints`、`radial_geometry`、`logo_projection_review`（仅严格顶视）、`export_precision_review` 和 `web_light_review` 子阶段。仅修改片体时跳过已合格的中心饰物与灯路制作；投影验收、开关网页和最终打包均绑定本版产物。
