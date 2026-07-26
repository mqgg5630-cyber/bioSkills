#!/usr/bin/env python3
"""
GSE42872 — 富集分析（GSEA preranked + ORA）

这是差异表达之后最自然的下一步。见 METHODS.md 第 11 节。

Skills: pathway-analysis/gsea, go-enrichment, kegg-pathways

用法:
    python scripts/05_enrichment.py              # 在线基因集库（需联网）
    python scripts/05_enrichment.py --offline    # 只用内置基因集（离线可跑）

排序统计量用 limma 的 moderated t —— 不能用 p 值（丢方向），
也不建议用裸 logFC（低表达基因的不稳定大倍数会劫持 leading edge）。
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
OUT = os.path.join(RES, "enrichment")

# 内置基因集：离线也能验证流程通不通
BUILTIN_SETS = {
    "MAPK_ERK_OUTPUT": [
        "DUSP6", "SPRY2", "SPRY4", "ETV4", "ETV5", "PHLDA1", "CCND1", "MYC",
        "FOSL1", "EPHA2", "IER3", "DUSP4", "SPRED1", "SPRED2", "ETV1",
    ],
    "CELL_CYCLE_G2M": [
        "CCNB1", "CDK1", "PLK1", "BUB1", "AURKA", "AURKB", "TOP2A", "MKI67",
        "CCNA2", "CDC20", "UBE2C", "TPX2",
    ],
    "MELANOCYTE_DIFFERENTIATION": [
        "MITF", "TYR", "TYRP1", "DCT", "PMEL", "MLANA", "SOX10", "PAX3",
    ],
    "CHOLESTEROL_HOMEOSTASIS": [
        "LDLR", "HMGCR", "HMGCS1", "SQLE", "INSIG1", "SREBF1", "SREBF2", "FDFT1",
    ],
}

ONLINE_LIBS = ["MSigDB_Hallmark_2020", "KEGG_2021_Human",
               "GO_Biological_Process_2023"]


def load_ranking():
    """从 DE 结果构建排序向量（基因 symbol -> moderated t）。"""
    f = os.path.join(RES, "DE_Vemurafenib_vs_Control.csv")
    if not os.path.exists(f):
        sys.exit(f"找不到 {f}，请先跑 02_limma_de.py")
    d = pd.read_csv(f).dropna(subset=["symbol"])
    if d.empty:
        sys.exit("DE 结果里没有基因 symbol —— 探针注释缺失，富集分析无法进行。\n"
                 "请检查 01_fetch.sh 是否取到 GPL6244.annot.gz")
    # 同一基因多探针时保留 |t| 最大的那个
    d = d.reindex(d.t.abs().sort_values(ascending=False).index)
    d = d.drop_duplicates("symbol")
    rnk = d.set_index("symbol")["t"].sort_values(ascending=False)
    print(f"排序向量: {len(rnk)} 基因, t 范围 {rnk.min():.1f} ~ {rnk.max():.1f}")
    return rnk, d


def run_gsea(rnk, gene_sets, tag, nperm=1000):
    import gseapy as gp
    print(f"\n== GSEA preranked [{tag}] ==")
    try:
        r = gp.prerank(rnk=rnk, gene_sets=gene_sets, permutation_num=nperm,
                       min_size=5, max_size=500, seed=42, threads=4,
                       outdir=None, verbose=False)
    except Exception as e:                                      # noqa: BLE001
        print(f"  失败: {type(e).__name__}: {str(e)[:120]}")
        return None
    res = r.res2d.copy()
    num = ["ES", "NES", "NOM p-val", "FDR q-val"]
    for c in num:
        if c in res:
            res[c] = pd.to_numeric(res[c], errors="coerce")
    res = res.sort_values("FDR q-val")
    cols = [c for c in ["Term", "ES", "NES", "NOM p-val", "FDR q-val", "Tag %"]
            if c in res]
    print(res[cols].head(20).to_string(index=False))
    res.to_csv(os.path.join(OUT, f"gsea_{tag}.csv"), index=False)
    return res


def run_ora(d, tag):
    import gseapy as gp
    up = d[(d["adj.P.Val"] < .05) & (d.logFC > 1)].symbol.tolist()
    dn = d[(d["adj.P.Val"] < .05) & (d.logFC < -1)].symbol.tolist()
    print(f"\n== ORA [{tag}] == 上调 {len(up)} / 下调 {len(dn)} 个基因")
    print("  (上下调必须分开做，混在一起会互相抵消)")
    out = {}
    for name, genes in (("up", up), ("down", dn)):
        if len(genes) < 5:
            print(f"  {name}: 基因太少({len(genes)})，跳过")
            continue
        try:
            e = gp.enrichr(gene_list=genes, gene_sets=ONLINE_LIBS,
                           organism="human", outdir=None)
            r = e.results.sort_values("Adjusted P-value")
            print(f"\n  --- {name} top10 ---")
            print(r[["Gene_set", "Term", "Adjusted P-value", "Overlap"]]
                  .head(10).to_string(index=False))
            r.to_csv(os.path.join(OUT, f"ora_{name}.csv"), index=False)
            out[name] = r
        except Exception as ex:                                 # noqa: BLE001
            print(f"  {name} 失败: {type(ex).__name__}: {str(ex)[:100]}")
    return out


def plot_gsea(res, tag):
    """NES 条形图。"""
    try:
        from plotnine import (aes, coord_flip, element_blank, element_text,
                              geom_col, ggplot, labs, scale_fill_manual, theme,
                              theme_bw)
    except ImportError:
        return
    r = res.dropna(subset=["NES"]).head(20).copy()
    if r.empty:
        return
    r["sig"] = (r["FDR q-val"] < .25).map({True: "FDR<0.25", False: "n.s."})
    r["Term"] = pd.Categorical(r.Term, categories=r.sort_values("NES").Term)
    p = (ggplot(r, aes("Term", "NES", fill="sig"))
         + geom_col()
         + coord_flip()
         + scale_fill_manual({"FDR<0.25": "#D55E00", "n.s.": "#CCCCCC"}, name="")
         + labs(title=f"GSEA NES ({tag})",
                subtitle="negative NES = down-regulated under Vemurafenib",
                x="", y="Normalized Enrichment Score")
         + theme_bw(9)
         + theme(panel_grid_minor=element_blank(),
                 axis_text_y=element_text(size=7),
                 plot_title=element_text(weight="bold"),
                 figure_size=(8, max(3, .35 * len(r)))))
    for ext in (".png", ".pdf"):
        p.save(os.path.join(FIG, f"fig09_gsea_{tag}{ext}"),
               dpi=300, verbose=False)
    print(f"  wrote fig09_gsea_{tag}.png / .pdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="只用内置基因集，不联网")
    ap.add_argument("--nperm", type=int, default=1000)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    try:
        import gseapy  # noqa: F401
    except ImportError:
        sys.exit("缺 gseapy，先装: pip install gseapy")

    rnk, d = load_ranking()
    summary = {}

    # 内置基因集：一定能跑，兼作流程自检
    res = run_gsea(rnk, BUILTIN_SETS, "builtin", a.nperm)
    if res is not None:
        plot_gsea(res, "builtin")
        summary["builtin"] = len(res)

    if not a.offline:
        res2 = run_gsea(rnk, ONLINE_LIBS[0], "hallmark", a.nperm)
        if res2 is not None:
            plot_gsea(res2, "hallmark")
            summary["hallmark"] = len(res2)
        else:
            print("\n  在线基因集不可达（网络受限），可加 --offline 跳过")
        run_ora(d, "enrichr")

    json.dump(summary, open(os.path.join(OUT, "enrichment_summary.json"), "w"),
              indent=2)
    print(f"\n05 完成 -> {OUT}")


if __name__ == "__main__":
    main()
