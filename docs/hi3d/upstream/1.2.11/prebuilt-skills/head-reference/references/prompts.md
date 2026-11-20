# 两种四视图与共用图像处理

版本化执行使用本能力的 [内置评审契约](review.md)：下列目视要求仍须实际查看，不由字段校验替代。完整矩阵、调用方附加规则与人工确认共同决定交接，旧的零散 pass 记录不自动等价于新版检查通过。

四视图有 aligned（转正）与 current（保留原姿态）两种策略；裁切、背景、颈部与材质是共用处理，不是三个必经业务分支。head/front 单图仍可独立执行；多输出不串接前一档。共用主体 A、调用方必选造型 H，姿态 B 二选一，外观 C 独立。H 没有时留空，有时每次生成/修订都携带。aligned 的正面约束仅用于其 front；current 不附任何转正句。

本页长块可按所选分支直接组合为实际 prompt，同时作为语义和验收依据；不要求无条件改成短版。按实际服务限制检查最终文本（含调用方 H/耳部规则/材质/布局及修订要求），仅超限时等义改写；不得直接截断或丢掉必选约束。调用方提供组合配方时优先按其分工，保存最终实际 prompt，仍按本页姿态和一致性标准实际看图。

## A. 共用主体与身份块

> Edit the supplied image of this same person. Isolate the complete head, including the full hairstyle, ears, eyebrows and existing head-worn accessories. Preserve identity, facial proportions, age, expression, natural asymmetry, hairline, parting, hair length, hairstyle volume and accessory placement. Remove the shoulders, chest, body, clothing and pedestal. Do not shorten long hair to fit a head-only crop; keep the crown, chin and all visible hair tips inside the frame with a small margin. Use the agreed neck crop and a clean neutral background. Do not beautify, rejuvenate, replace the person, add hair to bald areas, remove accessories or add text or a watermark.

把 agreed neck crop 替换成已确认的 `a natural short neck, with no shoulders` 或 `head only, without a visible neck`。不得把不确定的装饰物或垂下的长发当作背景删除。源图已缺失的发梢/头顶不能凭空宣称保留，必要补全注明推定。

若 H 或用户明确指定局部删除，把 A 中 full hairstyle / hair length / all visible hair tips 的保留范围改为“除该明确删除部分外的其余头发”，不要发送冲突约束。删除范围及原因写进 manifest；D 中同样保持已批准的删除结果，不因换视角重新补回。这个组合规则不自动授权删除其他刘海、长发或饰品。

## B. 姿态增量：二选一

### B(current)：保持姿态（head 或当前四视图基准）

> Keep the original head orientation, camera viewpoint, gaze and expression unchanged. This edit isolates the head only; do not turn it toward the camera, level a tilted head or invent extra views.

current 还必须明确：`Preserve the source yaw, chin-up or chin-down pitch, and sideways roll exactly in the anchor view. Do not level the eyes, straighten the head, neutralize the pitch or replace the camera viewpoint. Preserve the source projection cues; do not force a frontal orthographic portrait.` “exactly”是生成目标，不是已测角度保证。

### B(aligned)：转正（front 单图或转正四视图基准）

> Reorient this same head into a strict straight-on frontal orthographic reference at eye level: zero intended yaw, pitch and roll, with the head upright and the camera facing the facial plane squarely. Correct the head's orientation, not just the gaze. No three-quarter view, turned cheek, chin raised or tucked, head tilt, camera tilt or perspective from above or below. The eye line should read level; the facial midline should read vertical; paired facial features should have comparable perspective without erasing real anatomical asymmetry. Change head orientation and camera viewpoint only as needed. Preserve the original expression and personal asymmetry; do not mirror, symmetrize or beautify the face.

转正不等于改为无表情，也不自动闭嘴、去饰品或做光头。眼睛注视方向只有确有需要并已明确时才另加，不能把 neutral yaw/pitch/roll 解释为 neutral expression。

## C. 外观：与姿态模式独立

没有风格转换要求时追加：

> Preserve the source appearance and natural colors of the skin, lips, hair, eyebrows, eyes and accessories, including the person's recognizable age-related skin detail. Do not introduce a resin, clay, gray-model, illustration or beauty-filter treatment.

有明确材质配方时**替换**上述默认块，而不是同时要求“保留原皮肤细节”和“去细纹”。有 H 时同步限定默认外观块的适用范围，例如保留发色与发型但不保留 H 明确要求消除的毛丝质感。C 不覆盖 H，也不改 A/B 的身份、范围及姿态目标。明确复用已有树脂图时保持已确认材质，不重新套自然皮肤要求。

