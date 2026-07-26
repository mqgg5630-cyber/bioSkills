#!/usr/bin/env python3
"""
GSE118767 步骤 5 — 出图（matplotlib + scanpy）

Skills: data-visualization/dimensionality-reduction-plots, heatmaps-clustering,
        color-palettes（Okabe–Ito 色盲友好）
"""
import json
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore")
sc.settings.verbosity = 0
plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "DejaVu Sans",     # 图内一律英文，避免中文缺字形
})

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
         "#56B4E9", "#F0E442", "#999999", "#000000"]


def save(fig, name):
    for ext in (".png", ".pdf"):
        fig.savefig(os.path.join(FIG, name + ext))
    plt.close(fig)
    print(f"  wrote {name}.png / .pdf")


ad = sc.read_h5ad(os.path.join(RES, "adata_clustered.h5ad"))
qc = json.load(open(os.path.join(RES, "qc_summary.json")))
cl = json.load(open(os.path.join(RES, "cluster_summary.json")))
qcm = pd.read_csv(os.path.join(RES, "qc_metrics.csv"), index_col=0)
sweep = pd.read_csv(os.path.join(RES, "resolution_sweep_standard.csv"))
sweep_cc = pd.read_csv(os.path.join(RES, "resolution_sweep_cc_regressed.csv"))

lines = sorted(ad.obs.cell_line_truth.unique())
cmap_line = {l: OKABE[i % len(OKABE)] for i, l in enumerate(lines)}

# ---------------------------------------------------------------- Fig 1 QC
print("== Fig1 QC ==")
fig, ax = plt.subplots(1, 4, figsize=(14, 3.2))
ax[0].hist(qcm.n_genes_by_counts, bins=60, color="#0072B2", alpha=.8)
ax[0].axvline(500, color="#D55E00", ls="--", lw=1)
ax[0].set(xlabel="Genes per cell", ylabel="Cells", title="Gene count")
ax[1].hist(np.log10(qcm.total_counts), bins=60, color="#009E73", alpha=.8)
ax[1].set(xlabel="log10 UMI per cell", ylabel="Cells", title="Library size")
ax[2].hist(qcm.pct_counts_mt, bins=60, color="#CC79A7", alpha=.8)
ax[2].axvline(20, color="#D55E00", ls="--", lw=1)
ax[2].set(xlabel="Mitochondrial %", ylabel="Cells", title="MT fraction")
sc_ = qcm.copy()
ax[3].scatter(sc_.total_counts, sc_.n_genes_by_counts, s=1.5, alpha=.35,
              c=np.where(sc_.is_doublet_truth, "#D55E00", "#BBBBBB"))
ax[3].set(xscale="log", xlabel="UMI (log)", ylabel="Genes",
          title="Doublets (demuxlet)")
ax[3].legend(handles=[Line2D([], [], marker="o", ls="", color="#D55E00", label="doublet"),
                      Line2D([], [], marker="o", ls="", color="#BBBBBB", label="singlet")],
             fontsize=7, frameon=False)
fig.suptitle("Quality control — GSE118767 5 cell lines, 10x Chromium",
             fontweight="bold", y=1.04)
save(fig, "fig01_qc")

# ------------------------------------------------------ Fig 2 doublet 基准
print("== Fig2 doublet 基准 ==")
pr = pd.read_csv(os.path.join(RES, "doublet_pr_curve.csv"))
s = qc["scrublet"]
fig, ax = plt.subplots(1, 3, figsize=(12, 3.4))
ax[0].plot(pr.recall, pr.precision, color="#0072B2", lw=1.8)
ax[0].axhline(qc["ground_truth"]["doublet_pct"] / 100, color="#999999",
              ls=":", lw=1, label="random baseline")
ax[0].scatter([s["recall"]], [s["precision"]], color="#D55E00", zorder=5, s=45,
              label=f"default thr={s['threshold']}")
ax[0].set(xlabel="Recall", ylabel="Precision",
          title=f"PR curve (AUPRC={s['auprc']})")
ax[0].legend(fontsize=7, frameon=False)

f1 = pr.f1.values
ax[1].plot(pr.threshold[:-1], f1[:-1], color="#009E73", lw=1.6)
ax[1].axvline(s["threshold"], color="#D55E00", ls="--", lw=1, label="default")
ax[1].axvline(s["best_f1_threshold"], color="#0072B2", ls="--", lw=1, label="best F1")
ax[1].set(xlabel="Score threshold", ylabel="F1", title="F1 vs threshold")
ax[1].legend(fontsize=7, frameon=False)

cats = ["TP", "FP", "FN"]
vals = [s["tp"], s["fp"], s["fn"]]
ax[2].bar(cats, vals, color=["#009E73", "#D55E00", "#E69F00"])
for i, v in enumerate(vals):
    ax[2].text(i, v + 1, str(v), ha="center", fontsize=9)
