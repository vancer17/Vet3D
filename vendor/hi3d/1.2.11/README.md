# Hi3D Agent 1.2.11 实现参考与发行证据

本目录固定 Windows x64 Hi3D Agent 1.2.11 的客户端、Runtime、Skill 与本地脚本实现，供 Vet3D 开发参照。归档工具只读取和核验原件，不启动 Hi3D、随包程序或上游脚本。云端模型实现不在客户端快照中。

[发行与文件锁](reference.lock.json) · [便携证据映射](evidence-map.json) · [缓存审计](cache-audit.json) · [Debian 交接](../../../docs/vet3d/reference-portability.md) · [Hi3D 解析导航](../../../docs/hi3d/README.md)

## 内容与身份

| 路径 | 内容与边界 |
| --- | --- |
| `packages/Hi3D-1.2.11-win-x64.exe` | 捕获的原始安装器，681,253,896 字节，Git LFS 保存。摘要只确认捕获文件，不按文件名推断它与已安装快照完全等价。 |
| `packages/resources-win-x64.zip` | 按既有发行盘点白名单构建的完整干净 `resources/` 快照，689,343,570 字节，Git LFS 保存。 |
| `raw/resources/` | 3,131 个可阅读原件及 ASAR 容器，沿用安装相对路径；包含 Runtime、模板、support、预置代码与文档。它是阅读子集，完整依赖通过资源包取得。 |
| `raw/app-members/` | 固定 ASAR 的 1,043 个原始成员，保留成员字节。主进程、renderer、preload 及其依赖可以直接阅读。 |
| `raw/metadata/` | 既有发行盘点与锁的原字节副本，关联发行身份及完整文件集合。 |
| `raw/cache-delta/`、`cache-audit.json` | 经白名单比较的缓存实现增量及审计；没有增量时以审计结论表达，不复制重复部署件。 |
| `fixtures/`、`evidence-map.json` | 已固定的探针、必要合成资产、外部依赖原文及映射；原件、清洗派生和未归档出处分别标记。 |

完整快照包含 **6,697 个文件，共 1,444,854,396 字节**，对应原盘点中的磁盘文件；ASAR 成员另有 1,043 个记录。参考锁记录 4,178 个包及原件文件的摘要。缓存与探针由独立审计及证据映射维护，不冒充发行原件。

导出时源目录中有 1,530 个发行清单之外的 `.pyc`，均列入排除清单。其中 62 个位于预置 Skill 树，其余属于本机运行产生的其他缓存。没有删除或改写源目录；只有白名单内且大小、SHA-256 均匹配的文件进入完整快照。

| 固定对象 | SHA-256 |
| --- | --- |
| 原始安装器 | `69cc79e21976a819f96e0f0f4d88276a08cc946d052a1fd689c75a4a34ab949a` |
| 干净资源 ZIP | `c22f77fbf0d5ca1170bad498d9e030d8f7c1f81599308285c4ef96a655141e1f` |
| `app.asar` | `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a` |
| `runtime/dist/runtime.mjs` | `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47` |

原始来源为 `D:/download/Hi3D-1.2.11-win-x64.exe` 和 `D:/install/Hi3DAgent.__hi3d-transaction/resources`。这些地址只作来源元数据；获取与验证使用本目录相对路径。现有[发行锁](../../../docs/hi3d/upstream/1.2.11/inventory/inventory.lock.json)保持不变。

## 获取与验证

先安装 Git LFS 并取得实际对象，避免把指针当作安装器、ASAR 或资源包。Python 工具要求 3.11+，不需要安装 Hi3D 或 Blender。

**实际 CLI 示例。** 从仓库根目录执行，解包输出位于忽略的本地缓存中。

```bash
git lfs install --local
git lfs pull
git lfs fsck
python3 -B scripts/hi3d/verify-reference.py \
  --reference-dir vendor/hi3d/1.2.11
python3 -B scripts/hi3d/materialize-reference.py \
  --reference-dir vendor/hi3d/1.2.11 \
  --output-dir .cache/hi3d/1.2.11
python3 -B scripts/hi3d/verify-reference.py \
  --reference-dir vendor/hi3d/1.2.11 \
  --resources-root .cache/hi3d/1.2.11/resources
```

`verify-reference.py` 核验参考锁的文件、安装器、资源 ZIP、原始盘点及完整文件白名单。它不执行质量验收，也不把本次新清单当成独立签名信任根；发行身份由版本化盘点与 Git 提交关联。

`materialize-reference.py` 先验证包，再拒绝越界、重复、链接、文件集合或大小不符的 ZIP 成员，逐项核摘要，验证暂存目录后发布。已有目录只有完整一致时才复用；冲突不会被悄悄覆盖。原始 Windows 程序保留为证据，不能在 Debian 原生执行。

需要重建原有盘点和 P0／P1 时，使用解包后的完整 `resources` 根及[迁移核验命令](../../../docs/vet3d/reference-portability.md#debian-获取与核验)。历史 `docs/hi3d/upstream` 是部分原件快照；其内部未收录依赖应在完整同布局资源树查阅，原文不作路径重写。

## 重新导出

**实际 Windows CLI 示例。** 对应来源必须仍存在且匹配既有发行锁，目标须为新目录。不能用此命令覆盖已发布证据或自动升级到另一发行。

```powershell
python -B scripts/hi3d/export-reference.py --release-dir docs/hi3d/upstream/1.2.11 --resources-root 'D:/install/Hi3DAgent.__hi3d-transaction/resources' --installer 'D:/download/Hi3D-1.2.11-win-x64.exe' --output-dir '.cache/hi3d-reference-reexport'
```

导出器核对源文件白名单与摘要，按固定路径创建 ZIP，抽取固定 ASAR 成员，复制安装器并生成新收据。新的 ZIP 容器身份与内部原件身份分别核验；跨 Python／zlib 版本重建时不承诺压缩包字节相同。

## 缓存、探针与适用范围

缓存审计只比较公开的实现文件与必要元数据。登录凭据、Cookie、原始会话、原始日志、用户状态数据库及无关素材不进入本目录。部署重复件不因处在缓存中就再次归档；清洗或合成内容在映射中保留来源及派生身份。

临时探针和合成 GLB／BLEND／NPZ 仅证明其实际覆盖的分支；既有三个工作区 GLB 和留存会话不代表全部工具或业务路径。本次不因固定旧探针而宣称已复跑 Blender、云端任务或真实四足质量验收。具体归档与未归档项见证据映射。

当前核验层次、Windows 与 Debian 测试结果、真实 VMware 待验范围见[发布交接](../../../docs/vet3d/reference-portability.md)。第三方原件及其附带许可保留原身份，根 MIT 许可证不重新许可这些内容。 [第三方说明](../../../THIRD_PARTY_NOTICES.md)
