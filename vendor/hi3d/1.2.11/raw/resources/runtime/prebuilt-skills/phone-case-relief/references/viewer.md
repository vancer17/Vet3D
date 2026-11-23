# HTML 查看页

`scripts/build_viewer.py` 使用 Python 标准库，把最终 GLB 二进制嵌入一份中文或英文 HTML。页面支持旋转、缩放、外侧/内侧视角、自动旋转、全屏、本地打开另一 GLB 和下载嵌入模型。

```bash
python scripts/build_viewer.py \
  --model "$RUN_DIR/exports/case.glb" \
  --output "$RUN_DIR/exports/case_viewer.html" \
  --lang zh \
  --exterior-orbit "<按当前模型确认的三个值>" \
  --interior-orbit "<按当前模型确认的三个值>"
```

两个 orbit 必填，均为 model-viewer 的三个安全 angle/distance 值。先按实际 GLB 朝向确定并目视确认，不能沿用别的手机、姿态或坐标系；默认视图不得只显示空白内侧或薄侧面。需要偏离模型包围盒中心时，在任务产物中基于模板进一步设置 `camera-target` 并重新测试。

输入必须是内含至少一个 mesh 的 GLB 2.0，且 buffer/图片资源已打包为 GLB 内部数据或 data URI。输出必须是新的 `.html` 路径；脚本拒绝覆盖。模板固定从本工作流的 `assets/` 读取，因此整包复制后仍可运行，输入输出则位于业务任务目录。

GLB 会嵌入 HTML，但 model-viewer JavaScript 由固定版本 CDN 加载，故页面不是断网可用的完整离线包。用户要求离线时，另行打包可合法分发的运行时并实际断网测试。在 Hi3D 中交付工作区相对路径的 HTML 链接，由客户端“浏览器预览”通过本地 HTTP 打开；不要直接用系统命令或 `file://` 打开 HTML，也不要引导用户下载后双击文件。其他宿主使用其支持的 HTTP 预览入口；不伪造 Studio URL 或为 UI 卡片重复登记模型。

脚本只验证 GLB 容器、首个 JSON chunk、mesh 存在和无外部资源，再进行静态封装；它不检查闭合、尺寸、颜色或手机适配。能使用浏览器时验证加载事件、初始视角、颜色、按钮与下载；未执行浏览器测试时明确记为 `not_tested`，不能把 CLI 成功当成交互通过。

页面资产与模板公共实现见 [asset-page 契约](../../.dependency-asset-page/references/contract.md)，按 package.json 物化。中英查看器、内外相机、GLB 验证与输出保护保持本工作流实现；生成网页后仍需实际打开并检查下载。
