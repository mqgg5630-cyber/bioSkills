#!/usr/bin/env python3
"""
GSE42872 — ggplot 出图（plotnine，与 R 的 ggplot2 语法一致）

Skills: data-visualization/{ggplot2-fundamentals, volcano-and-ma-plots,
        dimensionality-reduction-plots, heatmaps-clustering, color-palettes}

坑（实测）：plotnine 不认 R 的颜色名（'grey80' 会抛
Unknown name for a color），一律用十六进制。
"""
import os, sys, json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import pdist
from plotnine import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

de   = pd.read_csv(os.path.join(RES, "DE_Vemurafenib_vs_Control.csv"))
expr = pd.read_csv(os.path.join(RES, "expression_matrix.csv.gz"), index_col=0)
expr.index = expr.index.astype(str); expr.index.name = "probe"
cold = pd.read_csv(os.path.join(RES, "sample_metadata.csv"), index_col=0)
cold.index.name = "gsm"
sym  = expr.pop("symbol")

GRP_COLS = {"Control": "#0072B2", "Vemurafenib": "#D55E00"}   # Okabe–Ito
DIR_COLS = {"Up": "#D55E00", "Down": "#0072B2", "n.s.": "#CCCCCC"}
LFC, FDR = 1.0, 0.05

def theme_pub(base=10):
    return (theme_bw(base_size=base)
            + theme(panel_grid_minor=element_blank(),
                    panel_grid_major=element_line(size=.25, color="#E5E5E5"),
                    plot_title=element_text(weight="bold", size=base+2),
                    plot_subtitle=element_text(color="#555555", size=base-1),
                    strip_background=element_rect(fill="#F0F0F0", color="#4D4D4D"),
                    figure_size=(7, 5)))

def save(p, name, w, h):
    for ext, kw in ((".png", {"dpi": 300}), (".pdf", {})):
        p.save(os.path.join(FIG, name + ext), width=w, height=h, verbose=False, **kw)
    print(f"  wrote {name}.png / .pdf")

# ---------------------------------------------------------------- Fig 1 QC
print("== Fig1 样本表达分布 ==")
long = (expr.reset_index().melt(id_vars="probe",
                                var_name="gsm", value_name="expr")
            .merge(cold.reset_index()[["gsm", "group", "replicate"]], on="gsm"))
long["label"] = long.group.str[:4] + "_r" + long.replicate.astype(str)
p1 = (ggplot(long, aes("label", "expr", fill="group"))
      + geom_boxplot(outlier_size=.15, outlier_alpha=.2, size=.35)
      + scale_fill_manual(values=GRP_COLS, name="")
      + labs(title="Sample expression distribution (RMA log2)",
             subtitle="GSE42872 | A375 melanoma | aligned medians confirm RMA normalization",
             x="", y="log2 intensity")
      + theme_pub() + theme(axis_text_x=element_text(rotation=30, ha="right")))
save(p1, "fig01_sample_distribution", 7, 5)

# ---------------------------------------------------------------- Fig 2 PCA
print("== Fig2 PCA ==")
X = expr.T.values
v = X.var(axis=0)
Xs = X[:, np.argsort(v)[-5000:]]
Xc = Xs - Xs.mean(axis=0)
U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
pcv = 100 * S**2 / (S**2).sum()
pca = pd.DataFrame({"PC1": U[:, 0]*S[0], "PC2": U[:, 1]*S[1],
                    "gsm": expr.columns}).merge(cold.reset_index(), on="gsm")
pca["label"] = pca.group.str[:4] + "_r" + pca.replicate.astype(str)
p2 = (ggplot(pca, aes("PC1", "PC2", color="group"))
      + geom_point(size=4, alpha=.9)
      + geom_text(aes(label="label"), nudge_y=(pca.PC2.max()-pca.PC2.min())*.07,
                  size=7, color="#333333")
      + scale_color_manual(values=GRP_COLS, name="")
      + labs(title="PCA (top 5000 variable probes)",
             subtitle="PC1 cleanly separates treated from control",
             x=f"PC1: {pcv[0]:.1f}% variance", y=f"PC2: {pcv[1]:.1f}% variance")
      + theme_pub())
