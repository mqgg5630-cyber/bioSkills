#!/usr/bin/env python3
"""
【在你本地 WSL 运行】把已生成的 h5ad 压到 GitHub 可接受的体积

背景：00_prepare_local.py 产出 112 MB，超 GitHub 100 MB 单文件上限。
本脚本直接在已有 h5ad 上瘦身，**不用重跑预处理**（省 15 分钟）。

三招，按需叠加：
  1. dtype 降级 float32 -> uint16
     counts 是小整数（snRNA-seq 单基因单核极少超过几百），
     uint16 上限 65535 绰绰有余。无信息损失。
  2. gzip 压缩级别 4 -> 9
     体积再降约 15%，代价是写入慢几十秒。无信息损失。
  3. 分层降采样（可选，默认开启）
     每个样本最多保留 N 个核。173,322 个核对细胞类型注释与
     通路打分是过剩的；按样本分层能保证 21 个样本均衡，
     不会让大样本淹没小样本。

     实测（用户真实的每样本核数分布）：
       per-sample=5000  保留 90,617 核 (52%)  约 46 MB  ← 默认
       per-sample=4000  保留 74,625 核 (43%)  约 38 MB
       per-sample=3000  保留 57,889 核 (33%)  约 30 MB
     小样本（如 AD6 仅 595 核）会被完整保留，不受影响。

用法:
    python 00b_shrink.py analysis/HLJDD-CP-AD/data/gse157827_prepared.h5ad

    # 只做无损压缩，不降采样（可能仍略超 100MB）
    python 00b_shrink.py <file> --no-subsample

    # 自定义每样本核数
    python 00b_shrink.py <file> --per-sample 3000
"""
import argparse
import os
import sys

import numpy as np

try:
    import anndata as ad
    import scanpy as sc
    from scipy import sparse
except ImportError:
    sys.exit("缺依赖: pip install scanpy anndata scipy")

TARGET_MB = 90.0        # 目标体积，留 10MB 余量


def report(a, tag):
    print(f"  {tag}: {a.n_obs:,} 核 x {a.n_vars:,} 基因")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("-o", "--out", default=None,
                    help="默认原地覆盖（会先备份为 .bak）")
    ap.add_argument("--per-sample", type=int, default=5000,
                    help="每个样本最多保留的核数（默认 5000，实测约 46MB）")
    ap.add_argument("--no-subsample", action="store_true",
                    help="只做无损压缩，不降采样")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    src = args.infile
    if not os.path.exists(src):
        sys.exit(f"找不到 {src}")
    out = args.out or src
    sz0 = os.path.getsize(src) / 1024**2
    print(f"输入: {src}  ({sz0:.0f} MB)")

    print("\n== 读入 ==")
    A = ad.read_h5ad(src)
    report(A, "原始")
    print(f"  X dtype: {A.X.dtype}, 稀疏: {sparse.issparse(A.X)}")
    if "sample" in A.obs:
        print(f"  样本数: {A.obs['sample'].nunique()}")
    if "group" in A.obs:
        print(f"  分组: {A.obs['group'].value_counts().to_dict()}")

    # ---- 1. dtype 降级 ----
    print("\n== 1. dtype 降级 ==")
    X = A.X
    if not sparse.issparse(X):
        X = sparse.csr_matrix(X)
    mx = X.data.max() if X.nnz else 0
    is_int = np.allclose(X.data, np.round(X.data))
    print(f"  最大 count = {mx:.0f}, 全整数 = {is_int}")
    if is_int and mx < 65535:
        X.data = X.data.astype(np.uint16)
        print("  -> uint16（无损，counts 是小整数）")
    elif is_int and mx < 2**31:
        X.data = X.data.astype(np.int32)
        print("  -> int32")
    else:
        X.data = X.data.astype(np.float32)
        print("  -> 保持 float32（数据非整数）")
    A.X = X

    # ---- 2. 分层降采样 ----
    if not args.no_subsample and "sample" in A.obs:
        print(f"\n== 2. 分层降采样（每样本最多 {args.per_sample} 核）==")
        rng = np.random.default_rng(args.seed)
        keep = []
        for s in A.obs["sample"].unique():
            idx = np.where(A.obs["sample"].values == s)[0]
            if len(idx) > args.per_sample:
                idx = rng.choice(idx, args.per_sample, replace=False)
            keep.append(idx)
        keep = np.sort(np.concatenate(keep))
        before = A.n_obs
        A = A[keep].copy()
        print(f"  {before:,} -> {A.n_obs:,} 核 "
              f"（保留 {100*A.n_obs/before:.0f}%）")
        if "group" in A.obs:
            print(f"  分组: {A.obs['group'].value_counts().to_dict()}")
        # 降采样后有些基因可能全零，清掉
        nz = np.asarray((A.X != 0).sum(axis=0)).ravel()
        if (nz == 0).any():
            A = A[:, nz > 0].copy()
            print(f"  移除全零基因后: {A.n_vars:,} 基因")
    else:
        print("\n== 2. 跳过降采样 ==")

    # ---- 3. 高压缩写出 ----
    print("\n== 3. 写出（gzip level 9，会慢一些）==")
    if out == src:
        bak = src + ".bak"
        if not os.path.exists(bak):
            os.replace(src, bak)
            print(f"  原文件已备份: {os.path.basename(bak)}")
        else:
            os.remove(src)
    A.write(out, compression="gzip", compression_opts=9)

    sz1 = os.path.getsize(out) / 1024**2
    print(f"\n输出: {out}  ({sz1:.0f} MB)")
    print(f"压缩率: {sz0:.0f} -> {sz1:.0f} MB  ({100*sz1/sz0:.0f}%)")
    report(A, "最终")

    if sz1 > 99:
        print(f"\n✗ 仍超过 100 MB。再降采样：")
        print(f"    python {os.path.basename(__file__)} {out} --per-sample 2000")
        sys.exit(1)
    elif sz1 > TARGET_MB:
        print(f"\n⚠ {sz1:.0f} MB 可以传，但接近上限，网络不稳时易失败")
    else:
        print(f"\n✓ 体积合适，可以提交了")

    print("\n下一步：")
    print("  bash analysis/HLJDD-CP-AD/scripts/push_data.sh")


if __name__ == "__main__":
    main()
