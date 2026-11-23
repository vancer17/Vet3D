# 专业依据与来源边界

以下为一手资料；数值必须按工艺与应用理解。设计表中的间隙范围属于本工作流的保守试配起点，不能说是资料给出的统一标准。

1. [Prusa：面向 3D 打印的建模](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135)。支持把朝向、支撑、薄壁与配合共同考虑；没有适用于所有设备的公差，需试打印与参数迭代。其活动件起始间隙表述不应被擅自改写为明确径向值。
2. [Prusa：切割工具与连接件](https://help.prusa3d.com/article/cut-tool_1779)。说明插接、独立销、卡扣和燕尾的分割方式。工具能创建连接几何，不能证明完整装配路径与强度。
3. [Prusa：象脚补偿](https://help.prusa3d.com/article/elephant-foot-compensation_114487)。说明首层扩张的补偿机制，其 0.4 mm 喷嘴约 0.2 mm 补偿是切片起点，不应再不加分析地叠加设计缩小量。
4. [Formlabs：卡扣接头与壳体设计](https://formlabs.com/blog/designing-3d-printed-snap-fit-enclosures/)。材料允许应变、根部几何、层向和装配功能决定卡扣设计；不能把 SLA/SLS 实例的尺寸直接当 FDM 标准。网页中 PCB 与外壳的空间余量不是榫槽配合间隙。
5. [Stratasys：FDM 工装设计指南](https://www.stratasys.com/contentassets/1a0cc7a8e7d14f29ac972189bfeade4c/dg_fdm_designconsiderationsfdmtooling_0718a.pdf)。第 11–13 页讨论分体装配与嵌件：定位和固定可由不同结构负责，嵌件预孔应依供应商结构建议与实装结果调整。工业设备参数不能直接移植到桌面 PLA。

## 免胶连接的补充依据

以下资料核读于 2026-09-13；新材料/工艺或页面变化时重核相关项，不必为每个模型重复整份调研。原作者资料说明结构原理，具体产品的尺寸、强度和装配成功仍须本任务验证。

6. [BOSL2：joiners.scad 原作者文档](https://github.com/BelfrySCAD/BOSL2/wiki/joiners.scad)。`dovetail`、`snap_pin`、`snap_pin_socket` 和 `rabbit_clip` 提供成对接口与参数定义；socket 的固定/可转动分支不同。库预设间隙与预紧不是用户机器的实测。引用原理不引入代码依赖；直接采用源码时核对对应作者与许可并保留要求。
7. [Protolabs Network：3D 打印卡扣设计](https://www.hubs.com/knowledge-base/how-design-snap-fit-joints-3d-printing/)。支持圆根、渐变臂、定位结构分担载荷和到位后卸载；FDM 层向与循环疲劳需考虑。根部圆角起点 `r≥0.5t` 仍需按局部结构验证；文中 nominal clearance 没有统一定义为径向/单边，不把 0.5 mm 直接套入所有孔槽。
8. [Klahn、Singer、Meboldt：Design Guidelines for Additive Manufactured Snap-Fit Joints（2016）](https://publikationen.bibliothek.kit.edu/1000142464/142615492)。第 4–5 页讨论 FDM 的受力层向、相对运动表面和可去除支撑；最终示例改用 SLS，不能称它证明了 PLA 卡扣性能。直梁公式是限定假设下的力学筛查，不是材料许用值。
9. [OpenAT：Twist Lock](https://makersmakingchange.github.io/OpenAT_Design_Guide/Design_Elements_For_3D_Printed_Parts/Twist-Lock.html)。实际开源辅助器具以插舌/槽搭接，再用凸点/凹窝保持转角，支持把抗拔与防反转分开设计；到位前碰到阻力不等于锁好。尺寸建议只覆盖作者的应用经验。
10. [OpenAT：Cotter Pins](https://makersmakingchange.github.io/OpenAT_Design_Guide/Design_Elements_For_3D_Printed_Parts/Cotter-Pins.html)。提供滑入后锁定的可打印销案例，并让到位后的弯曲段恢复；不是任意形状横销都有保持力的证据。
11. [OpenAT：Threads](https://makersmakingchange.github.io/OpenAT_Design_Guide/Design_Elements_For_3D_Printed_Parts/Threads.html)。说明打印螺纹的层向、落台与配对余量；其小牙尺寸与偏置经验不能直接移植，偏置方向须检查是否真实扩大母牙空间。
12. [Stratasys Direct：FDM Design Guide](https://www.stratasys.com/siteassets/sdm/content---website-storage/design-guides/dg_sdm_fdm_0725a.pdf?v=490918)。PDF 第 6 页推荐圆根/圆牙顶的 ACME 类螺纹，提示 FDM 活铰链循环限制和多件铰链路线；工业设备及支撑条件不能当成单喷嘴桌面默认。
13. [SPIROL：How to Select a Threaded Insert for Your 3D Printed Assembly](https://www.spirol.com/resources/white-papers/how-to-select-a-threaded-insert-for-your-3d-printed-assembly/)。以指定嵌件/试样讨论孔径、实体螺柱、周边路径、填充与安装工艺对性能的作用。采用其选型变量，不能把 M6 试样载荷与比例当所有打印嵌件的保证；普通热固性树脂不能按 FDM 热熔嵌件方式处理。
14. Prusa 材料说明：[PLA](https://help.prusa3d.com/article/pla_2062)、[PETG](https://help.prusa3d.com/article/petg_2059)。用于区分材料韧性、热条件与打印行为，不给出通用卡扣许用应变，也不授权自行替换用户指定材料。

本文吸收了高模拆件的“真实嵌入榫根、盲孔余肉、独立毫米公差、最终 STL 回读”和运动底座的“肩段承载、双向止退、所有松件窜动、释放工具与局部试片”方法。必要知识已自包含在 [免胶连接](glue-free-joints.md)，不依赖这些技能的安装或固定案例坐标。楔键/横销组合、产品选型优先级和数值算例是基于上述原则的工程推导，未被包装为来源已认证的产品。
