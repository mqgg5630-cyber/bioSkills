#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# GSE42872 取数。两条路，自动择优：
#   A) 直连 NCBI GEO（正统做法，需要能访问 ftp.ncbi.nlm.nih.gov）
#   B) 从 GitHub 的 jmzeng1314/GEO 稀疏检出同一个 series_matrix（镜像兜底）
#
# GSE42872: A375 黑色素瘤细胞 + 维罗非尼(vemurafenib) vs DMSO, 3v3
# 平台 GPL6244 = Affymetrix Human Gene 1.0 ST，RMA 归一化的 log2 强度值
# ---------------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$HERE/data"; mkdir -p "$DATA"
MATRIX="$DATA/GSE42872_series_matrix.txt.gz"

fetch_annot() {   # NCBI 官方 GPL6244 探针注释（带 Gene symbol）
  local a="$DATA/GPL6244.annot.gz"
  [[ -s "$a" ]] && return 0
  echo "[01] 顺带取官方平台注释 GPL6244.annot.gz ..."
  curl -fL --retry 3 --connect-timeout 20 -o "$a" \
    "https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL6nnn/GPL6244/annot/GPL6244.annot.gz" \
    2>/dev/null && gzip -t "$a" 2>/dev/null \
    && echo "[01] 注释 OK" || { rm -f "$a"; echo "[01] 注释拿不到（不影响主流程）"; }
}

if [[ -s "$MATRIX" ]]; then
  echo "[01] 已存在: $MATRIX"; gzip -t "$MATRIX" && echo "[01] gzip OK"
  fetch_annot
  exit 0
fi

echo "[01] 方式 A: 直连 NCBI GEO ..."
URL="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE42nnn/GSE42872/matrix/GSE42872_series_matrix.txt.gz"
if curl -fL --retry 3 --retry-delay 3 --connect-timeout 20 -o "$MATRIX" "$URL" 2>/dev/null && gzip -t "$MATRIX" 2>/dev/null; then
  echo "[01] NCBI 下载成功"
  fetch_annot
else
  echo "[01] NCBI 不可达，转方式 B: GitHub 镜像稀疏检出 ..."
  rm -f "$MATRIX"
  TMP="$(mktemp -d)"
  git clone -q --depth 1 --filter=blob:none --sparse https://github.com/jmzeng1314/GEO.git "$TMP"
  ( cd "$TMP" && git sparse-checkout set --no-cone \
      /GSE42872_main/GSE42872_series_matrix.txt.gz /GSE42872_main/anno_DEG.Rdata )
  cp "$TMP/GSE42872_main/GSE42872_series_matrix.txt.gz" "$DATA/"
  # 作者用 R/limma 跑出的结果，本流程用它做 (a) 探针注释 (b) 交叉验证
  cp "$TMP/GSE42872_main/anno_DEG.Rdata" "$DATA/" 2>/dev/null || true
  rm -rf "$TMP"
  echo "[01] 镜像获取成功"
fi

gzip -t "$MATRIX" && echo "[01] gzip 完整性 OK"
ls -lh "$DATA"