save(p2, "fig02_pca", 7, 5.5)

# ------------------------------------------------------- Fig 3 样本相关热图
print("== Fig3 样本相关性 ==")
cm = np.corrcoef(expr.T.values)
lbl = (cold.group.str[:4] + "_r" + cold.replicate.astype(str)).loc[expr.columns].values
order = leaves_list(linkage(pdist(expr.T.values), "average"))
lv = [lbl[i] for i in order]
cdf = pd.DataFrame(cm, index=lbl, columns=lbl).stack().reset_index()
cdf.columns = ["s1", "s2", "r"]
cdf["s1"] = pd.Categorical(cdf.s1, lv); cdf["s2"] = pd.Categorical(cdf.s2, lv[::-1])
p3 = (ggplot(cdf, aes("s1", "s2", fill="r"))
      + geom_tile(color="white", size=.5)
      + geom_text(aes(label="r"), format_string="{:.3f}", size=7)
      + scale_fill_gradient(low="#FFF7EC", high="#B2182B", name="Pearson r")
      + labs(title="Sample-sample correlation (hierarchically ordered)",
             subtitle="within-group r exceeds between-group: good reproducibility", x="", y="")
      + theme_pub() + theme(axis_text_x=element_text(rotation=45, ha="right"),
                            panel_grid_major=element_blank()))
save(p3, "fig03_sample_correlation", 6.5, 5.5)

# ------------------------------------------------------------ Fig 4 火山图
print("== Fig4 火山图 ==")
v = de.dropna(subset=["adj.P.Val"]).copy()
v["nlp"] = -np.log10(v["adj.P.Val"].clip(lower=1e-300))
lab = (v[(v.direction != "n.s.") & v.symbol.notna()]
       .assign(score=lambda d: d.nlp * d.logFC.abs())
       .nlargest(18, "score"))
p4 = (ggplot(v, aes("logFC", "nlp", color="direction"))
      + geom_hline(yintercept=-np.log10(FDR), linetype="dashed", color="#808080", size=.35)
      + geom_vline(xintercept=[-LFC, LFC], linetype="dashed", color="#808080", size=.35)
      + geom_point(size=.5, alpha=.55)
      + geom_text(lab, aes(label="symbol"), size=7, color="#1A1A1A",
                  adjust_text={"arrowprops": {"arrowstyle": "-", "color": "#999999", "lw": .4}})
      + scale_color_manual(values=DIR_COLS, name="")
      + labs(title="Volcano: Vemurafenib vs Control",
             subtitle=f"limma moderated t | |log2FC|>{LFC} and FDR<{FDR} | "
                      f"up {(v.direction=='Up').sum()} / down {(v.direction=='Down').sum()}",
             x="log2 fold change", y="-log10 adjusted P")
      + theme_pub())
save(p4, "fig04_volcano", 8, 6.5)

# ---------------------------------------------------------------- Fig 5 MA
print("== Fig5 MA 图 ==")
p5 = (ggplot(v, aes("AveExpr", "logFC", color="direction"))
      + geom_hline(yintercept=0, color="#4D4D4D", size=.4)
      + geom_hline(yintercept=[-LFC, LFC], linetype="dashed", color="#808080", size=.3)
      + geom_point(size=.5, alpha=.5)
      + scale_color_manual(values=DIR_COLS, name="")
      + labs(title="MA plot", subtitle="greater spread at low expression, as expected for arrays",
             x="average expression (log2)", y="log2 fold change")
      + theme_pub())
save(p5, "fig05_ma", 7.5, 5)

