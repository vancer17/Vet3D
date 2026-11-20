# 资产与页面契约

## 输入清单

```json
{"title":"作品","revision":"r1","assets":[
 {"file":"hero.png","role":"image","label":"外观"},
 {"file":"assembly.glb","role":"model","label":"装配模型"},
 {"file":"parts.zip","role":"download","label":"制作文件"}]}
```

每项可加 sha256；角色限定 image/model/video/download。image 支持 PNG/JPEG/WebP，video 仅 MP4，model 为自包含 GLB（有 mesh，无外部 buffer/image URI），download 接受其他明确文件。声明后缀不代替图像/视频解码验收；大资产 base64 内嵌会增大页面和内存，超大文件应由专用发布适配提供外链。

## 唯一公共实现

[page_assets.py](../scripts/page_assets.py)：`read_asset(root,relative,expected_sha256=None)` 拒绝绝对路径、父级穿越、越界 symlink、空文件及哈希不符，返回实际 bytes 与 file/bytes/sha256；不联网。`encode_asset` 生成 base64。`render_template(template,replacements,syntax)` 对显式已按上下文转义的片段作纯替换：tokens 要求所有键出现并一次匹配，避免用户文本再次被当 token；dollar 保留 string.Template 语义。模板必须来自可信包，不是代码执行器。`image_figure` 对标签 HTML 转义并内嵌真实图片。

[asset_page.py](../scripts/asset_page.py)：`load_assets(spec,root)` 校验清单、角色和可选期望哈希，GLB 容器检查复用 glb-clips.read_glb；返回记录/原始载荷。`render_page(title,revision,records,payloads,template)` 生成图片/模型/视频/下载卡片，标签和文件名按 HTML 上下文转义；视频不自动播放。`build_page(spec,root,output)` 先完成所有读取与页面构造，再创建新目录写 HTML/manifest。`main` 仅解析/呈现。没有模型时完全离线；有模型时仅模型组件依赖固定 CDN，加载失败仍保留文件下载。文件写入不是跨文件事务，失败时保留不完整新目录。

manifest 包含 title/revision、每个实际资产的 file/role/label/mime/bytes/sha256/revision、viewer_requires_network 和 browser_interaction_tested=false。revision 为调用方声明；不证明拍摄视角/GLB/制造件语义同版，必须由 delivery-review 和业务工作流核对。

## 专用适配保留

print-kit 保留无 CDN 的 three.js/STL 装配/拆解/摆盘、制造 ZIP 与三项输出；仅共用资产哈希/路径、图片卡和 dollar 模板替换。phone-case-relief 保留中英模板、必填内外相机、GLB 自包含检查、独占 HTML 输出与 ViewerError；仅共用读取/base64/token替换。lamp-design 保留 loopback chooser、选型/提交/恢复和各自 revision，read_catalog 核验清单中真实 media 文件，默认推荐仍是样机参考，不改为新产品交付。

验收覆盖不存在/空/越界/改动资产、错角色、恶意标签和模板标记、独占输出、嵌入字节与原件一致、专用适配的既有输出及真实浏览器。入口不负责重新建模、编码、切片、发布或完整交付认证。
