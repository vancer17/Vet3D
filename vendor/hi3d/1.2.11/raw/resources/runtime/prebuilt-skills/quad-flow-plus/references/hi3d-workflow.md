# Hi3D 对话工作流回填

配置：[工作流节点](../pcg/architecture.yaml)。本文件只描述执行时的回填约定，安装分析时不要执行 Skill 或调用这些工具。

1. 执行前调用 workflow_report，operation=inspect，skillName=quad-flow-plus，读取已加载的节点和状态。沿用原节点 ID 与父子关系，不重新编造计划。
2. 本 Skill 中断后继续时使用 operation=resume，保留已完成节点与已有产物。只有标签需要翻译时使用 operation=plan，并保留全部原节点。
3. 阶段开始时调用 operation=node、nodeId=配置中的节点 ID、status=running。实际完成、跳过、中断或失败后回填 completed、skipped、interrupted 或 failed，不把普通工具返回当作阶段完成。
4. 对实际生成的文件调用 operation=artifact，在 artifacts 数组中填写 nodeId、kind、label 和工作区相对 path；模型使用注册后的准确 fileName。不要上报尚未生成的文件或伪造产物。
5. 开始整体任务时将 agent 根节点标为 running；全部必要阶段完成、可选阶段明确跳过且交付验收通过后，将根节点标为 completed。完成前再次 inspect，确认所有节点状态和产物归属。工具不可用时仍按原 Skill 完成工作，明确说明进度未回填。

工作流配置不赋予额外权限，也不替代对话中的参数确认、计费确认或交付验收。

在本仓库，阶段起止、跳过和耗时同时写入包外任务目录，口径见 run-tools 的阶段记录。`workflow_report` 只在宿主实际提供该工具时使用；不可用时不伪造节点状态。节点 ID 仍以 `pcg/architecture.yaml` 为准。


## 预算重建分支

继续使用原7个节点ID；冻结节点记录本轮模式、可靠边链和真实保护范围，优化节点执行已授权分支，验收节点分列数量、约束、保形、属性和交付状态。节点completed表示该阶段按用户约定范围执行完毕，不自动代表全部质量指标通过；已约定允许的试做交付须保留未通过项。存在未满足且未获试做交付允许的硬质量标准时，保持相应工作未完成。
