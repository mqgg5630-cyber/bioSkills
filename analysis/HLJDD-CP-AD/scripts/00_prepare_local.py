#!/usr/bin/env python3
"""
【在你本地 WSL 运行】GSE157827 预处理 —— 把 1.2 GB 压到 <100 MB

为什么要这一步
--------------
GSE157827_RAW.tar 是 1.2 GB，超过 GitHub LFS 免费额度（1 GB 存储 / 1 GB 月流量），
而且上传 + 下载会消耗 2.4 GB 流量。

但原始数据里绝大部分是稀疏零值和低表达基因。做完 QC 与高变基因筛选后，
分析所需的信息可以压缩到 100 MB 以内，无需 LFS，普通 git 就能传。

本脚本做的事（全部是标准 QC，不丢关键信息）：
  1. 逐样本读入 10x 三件套，加样本名前缀避免 barcode 冲突
  2. 基础 QC：过滤低质量核、高线粒体比例
  3. 合并 21 个样本 → 一个 AnnData
  4. 保留 counts 层 + 高变基因子集
  5. 存成压缩 h5ad

用法（在 WSL 里）：
    # 1. 解压 tar
    mkdir -p ~/gse157827 && cd ~/gse157827
    tar -xf /mnt/e/0wangyao/wangyao/raw/1/GSE157827/GSE157827_RAW.tar

    # 2. 跑本脚本
    python 00_prepare_local.py ~/gse157827

    # 3. 产物 gse157827_prepared.h5ad 复制到仓库并提交
"""
import argparse
import glob
import gzip
import os
import re
import sys

import numpy as np
import pandas as pd

try:
    import scanpy as sc
    import anndata as ad
    from scipy import sparse
except ImportError:
    sys.exit("缺依赖，请先: pip install scanpy anndata scipy")

sc.settings.verbosity = 1

# QC 阈值（保守设置，宁可多留也不误删）
MIN_GENES = 200        # 每个核至少检出的基因数
MIN_CELLS = 3          # 每个基因至少在几个核中表达
MAX_MT_PCT = 20.0      # 线粒体比例上限
N_HVG = 4000           # 保留的高变基因数（比常规 2000 多留一些余量）


def find_samples(root):
    """在解压目录里找出所有样本的三件套。

    GEO 的命名通常是:
        GSM4775561_AD1_barcodes.tsv.gz
        GSM4775561_AD1_features.tsv.gz
        GSM4775561_AD1_matrix.mtx.gz
    """
    mtx = sorted(glob.glob(os.path.join(root, "**", "*matrix.mtx*"), recursive=True))
    if not mtx:
        sys.exit(f"在 {root} 下没找到 *matrix.mtx*，确认 tar 解压对了没")

    samples = []
    for m in mtx:
        d = os.path.dirname(m)
        base = os.path.basename(m)
        # 去掉 matrix.mtx.gz 得到前缀，如 GSM4775561_AD1_
        prefix = re.sub(r"matrix\.mtx(\.gz)?$", "", base)

        def find_partner(kind):
            for pat in (f"{prefix}{kind}.tsv.gz", f"{prefix}{kind}.tsv",
                        f"{prefix}{kind}s.tsv.gz", f"{prefix}{kind}s.tsv"):
                p = os.path.join(d, pat)
                if os.path.exists(p):
                    return p
            # 退一步：同目录下任意匹配
            c = glob.glob(os.path.join(d, f"{prefix}*{kind}*"))
            return c[0] if c else None

        bc = find_partner("barcode")
        ft = find_partner("feature") or find_partner("gene")
        if not (bc and ft):
            print(f"  ! 跳过 {base}（找不到配套 barcodes/features）")
            continue

        # 样本名：GSM4775561_AD1_ -> AD1
        name = prefix.rstrip("_")
        mm = re.match(r"GSM\d+[_-](.+)$", name)
        sample = mm.group(1) if mm else name
        samples.append({"sample": sample, "mtx": m, "bc": bc, "ft": ft})
    return samples