ax[2].set(ylabel="Cells", title=f"At default threshold\n"
                                f"recall={s['recall']:.2f}, precision={s['precision']:.2f}")
fig.suptitle(f"Scrublet benchmarked against demuxlet ground truth "
             f"(AUROC={s['auroc']})", fontweight="bold", y=1.04)
save(fig, "fig02_doublet_benchmark")

# ------------------------------------------------------- Fig 3 分辨率扫描
print("== Fig3 分辨率扫描 ==")
fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
ax[0].plot(sweep.resolution, sweep.ARI, "o-", color="#0072B2", label="ARI")
ax[0].plot(sweep.resolution, sweep.NMI, "s--", color="#009E73", label="NMI")
b = cl["best"]
ax[0].scatter([b["resolution"]], [b["ARI"]], s=140, facecolors="none",
              edgecolors="#D55E00", lw=2, zorder=5)
ax[0].annotate(f"best res={b['resolution']}\nARI={b['ARI']:.4f}",
               (b["resolution"], b["ARI"]), textcoords="offset points",
               xytext=(28, -22), fontsize=8, color="#D55E00")
ax[0].set(xscale="log", xlabel="Leiden resolution", ylabel="Score",
          title="Agreement with demuxlet ground truth")
ax[0].legend(fontsize=8, frameon=False)
ax[0].grid(alpha=.25)

ax[1].plot(sweep.resolution, sweep.n_clusters, "o-", color="#CC79A7",
           label="standard")
ax[1].plot(sweep_cc.resolution, sweep_cc.n_clusters, "^--", color="#56B4E9",
           label="cell-cycle regressed")
ax[1].axhline(cl["n_true_classes"], color="#D55E00", ls=":", lw=1.5,
              label=f"true = {cl['n_true_classes']}")
ax[1].set(xscale="log", xlabel="Leiden resolution", ylabel="Number of clusters",
          title="Cluster count vs resolution")
ax[1].legend(fontsize=8, frameon=False)
ax[1].grid(alpha=.25)
fig.suptitle("Resolution benchmark", fontweight="bold", y=1.03)
save(fig, "fig03_resolution_sweep")

# ------------------------------------------------------------- Fig 4 UMAP
print("== Fig4 UMAP ==")
fig, ax = plt.subplots(1, 3, figsize=(14.5, 4.3))
U = ad.obsm["X_umap"]
for l in lines:
    m = (ad.obs.cell_line_truth == l).values
    ax[0].scatter(U[m, 0], U[m, 1], s=2.2, alpha=.75, c=cmap_line[l], label=l)
ax[0].set_title("Ground truth (demuxlet SNP)")
ax[0].legend(markerscale=5, fontsize=7.5, frameon=False, loc="best")

for i, (key, ttl) in enumerate(
        [("leiden_best", f"Leiden res={b['resolution']} (ARI={b['ARI']:.4f})"),
         ("leiden_split", f"Leiden res={cl['split_reference']['resolution']} "
                          f"(ARI={cl['split_reference']['ARI']:.3f})")], start=1):
    cats = sorted(ad.obs[key].unique(), key=lambda x: int(x))
    for j, c in enumerate(cats):
        m = (ad.obs[key] == c).values
        ax[i].scatter(U[m, 0], U[m, 1], s=2.2, alpha=.75,
                      c=OKABE[j % len(OKABE)], label=c)
    ax[i].set_title(ttl)
    ax[i].legend(markerscale=5, fontsize=7, frameon=False, ncol=2)
for a_ in ax:
    a_.set(xlabel="UMAP1", ylabel="UMAP2", xticks=[], yticks=[])
fig.suptitle("UMAP — 5 lung adenocarcinoma cell lines", fontweight="bold", y=1.02)
save(fig, "fig04_umap")

# --------------------------------------------------- Fig 5 混淆矩阵 + 亚群
print("== Fig5 混淆矩阵 ==")
cmb = pd.read_csv(os.path.join(RES, "confusion_best.csv"), index_col=0)
cms = pd.read_csv(os.path.join(RES, "confusion_split.csv"), index_col=0)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for a_, cm, ttl in [(ax[0], cmb, f"res={b['resolution']} (ARI={b['ARI']:.4f})"),
                    (ax[1], cms, f"res={cl['split_reference']['resolution']} "
                                 f"(ARI={cl['split_reference']['ARI']:.3f})")]:
    im = a_.imshow(cm.values, cmap="Blues", aspect="auto")
    a_.set(xticks=range(cm.shape[1]), yticks=range(cm.shape[0]),
           xlabel="True cell line", ylabel="Leiden cluster", title=ttl)
    a_.set_xticklabels(cm.columns, rotation=40, ha="right")
    a_.set_yticklabels(cm.index)
    mx = cm.values.max()
    for r in range(cm.shape[0]):
        for c in range(cm.shape[1]):
            v = cm.values[r, c]
            if v:
                a_.text(c, r, str(v), ha="center", va="center", fontsize=7,
                        color="white" if v > mx * .5 else "black")