独立单图 head 为 `A + H + B(current) + C`，front 为 `A + H + B(aligned) + C`。四视图从原图建立自己的基准，按 pose_mode 选择同一个 B 块，不依赖另两张单图；明确复用时才续接。旧称 B(head)/B(front) 分别对应这两个姿态块。

## D(aligned). 转正四视图

从原图用 `A + H + B(aligned) + C` 建立自己的正面基准并验收；它不是 front 单图的自动续接。明确复用已有合格正面时才省去此步。其余视角用以下 D(aligned) 与完整 H，外观跟随基准，不再附 B(aligned) 去覆盖侧/背面。

> Using the approved front head image as the identity, crop and appearance reference, produce the SAME complete head in four orthographic views: FRONT, RIGHT, BACK, LEFT. The front is upright and straight-on at eye level. RIGHT means a strict side profile whose nose points toward the RIGHT edge of the image. LEFT means a strict side profile whose nose points toward the LEFT edge of the image. These labels describe the nose direction on screen, NOT the camera's side or the person's anatomical side. The two profiles must face opposite screen directions: in RIGHT the nose is on the right and the back of the skull on the left; in LEFT the nose is on the left and the back of the skull on the right. Use strict 90-degree profiles without a visible far-side eye or far-side nostril; do not uncover a near eye hidden by the original fringe. Never duplicate the same side. The back must show the rear of the head, not another face. Preserve one consistent identity, age, expression where visible, hairline, parting, hairstyle silhouette, hair length, accessories, colors and approved surface material across all views. Match head scale, top and bottom extent and the agreed neck crop. Retain the full hair; no shoulders, chest, clothing or pedestal. Infer only the hidden surfaces needed to complete one coherent head. Side and back views must be genuine changes in viewpoint, not mirrors or rotated copies of the front image. Keep a clean neutral background and consistent broad soft illumination. No text, labels or watermark.

工具输出独立图时直接要求四张并保留视角标签；工具仅适合拼图时再追加：

> Arrange a 2x2 sheet: FRONT upper left, RIGHT (nose pointing image-right) upper right, BACK lower left, LEFT (nose pointing image-left) lower right. Use a narrow plain gutter, equal-size cells and no written labels; keep every head and hair silhouette fully inside its cell.

四格按阅读顺序固定为 `front, right, back, left`：左上 front、右上 right、左下 back、右下 left；左右以鼻尖在画面中的朝向命名。manifest 声明 `view_convention=screen-nose-direction-v1`，文件名与语义标签保持一致；下游上传顺序由调用方按服务契约适配，不把“相机左/右”直接当作 left/right。拼图切分时去掉真实分隔线，各图等比 pad，不拉伸；格位是目标，切分后仍须实际检查方向，不能仅凭位置或文件名认定通过。

长版与必要的限长改写都保留正向位置描述：右上鼻尖朝该格右边缘、后脑在左；右下鼻尖朝该格左边缘、后脑在右。两侧应为相反方向的真实严格侧面，不露远侧眼或远侧鼻翼；近侧眼可被原有刘海遮住，不为露眼改发型。若实际两格仍是同侧，不能仅交换标签或镜像补齐；按原修订边界重新生成缺失方向，再检查整组。用错误四格作修订参考得到成功，不等于只输入基准的通用配方已验证；复用验证须记录真实参考图、实际模型和最终 prompt，并检查独立生成的输出。

复用旧图时保留原图片、实际 prompt、生成输入和旧 manifest。若仅左右标签错了，另存新 manifest，按实际鼻尖朝向同步调整 images/prompts/generation_inputs 的键与引用并重新评审；需要新文件名时另存不改像素的副本。不能只补约定字段就称已迁移，不镜像图片、不改写旧实际 prompt，不因命名修正自动重新生图或重提旧模型。

## D(current). 当前视角四视图

从原图用 `A + H + B(current) + C` 得到 view_0，分别验收原 yaw/pitch/roll 保留后补其余方向；不能先转正再试图恢复姿态。采用固定头部、移动相机的表达：以基准画面的上方作为虚拟环绕轴，相机向基准相机的左侧绕行，目标为 0/90/180/270 度，保持相同镜头模型、距离与目标中心。该坐标约定只是生成配方；单张照片不能唯一分解头部与相机的实际姿态。若原图几乎竖直俯拍等导致方向不明确，先澄清，不伪造精确相机。

