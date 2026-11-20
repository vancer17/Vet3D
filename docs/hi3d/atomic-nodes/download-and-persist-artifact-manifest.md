# 逐项下载与产物清单落盘

以 Hi3D Agent 1.2.11（Windows x64）事务备份为核查基线。来源节点确定原作业、输出根及本次可用的下载来源。本节点执行逐条传输、发布和清单落盘。 [来源确认与恢复](confirm-download-source-and-recovery.md) · [随包下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)

## 业务定义

| 项目 | 约定 |
| --- | --- |
| 触发 | 已受理的 3D 作业进入下载分支。组合调用在观察到原任务成功后内部进入，也可用独立动作恢复原作业的下载。 |
| 输入 | 原作业账本、原任务 ID、匹配的账号与环境、工作区输出根。已聚合时读取原 `artifact`，否则消费本次成功查询的有序 URL。完整签名地址留在当前调用的内存中。 |
| 图片角色 | 结果查询使用原作业的任务 ID，文件传输使用该结果中的下载地址。原生成计划继续记录主图、补充参考、目标方向和必保项，下游按该计划比对实际候选。 |
| 输出 | 与原作业绑定的实际文件清单。每个文件有路径、字节数、SHA-256。新下载还产生每项的 `.download.json` 检查点和作业级 `artifact`。 |
| 完成条件 | 现有 `artifact` 中的记录全部通过本地复验，或本次有序候选的全部文件已逐项发布并保存 `artifact`。 |
| 下游 | 把原作业引用和实际文件清单交给候选适用性检查。组合动作也可能在返回前自动登记唯一符合条件的 GLB。对已登记版按实物确认，未登记件按用途验收后选定。 [候选适用性](check-model-candidate-suitability.md) · [主模型交接](select-primary-model-and-confirm-handoff.md) |

## Skill 绑定

通用 Hi3D Skill 指导普通 3D 生成使用桌面 Runtime 的组合调用，等待和下载由同一命令执行。查询出错按该 Skill 报告原因并结束本轮。用户明确要求恢复后沿原作业继续。免费重试的下载使用已受理的子作业及其任务 ID。领域 Skill 的质量与交付条件在下游按需执行。 [通用入口](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) · [独立动作与查询错误](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) · [免费重试参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md)

## LLM Tools

| 工具 | 在此阶段的作用 | 调用时机 |
| --- | --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md#已下载-3d-产物与登记) | `generate_3d` 与 `retry` 在观察成功后内部下载。独立 `download` 返回 `cached` 与 `artifact`。组合成功回包提供 `files` 路径列表，并按条件继续登记。 | 正常组合调用内部下载。需要补取已经成功的任务时，沿原 `jobPath` 和原绑定 `outputDir` 调用 `download`。 |
| [`exec`](../tools/exec.md) · [`wait`](../tools/wait.md) | 运行或续读承载上述 Tool 的 Code Mode 单元。 | 已由 `exec` 发起且单元仍在运行时，沿原 `cell_id` 取回结果。 |

