# 可打印头雕的参考图配方

主体范围、保持姿态/转正、四视图及实际姿态验收唯一维护于 [head-reference](../../head-reference/references/prompts.md)。本页维护头雕所有图像分支必带的头发造型 H 和独立的彩色树脂材料 C，不复制姿态与多视图能力。先看输入；人物性别、发型和饰品按实际输入，不写死案例人物。

主要选择是转正四视图 `pose_mode=aligned` 与当前视角四视图 `pose_mode=current`，后者保留原图 yaw/pitch/roll。头部裁切、颈部、背景、头发造型和材料是共用参数；head/front 单图操作仍可独立调用，不是先 head 再 front 再四视图。两种四视图分别从原图建立本模式基准，只有明确要求复用已有合格图时才续接并记录真实来源。

## Hi3D 实际发送的完整配方

按下文组合表准备本分支完整 A/H/E/B/C/D 约束。主体、姿态和多视图块从上方链接的 head-reference 读取，H/E 与彩色树脂材料从本页读取；任务消息不应另抄一套图像规则。只组合本次分支需要的块，不把整份说明文档、验收表或相互冲突的材料全部发给模型。

Hi3D 文生图和图生图的最终 prompt 按 [独立工具的计数策略](../../hi3d/SKILL.md#图片生成与编辑) 限制为 **4000 个字符**。先把包括实际颈部/删除范围、布局和追加修订的最终文本保存为 UTF-8 文件，执行该工具的 Python `check-image-prompt`；不目测，不按英文单词数或 token 估算，一个中文字或英文字母算一个字符，空格、换行和标点也计入。

完整英文长块可能超限，不能直接以“完整携带”为由发送。超过 4000 时，用下方 [H 紧凑表达](#hi3d-h-预算内等义表达) 与 [E 紧凑表达](#hi3d-e-预算内等义表达) **替换**对应长块，合并其他重复措辞，保持全部适用约束并精简到 4000 字符以下；再次执行 Python 检查，`valid=true` 才生成。无需压缩到旧的 900/1000 目标，也不能叠加两版、机械截断、省略 H/E 或把它们放到服务未定义字段。长块和详细解释保留为语义及评审依据，不属于必须逐字发送的内容。保存实际发送文本并绑定本次评审；追加修订或 request/settings 覆盖后重新检查，长历史修订合并为本轮仍有效要求，不逐轮累加整段旧 prompt。其他服务遵从其实际限制。

两种四视图仍从原图独立建立自己的基准，通过实际检查后才补视图。补图保留已通过的身份、姿态、造型和材料；失败版本保留，同项定向修订次数与 pending 原任务恢复边界不变。

## H. 所有模式共用、不可省略的头发质感

本 workflow 不论 head、front 或 four-views 的 aligned/current 模式，不论自然色、彩色树脂或灰树脂，所有参考图生成和修订必须携带本块；不能把它设成四视图专属或材质复选项。保留发色不等于保留照片毛丝。通用 head-reference 接收此块为 `required_shape_constraints`，自身其他非头雕任务不因此被强制树脂化。

区分处理对象：**大片发体塑出雕刻发流；独立垂下的细发丝适度加粗或局部删除；邻近大块头发的碎细发并入主体，成为连续雕刻发流的一部分**。不能把“简化大片头发”理解成抹平发流，也不能把“细发加粗”扩展为全头统一膨胀。以下两个英文段落共同定义 H 的完整语义；实际请求必须携带全部适用约束，超预算时使用下方等义表达，不要求逐字发送长块。

> HAIR — mandatory printable-sculpture constraint in every requested view: preserve the person's main hairstyle, natural hairline, parting, overall hair length, flow and volume. Replace photographic fibers with a coherent continuous solid molded sculptural mass. Treat fine hair by location: isolated dangling fine strands may be moderately thickened or locally removed; fine wisps near a large hair mass must merge into that mass as part of its continuous carved flow, not become separate thicker strands. Root-attached substantial bangs in front of the forehead or eyes may remain. Preserve their placement, natural direction and curvature; turn excessively slender fringe into coherent rounded sculpted locks with substantial, continuous root connections and gently tapered, non-needle tips. Free tips may remain separated from the forehead: do not indiscriminately remove substantial bangs merely because they hang free, force them flat onto the forehead, or bridge them with skin-colored sheets. Keep already substantial bangs unchanged. No detached floating fragments or hair-thin weak necks; if a connection is unclear, flag it for review instead of assuming success or deleting the whole fringe. Keep the main hair mass and natural hairline; do not shave the head, raise the hairline or remove substantial integrated bangs indiscriminately. Group fine fibers into naturally flowing broad, flattened connected locks with a clear hierarchy of main volume, broad locks, and visible medium-scale carved hair flow WITHIN the locks. Include curved incised channels and rounded ridges that follow the parting and natural S-shaped flow, with varied width, depth and spacing, fading before the rounded tips. These must read as modeled relief with soft groove shadows, not painted lines, dense fibers or smooth featureless petals. Fuse adjacent fine ridges and fill fine gaps; round fragile pointed tips without forcing all free ends to touch the face or other locks. Apply equally to crown, part roots, temples, ear margins, back hair and nape. No individual strands, fine parallel fibers, wisps, flyaways, hair cards, comb-tooth edges, hair-thin unsupported curls or fragile pointed ends. Simplify within the overall hairstyle silhouette, allowing local moderate thickening of slender fringe: no inflated ropes, tubes or petals, no added hair in bald areas. The hairline, sideburns and roots end cleanly at their true boundary: no extra thin shell, membrane, scalp-colored sheet or apron across the forehead, cheek, ear or temple. Preserve eyebrows and existing short facial hair as subtle shallow relief following their original shape and coverage, not thick locks or individual hairs. Avoid the obvious exaggerated false-eyelash effect associated with heavy makeup; soften or remove only those conspicuous artificial lash fans or clusters. Natural upper and lower eyelashes may remain. Preserve the original makeup, including eyeshadow, eyeliner and lip color, subject only to the selected material treatment; do not remove makeup or force a bare-faced or light-makeup look. Preserve eyelid contours, eye shape and eyebrows. Preserve identity and the requested pose; do not turn a side view into a front view.

> Where surface hair-flow grooves or ridges are excessively fine, you may moderately widen them into readable medium-scale sculpted relief during generation or editing, merging adjacent micro-lines where needed. Preserve their natural direction, curvature, taper and varied widths/depths within the existing hair mass; keep already-readable flow unchanged. Do not uniformly thicken all detail, inflate the hairstyle, create rope-like tubes, or smooth away the carved flow. Surface relief widening and the moderate fringe thickening described above are both permitted; neither authorizes globally enlarging the hairstyle.

过细的表面发流可适度加粗：沿原走向加宽细刻槽/细脊，必要时合并相邻微细线，保留中尺度雕刻层次、自然粗细/深浅变化及渐隐收尾。独立悬垂细丝可适度加粗为根部厚实、末端圆钝的实体束，或局部删除；靠近主发体的碎细发则融合进主体，整理为连续发流，不一律加粗成独立束。保留的悬垂发束保持方向和自然弧度，发梢不必贴额或与别束连接。已经足够厚实的刘海和清晰发流无需再加粗，不整体膨胀发型、不磨成光滑块。这是所有分支 H 的图像造型调整，不是默认开启几何后处理或在标签图里改变几何。

实际逐图验收分别检查 `hair_mass`、`carved_flow`、`hair_microdetail`：普通尺寸能看到连贯发束和清楚的发流；放大能看到束内中尺度刻槽及柔和阴影，而不是只有光滑瓣状块、画线或密集细丝。适度加粗后仍须保留宽度/深浅变化、沿发流渐隐的起伏，无针尖发梢或贴脸薄膜。`unsupported_fringe` 沿用稳定检查 ID，但按当前策略检查刘海根部连接、是否仍有毛丝状细颈/薄片和脆弱尖端，以及各视图加粗/局部删除/并入主体的结果是否一致；不能仅因发梢悬空判 fail。局部去除独立细丝，或保留有根连接且适度加粗的悬垂刘海，均允许通过；邻近主体的碎细发仍须并入连续发流，真正脱离主体的漂浮碎片仍不通过；连接被遮挡无法判断时记 uncertain。不能只把问题遮住、强制贴额或铺薄膜桥接来通过。

保留主要发型；允许局部删除独立垂下的细发丝，不等于删除整片厚实刘海、截短长发或改变发际线。主体附近的细发必须合并进去，不能只把它们加粗后继续独立悬挂。组合 head-reference 或灰树脂配方时，保留主发长/发际线，但允许本段的局部宽度和发尖圆润调整，不同时要求“每根细丝宽度都不动”。未满足实体质感或刘海连接要求即定向修订，不送入新 Hi3D 请求；合理加粗后仍无法解决时交用户选择，不自行大面积删发。不能靠膨胀成粗绳解决头发简化。图像表达不保证真实厚度、闭合性或切片结果，仍须按实际尺寸、材料和工艺检查网格；允许悬空不等于免除打印支撑评估。

所有材料与姿态分支沿用 `eyelash_removal` 检查 ID，但只避免浓妆中明显夸张的假睫毛效果，不再要求去掉全部上下睫毛。自然睫毛可以保留；保留原有眼影、眼线、唇色等妆容（仅服从已选材料转换），不要求卸妆、淡妆或素颜。按正常展示尺寸判断是否有明显假睫毛，不逐根放大追查，也不因少量自然睫毛反复重生。后脑或自然遮挡视图如实记录不可见，不改视角、不遮眼来规避检查。本条不是眼球几何修复。

## E. 四视图耳朵位置与头发遮挡一致，不要求露耳

两种 four-views 模式的基准生成、补视图及修订均携带本块。以同一个头部和发型为准，检查正面与侧面（current 则按相对视角）的耳朵相对位置、头发在耳朵前后的遮挡关系，而不是检查耳朵是否露出来。全部或部分遮耳均合法；自然观察方向造成的可见范围变化不等于矛盾，也不要求各图具有相同二维耳位或露出面积。

> EAR / HAIR CONSISTENCY — keep the same ear placement relative to the eyes, temples and jaw, and the same three-dimensional hair-over-ear relationship throughout the four views. Ears may remain partly or completely covered by hair; exposed ears are NOT a requirement. Preserve the approved reference's hairstyle and ear coverage. Do not pull hair away, tuck it behind the ears, move ears outward or invent exposed ear contours to make a profile clearer. A profile must not uncover an ear by removing or relocating the hair that covers it in the reference. Allow only visibility changes explained by viewing the same fixed head and hairstyle from another direction; do not force identical screen coordinates or visible ear area across projections. Do not invent measurements of hidden anatomy. Preserve the selected pose mode, including pitch and roll in current mode.

整组使用 `set/ear_hair_consistency` 检查并引用四图证据。自然遮挡可通过，不能仅因耳朵或耳根不可见判失败；确实无法判断整组关系时才记 uncertain。发现矛盾时按基准的遮挡修订问题视图，不拨开头发来“帮助检查”，也不顺带转正 current。完整规则见 [内置评审](image-review.md)。

## 两种四视图与单图操作的 prompt 组合

这里 A/B/C 字母沿用 head-reference 的主体、姿态、外观块命名；下表定义实际请求必须具备的组合。H/E 采用完整语义，字符预算不足时替换为下方紧凑表达。按已确认范围替换 A 的颈部与局部删发句；current 的 B 同时包含其 yaw/pitch/roll 保持补句。D 携带该能力的正向侧面位置说明，输出拼图时追加对应 2×2 布局；不把 B(aligned) 附到侧/背面。头发块 H 在每种组合中均必选：

| 独立分支 | 原图开始的完整组合 | 交接前要求 |
| --- | --- | --- |
| head（独立单图） | `A + H + B(current) + C` | 保持原姿态且头发实体质感通过 |
| front（独立单图） | `A + H + B(aligned) + C` | 头发通过，并分别记录 yaw/pitch/roll 转正检查 |
| four-views / aligned | 用 `A + H + E + B(aligned) + C` 建立正面，再以 `D(aligned) + H + E + 已确认材料保持句` 补视图 | 正面转正、各图头发、耳朵位置/遮挡及整组一致性全通过；不要求露耳 |
| four-views / current | 用 `A + H + E + B(current) + C` 建立当前视角基准，再以 `D(current) + H + E + 已确认材料保持句` 补视图 | 基准 yaw/pitch/roll 保留、固定头部姿态、相对视角、头发及耳朵位置/遮挡一致性全通过；不要求露耳 |

材质选择不覆盖 H；自然色采用 head-reference 的 C，保留原妆容而非要求素颜。彩色树脂采用下一节完整 C。明确生成灰树脂图时读取 [gray-resin](gray-resin.md)：在 A/B/D 已负责主体与姿态的组合中，仅取其 SKIN、MATERIAL AND EYES 及灯光正文作为 C，不再叠加另一套开头和 HAIR；头发及睫毛按本页 H，替换灰配方中冲突的睫毛句，不改该独立能力的默认用途。不把灰配方单图默认转正句套入 head 或 current 四视图。灰模的全灰眼球与彩色分支的自然虹膜颜色不能混用。续做自然色/灰树脂四视图时，以保持已验收基准材料为目标，不重新改变风格。

## 彩色树脂外观增量

将本块作为 head-reference 的外观 C 块，替换“保持原始皮肤细节”块；不要同时发送冲突外观要求。它不是完整 prompt，必须与上面的 H 及所选分支组合。沿用已确认颈部范围，head 和 current 四视图禁止擅自转正。

> Use a high-quality colored opaque matte resin head-sculpture appearance throughout the entire head. Preserve this person's recognizable facial proportions, face shape, age, expression and natural asymmetry, and the existing hairstyle volume and accessories. Use natural colors corresponding to the source, including skin, lips, hair, eyebrows, irises and pupils, as softly colored opaque resin. Retain the source makeup colors and placement, including eyeshadow, eyeliner and lip color; do not strip makeup or force a bare-faced appearance. Keep the natural iris and pupil appearance; remove all eye catchlights, specular dots, reflected windows and glossy corneal reflections. The eyes should read as matte sculpted forms, not glass. Simplify skin into smooth sculptural surfaces: remove pores, photographic microtexture, fine scratch-like wrinkles and noisy bumps, while retaining the main age-defining folds and anatomical contours. Do not beautify, rejuvenate or replace the identity. Retain all mandatory hair-sculpture constraints supplied separately. Clean light gray background, broad soft studio illumination, restrained ambient occlusion, no glossy or metallic surface, no text, no watermark. This is a dimensional sculpture visualization with natural colors, not a desaturated photograph.

金属饰品的颜色与形状按原图保留；树脂化描述不授权删除饰品。本节彩色分支保留自然虹膜/瞳孔颜色；灰图分支另按 gray-resin subskill 的全灰微凸眼球规则处理。无高光是目标，生成模型仍可能留下小亮点，应实际看图；不得声称提示词保证一次成功。

## 彩色树脂基准续做四视图

在 four-views 内部按 pose_mode 选择 head-reference 的 D(aligned) 或 D(current)，携带 H/E 全部适用约束并遵守上述预算，以本模式通过姿态及头发检查的基准图续做；追加以下材料句。不把 B(aligned) 追加到每张视图，更不能用它覆盖 current 的原图抬头/低头和侧倾：

> Preserve the approved colored matte resin material in every view and retain all mandatory hair-sculpture constraints supplied separately. Keep natural iris/pupil colors with no eye reflections. Keep the smooth sculptural skin while preserving the main age-defining folds. Use the same pale-gray background and broad soft lighting as the approved reference.

交接实际四张图与包含 pose_mode/view_frame 的 manifest；拆图、等比 pad、视角和饰品侧别检查按 head-reference。aligned 的画面鼻尖方向命名与 view_convention 沿用该能力，四格 front/right/back/left；按 [服务交接](execution.md#几何生成与服务交接) 转为公共 Hi3D front/back/left/right 上传顺序，不能把相机侧别当标签。current 保留 view_0/90/180/270 相对标签，在服务契约验证前不提交、不冒充标准正面。角度是生成目标而非已测相机。图像中的平滑不代表几何去噪或鼻修复已执行。

H 约束的是几何参考图准备，不授权在已冻结几何的黑白标签图中重塑头发。标签仍须保持对应渲染的几何轮廓，仅改语义材质；最终纹理默认使用前面已生成并验收的 front，来源绑定、缺失 front 与材料冲突按 [纹理输入契约](execution.md#纹理生成) 处理，不自动回退原照片。发现参考图未验收时暂停新的下游提交，历史模型标注来源质量未通过，不篡改旧任务或自动重跑。

## Hi3D H 预算内等义表达

超预算时用这一整段替换上方两个英文 H 段落，A/B/C/D 和适用的 E 仍按分支组合。仅缩短表达，不改变造型或评审门槛；本次参考图有特殊发型、饰品或修订要求时补充后重新计数。

> 每个视图均须满足打印头雕造型：保持人物身份、指定姿态、主要发型轮廓、自然发际线、分缝、发长、发流与体积，不剃头、不抬发际线、不在秃处添发。将照片毛丝转为连续实体雕刻发体，保留主发体、宽扁连贯发束和束内清晰中尺度发流三层结构。刻槽与圆润脊面沿分缝和自然S形流向弯曲，宽度、深浅、间距自然变化，在圆钝发梢前渐隐；呈实体浮雕与柔和槽影，不画线、不留密集毛丝、不磨成光滑花瓣。过细表面槽脊可沿原走向适度加宽、合并邻近微线与细缝，保留曲率、渐细和层次；已有清晰发流不改，不统一加粗或膨胀成绳管。独立悬垂细丝可适度加粗或局部删除；邻近主发体的碎细发必须融合成连续发流，不能只加粗为独立束。保留厚实刘海的位置、弧度和自然方向；过细刘海改为根部厚实连贯、末端渐细圆钝的实体束，已有厚实刘海不改。发梢可离开额头和其他束，不因悬空一律删除、不压贴额头、不用肤色薄膜桥接。禁止漂浮碎片、毛丝状弱细颈、尖针发梢、单丝、平行纤维、飞发、发片、梳齿边缘、细弱悬空卷发；不大面积删刘海或截短主发长。连接遮挡不清须留待评审，不假定通过。头顶、分缝根、鬓角、耳缘、后脑和颈后同样处理；根部、鬓发与发际线在真实边界结束，不跨额头、脸颊、耳部或太阳穴添加薄壳、头皮色膜或围裙。眉毛和原有短胡须保持原形与覆盖，用浅浮雕表达，不变成粗束或独立毛。只减弱浓妆中明显夸张的人工扇状假睫毛；自然上下睫毛可保留，不逐根追查。保留原眼影、眼线、唇色及妆容位置，仅服从所选材料转换，不强制卸妆、素颜或淡妆。保持眼睑、眼形、眉毛、人物辨识度和所选姿态，不把侧面转正。

## Hi3D E 预算内等义表达

四视图的基准、补图和修订超预算时，用这一段替换英文 E；单图分支仍不新增四视图要求。

> 四视图保持同一头部、耳朵相对眼睛/太阳穴/下颌的位置，以及同一三维发耳前后遮挡关系。耳朵可部分或全部被遮盖，不要求露耳；保持已验收基准的发型和遮耳关系。禁止为侧面清楚而拨开发丝、塞到耳后、移走遮耳发块、把耳朵外移或虚构隐藏耳轮廓/解剖测量。只允许固定头部和发型从不同观察方向产生的自然可见变化，不强求相同二维耳位或露耳面积。保持所选姿态模式，current 尤其保留原俯仰与侧倾。
