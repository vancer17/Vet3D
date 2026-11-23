# 本地几何输入契约

## geometry_inputs 原子契约

| 入口 | 输入 → 输出 | 副作用与失败 |
| --- | --- | --- |
| `prepare_image(image, *, size=1536, padding=1.15)` | 带真实 alpha 的 PIL 图像 → 同尺寸白底 RGB、RGBA | 不修改输入；Pillow；拒绝无 alpha、空/全不透明 mask、非法尺寸/边距。保留软 alpha，避免带 mask paste 将 alpha 二次相乘 |
| `read_bridge(content, *, count=4)` | rendered_views.zip bytes → normal/ccm_png/ccm_exr/mask 有序字节列表及 camera_info | 标准库内存读取，不解压到路径；要求完整唯一 0..count-1 的 normal/CCM；拒绝重复、空或缺失必需视图；mask/camera 可选 |
| `build_prep_zip(gray_images, bridge)` | 有序真实 PNG bytes + 同阶段 bridge → ZIP bytes | 要求标准四视图，检查数量与 PNG 解码、EXR magic，原样保留浮点 CCM 字节，不嵌入 mesh；EXR magic 检查不替代完整解码/数值验证 |
| `main(argv=None)` | prepare 或 bridge 参数 → 退出码 | prepare 创建新目录并保存两个 PNG；bridge 以 xb 写新 ZIP。拒绝覆盖；I/O/格式错误传播，失败时可能保留部分输出供检查，不自动重试 |

图像准备依据 Geo 提交 63dbc6cb 中的 bbox→裁方→边距→resize/白底合成；本工具保持软 alpha，不复制源中控的空前景回退或其顶层配置。bridge 依据同提交 parse_rendered_views_zip/build_prep_zip 的文件交接，额外拒绝歧义 view 和错误文件格式；不包含生成、控制图坐标变换或 full 的额外人脸视图。


验证使用随包 tests/test_geometry_inputs.py；仅测试本地文件和模拟输入，不提交服务。
