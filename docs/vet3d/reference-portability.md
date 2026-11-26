<!-- 文件信息：Hi3D 参考资料的发布、获取与验证说明。
作用：保留归档操作和当次验证证据，提供当前可用的参考入口。
边界：历史验证不代表新产品已实现，不依赖已撤销的分层实施规划。 -->
# Hi3D 参考资料的发布与 Debian 交接

本页说明 Vet3D 工程成果和 Hi3D Agent 1.2.11 参考实现的归档、获取、编码及验证。参考内容供实现追溯；Windows 宿主、随包解释器和原生程序不因此具备 Debian 原生运行能力。云端模型实现不属于客户端快照。

[项目入口](../../README.md) · [Hi3D 解析导航](../hi3d/README.md) · [固定版本索引](../hi3d/upstream/1.2.11/README.md) · [参考包](../../vendor/hi3d/1.2.11/README.md)

下文发布过程与已执行检查保留归档交接时的事实和环境范围。旧产品实施规划已撤销，不据此重新解释历史验证，也不将其作为新产品能力证明。

## 发布工作区与归档范围

本次发布在独立 `publish/hi3d-reference` 分支和发布工作树中进行。主项目工作目录的原始文件、暂存区、未暂存及未跟踪成果另存基线；复制确认的最终文件到发布工作树后整理提交，不通过重置主目录取得干净状态。发布后迁移环境应从远程提交重新克隆，避免将 Windows `.git` 配置直接复制到 Linux。

| 内容 | 归档方式与证据含义 |
| --- | --- |
| Vet3D 文档、源码和测试 | 普通 Git；包括盘点、抽离、归档与本次参考包工具。 |
| 可阅读原件 | `vendor/hi3d/1.2.11/raw/`，保留所选原文件与 ASAR 成员字节，覆盖范围由参考锁说明。 |
| 原始安装器与完整资源包 | `vendor/hi3d/1.2.11/packages/`，Git LFS 保存真实内容，Git 提交保存指针。 |
| 缓存增量 | 仅纳入白名单比较后确认的实现，重复部署件、未覆盖范围及排除项分别记录。 |
| 探针与会话样例 | 原件、脱敏派生、合成夹具和未归档出处分别标记；派生结果不能替代原件摘要。 |

完整资源包按锁定发行文件构建，当前源目录的额外运行缓存不自动成为发行原件。原始安装器和已安装资源各自记录身份，不能仅凭版本文件名宣称安装器已经复现相同文件树。

普通 Git 不存放完整 Windows 程序和大型压缩快照。LFS 使用方式及当前大小限制见 [GitHub LFS 说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)。第三方原件保留自身来源与许可，不能因收录在 Vet3D 仓库而改变其身份。

## 编码、换行与路径

| 文件类别 | 规则 |
| --- | --- |
| Vet3D 自研文本、脚本、新清单与交接文档 | UTF-8、无 BOM、LF；Python 文本读写显式指定编码。 |
| 固定 Hi3D 原件和已有摘要锁定清单 | 原始字节保持不变，包括已有 CRLF；原件路径使用 `-text`。 |
| 安装器、ASAR、模型与压缩包 | 二进制或 LFS，不执行转码和换行转换。 |
| 脱敏／转换夹具 | 新文件按 UTF-8、无 BOM、LF 保存，记录源身份、转换方式及派生摘要。 |