def read_one(s):
    """读单个样本的 10x 三件套。"""
    opener = gzip.open if s["mtx"].endswith(".gz") else open
    from scipy.io import mmread
    with opener(s["mtx"], "rb") as f:
        X = mmread(f).T.tocsr()          # mtx 是 gene x cell，转成 cell x gene

    bc = pd.read_csv(s["bc"], header=None, sep="\t")[0].astype(str).values
    ft = pd.read_csv(s["ft"], header=None, sep="\t")
    # features 通常 3 列: ensembl_id, symbol, type；取第 2 列 symbol
    genes = ft[1].astype(str).values if ft.shape[1] > 1 else ft[0].astype(str).values

    if X.shape != (len(bc), len(genes)):
        raise ValueError(f"{s['sample']} 维度不符: X={X.shape} "
                         f"barcodes={len(bc)} genes={len(genes)}")

    a = ad.AnnData(X=X.astype(np.float32))
    a.obs_names = [f"{s['sample']}_{b}" for b in bc]   # 加前缀防冲突
    a.var_names = genes
    a.var_names_make_unique()
    a.obs["sample"] = s["sample"]
    # AD1/AD2... -> AD;  NC3/NC7... -> NC
    a.obs["group"] = "AD" if s["sample"].upper().startswith("AD") else "NC"
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indir", help="GSE157827_RAW.tar 的解压目录")
    ap.add_argument("-o", "--out", default="gse157827_prepared.h5ad")
    ap.add_argument("--n-hvg", type=int, default=N_HVG)
    args = ap.parse_args()

    print("== 1. 扫描样本 ==")
    samples = find_samples(args.indir)
    print(f"找到 {len(samples)} 个样本: {[s['sample'] for s in samples]}")
    if not samples:
        sys.exit("没有可用样本")

    print("\n== 2. 逐样本读入并 QC ==")
    parts, stats = [], []
    for i, s in enumerate(samples, 1):
        a = read_one(s)
        n0 = a.n_obs
        a.var["mt"] = a.var_names.str.upper().str.startswith("MT-")
        sc.pp.calculate_qc_metrics(a, qc_vars=["mt"], inplace=True,
                                   percent_top=None, log1p=False)
        grp = "AD" if s["sample"].upper().startswith("AD") else "NC"
        a = a[(a.obs.n_genes_by_counts >= MIN_GENES) &
              (a.obs.pct_counts_mt < MAX_MT_PCT)].copy()
        stats.append({"sample": s["sample"], "group": grp,
                      "cells_raw": n0, "cells_qc": a.n_obs,
                      "median_genes": float(np.median(a.obs.n_genes_by_counts))
                      if a.n_obs else 0.0,
                      "median_umi": float(np.median(a.obs.total_counts))
                      if a.n_obs else 0.0})
        print(f"  [{i:2d}/{len(samples)}] {s['sample']:<6} "
              f"{n0:>7} -> {a.n_obs:>7} 核")
        if a.n_obs == 0:
            print(f"      ! {s['sample']} QC 后无细胞剩余，已跳过。"
                  f"若多数样本如此，请放宽 MIN_GENES / MAX_MT_PCT")
            continue
        parts.append(a)

    print("\n== 3. 合并 ==")
    if not parts:
        sys.exit("所有样本 QC 后都没有细胞剩余。请检查数据或放宽 QC 阈值：\n"
                 f"  当前 MIN_GENES={MIN_GENES}, MAX_MT_PCT={MAX_MT_PCT}")
    A = ad.concat(parts, join="outer", index_unique=None)
    del parts
    A.obs["group"] = A.obs["group"].astype("category")
    A.obs["sample"] = A.obs["sample"].astype("category")
    print(f"合并后: {A.n_obs:,} 核 x {A.n_vars:,} 基因")
    print(f"分组: {A.obs.group.value_counts().to_dict()}")

    sc.pp.filter_genes(A, min_cells=MIN_CELLS)
    print(f"基因过滤后: {A.n_vars:,}")

    print("\n== 4. 归一化 + 高变基因 ==")
    A.layers["counts"] = A.X.copy()
    sc.pp.normalize_total(A, target_sum=1e4)
    sc.pp.log1p(A)
    n_hvg = min(args.n_hvg, A.n_vars - 1)
    try:
        sc.pp.highly_variable_genes(A, n_top_genes=n_hvg, batch_key="sample")
    except Exception as e:
        print(f"  (batch_key 模式失败: {type(e).__name__}，改用全局模式)")
        sc.pp.highly_variable_genes(A, n_top_genes=n_hvg)

    # cGAS-STING 与小胶质细胞标记基因必须保留，即使不在 HVG 里
    keep_extra = [
        # cGAS-STING 通路
        "CGAS", "MB21D1", "TMEM173", "STING1", "TBK1", "IRF3", "IKBKE",
        "IFI16", "TREX1", "ENPP1", "NFKB1", "RELA", "IFNB1", "IFNA1",
        "ISG15", "IFIT1", "IFIT3", "MX1", "OAS1", "STAT1", "IRF7", "CXCL10",
        # 小胶质细胞
        "P2RY12", "TMEM119", "CX3CR1", "CSF1R", "AIF1", "ITGAM", "PTPRC",
        "TREM2", "TYROBP", "APOE", "CST7", "SPP1", "CD68", "CD74",
        # 其他主要细胞类型标记
        "SNAP25", "RBFOX3", "SYT1", "SLC17A7", "GAD1", "GAD2",       # 神经元
        "AQP4", "GFAP", "SLC1A2", "ALDH1L1",                          # 星形胶质
        "PLP1", "MBP", "MOG", "MOBP",                                 # 少突胶质
        "PDGFRA", "CSPG4", "VCAN",                                    # OPC
        "CLDN5", "FLT1", "PECAM1", "VWF", "EGFL7", "B2M", "HLA-E",   # 内皮
        # 炎症
        "IL1B", "IL6", "TNF", "NLRP3", "CCL2", "CCL3", "CCL4",
    ]
    extra = [g for g in keep_extra if g in A.var_names]
    A.var["keep"] = A.var["highly_variable"].copy()
    A.var.loc[extra, "keep"] = True
    print(f"HVG {int(A.var.highly_variable.sum())} + "
          f"强制保留标记基因 {len(extra)} -> 共 {int(A.var.keep.sum())}")

    print("\n== 5. 裁剪并保存 ==")
    B = A[:, A.var["keep"]].copy()
    B.X = B.layers["counts"].copy()      # 只留 counts，log 值可在下游重算
    del B.layers["counts"]
    if not sparse.issparse(B.X):
        B.X = sparse.csr_matrix(B.X)
    B.X = B.X.astype(np.float32)
    # 精简 obs，去掉一堆 QC 中间列
    B.obs = B.obs[["sample", "group", "n_genes_by_counts",
                   "total_counts", "pct_counts_mt"]].copy()
    B.var = B.var[["highly_variable"]].copy()

    B.write(args.out, compression="gzip")
    sz = os.path.getsize(args.out) / 1024**2
    print(f"\n已保存: {args.out}  ({sz:.0f} MB)")
    print(f"  {B.n_obs:,} 核 x {B.n_vars:,} 基因")

    pd.DataFrame(stats).to_csv("gse157827_qc_per_sample.csv", index=False)
    print("  逐样本 QC: gse157827_qc_per_sample.csv")

    if sz > 95:
        print(f"\n⚠ 超过 95 MB，接近 GitHub 单文件 100 MB 上限。")
        print(f"  建议减少高变基因数重跑：")
        print(f"    python {os.path.basename(__file__)} {args.indir} --n-hvg 2000")
    else:
        print(f"\n✓ 体积合适，可直接 git 提交（无需 LFS）")


if __name__ == "__main__":
    main()
