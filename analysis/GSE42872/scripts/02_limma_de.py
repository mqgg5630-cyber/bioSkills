#!/usr/bin/env python3
"""
GSE42872 — 解析 GEO series matrix -> limma 风格 moderated t 检验 -> 结果表

为什么用 limma 而不是 DESeq2
---------------------------------
GSE42872 是 Affymetrix GPL6244 芯片，series matrix 里是 **RMA 归一化后的
log2 荧光强度**（实测值域 2.67 ~ 14.56），是连续型数据。
DESeq2/edgeR 的负二项模型是给**整数 counts** 用的，喂 log2 强度值在统计上是错的。
芯片数据的正解是 limma 的 lmFit + eBayes（Smyth 2004）。

本脚本用 numpy/scipy 复刻了 limma 的经验贝叶斯方差收缩，
并与原作者用真 R/limma 跑出的结果做交叉验证（见 03 脚本输出）。

Skills: database-access/geo-data, expression-matrix/counts-ingest,
        differential-expression/de-results
"""
import gzip, io, json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from limma_py import lmfit_ebayes, bh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
os.makedirs(RES, exist_ok=True)
MATRIX = os.path.join(DATA, "GSE42872_series_matrix.txt.gz")

# ---------------------------------------------------------------- 1. 解析 GEO
print("== 1. 解析 series matrix ==========================================")
meta, rows, in_table = {}, [], False
with gzip.open(MATRIX, "rt", encoding="utf-8", errors="replace") as f:
    for line in f:
        if line.startswith("!series_matrix_table_begin"):
            in_table = True; continue
        if line.startswith("!series_matrix_table_end"):
            break
        if in_table:
            rows.append(line)
        elif line.startswith("!"):
            k, _, v = line[1:].rstrip("\n").partition("\t")
            meta.setdefault(k, []).append([x.strip('"') for x in v.split("\t")])

expr = pd.read_csv(io.StringIO("".join(rows)), sep="\t", index_col=0)
expr.index = expr.index.astype(str)
print(f"表达矩阵: {expr.shape[0]} 探针 x {expr.shape[1]} 样本")
print(f"值域: {expr.values.min():.2f} ~ {expr.values.max():.2f}  (log2 RMA)")

title = meta["Series_title"][0][0]
print(f"研究: {title}")

# ---------------------------------------------------------------- 2. 样本表
print("\n== 2. 构建样本表 ==================================================")
gsm    = meta["Sample_geo_accession"][0]
titles = meta["Sample_title"][0]
group  = ["Vemurafenib" if "Vemurafenib" in t else "Control" for t in titles]
rep    = [int(t.rstrip()[-1]) for t in titles]
coldata = pd.DataFrame({"gsm": gsm, "title": titles, "group": group, "replicate": rep})
coldata = coldata.set_index("gsm").loc[expr.columns]
coldata.index.name = "gsm"
print(coldata.to_string())
coldata.to_csv(os.path.join(RES, "sample_metadata.csv"))

# ------------------------------------------------------- 3. 探针 -> 基因符号
print("\n== 3. 探针注释 ====================================================")
from annotate import annotate
symbol, annot_source = annotate(expr, DATA)

# ---------------------------------------------------------------- 4. limma
print("\n== 4. limma lmFit + eBayes ========================================")
fit = lmfit_ebayes(expr.values, coldata["group"].values, "Control", "Vemurafenib")
print(f"经验贝叶斯先验: s0^2 = {fit['s02']:.5f}, d0 = {fit['d0']:.3f}")
print(f"残差自由度 {len(coldata)-2} -> 收缩后总自由度 {fit['df_total']:.2f}")

res = pd.DataFrame({
    "probe":   expr.index,
    "symbol":  symbol.values,
    "logFC":   fit["logFC"],        # Vemurafenib - Control
    "AveExpr": fit["AveExpr"],
    "t":       fit["t"],
    "P.Value": fit["P_Value"],
})
res["adj.P.Val"] = bh(res["P.Value"].values)
res = res.sort_values("P.Value").reset_index(drop=True)

LFC, FDR = 1.0, 0.05
res["direction"] = np.where((res["adj.P.Val"] < FDR) & (res.logFC >  LFC), "Up",
                    np.where((res["adj.P.Val"] < FDR) & (res.logFC < -LFC), "Down", "n.s."))

n_up   = (res.direction == "Up").sum()
n_down = (res.direction == "Down").sum()
print(f"\npadj<0.05           : {(res['adj.P.Val']<FDR).sum()}")
print(f"padj<0.05 & |LFC|>1 : {n_up+n_down}  (up {n_up} / down {n_down})")

res.to_csv(os.path.join(RES, "DE_Vemurafenib_vs_Control.csv"), index=False)
res[res.direction != "n.s."].to_csv(os.path.join(RES, "DE_significant.csv"), index=False)

print("\n=== Top 20 ===")
print(res.head(20)[["probe","symbol","logFC","t","adj.P.Val","direction"]].to_string(index=False))

# 归一化矩阵也存一份，画图用
out = expr.copy(); out.insert(0, "symbol", symbol.values)
out.index.name = "probe"
out.to_csv(os.path.join(RES, "expression_matrix.csv.gz"))

json.dump({
    "accession": "GSE42872", "title": title, "platform": meta["Series_platform_id"][0][0],
    "n_probes": int(expr.shape[0]), "n_samples": int(expr.shape[1]),
    "method": "limma lmFit + eBayes (numpy/scipy reimplementation)",
    "annotation_source": annot_source,
    "n_annotated": int(pd.notna(symbol).sum()),
    "prior_s02": float(fit["s02"]), "prior_df0": float(fit["d0"]),
    "n_padj05": int((res["adj.P.Val"] < FDR).sum()), "n_up": int(n_up), "n_down": int(n_down),
}, open(os.path.join(RES, "run_summary.json"), "w"), indent=2)
print("\n02 完成 ->", RES)
