#!/usr/bin/env python3
"""
GSE118767 步骤 2 — 质控 + doublet 检测与基准评估

本数据集的独特价值：demuxlet 基于 SNP 给出了每个细胞的真实身份，
其中 96 个细胞被标为 DBL（doublet）。这构成 doublet 检测的**金标准**，
让我们能客观评估 Scrublet 的性能，而不是只跑一遍看个数字。

Skills: single-cell/preprocessing, single-cell/doublet-detection
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
import scanpy as sc
from sklearn.metrics import (average_precision_score, precision_recall_curve,
                             roc_auc_score)

warnings.filterwarnings("ignore")
sc.settings.verbosity = 0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
os.makedirs(RES, exist_ok=True)

# QC 阈值（见 METHODS 说明）
MIN_GENES, MAX_MT_PCT, MIN_CELLS_PER_GENE = 500, 20.0, 3
EXPECTED_DBL_RATE = 0.025          # 10x 载入 ~4000 细胞的经验值

print("== 1. 读入原始 counts ==========================================")
cnt = pd.read_csv(os.path.join(DATA, "sc_10x_5cl.count.csv.gz"), index_col=0)
met = pd.read_csv(os.path.join(DATA, "sc_10x_5cl.metadata.csv.gz"), index_col=0)
print(f"原始矩阵: {cnt.shape[0]} 基因 x {cnt.shape[1]} 细胞")
print(f"数据类型: {cnt.values.dtype}, 最大值 {cnt.values.max()} (整数 counts)")

adata = sc.AnnData(cnt.T.astype("float32"))
adata.obs = met.loc[adata.obs_names].copy()
adata.obs["cell_line_truth"] = adata.obs["cell_line_demuxlet"].astype(str)
adata.obs["is_doublet_truth"] = (adata.obs["demuxlet_cls"] == "DBL")

n_dbl = int(adata.obs.is_doublet_truth.sum())
print(f"\ndemuxlet ground truth:")
print(f"  单细胞 SNG: {len(adata) - n_dbl}")
print(f"  双细胞 DBL: {n_dbl} ({100*n_dbl/len(adata):.2f}%)")
print(f"  细胞系分布: {adata.obs.cell_line_truth.value_counts().to_dict()}")

print("\n== 2. QC 指标 ==================================================")
adata.var["mt"] = adata.var_names.str.startswith("MT-")
adata.var["ercc"] = adata.var_names.str.startswith("ERCC")
print(f"线粒体基因 {int(adata.var.mt.sum())} 个, ERCC spike-in {int(adata.var.ercc.sum())} 个")
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ercc"], inplace=True,
                           percent_top=None, log1p=False)
qc_before = dict(
    n_cells=int(adata.n_obs), n_genes=int(adata.n_vars),
    median_genes=float(np.median(adata.obs.n_genes_by_counts)),
    median_umi=float(np.median(adata.obs.total_counts)),
    median_mt_pct=float(np.median(adata.obs.pct_counts_mt)),
    median_ercc_pct=float(np.median(adata.obs.pct_counts_ercc)),
)
print(f"中位基因数 {qc_before['median_genes']:.0f}, 中位 UMI {qc_before['median_umi']:.0f}")
print(f"中位 MT% {qc_before['median_mt_pct']:.2f}, 中位 ERCC% {qc_before['median_ercc_pct']:.2f}")

adata.obs[["n_genes_by_counts", "total_counts", "pct_counts_mt",
           "pct_counts_ercc", "cell_line_truth", "is_doublet_truth"]] \
    .to_csv(os.path.join(RES, "qc_metrics.csv"))

print("\n== 3. Doublet 检测 (Scrublet) ==================================")
# 先在含全部细胞的矩阵上跑，以便与 ground truth 比对
ad_s = adata[:, ~adata.var.ercc].copy()      # spike-in 不参与
sc.pp.scrublet(ad_s, expected_doublet_rate=EXPECTED_DBL_RATE, random_state=0)
adata.obs["doublet_score"] = ad_s.obs["doublet_score"].values
adata.obs["predicted_doublet"] = ad_s.obs["predicted_doublet"].values.astype(bool)
thr = float(ad_s.uns["scrublet"]["threshold"])

truth = adata.obs.is_doublet_truth.values
score = adata.obs.doublet_score.values
pred = adata.obs.predicted_doublet.values

auroc = roc_auc_score(truth, score)
auprc = average_precision_score(truth, score)
tp = int((pred & truth).sum()); fp = int((pred & ~truth).sum())
fn = int((~pred & truth).sum())
recall = tp / max(truth.sum(), 1)
precision = tp / max(pred.sum(), 1)

print(f"AUROC = {auroc:.4f}")
print(f"AUPRC = {auprc:.4f}  (随机基线 {truth.mean():.4f})")
print(f"默认阈值 {thr:.3f}: 预测 {int(pred.sum())} 个")
print(f"  TP={tp} FP={fp} FN={fn}")
print(f"  召回率 {recall:.3f}  精确率 {precision:.3f}")
print(f"  -> 精确率极高但召回率有限：默认阈值偏保守")

# PR 曲线，找 F1 最优阈值作为对照
p_arr, r_arr, t_arr = precision_recall_curve(truth, score)
f1 = 2 * p_arr * r_arr / np.clip(p_arr + r_arr, 1e-12, None)
bi = int(np.nanargmax(f1))
best_thr = float(t_arr[min(bi, len(t_arr) - 1)])
print(f"F1 最优阈值 {best_thr:.3f}: F1={f1[bi]:.3f} "
      f"(精确 {p_arr[bi]:.3f} / 召回 {r_arr[bi]:.3f})")

pd.DataFrame({"threshold": np.append(t_arr, np.nan),
              "precision": p_arr, "recall": r_arr, "f1": f1}) \
    .to_csv(os.path.join(RES, "doublet_pr_curve.csv"), index=False)

print("\n== 4. 过滤 =====================================================")
n0 = adata.n_obs
keep = ((adata.obs.n_genes_by_counts > MIN_GENES) &
        (adata.obs.pct_counts_mt < MAX_MT_PCT) &
        (~adata.obs.predicted_doublet))
adata = adata[keep].copy()
print(f"细胞: {n0} -> {adata.n_obs} (移除 {n0 - adata.n_obs})")

adata = adata[:, ~adata.var.ercc].copy()
g0 = adata.n_vars
sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)
print(f"基因: {g0} -> {adata.n_vars} (去 ERCC 并要求 >= {MIN_CELLS_PER_GENE} 细胞表达)")
print(f"过滤后残余真实 doublet: {int(adata.obs.is_doublet_truth.sum())}")

adata.layers["counts"] = adata.X.copy()
adata.write(os.path.join(RES, "adata_qc.h5ad"))

json.dump({
    "qc_before": qc_before,
    "qc_thresholds": {"min_genes": MIN_GENES, "max_mt_pct": MAX_MT_PCT,
                      "min_cells_per_gene": MIN_CELLS_PER_GENE},
    "ground_truth": {"n_total": int(n0), "n_doublet": n_dbl,
                     "doublet_pct": round(100 * n_dbl / n0, 2),
                     "cell_lines": adata.obs.cell_line_truth.value_counts().to_dict()},
    "scrublet": {"expected_rate": EXPECTED_DBL_RATE, "threshold": round(thr, 4),
                 "auroc": round(auroc, 4), "auprc": round(auprc, 4),
                 "baseline_auprc": round(float(truth.mean()), 4),
                 "n_predicted": int(pred.sum()), "tp": tp, "fp": fp, "fn": fn,
                 "recall": round(recall, 4), "precision": round(precision, 4),
                 "best_f1": round(float(f1[bi]), 4),
                 "best_f1_threshold": round(best_thr, 4)},
    "after_filter": {"n_cells": int(adata.n_obs), "n_genes": int(adata.n_vars),
                     "residual_doublets": int(adata.obs.is_doublet_truth.sum())},
}, open(os.path.join(RES, "qc_summary.json"), "w"), indent=2)

print(f"\n02 完成 -> {RES}")
