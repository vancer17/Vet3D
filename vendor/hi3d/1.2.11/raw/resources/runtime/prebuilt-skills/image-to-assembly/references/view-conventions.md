# Hi3D 视图定义与提交校验

## 分开三种命名

**API 槽位、官网界面标签、物体自身左右不是同一命名层。** 以 `api_slot` 保存上传方向；部件名 `LeftArm/RightArm` 只表示语义身份，不决定拍摄方向。文件名也不作为方向证据。

2026-09-09核对[官网工作台](https://www.hi3d.ai/zh/workspace?panel=generate-3d&view=multi-view)公开前端：界面 `Left` 使用 `apiSlot:right`，界面 `Right` 使用 `apiSlot:left`；[当日公开代码](https://hitem3dstatic.zaohaowu.net/website/nuxt-app/public/_nuxt/DzXIWTpoFJRPBFZQ.js)还将示例数组映射为 `front:0, back:1, left:3, right:2`。[官方 API 文档](https://docs.hi3d.ai/zh/api/api-reference/list/create-task)规定上传顺序为 API front/back/left/right，不能直接照搬界面排列。

官网猫形机器人示例可直接核对：正脸在[示例1](https://hitem3dstatic.zaohaowu.net/FE/static/sparc3d-website/example/general_multi_to_3d_example1.webp)，后背在[示例2](https://hitem3dstatic.zaohaowu.net/FE/static/sparc3d-website/example/general_multi_to_3d_example2.webp)；[示例3](https://hitem3dstatic.zaohaowu.net/FE/static/sparc3d-website/example/general_multi_to_3d_example3.webp)脸朝画面左、持骰子手在近侧，进入 API right；[示例4](https://hitem3dstatic.zaohaowu.net/FE/static/sparc3d-website/example/general_multi_to_3d_example4.webp)脸朝画面右、垂下的手在近侧，进入 API left。这是官网代码与图像的交叉核对，不是仅凭一次随机生成推断。

网站资源会更新；变更时重新核对当日标签、样例与槽位，记录版本。不能把哈希资源链接视为永久接口，也不能将本地坐标称为供应商承诺的原生网格轴。

## 唯一工作坐标与相机表

在送入 Hi3D 的部件局部工作框架中，正面朝 **−Y**，上方 **+Z**；前视图画面右方为 **+X**。这是右手坐标框架，避免再把 +X 直接称为“物体自身右侧”。已有项目采用别的坐标时记录变换，不改语义部件身份。

相机朝向原点、上方向 +Z。生图参考相机、提示词、检查渲染和上传都读取 [view_contract.py](../scripts/view_contract.py) 的 `CAMERA_DIRECTIONS` / `SCREEN_FRONT`：

| API 槽位 | 相机所在方向 | 图中正面方向 | 当前官网界面标签 |
|---|---|---|---|
| front | −Y | 朝向相机 | Front |
| back | +Y | 背离相机 | Rear |
| left | −X | 朝画面右 | Right |
| right | +X | 朝画面左 | Left |

“正面方向”可用脸/喙、车头、椅前沿或选定功能面判断，不限人型。无天然正面的物品先选定功能面；不要用图片水平翻转冒充另一真实侧面，以免文字和非对称附件翻错。

## 生成与放行

1. 开始生图前为每个 API 槽生成带轴/朝向标记的诊断粗模视图，核对前向地标在侧图的投影。实际上传图片去掉辅助标记。提示词明确相机方向和“正面特征朝画面左/右”，不能只写 left/right。
2. 看实际图确认前向地标和非对称附件关系，再填写[清单模板](../assets/views-manifest.example.json)。路径相对清单目录；四图可用任意文件名，`views` 键始终是 API 槽。记录摘要、相机方向、画面前向、`direction_reviewed` 和具体证据。旋转对称且方向不可观察时明确 `rotation_symmetric=true`，记录范围，不伪造可见地标。
3. 通过 [受审视图交接](hi3d.md) 的 `reviewed_submit.py --views-manifest` 提交，显式提供独立hi3d-api工具目录；固定API顺序核对位图、相机方向、画面朝向、审查与字节摘要。方向错误、图像更新或缺审查在鉴权前失败；单图直接交给独立工具。
4. 提交记录还保留实际 multipart 回读的文件数、顺序、摘要和请求体摘要。清单校验不能自动理解图像内容，执行代理仍须做第2步的真实视觉检查；不能把手填元数据当图像正确的证明。
5. 高模检查时保留相机约定和输出来源。背面混入前脸、侧面前后颠倒时先核对这条链及官方示例，再决定修图或有依据的重试；不能直接归因于模型能力。

既有图片按显式API槽位迁移，不必为文件改名重生；只有预览名称改变而几何未变时不重新付费。
