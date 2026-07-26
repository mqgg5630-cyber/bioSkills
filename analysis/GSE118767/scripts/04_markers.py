#!/usr/bin/env python3
"""
GSE118767 步骤 4 — 标记基因与亚群表征

⚠️ 关于 double-dipping（数据重复使用）
   bioSkills 的 single-cell/clustering skill 明确指出：
   聚类算法的目标就是最大化组间差异，再对同一批数据上的这些簇做
   差异检验，等于"用产生假设的数据去检验该假设"，
   得到的 p 值不是偏高，而是**根本无效**。

   本脚本据此做两件事：
   1. 细胞系之间的标记基因 —— 用 demuxlet ground truth 作分组，
      标签独立于表达数据（来自 SNP），**不存在 double-dipping**，
      p 值有效。
   2. 亚群内部的差异基因 —— 分组来自聚类本身，
      **明确标注 p 值不可作为推断依据**，仅用于描述与生成假设。

Skills: single-cell/markers-annotation, single-cell/clustering
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
import scanpy as sc

warnings.filterwarnings("ignore")
sc.settings.verbosity = 0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

TOP_N = 30

print("== 1. 载入 =====================================================")
ad = sc.read_h5ad(os.path.join(RES, "adata_clustered.h5ad"))
full = sc.read_h5ad(os.path.join(RES, "adata_lognorm.h5ad"))
full.obs = ad.obs.reindex(full.obs_names).combine_first(full.obs)
full = full[ad.obs_names].copy()
print(f"{full.n_obs} 细胞 x {full.n_vars} 基因")

print("\n== 2. 细胞系标记基因（标签来自 SNP，p 值有效）==================")
sc.tl.rank_genes_groups(full, "cell_line_truth", method="wilcoxon",
                        key_added="rgg_line")
rows = []
for line in full.obs.cell_line_truth.unique():
    d = sc.get.rank_genes_groups_df(full, group=line, key="rgg_line")
    d = d[(d.pvals_adj < 0.05) & (d.logfoldchanges > 1)].head(TOP_N)
    d.insert(0, "cell_line", line)
    rows.append(d)
    top = d.names.head(6).tolist()
    print(f"  {line:<8} 显著上调 {len(d):>3} 个, top6: {', '.join(top)}")
mk = pd.concat(rows, ignore_index=True)
mk.to_csv(os.path.join(RES, "markers_cell_line.csv"), index=False)

print("\n== 3. 亚群表征（p 值仅描述，不作推断）==========================")
sub_out, sub_summary = [], []
for line in ["H838", "H1975"]:
    m = full.obs.cell_line_truth == line
    sub = full[m].copy()
    vc = sub.obs.leiden_split.value_counts()
    keep = vc[vc >= 20].index.tolist()
    if len(keep) < 2:
        continue
    sub = sub[sub.obs.leiden_split.isin(keep)].copy()
    sub.obs["sg"] = sub.obs.leiden_split.astype(str)
    sc.tl.rank_genes_groups(sub, "sg", method="wilcoxon", key_added="rgg_sub")

    g0, g1 = keep[0], keep[1]
    d = sc.get.rank_genes_groups_df(sub, group=str(g0), key="rgg_sub")
    up = d[(d.pvals_adj < 0.05) & (d.logfoldchanges > 0.5)]
    dn = d[(d.pvals_adj < 0.05) & (d.logfoldchanges < -0.5)]
    print(f"\n  {line}: 亚群 {g0} (n={vc[g0]}) vs {g1} (n={vc[g1]})")
    print(f"    上调 {len(up)} / 下调 {len(dn)} 个基因")
    print(f"    {g0} 富集 top8: {', '.join(up.names.head(8).tolist())}")
    print(f"    {g1} 富集 top8: {', '.join(dn.names.head(8).tolist())}")

    # 细胞周期分数差异 —— 定量确认亚群是否由周期驱动
    s0 = sub.obs.loc[sub.obs.sg == str(g0), ["S_score", "G2M_score"]].mean()
    s1 = sub.obs.loc[sub.obs.sg == str(g1), ["S_score", "G2M_score"]].mean()
    print(f"    S_score  {s0.S_score:+.3f} vs {s1.S_score:+.3f}")
    print(f"    G2M_score {s0.G2M_score:+.3f} vs {s1.G2M_score:+.3f}")

    t = up.head(TOP_N).copy(); t.insert(0, "direction", f"up_in_{g0}")
    b = dn.head(TOP_N).copy(); b.insert(0, "direction", f"up_in_{g1}")
    o = pd.concat([t, b], ignore_index=True); o.insert(0, "cell_line", line)
    sub_out.append(o)
    sub_summary.append({
        "cell_line": line, "cluster_a": str(g0), "cluster_b": str(g1),
        "n_a": int(vc[g0]), "n_b": int(vc[g1]),
        "n_up": int(len(up)), "n_down": int(len(dn)),
        "top_up": up.names.head(10).tolist(),
        "top_down": dn.names.head(10).tolist(),
        "S_score_a": round(float(s0.S_score), 4),
        "S_score_b": round(float(s1.S_score), 4),
        "G2M_score_a": round(float(s0.G2M_score), 4),
        "G2M_score_b": round(float(s1.G2M_score), 4),
    })
if sub_out:
    pd.concat(sub_out, ignore_index=True) \
      .to_csv(os.path.join(RES, "markers_subcluster.csv"), index=False)

print("\n== 3b. 亚群溯源：技术性深度差异 vs 生物学异质性 =================")
# 关键诊断：若两个亚群的测序深度差异悬殊，则"亚群"很可能是
# 文库深度造成的技术性分层，而非真实转录状态差异。
from scipy.stats import mannwhitneyu
depth_diag = []
for item in sub_summary:
    line, ca, cb = item["cell_line"], item["cluster_a"], item["cluster_b"]
    o = full.obs[full.obs.cell_line_truth == line]
    x = o.loc[o.leiden_split == ca, "total_counts"].values
    y = o.loc[o.leiden_split == cb, "total_counts"].values
    xg = o.loc[o.leiden_split == ca, "n_genes_by_counts"].values
    yg = o.loc[o.leiden_split == cb, "n_genes_by_counts"].values
    ratio = float(np.median(x) / np.median(y))
    p_umi = float(mannwhitneyu(x, y)[1])
    g_ratio = float(np.median(xg) / np.median(yg))
    verdict = ("技术性：深度差异主导" if (ratio > 1.5 or ratio < 0.67)
               else "生物学：深度相当，反映真实异质性")
    depth_diag.append({"cell_line": line, "umi_ratio": round(ratio, 3),
                       "umi_p": p_umi, "gene_ratio": round(g_ratio, 3),
                       "median_umi_a": float(np.median(x)),
                       "median_umi_b": float(np.median(y)),
                       "verdict": verdict})
    print(f"  {line}: UMI 中位 {np.median(x):.0f} vs {np.median(y):.0f} "
          f"(比值 {ratio:.2f}x, p={p_umi:.2e})")
    print(f"        基因数比 {g_ratio:.2f}x  ->  {verdict}")
    item["depth_ratio"] = round(ratio, 3)
    item["verdict"] = verdict

print("\n== 4. 已知细胞系特征基因核查 ===================================")
# EGFR 突变系 HCC827/H1975 高表达 EGFR；H2228 携带 EML4-ALK
known = {"EGFR": "HCC827/H1975 (EGFR 扩增或突变)",
         "ALK": "H2228 (EML4-ALK 融合)",
         "KRT81": "细胞系间差异标记",
         "VIM": "间质表型",
         "CDH1": "上皮表型"}
rows = []
for g, note in known.items():
    if g not in full.var_names:
        continue
    x = full[:, g].X
    x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
    mean_by = pd.Series(x).groupby(full.obs.cell_line_truth.values).mean()
    rows.append({"gene": g, "note": note,
                 **{k: round(float(v), 3) for k, v in mean_by.items()}})
    print(f"  {g:<6} {mean_by.round(2).to_dict()}   ({note})")
if rows:
    pd.DataFrame(rows).to_csv(os.path.join(RES, "known_markers.csv"), index=False)

json.dump({"top_n": TOP_N,
           "n_markers_total": int(len(mk)),
           "markers_per_line": mk.cell_line.value_counts().to_dict(),
           "subclusters": sub_summary,
           "depth_diagnosis": depth_diag,
           "note": ("细胞系标记基因的分组来自 demuxlet SNP 判定，独立于表达数据，"
                    "p 值有效；亚群差异基因的分组来自聚类，存在 double-dipping，"
                    "p 值不可作为推断依据。")},
          open(os.path.join(RES, "markers_summary.json"), "w"), indent=2)
print(f"\n04 完成 -> {RES}")
