# 制作记录

复制到包外任务目录后填写。未知值写 `null`。没有该需求的子系统写明不适用，不造空任务。路径尽量相对工程。

## 范围

- `host_os`：实际执行机器的系统与 CPU 架构
- `target_platform`：用户指定的平台；未指定时为当前宿主可打开的工程
- `asset_mode`：`hi3d` / `existing` / `procedural` / `auto`
- 本次是新建、指定工程的局部修改，还是只打包

## 视觉

- `art_direction_version`
- 选定概念图、提示词版本和必须保留的特征
- 可玩范围、可视范围、展示路线和活动节点
- 概念证据与 UE 画面证据分开

## 每项资产

- `asset_id`、家族、作用、`dimensions_cm`、`min_view_distance_cm`
- 来源：本次新制，或用户指定复用
- 母版与变体关系；主要建筑或人物的结构、功能或行为差异
- 单体图、输入哈希、无密钥参数摘要
- 源高模、运行副本、UE 资源路径
- 模型任务 ID 与状态；绑定调用 ID 与状态。两者不要混用
- 状态：`draft` / `reviewed` / `accepted` / `rejected`
- `visual_status`：`not_checked` / `captured_unreviewed` / `reviewed_pass` / `reviewed_fail`

## 运行

- 引擎版本、主地图、输入、相机和性能测试条件
- 保存重载结果
- 打包状态；未要求打包时写不适用
- 阶段：`not_started` / `in_progress` / `passed` / `failed` / `blocked`

没有虚幻引擎时，导入、样板画面、运行和打包保持未验证，并写明探测到的缺失项。
