#!/usr/bin/env python3
"""
GSE118767 步骤 3 — 归一化、降维、聚类分辨率基准与亚群溯源

这是本流程"难"的部分。三个递进的问题：

  Q1  分辨率该怎么选？
      常规做法只能看 UMAP 主观判断。本数据有 demuxlet ground truth，
      可以用 ARI/NMI 客观扫描，得到真正的最优分辨率。

  Q2  分辨率略高时多出来的簇是什么？
      是过聚类假象，还是真实亚群？

  Q3  如果是真实亚群，由什么驱动？
      细胞周期是最常见的混杂因素 —— 用回归消除后重跑，
      若 ARI 不变，则可排除细胞周期，说明是真实转录异质性。

Skills: single-cell/preprocessing, clustering, markers-annotation
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
import scanpy as sc
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             silhouette_score)

warnings.filterwarnings("ignore")
sc.settings.verbosity = 0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

N_HVG, N_PCS, N_NEIGHBORS = 2000, 30, 15
RESOLUTIONS = [0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 0.80, 1.00]

# Tirosh 2016 细胞周期基因
S_GENES = ["MCM5", "PCNA", "TYMS", "FEN1", "MCM2", "MCM4", "RRM1", "UNG",
           "GINS2", "MCM6", "CDCA7", "DTL", "PRIM1", "UHRF1", "SLBP",
           "CLSPN", "POLA1", "MSH2", "RRM2", "CDC45", "CDC6", "EXO1"]
G2M_GENES = ["HMGB2", "CDK1", "NUSAP1", "UBE2C", "BIRC5", "TPX2", "TOP2A",
             "NDC80", "CKS2", "NUF2", "CKS1B", "MKI67", "TMPO", "CENPF",
             "TACC3", "SMC4", "CCNB2", "CKAP2", "AURKB", "BUB1", "KIF11",
             "ANP32E", "GTSE1", "CDC20", "TTK", "CDC25C", "KIF2C", "RANGAP1",
             "NCAPD2", "DLGAP5", "CDCA3", "HMMR", "AURKA", "PSRC1", "ANLN",
             "LBR", "CKAP5", "CENPE", "CTCF", "NEK2", "G2E3", "GAS2L3"]


def leiden(ad, res, key):
    sc.tl.leiden(ad, resolution=res, key_added=key, flavor="igraph",
                 n_iterations=2, directed=False, random_state=0)
    return ad.obs[key]


def sweep(ad, truth, tag):
    """扫描分辨率，用 ground truth 客观打分。"""
    rows = []
    for r in RESOLUTIONS:
        lab = leiden(ad, r, "_tmp")
        rows.append({
            "resolution": r,
            "n_clusters": int(lab.nunique()),
            "ARI": round(adjusted_rand_score(truth, lab), 4),
            "NMI": round(normalized_mutual_info_score(truth, lab), 4),
        })
        print(f"  res={r:<5} 簇数={rows[-1]['n_clusters']:<3} "
              f"ARI={rows[-1]['ARI']:.4f}  NMI={rows[-1]['NMI']:.4f}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RES, f"resolution_sweep_{tag}.csv"), index=False)
    return df


print("== 1. 归一化与降维 =============================================")
adata = sc.read_h5ad(os.path.join(RES, "adata_qc.h5ad"))
print(f"输入: {adata.n_obs} 细胞 x {adata.n_vars} 基因")

sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 细胞周期打分（在全基因上算，比只用 HVG 稳）
s_use = [g for g in S_GENES if g in adata.var_names]
g_use = [g for g in G2M_GENES if g in adata.var_names]
sc.tl.score_genes_cell_cycle(adata, s_genes=s_use, g2m_genes=g_use)
print(f"细胞周期基因命中: S={len(s_use)}/{len(S_GENES)}, "
      f"G2M={len(g_use)}/{len(G2M_GENES)}")
print(f"时相分布: {adata.obs.phase.value_counts().to_dict()}")

sc.pp.highly_variable_genes(adata, n_top_genes=N_HVG)
adata.raw = adata
print(f"高变基因: {N_HVG}")

ad = adata[:, adata.var.highly_variable].copy()
sc.pp.scale(ad, max_value=10)
sc.tl.pca(ad, n_comps=50, svd_solver="arpack")
vr = ad.uns["pca"]["variance_ratio"]
print(f"PCA: 前 {N_PCS} 个 PC 累计解释 {100*vr[:N_PCS].sum():.1f}% 方差")
sc.pp.neighbors(ad, n_neighbors=N_NEIGHBORS, n_pcs=N_PCS)
sc.tl.umap(ad, random_state=0)

truth = ad.obs.cell_line_truth.astype(str).values
n_true = len(np.unique(truth))
print(f"Ground truth: {n_true} 个细胞系")

print("\n== 2. 分辨率扫描（标准流程）===================================")
sw = sweep(ad, truth, "standard")
best = sw.loc[sw.ARI.idxmax()]
print(f"\n最优: res={best.resolution} ARI={best.ARI:.4f} "
      f"({int(best.n_clusters)} 簇, 真值 {n_true} 类)")

leiden(ad, float(best.resolution), "leiden_best")
ad.obs["leiden_best"] = ad.obs["leiden_best"].astype(str)

# 略高分辨率，用于研究亚群
RES_SPLIT = 0.20
leiden(ad, RES_SPLIT, "leiden_split")
ad.obs["leiden_split"] = ad.obs["leiden_split"].astype(str)
n_split = ad.obs.leiden_split.nunique()
ari_split = adjusted_rand_score(truth, ad.obs.leiden_split)
print(f"对照 res={RES_SPLIT}: {n_split} 簇, ARI={ari_split:.4f}")

print("\n== 3. 混淆矩阵 =================================================")
cm_best = pd.crosstab(ad.obs.leiden_best, ad.obs.cell_line_truth)
print("最优分辨率下："); print(cm_best.to_string())
cm_best.to_csv(os.path.join(RES, "confusion_best.csv"))

cm_split = pd.crosstab(ad.obs.leiden_split, ad.obs.cell_line_truth)
cm_split.to_csv(os.path.join(RES, "confusion_split.csv"))
print(f"\nres={RES_SPLIT} 下（多出的簇即为亚群）："); print(cm_split.to_string())

# 哪些细胞系被拆分
split_lines = []
for line in cm_split.columns:
    col = cm_split[line]
    majors = col[col >= 0.10 * col.sum()]
    if len(majors) > 1:
        split_lines.append({"cell_line": line,
                            "n_subclusters": int(len(majors)),
                            "sizes": majors.tolist()})
        print(f"  {line} 被拆为 {len(majors)} 个亚群: {majors.tolist()}")

print("\n== 4. 亚群成因：是不是细胞周期？================================")
# 亚群 vs 细胞周期时相的列联表
cc_tables = {}
for item in split_lines:
    line = item["cell_line"]
    sub = ad.obs[ad.obs.cell_line_truth == line]
    t = pd.crosstab(sub.leiden_split, sub.phase)
    t = t[t.sum(axis=1) >= 20]          # 忽略零星细胞
    cc_tables[line] = t
    print(f"\n  {line} 亚群 x 细胞周期时相:")
    print("    " + t.to_string().replace("\n", "\n    "))
    frac = t.div(t.sum(axis=1), axis=0)
    print(f"    各亚群 G2M 占比: "
          f"{[f'{v:.2f}' for v in frac.get('G2M', pd.Series(dtype=float))]}")

print("\n== 5. 细胞周期回归后重跑（关键对照）============================")
ad_cc = adata[:, adata.var.highly_variable].copy()
sc.pp.regress_out(ad_cc, ["S_score", "G2M_score"])
sc.pp.scale(ad_cc, max_value=10)
sc.tl.pca(ad_cc, n_comps=50, svd_solver="arpack")
sc.pp.neighbors(ad_cc, n_neighbors=N_NEIGHBORS, n_pcs=N_PCS)
sw_cc = sweep(ad_cc, truth, "cc_regressed")
best_cc = sw_cc.loc[sw_cc.ARI.idxmax()]
lab_cc = leiden(ad_cc, RES_SPLIT, "_t")
ari_cc_split = adjusted_rand_score(truth, lab_cc)
print(f"\n回归后最优: res={best_cc.resolution} ARI={best_cc.ARI:.4f}")
print(f"回归后 res={RES_SPLIT}: {lab_cc.nunique()} 簇, ARI={ari_cc_split:.4f}")
delta = ari_cc_split - ari_split
print(f"ΔARI = {delta:+.4f}")
if abs(delta) < 0.02 and lab_cc.nunique() >= n_split:
    print("  -> 回归细胞周期几乎不改变聚类结构，"
          "可排除细胞周期作为亚群主因；亚群反映真实转录异质性。")
else:
    print("  -> 聚类结构明显改变，细胞周期是重要驱动因素。")

print("\n== 6. 轮廓系数（内部指标对照）==================================")
X = ad.obsm["X_pca"][:, :N_PCS]
sil_truth = silhouette_score(X, truth)
sil_best = silhouette_score(X, ad.obs.leiden_best)
print(f"以真实细胞系为标签: {sil_truth:.4f}")
print(f"以最优聚类为标签  : {sil_best:.4f}")
print("  注：内部指标偏好紧致球状簇，其高低不代表与真值的一致性，"
      "仅作对照。ARI/NMI 才是有 ground truth 时的正确度量。")

print("\n== 7. 保存 =====================================================")
ad.obs["S_score"] = adata.obs["S_score"].values
ad.obs["G2M_score"] = adata.obs["G2M_score"].values
ad.obs["phase"] = adata.obs["phase"].values
ad.write(os.path.join(RES, "adata_clustered.h5ad"))
adata.write(os.path.join(RES, "adata_lognorm.h5ad"))

json.dump({
    "params": {"n_hvg": N_HVG, "n_pcs": N_PCS, "n_neighbors": N_NEIGHBORS,
               "resolutions": RESOLUTIONS},
    "pca_var_explained_pct": round(float(100 * vr[:N_PCS].sum()), 2),
    "n_true_classes": int(n_true),
    "cell_cycle": {"n_s_genes": len(s_use), "n_g2m_genes": len(g_use),
                   "phase_counts": adata.obs.phase.value_counts().to_dict()},
    "best": {"resolution": float(best.resolution),
             "n_clusters": int(best.n_clusters),
             "ARI": float(best.ARI), "NMI": float(best.NMI)},
    "split_reference": {"resolution": RES_SPLIT, "n_clusters": int(n_split),
                        "ARI": round(float(ari_split), 4)},
    "split_cell_lines": split_lines,
    "cc_regressed": {"best_resolution": float(best_cc.resolution),
                     "best_ARI": float(best_cc.ARI),
                     "ARI_at_split_res": round(float(ari_cc_split), 4),
                     "delta_ARI": round(float(delta), 4)},
    "silhouette": {"by_truth": round(float(sil_truth), 4),
                   "by_cluster": round(float(sil_best), 4)},
}, open(os.path.join(RES, "cluster_summary.json"), "w"), indent=2)

print(f"03 完成 -> {RES}")
