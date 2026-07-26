#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 备用数据源：当 NCBI GEO 不可达（公司防火墙 / 国内网络 / CI 沙箱）时，
# 从 GitHub 上现成的仓库里稀疏检出一个真实的 RNA-seq counts 矩阵，
# 用来跑通 02/03 的 DESeq2 + ggplot2 流程。
#
# 默认拉 sanbomics 的 8 样本人类 counts 表（Ctr ×4 vs RS ×4，60663 基因）。
# 只下这一个文件（sparse-checkout + blob:none），不是整仓 35MB。
#
# 用法：
#   bash 00_fetch_offline_dataset.sh            # 默认 sanbomics
#   bash 00_fetch_offline_dataset.sh airway     # airway GSE52778 元数据
# ---------------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$HERE/data"
mkdir -p "$DATA"
WHICH="${1:-sanbomics}"

sparse_get() {  # repo, dest_dir, files...
  local repo="$1" dest="$2"; shift 2
  local tmp; tmp="$(mktemp -d)"
  git clone -q --depth 1 --filter=blob:none --sparse "$repo" "$tmp"
  ( cd "$tmp" && git sparse-checkout set --no-cone "$@" )
  for f in "$@"; do
    [[ -f "$tmp/${f#/}" ]] && cp "$tmp/${f#/}" "$dest/" && echo "  got $(basename "$f")"
  done
  rm -rf "$tmp"
}

case "$WHICH" in
  sanbomics)
    echo "[00] fetching sanbomics count table (8 samples, human) ..."
    sparse_get https://github.com/mousepixels/sanbomics_scripts.git "$DATA" \
      /count_table_for_deseq_example.csv
    ;;
  airway)
    echo "[00] fetching airway (GSE52778) run table ..."
    sparse_get https://github.com/jmzeng1314/GEO.git "$DATA" \
      /airway_RNAseq/SraRunTable.txt /GSE42872_main/GSE42872_series_matrix.txt.gz
    ;;
  *)
    echo "unknown dataset: $WHICH (use 'sanbomics' or 'airway')" >&2; exit 1 ;;
esac

echo "[00] done. files in $DATA:"
ls -lh "$DATA"
