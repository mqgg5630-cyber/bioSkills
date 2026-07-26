#!/usr/bin/env bash
# GSE118767 单细胞聚类基准分析 —— 一键全流程
#   bash analysis/GSE118767/run_all.sh
# 依赖: conda create -n sc python=3.11 && conda activate sc
#       pip install scanpy leidenalg igraph scikit-image scikit-learn python-docx
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

$PY -c "import scanpy, leidenalg, skimage, sklearn" 2>/dev/null || {
  echo "缺依赖，请先执行："
  echo "  pip install scanpy leidenalg igraph scikit-image scikit-learn python-docx"
  exit 1; }

bash    "$HERE/scripts/01_fetch.sh"
$PY     "$HERE/scripts/02_qc_doublet.py"
$PY     "$HERE/scripts/03_cluster_benchmark.py"
$PY     "$HERE/scripts/04_markers.py"
$PY     "$HERE/scripts/05_figures.py"
$PY     "$HERE/scripts/06_make_docx.py" || echo "(docx 生成需 python-docx)"

echo
echo "结果: $HERE/results"
echo "图  : $HERE/figures"
echo "文档: $HERE/docs"
