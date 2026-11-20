# auto-rig

服务代码：[hi3dreamer/auto-rig](http://172.31.0.3:8099/hi3dreamer/auto-rig)。

基于 SkinTokens 的自动骨骼与蒙皮服务，单模型输入，返回带绑定的 GLB；不生成动作。

输入、输出、参数默认值、来源版本限制及统一 mdf-call 调用示例见 [service-select 服务契约](../../.dependency-service-select/references/mdf/auto-rig.md)。使用 `--service auto-rig`，以 `mesh` 文件引用提交并接收 `rigged_mesh`；与其他 MDF 下游服务共用默认 HTTP 中控入口，SDK 队列/TCP 直连为显式选项。

[服务速查](../mdf_list.md) · [共用格式](README.md)

人形输入推荐静止身体单独提交；原始服务结果、高模回迁和动作修复的职责边界在服务页维护。完整本地流程及可复用脚本见 [身体绑定与蒙皮修复](../../rig-retarget/references/service-rig.md)，作为另行提供的业务工作流使用；不以归一化或非空 GLB 代替关节变形验收。
