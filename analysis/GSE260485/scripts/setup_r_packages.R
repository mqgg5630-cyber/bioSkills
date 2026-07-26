#!/usr/bin/env Rscript
# One-time dependency install for the GSE260485 pipeline.
cran <- c("ggplot2", "dplyr", "tidyr", "ggrepel", "patchwork",
          "scales", "matrixStats", "ashr", "viridisLite", "BiocManager")
missing <- cran[!cran %in% rownames(installed.packages())]
if (length(missing)) install.packages(missing, repos = "https://cloud.r-project.org")

if (!requireNamespace("DESeq2", quietly = TRUE)) BiocManager::install("DESeq2", ask = FALSE)

for (p in c(cran, "DESeq2")) {
  cat(sprintf("%-14s %s\n", p, as.character(packageVersion(p))))
}