`.gitattributes` 控制 Git 换行处理，不替代 UTF-8 编码检查。已有版本目录的原件保护规则继续有效。不要对整个仓库执行换行重规范化后再把结果称为同一原件；编辑器也应跳过原件目录的自动格式化。 [Git 属性说明](https://git-scm.com/docs/gitattributes)

Windows PowerShell 5.1 的默认文本输出不适合作为新锁定清单的写入方式。使用 Python 显式 UTF-8 写入或 PowerShell 7 的明确编码参数；二进制备份和补丁直接按字节保存。当前 Python 工具依赖 `hashlib.file_digest`，要求 Python 3.11 或更高版本。

便携清单使用仓库相对路径及 `/` 分隔符；Windows 本机路径只作为原始出处元数据。实际克隆后检查大小写、文件身份和符号链接，不复制 Windows 的 `core.ignorecase` 或 `core.filemode` 配置。已有脚本可以通过 `python3 script.py` 启动，不以复制的执行位作为运行前提。

## 证据引用的可用范围

分析文档保留原始出处，以 `evidence-map.json` 将固定安装路径、部署目录和临时探针关联到仓库文件或归档成员。没有归档的凭据、原始会话和宿主状态应保持未归档状态，不用合成夹具冒充原始记录。

历史 `docs/hi3d/upstream/1.2.11/prebuilt-skills/` 是部分原件快照，其内部存在未随该子集归档的同目录或跨目录链接。本次发布前扫描发现178处缺失文件链接，均位于这些上游原件内部；自研分析文档未发现缺失的仓库相对文件链接。该数量是当次范围扫描结果，不是永久阈值。

保留原件链接与摘要，不在原件中改写路径。需要跟随完整 Skill 依赖时，进入 `vendor` 中按原布局保存的实现，或解包完整 `resources/runtime/prebuilt-skills/`。若原包本身已有链接错误或目标仍不可用，按映射中的具体缺口记录，不能宣称所有原文链接都已修复。

## Debian 获取与核验

建议将仓库克隆到虚拟机自身磁盘，例如 `~/src/Vet3D`；VMware 共享目录可用于搬运归档。发布代码用到链接、文件身份和持久化语义，测试应在实际开发文件系统重跑，不能用共享目录上的一次通过替代原生文件系统验证。

安装 Git、Git LFS 和 Python 3.11+，配置私有仓库访问后执行。下面示例分支用于本次发布；合并后可改为 `main`。使用跳过自动下载的克隆，随后显式取得 LFS 对象。

**实际命令示例。** 使用项目内工具核验；不会启动随包 Windows 程序或执行上游脚本。

```bash
export LC_ALL=C.UTF-8
export PYTHONUTF8=1
GIT_LFS_SKIP_SMUDGE=1 git -c core.autocrlf=false clone \
  --branch publish/hi3d-reference \
  https://github.com/vancer17/Vet3D.git ~/src/Vet3D
cd ~/src/Vet3D
git config core.autocrlf false
git lfs install --local
git lfs pull
git lfs fsck
python3 --version
python3 -B -m unittest discover -s tests/hi3d -v
python3 -B scripts/hi3d/verify-reference.py \
  --reference-dir vendor/hi3d/1.2.11
python3 -B scripts/hi3d/export-evidence.py \
  --reference-dir vendor/hi3d/1.2.11 --verify
python3 -B scripts/hi3d/materialize-reference.py \
  --reference-dir vendor/hi3d/1.2.11 \
  --output-dir .cache/hi3d/1.2.11
```

克隆只取得 LFS 指针时，指针存在不代表原始安装器或快照已取得。`git lfs pull` 或摘要核验失败时停止，保留错误并检查对象可用性，不继续把缺件状态称为验证通过。

对解包后的完整资源再运行现有盘点工具。输出使用新的临时目录，发行锁不改写。

```bash
check_dir="$(mktemp -d)"
python3 -B scripts/hi3d/inventory.py \
  --resources-root .cache/hi3d/1.2.11/resources \
  --output-dir "$check_dir/inventory"
cmp docs/hi3d/upstream/1.2.11/inventory/inventory.jsonl \
  "$check_dir/inventory/inventory.jsonl"
cmp docs/hi3d/upstream/1.2.11/inventory/inventory.lock.json \
  "$check_dir/inventory/inventory.lock.json"
```

需要重新复核 P0／P1 时，在仓库外生成新归档；参数使用既有发行目录与刚解包的完整资源根。

```bash
python3 -B scripts/hi3d/archive-p0.py \
  --release-dir docs/hi3d/upstream/1.2.11 \
  --resources-root .cache/hi3d/1.2.11/resources \
  --output-dir "$check_dir/archived-p0"
python3 -B scripts/hi3d/archive-p1.py \
  --release-dir docs/hi3d/upstream/1.2.11 \
  --resources-root .cache/hi3d/1.2.11/resources \
  --output-dir "$check_dir/archived-p1"
```

只有完整资源目录可用于全量盘点；可阅读原件子集不应被用来运行这项全量核验。

## 自动检查与实际验证边界

[Reference portability 工作流](../../.github/workflows/reference-check.yml) 对 push／PR 运行 Windows、Linux 的 Python 3.11／3.13 标准库测试，跳过大型 LFS 自动下载。手动触发并启用 `full_reference` 时，才下载和校验完整 LFS 参考包、解包并重算盘点。普通单元测试通过不证明远程 LFS 对象齐全。

工作流通过固定 SHA 引用官方 [checkout](https://github.com/actions/checkout) 和 [setup-python](https://github.com/actions/setup-python) 实现。CI runner 不等同于目标 Debian 虚拟机；实际执行结果以对应提交和工作流记录为准。

| 已执行检查 | 结果与限制 |
| --- | --- |
| 既有 P0／P1 29份归档原件 | 本次发布工作树内逐件 SHA-256 匹配收据。 |
| 既有 Python 凭据模式扫描 | 自研 `src/scripts/tests` 中未命中所检查的私钥、GitHub Token及 OpenAI 项目密钥模式；不是全内容无秘密的证明。缓存正文未据此获准全量上传。 |
| Windows 文本检查 | 自研文本可用 UTF-8 解码、无 BOM；发布属性使自研文本统一 LF，原件规则另行生效。 |
| Debian 13／WSL2 基础测试 | Python 3.13.5、Git 2.47.3、Git LFS 3.6.1；在 Linux 原生 `/tmp` 副本运行既有22项测试，全部通过，包括符号链接用例。 |
| Debian 13／WSL2 新工具测试 | 在用户 home 的原生 ext4 新副本运行含参考包与证据工具的47项测试，全部通过、无跳过；该轮是复制后的独立副本，不能冒充远程新克隆验收。 |
| Debian 完整本地恢复 | 将4178项参考原件和包复制到原生 ext4 后，原 CLI 解包6697项资源，`verify-reference --resources-root` 返回完整资源已验证。重算盘点的7740条记录、JSONL及发行锁与仓库逐字节一致，排除的额外本地缓存为0。 |
| Debian P0／P1 重建 | 从该完整解包资源重新生成 P0 的14份原件／16项证据和 P1 的15份原件／43项证据，两个收据与仓库逐字节一致。 |
| Debian 证据映射 | `export-evidence --verify` 验证274项源映射、82份夹具和4个缓存根审计，完成；未归档来源仍按原有状态保留。 |
| VMware Debian | 尚未实测。WSL2 的通过不能等同于 VMware、共享文件夹或目标开发配置通过。 |
| 完整新克隆、LFS 与参考包恢复 | 需用本次实际发布提交执行并记录；不得仅依据本页命令示例宣称完成。 |
| Windows 应用与云端模型 | 本次归档不验证 Debian 原生运行 Windows 应用，不验证云端建模画质、骨架或动物动作。 |

新克隆验收后应记录实际提交、LFS 下载与核验结果、解包清单及盘点比较。后续使用新的宿主、Blender、模型或资源版本时，按实际消费者和变化范围验证所需能力，不从归档工具通过推断产品链路通过。
