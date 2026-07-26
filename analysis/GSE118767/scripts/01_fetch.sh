#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# GSE118767 / sc_mixology — 取真实 10x 单细胞原始 counts
#
# 数据来源：LuyiTian/sc_mixology (94★)，GEO 登录号 GSE118767
# 五个人肺腺癌细胞系（A549/H838/H2228/HCC827/H1975）等比例混合后
# 用 10x Chromium 建库。每个细胞的真实身份由 demuxlet 基于 SNP 判定，
# 构成客观 ground truth —— 这是本数据集最大的价值。
#
# 双通道：
#   A) GitHub 稀疏检出（默认，只拉 2 个文件约 14MB，不是整仓 377MB）
#   B) NCBI GEO（原始出处，作为备份说明）
# ---------------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$HERE/data"; mkdir -p "$DATA"

CNT="$DATA/sc_10x_5cl.count.csv.gz"
MET="$DATA/sc_10x_5cl.metadata.csv.gz"

if [[ -s "$CNT" && -s "$MET" ]]; then
  echo "[01] 已存在，跳过下载"
  gzip -t "$CNT" && gzip -t "$MET" && echo "[01] gzip 完整性 OK"
  ls -lh "$DATA"; exit 0
fi

echo "[01] 从 GitHub 稀疏检出 sc_mixology 数据 ..."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone -q --depth 1 --filter=blob:none --sparse \
  https://github.com/LuyiTian/sc_mixology.git "$TMP"
( cd "$TMP" && git sparse-checkout set --no-cone \
    /data/csv/sc_10x_5cl.count.csv.gz \
    /data/csv/sc_10x_5cl.metadata.csv.gz )

cp "$TMP/data/csv/sc_10x_5cl.count.csv.gz"    "$DATA/"
cp "$TMP/data/csv/sc_10x_5cl.metadata.csv.gz" "$DATA/"

gzip -t "$CNT" && gzip -t "$MET" && echo "[01] gzip 完整性 OK"
echo "[01] 完成："
ls -lh "$DATA"

cat <<'NOTE'

[01] 说明：
  原始数据也可从 NCBI GEO 获取（GSE118767），但那里是 scPipe 处理前的
  fastq/bam。本流程使用仓库提供的 scPipe 输出 counts 矩阵，
  与论文所用数据完全一致。
NOTE