`download_job`、`fetch` 与 `unpack` 是随包 Python 函数。生产样例使用组合 `generate_3d` 及 Code Mode 续读。独立 `download` 的请求结构来自已核实的工具契约。 [Tool 注册](../tools/hi3d-api.md#工具名称与注册来源) · [组合调用实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:34>)

## Hi3D 实现

### 决策

- **已有聚合清单。** `download_job` 校验原作业的账号与环境，再检查顶层记录、`files` 和可选 `cover`。要求各路径解析后位于本次输出根，且是普通文件，字节数和 SHA-256 一致。校验成功返回 `cached: true`，该下载分支直接使用本地清单。 [缓存验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:120>)
- **需要处理新鲜候选。** 无聚合清单时使用本次成功刷新取得的有序 URL，沿用首次保存的 `download_output`。`hi3d-result-<index>` 由当前候选序号决定。检查点身份是原始候选 URL 的 `SHA-256(scheme://netloc/path)`，省略查询和片段。有效签名刷新可在同序号、同身份的条件下复用已完成项。序号位置的身份冲突会停止。 [目录绑定与逐项身份](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:182>)

### 执行

**根据实际接口重建的请求示例。** 原作业已受理并到达成功状态。使用原工作区的相对路径。

```json
{
  "action": "download",
  "jobPath": "hi3d/model.json",
  "outputDir": "exports/hi3d-model"
}
```

1. **取回原文件。** `fetch` 校验绝对 HTTPS、主机部分和内嵌凭据，重定向时逐跳复验。下载请求显式写入 User-Agent，禁用环境代理，API Authorization 留在结果查询通道。`opener.open(timeout=180)` 是传输请求的超时参数。声明大小或流式累计超过 1 GiB，以及空响应，均导致中止。数据先写同目录临时文件，再用 `os.link` 排他创建暂存目标。 [HTTPS 与传输校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:20>) · [URL 约束](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:54>)
2. **确定格式与展开范围。** 按候选 URL 路径的允许后缀命名，其他后缀暂用 `.bin`，通过前 16 字节识别 PNG、JPEG、WebP 或 GLB。识别为 GLB、以 `.glb` 取得的非 ZIP，或解包所得 `.glb`，均检查 magic `glTF`、版本 2、声明长度与实长一致且至少 20 字节。ZIP 内容在常规后缀下可改名为 `.zip` 再解包。`.3mf` 与 `.usdz` 保留为原容器。ZIP 原件和解出的文件都纳入结果，原件在前，解出文件按路径排序。 [后缀、探测与归档分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:205>) · [GLB 检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:26>)
3. **校验 ZIP 成员。** 解包前核对条目数最多 10,000、声明解压总量最多 8 GiB。绝对路径、`..`、反斜杠、冒号、Unix 符号链接条目、重复规范化名称均导致拒绝。解包到新建暂存子目录，写入前校验工作区路径，文件以 `xb` 排他创建。空档案或解包所得 GLB 头部校验失败会停止该项。 [ZIP 校验与解包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:74>)
4. **按项发布。** 在输出根下为该项新建 `.download-stage-*`，计算暂存文件的大小、SHA-256 和最终路径。首次创建最终目录并排他保存 `complete:false` 检查点。目的文件已存在时核对摘要，一致则保留，否则报冲突。新文件用 `os.link` 创建。所有文件通过后，原子替换检查点为 `complete:true`，随后将记录写入作业的 `downloaded_results[str(index)]`。正常返回或抛错都会进入暂存目录清理。 [发布与清理顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:236>) · [排他与原子 JSON 写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:175>)
5. **落盘聚合清单。** 每个已完成项从检查点或本次发布进入 `records`，循环结束后才写入 `job.artifact = {**records[0], "files": records, "downloaded_at": now()}`。顶层 `path`、`bytes`、`sha256` 来自首个文件。模型与作业预览同在 `files`。可选 `cover` 属于已有清单的兼容复验字段。 [聚合落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:258>) · [可选封面复验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:120>)

**实现伪代码。** 省略格式检查的细节和已有聚合清单分支。`stage_and_record` 返回已检查的暂存源与最终清单。同一 Runtime 的作业串行、文件排他发布及检查点写入各有独立边界。

```python
def persist_fresh_candidates(job_path, job, output, urls):
    records = []
    for index, url in enumerate(urls):
        identity = hash_original_https_url_without_query_or_fragment(url)
        final = output / f"hi3d-result-{index}"
        marker = final / ".download.json"
        prior = load(marker) if final.exists() else None
        if prior is not None and prior.get("identity") != identity:
            raise ValueError("Result order or identity changed; preserve existing downloads")
        if prior is not None and prior.get("complete"):
            verify_records(prior["files"], output)
            records.extend(prior["files"])
            continue

        with candidate_staging(output) as staging:
            staged_files, completed = stage_and_record(url, staging, final)
            if not final.exists():
                final.mkdir()
                save(marker, {"identity": identity, "files": completed, "complete": False},
                     exclusive=True)
            else:
                prior = load(marker)
                if prior["identity"] != identity or prior["files"] != completed:
                    raise ValueError("Downloaded content changed while recovering publication")
            for staged, entry in zip(staged_files, completed):
                publish_by_exclusive_link_or_reuse_matching_digest(staged, entry)
            save(marker, {"identity": identity, "files": completed, "complete": True})
            job.setdefault("downloaded_results", {})[str(index)] = completed
            save(job_path, job)
        records.extend(completed)

    artifact = {**records[0], "files": records, "downloaded_at": now()}
    job["artifact"] = artifact
    save(job_path, job)
    return {"cached": False, "artifact": artifact}
```

### 验收

- **确认下载完成。** 独立动作返回完整 `artifact.files`，组合动作从同一清单提取 `files` 路径。下载完成覆盖当次候选取回与本地发布校验。GLB 结构解码、贴图、主体还原度和用途由候选验收检查。组合调用若返回 `attention/register-model`，继续使用回包保留的已下载文件。 [CLI 返回](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:220>) · [组合回包和登记](../tools/hi3d-api.md#已下载-3d-产物与登记)
- **按真实候选选择主模型。** 顶层首项只有文件记录。作业 WebP 或预览 GLB 可与主精度候选并列到达。主模型版本引用来自下游验收和登记回执。某张预览图与某份 GLB 的对应关系需要独立证据。 [候选取证](check-model-candidate-suitability.md#验收) · [主模型选定](select-primary-model-and-confirm-handoff.md#决策)

## 完成与恢复

| 情形 | 处理与边界 |
| --- | --- |
| 已有 `artifact` | 核对原账号与环境后复验。复验失败保留现状并报错，该分支没有自动刷新并替换聚合清单的路径。 |
| 列表中某项失败，前项已完成 | 沿原作业和输出目录恢复。使用本次新鲜 URL，依序校验完整检查点，再处理缺失或未完成的当前项。 |
| 刷新后签名变化或候选漂移 | 同序号、同 `scheme://netloc/path` 可复用有效完整项。序号处身份变化、已发布文件摘要冲突，或重抓所得清单与 `complete:false` 检查点不同，均停止并保留现有文件。 |
| 新列表缩短为原列表的前缀 | 逐项循环只处理本次列表。前缀检查点有效时可保存较短的聚合清单。检查完整性时对照本次交付预期，并查看原检查点及已落盘记录。 |
| `complete:false` | 重新下载整项到新暂存目录并重建清单，与原检查点逐项比对。保留内容一致的已发布文件，补齐缺件后再写 `complete:true`。传输恢复粒度为候选项。 |
| 已完成检查点、作业逐项记录尚未写入 | 完整检查点可直接进入新聚合清单。复用路径不回填作业逐项记录，排查时读取检查点和实际字节。 |
| 最终目录已建但检查点缺失、强制终止或发布冲突 | 核对原目录、检查点和已有文件，保留原作业与诊断。实现要求已存在目录能读到检查点，缺失会报错。强制退出可能留下暂存内容，桌面实际中断行为仍待实测。 |
| 任务仍在运行或本次刷新报错 | 正常进行中沿原作业查询。查询报错按 Skill 报告，在用户要求恢复后继续。独立动作对本次新写入的刷新错误可返回带作业摘要的 `phase: "download"` 结果，其他文件或校验错误走 CLI 异常分支。 [原作业续查](locate-job-and-qualify-resume.md) · [CLI 异常分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:223>) |
| 已落盘，版本登记待处理 | 使用当前清单中的实际候选进入验收与选定。对 `attention/register-model` 继续登记交接，保留同一任务输出。 [主模型交接](select-primary-model-and-confirm-handoff.md) |

## Vet3D 迁移与核查范围

### 与供应商无关的交接契约

用任务标识、输出根、候选身份和实际文件摘要衔接刷新、落盘及验收。下载地址及凭据只交给传输层。逐项检查点和聚合清单分别持久化，明确已暂存、发布中、已发布与聚合完成。重入时先验证已发布文件，冲突交给原任务恢复。分别记录产物角色、主模型选定、质量结论与版本登记。服务提供稳定产物 ID 时优先使用，只有序号和 URL 线索时应显式校验候选集合。服务返回缩短列表时保留范围差异，由调用方核对。 [适用性检查](check-model-candidate-suitability.md#业务定义) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md)

### 核查依据与缺口

- **安装包证据。** Windows x64 1.2.11 的 `hi3d_artifacts.py` SHA-256 为 `bf475fd266246ac2aeeeda6d512a01aeab4a0db14207b0c54fd2883ad930a056`。Runtime `Rg.run` 以作业路径串行，可从来源节点的分派锚点复核。Python 路径校验、排他发布和原子 JSON 替换分别由随包实现执行。 [下载脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>) · [工作区路径与保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:144>) · [Runtime 分派证据](confirm-download-source-and-recovery.md#执行)
- **随包测试与离线复核。** 用随包 Python 运行 49 个原测试，全部通过。恢复测试覆盖后项失败时复用前项、未完成检查点重抓、变更文件拒绝及暂存清理。账号测试覆盖无 API 凭据的文件请求、大小与解包约束。另用真实 `download_job` 配合本地查询和下载替身，复现同身份签名刷新、完整检查点缺作业逐项记录时仍能聚合，以及 ZIP 解包和 3MF、USDZ 原容器保留。候选缩短为原列表的前缀时，客户端能按本次列表生成较短 `artifact`。跨次候选集合是否完整需结合服务或交付要求判断。 [随包恢复测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_recovery.py:18>) · [下载测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py:638>)
- **本机历史样本。** 2026-11-11 的普通多视图作业保留两个 GLB 和一个 WebP。三个 `hi3d-result-<index>/.download.json` 都为 `complete:true`。三份实物字节数与 SHA-256 分别和检查点、`downloaded_results`、`artifact.files` 一致。聚合顶层同第一项，WebP 位于 `files`。组合工具随后返回 `attention/register-model`，下游另行选件登记。该样本覆盖成功落盘与登记分流。 [原作业账本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>) · [组合工具回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>)
- **待实测。** 真实服务签名过期后重新取件、候选顺序或集合变化、真实 ZIP 返回的内容、桌面强制终止与重连、跨 Runtime 争用。不同供应商和文件系统的发布与恢复契约按所选实现验证。
