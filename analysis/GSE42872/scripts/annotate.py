#!/usr/bin/env python3
"""
GPL6244 探针 -> 基因符号 注释。三级降级，按优先级自动选：

  1. NCBI 官方 GPL6244.annot.gz         <- 最好，权威，带 Gene symbol / Gene ID
  2. GitHub 镜像的 anno_DEG.Rdata       <- 兜底，靠 AveExpr 反查（有歧义）
  3. 全部为空                            <- 下游按探针 ID 出图，不崩

抽成独立模块，是因为 01_fetch.sh 走 NCBI 分支时不会下 anno_DEG.Rdata，
导致注释缺失（这正是 fig06 报空距离矩阵的根因）。
"""
import gzip
import io
import os
import urllib.request

import pandas as pd

ANNOT_URL = ("https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL6nnn/"
             "GPL6244/annot/GPL6244.annot.gz")


def fetch_ncbi_annot(data_dir, timeout=60):
    """下载并解析 NCBI 官方平台注释，返回 {probe_id: symbol}。失败返回 None。"""
    local = os.path.join(data_dir, "GPL6244.annot.gz")
    if not os.path.exists(local):
        try:
            print(f"  下载官方注释 {ANNOT_URL} ...")
            req = urllib.request.Request(
                ANNOT_URL, headers={"User-Agent": "Mozilla/5.0 (bioSkills)"})
            with urllib.request.urlopen(req, timeout=timeout) as r, \
                 open(local, "wb") as f:
                f.write(r.read())
        except Exception as e:                                  # noqa: BLE001
            print(f"  官方注释下载失败: {type(e).__name__}: {e}")
            return None

    try:
        rows, started = [], False
        with gzip.open(local, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("!platform_table_begin"):
                    started = True
                    continue
                if line.startswith("!platform_table_end"):
                    break
                if started:
                    rows.append(line)
        if not rows:
            print("  注释文件里没找到 platform_table")
            return None

        tab = pd.read_csv(io.StringIO("".join(rows)), sep="\t",
                          dtype=str, low_memory=False)
        if "Gene symbol" not in tab.columns:
            print(f"  注释表缺 'Gene symbol' 列，实际列: {list(tab.columns)[:6]}")
            return None

        tab = tab[["ID", "Gene symbol"]].dropna()
        # 一个探针可能对多个基因（用 /// 分隔），取第一个
        tab["Gene symbol"] = tab["Gene symbol"].str.split("///").str[0].str.strip()
        tab = tab[tab["Gene symbol"] != ""]
        return dict(zip(tab["ID"].astype(str), tab["Gene symbol"]))
    except Exception as e:                                      # noqa: BLE001
        print(f"  解析官方注释出错: {type(e).__name__}: {e}")
        return None


def fetch_rdata_annot(data_dir, expr):
    """兜底：从作者的 anno_DEG.Rdata 靠 AveExpr 唯一匹配反查。"""
    path = os.path.join(data_dir, "anno_DEG.Rdata")
    if not os.path.exists(path):
        return None
    try:
        import pyreadr
        ref = pyreadr.read_r(path)["DEG"]
    except Exception as e:                                      # noqa: BLE001
        print(f"  读 anno_DEG.Rdata 失败: {type(e).__name__}: {e}")
        return None

    ave, lut = expr.mean(axis=1).round(5), {}
    for p, v in ave.items():
        lut.setdefault(v, []).append(p)
    out = {}
    for _, r in ref.iterrows():
        cand = lut.get(round(r["AveExpr"], 5), [])
        if len(cand) == 1:                       # 只接受唯一匹配，避免配错
            out[str(cand[0])] = r["symbol"]
    return out or None


def annotate(expr, data_dir):
    """返回 (symbol_series, source_str)。symbol_series 与 expr.index 对齐。"""
    print("探针注释:")

    m = fetch_ncbi_annot(data_dir)
    if m:
        s = pd.Series({p: m.get(str(p)) for p in expr.index}, dtype=object)
        n = s.notna().sum()
        if n > 0:
            print(f"  [来源] NCBI 官方 GPL6244.annot -> {n}/{len(expr)} 个探针有 symbol")
            return s.reindex(expr.index), "NCBI GPL6244.annot"

    m = fetch_rdata_annot(data_dir, expr)
    if m:
        s = pd.Series({p: m.get(str(p)) for p in expr.index}, dtype=object)
        n = s.notna().sum()
        print(f"  [来源] anno_DEG.Rdata 反查 -> {n}/{len(expr)} 个探针有 symbol")
        print("  注：AveExpr 反查存在少量匹配歧义，官方注释可用时优先用官方的")
        return s.reindex(expr.index), "anno_DEG.Rdata (AveExpr 反查)"

    print("  [来源] 无可用注释，结果以探针 ID 输出")
    return pd.Series(index=expr.index, dtype=object), "none"
