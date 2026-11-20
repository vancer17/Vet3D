# 同型号设备资料与设计输入

选设备与开接口前读取。官方营销尺寸用于名义三围，开发者尺寸图用于可用的接口/避让/操作区；二者精度和定义不同，按明确型号/代数/充电版本保存本任务来源，不用网页图片比例推断未标尺寸。

- [Apple AirPods 4 技术规格](https://www.apple.com/airpods-4/specs/)：识别具体充电盒版本、公开三围和功能；新任务重新核对，不把示例值当通用常量。
- [Apple 配件尺寸图索引](https://developer.apple.com/accessories/dimensional-drawings/)：查匹配版本的完整图页。
- [AirPods 4 USB-C 无线充电盒尺寸图](https://developer.apple.com/download/files/accessories/dimensional-drawings/wireless-charging-case-usb-c-for-airpods-4.pdf)：用于图中明确标注的尺寸与避让；标题为无线充电盒，不能只因同为AirPods 4就推断非ANC标准盒的所有功能窗一致。
- [Apple 重置操作](https://support.apple.com/en-gb/118531)：核对正面轻点/后部按钮与开盖要求。LED观察孔不等于配对、触控或复位操作窗。

读图时分别记录原盒三围、盖线/转轴、开盖角与扫掠、插头金属头和外壳keepout、LED、扬声器/挂绳/按钮/触控范围。盖后缘的lid clearance scoop尺寸不能误当盖缝高度；若图没有圆角、转轴或完整OEM曲面，就保持名义状态，向用户说明卡尺/扫描要补哪些量。

脚本中的底部通道与插头是一个数字接口示例（见runtime），不是USB-C标准外壳尺寸。以当前实际线缆和设备数据替换并验证全部插入路径；官方建议keepout只能作为起点。无线充电、触控、保持力、磨损和设备保护均不能从无交叉网格得出。

艺术研究可看真实厂商/原创作者的保护套正背面、材质、分盖线和功能窗口，比较紧凑轮廓与携带时突出物；提取一般设计元素，不复刻商业角色，也不以商品“兼容”文案代替本套几何和试装证据。