> Use the approved CURRENT-VIEW anchor as view_0. Preserve the same person's head in its original posed orientation, including the original yaw, chin-up/chin-down pitch and sideways roll. Freeze that posed head in one shared scene. Move only the camera around it, using the anchor image's up direction as the virtual orbit axis: view_0 at the original camera, view_90 one quarter orbit toward camera-left, view_180 opposite that camera, view_270 three quarters around in the same direction. Keep the same lens/projection, camera distance, target center, lighting, crop policy, material, identity, expression, hairline, hairstyle and approved local deletions. These names are RELATIVE camera positions, not anatomical front/left/back/right. Do not straighten, level or front-align the head in any view. Do not force the same 2D eye-line tilt in every view: the projections must follow the SAME frozen 3D pose. Generate true new viewpoints, not rotated or mirrored copies. Infer only unseen surfaces needed for one coherent head. Keep the complete head and hair within equal-size frames with comfortable margins; no shoulders, body, pedestal, text or watermark.

与 D(current) 同时携带完整 H 与所选材质保持句。可独立四图；仅工具需要时用 2×2：左上 view_0、右上 view_90、左下 view_180、右下 view_270，无文字。每张等比 pad，允许同一摆放姿态换视角时投影轮廓自然变化，不拉平、不强行等高，也不要求 view_180 必定是纯后脑。保留相对标签，不把 view_0 改称 front 来凑服务格式。

## 检查与恢复

| 模式 / 单图操作 | 必须检查 | 不应发生 |
| --- | --- | --- |
| head | 原姿态、表情及身份保持；头顶/下巴/长发完整；无肩胸；满足 H | 自动转正、未请求的材质/皮肤变化、截短长发 |
| front | 上述范围及 H 保持；分别检查实际 yaw/pitch/roll | 镜像或只转眼睛冒充转正、抹掉个人不对称、把表情改中性 |
| four-views / aligned | 本分支正面通过姿态检查；标准四向真实、同一身份/发型/尺度及颈部范围，各图满足 H | 四张正面、左右镜像、后脑长脸、逐图变发型、未验收正面 |
| four-views / current | view_0 对照原图分别保留 yaw/pitch/roll；相对四向真实且为同一固定姿态，各图满足 H | 擅自转正/摆直、抬平或低头归零、逐图改变姿态、二维旋转或硬套正面鼻尖规则 |

以下零度方向的检查只适用于 front 单图及 aligned 的正面。current 用相同解剖线索逐项对照原图的保持程度，不要求眼线水平、中线竖直、两侧显露相等，也不因原有偏航/俯仰/侧倾而判失败；需要原图和 view_0 共同证据。所有模式都须查看全图及细节：

- yaw（左右转头）：综合鼻梁/鼻尖与面部中线、两侧眼眶/颧部的透视缩短、脸颊显露与耳部可见性；不能只看鼻尖居中或双眼是否注视镜头。发型遮耳和真实面部不对称不能单独作为转头证据。
- pitch（抬头/低头）：综合鼻底/鼻孔、下巴底面及额头/下半脸的俯仰透视；不要为减少鼻孔可见性而改鼻形，也不凭单一解剖特征判定。
- roll（侧倾）：综合双眼内外角连线与面部中线是否相对画面水平/竖直；不要用镜像对称或局部拉伸消除个人不对称。

记录 `pass/fail/uncertain` 与实际观察，未观察记 `not_checked`；只有必需项全为 pass 才可交接。二维目视无法证明精确的零度姿态，不编造角度或算法分数；若使用关键点/姿态估计，附实际方法、可信度与图像版本，估计值仍须目视复核。拿不准不能默认为 pass。检查表空白或仅写“正面”不算验收。

所有模式均核对 H；不能以“大体有发束但仍有密集毛丝/尖薄发梢”通过头雕造型检查。针对失败点修订，保留原图、旧版和实际 prompt，不覆盖已通过基准。同一问题连续两次针对性修订仍失败就交用户选择。四视图缺项只处理缺项及一致性；基准变更后重查全部关联视图。各输出独立失败/恢复，不自动重跑 mesh。

manifest 至少记录：`mode`、`pose_mode`、`source`、`generation_inputs`、`reference_anchor`（本模式基准；旧 reference_front 仅用于 aligned）、`required_shape_constraints`（H）、`neck_crop`、`appearance` 与每项 path/sha256/view/size/pad/inferred/reused。评审 request/decision 输出派生 `view_frame`，相对角度是生成目标，不是相机标定。checks 绑定图片及实际 prompt：aligned 查转正，current 查保留原 yaw/pitch/roll 与固定姿态的相对视角。记录 generation_status、review_status 和失败原因；改图、模式或 prompt 后旧结论失效。推定图不提供高模三维真值。下游不支持该语义时暂停交接，不擅自改图或改标签。
