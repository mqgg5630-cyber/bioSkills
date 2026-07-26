#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# R + Bioconductor 环境（WSL Ubuntu / Debian）
#
# 你报的错：
#   Rscript: command not found, but can be installed with: sudo apt install r-base-core
# 说明系统完全没有 R。下面二选一。
#
#   方式 1（推荐，你已经有 conda）：conda 装，不需要 sudo，不污染系统
#   方式 2：apt 装系统级 R，需要 sudo
# ---------------------------------------------------------------------------
set -euo pipefail
METHOD="${1:-conda}"

case "$METHOD" in
conda)
  command -v conda >/dev/null || { echo "没找到 conda，改用: bash setup_r.sh apt"; exit 1; }
  echo "[*] conda 创建 R 环境 bioskills-r ..."
  # conda-forge 的 r-base + bioconda 的 Bioconductor 包
  conda create -y -n bioskills-r -c conda-forge -c bioconda \
    r-base=4.3 \
    r-ggplot2 r-dplyr r-tidyr r-ggrepel r-patchwork r-scales r-matrixstats r-ashr \
    bioconductor-limma bioconductor-deseq2 bioconductor-geoquery \
    bioconductor-hugene10sttranscriptcluster.db
  echo
  echo "完成。用之前： conda activate bioskills-r"
  echo "然后：        Rscript analysis/GSE42872/scripts/02_limma_de.R"
  ;;

apt)
  echo "[*] apt 安装系统级 R（需要 sudo）..."
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    r-base r-base-dev \
    libcurl4-openssl-dev libssl-dev libxml2-dev \
    libfontconfig1-dev libharfbuzz-dev libfribidi-dev \
    libfreetype6-dev libpng-dev libtiff5-dev libjpeg-dev libcairo2-dev
  echo "[*] 安装 R 包（编译较慢，10-30 分钟）..."
  sudo Rscript -e '
    options(repos = c(CRAN = "https://cloud.r-project.org"))
    install.packages(c("BiocManager","ggplot2","dplyr","tidyr","ggrepel",
                       "patchwork","scales","matrixStats","ashr"), Ncpus = parallel::detectCores())
    BiocManager::install(c("limma","DESeq2","GEOquery","hugene10sttranscriptcluster.db"),
                         ask = FALSE, update = FALSE)
  '
  ;;
*)
  echo "用法: bash setup_r.sh [conda|apt]" >&2; exit 1 ;;
esac

echo
echo "[*] 核对："
Rscript -e 'for (p in c("ggplot2","limma","DESeq2","GEOquery")) {
  v <- tryCatch(as.character(packageVersion(p)), error=function(e) "未安装")
  cat(sprintf("  %-10s %s\n", p, v)) }'
