#!/usr/bin/env bash
# Run the whole GSE260485 pipeline locally.
#   bash analysis/GSE260485/run_all.sh
# Requires R >= 4.3 with: DESeq2, ashr, ggplot2, dplyr, tidyr, ggrepel,
# patchwork, scales, matrixStats  (see setup_r_packages.R)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash    "$HERE/scripts/01_download.sh"
Rscript "$HERE/scripts/02_deseq2.R"
Rscript "$HERE/scripts/03_ggplot_figures.R"

echo
echo "Results : $HERE/results"
echo "Figures : $HERE/figures"
