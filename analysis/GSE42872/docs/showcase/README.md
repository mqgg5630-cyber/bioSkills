# 样例结果快照

这里是 GSE42872 流程跑出来的**代表性结果快照**，固定不动，方便不跑代码也能直接看。

跑流程产生的完整输出在 `../../figures/` 和 `../../results/`，那两个目录**不入 git**
（每次运行都会重新生成，入库会导致 `git pull` 冲突）。

## 关键数字（`run_summary.json`）

```
33,297 探针 × 6 样本，GPL6244 芯片，RMA log2 强度
限量贝叶斯先验: s0² = 0.01080, d0 = 3.000
padj<0.05            : 9,877
padj<0.05 且 |LFC|>1 : 1,303  (上调 701 / 下调 602)
```

## 验证结果（`validation.json`）

```json
{
  "n_aligned": 17239,
  "logFC_pearson_r": 0.9986,
  "logFC_exact_match": 17202,
  "logFC_exact_pct": 99.79,
  "t_pearson_r": 0.9956,
  "top50_overlap": 42,
  "mapk_all_down": true
}
```

与原作者用真 R/limma 跑出的结果对比：**99.79% 的 logFC 逐位相同**。

## 图

| 文件 | 内容 |
|---|---|
| `fig02_pca.png` | PCA，PC1 = 82.4% 方差，两组完全分开 |
| `fig04_volcano.png` | 火山图，上调 701 / 下调 602 |
| `fig06_heatmap_top50.png` | top50 差异基因 z-score 热图 |
| `fig07_MAPK_targets.png` | **12 个 MAPK 通路基因全部下调**（生物学阳性对照） |

完整的 8 张图请自己跑 `bash analysis/GSE42872/run_all.sh`。