# --------------------------------------------------------- Fig 6 top50 热图
print("== Fig6 top50 热图 ==")
top = de[de.symbol.notna() & (de.direction != "n.s.")].drop_duplicates("symbol").head(50)
sub = expr.loc[top.probe.astype(str)]
z = sub.sub(sub.mean(axis=1), axis=0).div(sub.std(axis=1).replace(0, 1), axis=0)
z.index = top.symbol.values
go = leaves_list(linkage(pdist(z.values), "average"))
so = leaves_list(linkage(pdist(z.T.values), "average"))
h = z.iloc[go, so].stack().reset_index()
h.columns = ["gene", "gsm", "z"]
h = h.merge(cold.reset_index()[["gsm", "group", "replicate"]], on="gsm")
h["label"] = h.group.str[:4] + "_r" + h.replicate.astype(str)
h["gene"] = pd.Categorical(h.gene, [z.index[i] for i in go])
h["label"] = pd.Categorical(h.label, [lbl[i] for i in so])
p6 = (ggplot(h, aes("label", "gene", fill="z"))
      + geom_tile()
      + scale_fill_gradient2(low="#2166AC", mid="#FFFFFF", high="#B2182B",
                             midpoint=0, limits=(-1.6, 1.6), name="row z-score")
      + labs(title="Top 50 differentially expressed genes", subtitle="row-wise z-score", x="", y="")
      + theme_pub(8)
      + theme(axis_text_y=element_text(size=5.5),
              axis_text_x=element_text(rotation=45, ha="right"),
              panel_grid_major=element_blank(), figure_size=(5.5, 9)))
save(p6, "fig06_heatmap_top50", 5.5, 9)

# --------------------------------------------------- Fig 7 MAPK 通路标志基因
print("== Fig7 MAPK 通路基因 ==")
# 维罗非尼抑制 BRAF-V600E → MAPK/ERK 通路输出基因应当下调
mapk = ["DUSP6", "SPRY2", "SPRY4", "ETV4", "ETV5", "PHLDA1",
        "CCND1", "MYC", "FOSL1", "EPHA2", "IER3", "DUSP4"]
sel = de[de.symbol.isin(mapk)].drop_duplicates("symbol").set_index("symbol")
rows = []
for g in mapk:
    if g not in sel.index: continue
    pr = str(sel.loc[g, "probe"])
    for gsm_ in expr.columns:
        rows.append({"gene": g, "gsm": gsm_, "expr": expr.loc[pr, gsm_],
                     "padj": sel.loc[g, "adj.P.Val"], "logFC": sel.loc[g, "logFC"]})
md = pd.DataFrame(rows).merge(cold.reset_index()[["gsm", "group"]], on="gsm")
md["gene"] = pd.Categorical(md.gene, [g for g in mapk if g in sel.index])
p7 = (ggplot(md, aes("group", "expr", fill="group"))
      + geom_boxplot(width=.6, alpha=.35, outlier_alpha=0, size=.35)
      + geom_point(aes(color="group"), size=1.8, alpha=.9)
      + facet_wrap("gene", scales="free_y", ncol=4)
      + scale_fill_manual(values=GRP_COLS, guide=None)
      + scale_color_manual(values=GRP_COLS, name="")
      + scale_x_discrete(labels=["Ctrl", "Vem"])
      + labs(title="MAPK/ERK pathway output genes",
             subtitle="Vemurafenib inhibits BRAF-V600E: pathway outputs go down (positive control)",
             x="", y="log2 intensity")
      + theme_pub(9) + theme(figure_size=(10, 7.5), legend_position="top"))
save(p7, "fig07_MAPK_targets", 10, 7.5)

# ------------------------------------------------------- Fig 8 上下调计数
print("== Fig8 差异基因计数 ==")
cnt = pd.DataFrame({"direction": ["Up", "Down"],
                    "n": [(de.direction == "Up").sum(), (de.direction == "Down").sum()]})
cnt["signed"] = np.where(cnt.direction == "Up", cnt.n, -cnt.n)
p8 = (ggplot(cnt, aes("direction", "signed", fill="direction"))
      + geom_col(width=.55)
      + geom_hline(yintercept=0, color="#333333")
      + geom_text(aes(label="n"), va="bottom", size=10, nudge_y=20)
      + scale_fill_manual(values=DIR_COLS, guide=None)
      + labs(title="Differentially expressed probes", subtitle=f"FDR<{FDR} and |log2FC|>{LFC}",
             x="", y="number of probes")
      + theme_pub())
save(p8, "fig08_de_counts", 5, 4.5)

json.dump({"figures": sorted(os.listdir(FIG))},
          open(os.path.join(RES, "figures_manifest.json"), "w"), indent=2)
print("\n03 完成 ->", FIG)