fig.suptitle("Cluster vs ground truth", fontweight="bold", y=1.03)
save(fig, "fig05_confusion")

# --------------------------------------------------- Fig 6 亚群深度诊断
print("== Fig6 亚群溯源 ==")
mk = json.load(open(os.path.join(RES, "markers_summary.json")))
diag = mk.get("depth_diagnosis", [])
if diag:
    fig, ax = plt.subplots(1, len(diag) * 2, figsize=(6 * len(diag), 3.6))
    ax = np.atleast_1d(ax)
    for i, d in enumerate(diag):
        line = d["cell_line"]
        o = ad.obs[ad.obs.cell_line_truth == line]
        sub = [c for c in o.leiden_split.unique()
               if (o.leiden_split == c).sum() >= 20]
        # 左：UMI 深度
        a_ = ax[2 * i]
        data = [o.loc[o.leiden_split == c, "total_counts"].values for c in sub]
        bp = a_.boxplot(data, tick_labels=[f"c{c}" for c in sub], patch_artist=True,
                        widths=.55, showfliers=False)
        for p_, col in zip(bp["boxes"], OKABE):
            p_.set_facecolor(col); p_.set_alpha(.55)
        a_.set(yscale="log", ylabel="UMI per cell",
               title=f"{line}: depth {d['umi_ratio']}×\n{d['verdict'].split('：')[0]}")
        # 右：细胞周期分数
        a_ = ax[2 * i + 1]
        for j, c in enumerate(sub):
            m = o.leiden_split == c
            a_.scatter(o.loc[m, "S_score"], o.loc[m, "G2M_score"], s=5,
                       alpha=.6, c=OKABE[j % len(OKABE)], label=f"c{c}")
        a_.set(xlabel="S score", ylabel="G2M score",
               title=f"{line}: cell-cycle scores")
        a_.legend(fontsize=7, markerscale=2, frameon=False)
    fig.suptitle("Sub-cluster origin: technical depth vs biological state",
                 fontweight="bold", y=1.04)
    save(fig, "fig06_subcluster_origin")

# ------------------------------------------------------- Fig 7 标记基因
print("== Fig7 标记基因热图 ==")
full = sc.read_h5ad(os.path.join(RES, "adata_lognorm.h5ad"))
full = full[ad.obs_names].copy()
full.obs = ad.obs.copy()
mkdf = pd.read_csv(os.path.join(RES, "markers_cell_line.csv"))
top = (mkdf.sort_values(["cell_line", "pvals_adj"])
            .groupby("cell_line").head(5))
genes = [g for g in top.names.tolist() if g in full.var_names]
sc.pl.dotplot(full, genes, groupby="cell_line_truth", show=False,
              standard_scale="var", cmap="Reds", figsize=(11, 3.2))
plt.suptitle("Top marker genes per cell line (groups from SNP, p-values valid)",
             fontweight="bold", y=1.06, fontsize=10)
save(plt.gcf(), "fig07_markers_dotplot")

# --------------------------------------------------- Fig 8 已知标记验证
print("== Fig8 已知标记 ==")
kp = os.path.join(RES, "known_markers.csv")
if os.path.exists(kp):
    kn = pd.read_csv(kp)
    gs = [g for g in kn.gene if g in full.var_names]
    fig, ax = plt.subplots(1, len(gs), figsize=(3.1 * len(gs), 3.2))
    ax = np.atleast_1d(ax)
    for i, g in enumerate(gs):
        x = full[:, g].X
        x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
        df = pd.DataFrame({"v": x, "l": full.obs.cell_line_truth.values})
        data = [df.loc[df.l == l, "v"].values for l in lines]
        bp = ax[i].boxplot(data, tick_labels=lines, patch_artist=True, widths=.6,
                           showfliers=False)
        for p_, l in zip(bp["boxes"], lines):
            p_.set_facecolor(cmap_line[l]); p_.set_alpha(.65)
        ax[i].set_title(g)
        ax[i].set_ylabel("log-norm expr" if i == 0 else "")
        ax[i].tick_params(axis="x", rotation=45, labelsize=7)
    fig.suptitle("Known cell-line marker validation "
                 "(HCC827 = EGFR-amplified)", fontweight="bold", y=1.04)
    save(fig, "fig08_known_markers")

print(f"\n05 完成 -> {FIG}")
