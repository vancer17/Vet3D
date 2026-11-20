# Geo2 对照与交接

目标服务契约唯一维护于 [geometry-v4-geo2-pass1-cfg-distill-quant](../../.dependency-service-select/references/mdf/geometry-v4-geo2-pass1-cfg-distill-quant.md) 与 [共有契约](../../.dependency-service-select/references/geometry-v4-contract.md#外露表面坐标与缓存优先级)。这里说明本 skill 的产物接入，不复制服务客户端。

已核对源码的事实：

1. MDF 入口收 `prep_zip` 和 `stage1_mesh_glb`，不透传 `coords_npz` / `coords_from_mesh`；不要把它们加入请求后假定生效。
2. 准备阶段会扫描 bridge 根目录 NPZ，优先选 latent_scale 匹配且有 coords 的文件，否则可回退到其他 coords NPZ。本 skill 的 package 因此要求原 ZIP 没有竞争 coords，也没有嵌入 GLB；否则拒绝，不默默覆盖旧内容。
3. 没有 coords 时，默认 mesh_voxelizer 路径先将装配 GLB 归一化到居中尺度，再体素化所有三角面，floor-divide 并去重到 latent 坐标。它没有执行外部空气连通性剔除。
4. 本 skill 在同一高分辨率格网中筛选，再同样除以 L；直接提供最终 latent coords 后，上游 NPZ 路径不会再次池化。本地保存的 raw surface/removed 文件不放入服务包。

先用 geometry-input 组装并检查同源 GrayColor、浮点 CCM、mask 与实际相机，再附加坐标：

```bash
"$PYTHON" "$SKILL_DIR/scripts/exterior_surface.py" package \
  --prep-zip "$RUN_DIR/prep.zip" \
  --coords "$RUN_DIR/exterior/geo2_coords.npz" \
  --source "$RUN_DIR/assembled.glb" --grid-size "$G" --latent-scale "$L" \
  --output "$RUN_DIR/prep_exterior.zip"
```

`attach_coords` 验证源哈希、G/L/坐标范围与唯一性，保留原 ZIP 每个成员字节，根目录只新增 `geo2_coords.npz`。重复成员、危险路径、内嵌 mesh 或已有 root coords NPZ 均失败；不验证相机与 CCM 数值，也不生成新图像。外观条件必须由执行者在打包前检查。修改装配位置/部件或影响包围盒的清理后，不能沿用未知版本的 CCM。

MDF 业务文件：

```json
{
  "prep_zip": {"$file": "prep_exterior.zip"},
  "stage1_mesh_glb": {"$file": "assembled.glb"},
  "postprocess": false,
  "return_origin_mesh": true
}
```

原 GLB 在这里仍是同源坐标/视图载体，内部条件通过 NPZ 排除；交付时明确“已过滤生成坐标，原 GLB 未删面”。`save_vxz` 是生成结果导出开关，不能用于请求输入外壳提取。

这条 NPZ 自动发现路径有固定版本源码依据，尚不等于当前线上 worker 的兼容承诺。第一次在目标部署使用时核对实际源码/profile 和被消费的坐标数量/内容，不只看任务成功。若部署改变发现逻辑，改走明确受支持的入口或先在新副本清理 mesh，不能静默发送无效字段或强行宣称生效。
