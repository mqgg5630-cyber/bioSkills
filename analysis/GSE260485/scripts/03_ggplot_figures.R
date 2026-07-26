#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# GSE260485 - publication-style ggplot2 figures
# Skills used:
#   data-visualization/ggplot2-fundamentals    (theme, grammar, saving)
#   data-visualization/volcano-and-ma-plots    (shrunken LFC on x, padj on y)
#   data-visualization/dimensionality-reduction-plots (PCA on VST, % variance)
#   data-visualization/heatmaps-clustering     (z-score rows, diverging palette)
#   data-visualization/color-palettes          (colorblind-safe Okabe-Ito)
#   data-visualization/multipanel-figures      (patchwork composite)
#
# Figures written to ../figures as both PNG (300 dpi) and PDF (vector).
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(ggrepel)
  library(patchwork)
  library(DESeq2)
  library(matrixStats)
  library(scales)
})

root    <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])), ".."))
res_dir <- file.path(root, "results")
fig_dir <- file.path(root, "figures")
dir.create(fig_dir, showWarnings = FALSE, recursive = TRUE)

obj       <- readRDS(file.path(res_dir, "deseq2_objects.rds"))
dds       <- obj$dds; vsd <- obj$vsd; gene_anno <- obj$gene_anno; coldata <- obj$coldata

# --- shared aesthetics ------------------------------------------------------
# Okabe-Ito colorblind-safe palette (color-palettes skill)
cond_cols <- c(Control        = "#999999",
               TMX            = "#0072B2",
               Fasting        = "#E69F00",
               TMXplusFasting = "#D55E00")
cond_labs <- c(Control = "Control", TMX = "TMX", Fasting = "Fasting",
               TMXplusFasting = "TMX + Fasting")

theme_pub <- function(base_size = 11) {
  theme_bw(base_size = base_size) +
    theme(panel.grid.minor = element_blank(),
          panel.grid.major = element_line(linewidth = 0.25, colour = "grey90"),
          panel.border     = element_rect(linewidth = 0.5, colour = "grey30"),
          strip.background = element_rect(fill = "grey95", colour = "grey30"),
          strip.text       = element_text(face = "bold"),
          plot.title       = element_text(face = "bold", size = rel(1.05)),
          plot.subtitle    = element_text(colour = "grey35", size = rel(0.85)),
          legend.key       = element_blank())
}
save_fig <- function(p, name, w, h) {
  ggsave(file.path(fig_dir, paste0(name, ".png")), p, width = w, height = h, dpi = 300, bg = "white")
  # cairo_pdf gives proper unicode/font handling; fall back to base pdf() if absent
  ok <- tryCatch({
    ggsave(file.path(fig_dir, paste0(name, ".pdf")), p, width = w, height = h, device = grDevices::cairo_pdf)
    TRUE
  }, error = function(e) FALSE)
  if (!ok) ggsave(file.path(fig_dir, paste0(name, ".pdf")), p, width = w, height = h)
  message("  wrote ", name, ".png / .pdf")
}

message("== Fig 1: library QC =========================================")
qc <- read.csv(file.path(res_dir, "library_qc.csv")) |>
  mutate(condition = factor(condition, levels = names(cond_cols)))

p_lib <- ggplot(qc, aes(reorder(sample, total_counts), total_counts / 1e6, fill = condition)) +
  geom_col(width = 0.75) +
  coord_flip() +
  scale_fill_manual(values = cond_cols, labels = cond_labs, name = NULL) +
  labs(title = "Library size after filtering", x = NULL, y = "Assigned counts (millions)") +
  theme_pub()

p_sf <- ggplot(qc, aes(condition, size_factor, fill = condition)) +
  geom_boxplot(outlier.shape = NA, alpha = 0.35, width = 0.6) +
  geom_jitter(aes(colour = condition), width = 0.12, size = 2.2) +
  geom_hline(yintercept = 1, linetype = "dashed", colour = "grey40") +
  scale_fill_manual(values = cond_cols, guide = "none") +
  scale_colour_manual(values = cond_cols, guide = "none") +
  scale_x_discrete(labels = cond_labs) +
  labs(title = "DESeq2 median-of-ratios size factors",
       subtitle = "all near 1 -> no pathological library-depth skew",
       x = NULL, y = "size factor") +
  theme_pub() + theme(axis.text.x = element_text(angle = 20, hjust = 1))

save_fig(p_lib | p_sf, "fig01_library_qc", 11, 4.6)

message("== Fig 2: PCA on VST =========================================")
pcadata <- plotPCA(vsd, intgroup = "condition", returnData = TRUE, ntop = 2000)
pv <- round(100 * attr(pcadata, "percentVar"))
pcadata$condition <- factor(as.character(pcadata$condition), levels = names(cond_cols))

p_pca <- ggplot(pcadata, aes(PC1, PC2, colour = condition)) +
  geom_point(size = 3.4, alpha = 0.95) +
  geom_text_repel(aes(label = sub("MCF7_", "", name)), size = 2.7,
                  show.legend = FALSE, max.overlaps = 20, colour = "grey25") +
  scale_colour_manual(values = cond_cols, labels = cond_labs, name = NULL) +
  labs(title = "PCA of MCF7 xenograft transcriptomes (VST, top 2000 variable genes)",
       subtitle = "GSE260485 - fasting +/- tamoxifen",
       x = paste0("PC1: ", pv[1], "% variance"),
       y = paste0("PC2: ", pv[2], "% variance")) +
  theme_pub() + coord_fixed(ratio = 1)

save_fig(p_pca, "fig02_pca", 7.5, 6)

message("== Fig 3: sample-distance heatmap ============================")
d <- as.matrix(dist(t(assay(vsd))))
dl <- as.data.frame(as.table(d)) |>
  setNames(c("s1", "s2", "dist"))
ord <- hclust(as.dist(d))$order
lev <- colnames(d)[ord]
dl$s1 <- factor(dl$s1, levels = lev); dl$s2 <- factor(dl$s2, levels = rev(lev))

p_dist <- ggplot(dl, aes(s1, s2, fill = dist)) +
  geom_tile(colour = "white", linewidth = 0.3) +
  scale_fill_viridis_c(option = "mako", direction = -1, name = "Euclidean\ndistance") +
  scale_x_discrete(labels = function(x) sub("MCF7_", "", x)) +
  scale_y_discrete(labels = function(x) sub("MCF7_", "", x)) +
  labs(title = "Sample-to-sample distance (VST)",
       subtitle = "hierarchically ordered; blocks = replicate concordance",
       x = NULL, y = NULL) +
  theme_pub() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1), panel.grid = element_blank()) +
  coord_fixed()

save_fig(p_dist, "fig03_sample_distance", 7.8, 6.8)

message("== Fig 4: volcano panels =====================================")
contrast_files <- c(
  "TMX vs Control"            = "DE_TMX_vs_Control.csv",
  "Fasting vs Control"        = "DE_Fasting_vs_Control.csv",
  "TMX+Fasting vs Control"    = "DE_TMXplusFasting_vs_Control.csv",
  "TMX+Fasting vs TMX"        = "DE_TMXplusFasting_vs_TMX.csv"
)
de <- bind_rows(lapply(names(contrast_files), function(nm) {
  read.csv(file.path(res_dir, contrast_files[[nm]])) |> mutate(contrast_label = nm)
}))
de$contrast_label <- factor(de$contrast_label, levels = names(contrast_files))

LFC_CUT <- 1; FDR_CUT <- 0.05
volc <- de |>
  filter(!is.na(padj)) |>
  mutate(
    # volcano skill: plot SHRUNKEN lfc, keep unshrunken Wald padj on y
    negLog10 = -log10(padj),
    # axis truncation convention: cap the tail, mark capped points
    capped   = negLog10 > 60,
    negLog10 = pmin(negLog10, 60),
    class = case_when(
      padj < FDR_CUT & log2FC_shrunk >  LFC_CUT ~ "Up",
      padj < FDR_CUT & log2FC_shrunk < -LFC_CUT ~ "Down",
      TRUE ~ "n.s."
    )
  )
lab <- volc |> filter(class != "n.s.") |> group_by(contrast_label) |>
  slice_max(order_by = negLog10 * abs(log2FC_shrunk), n = 10) |> ungroup()

p_volc <- ggplot(volc, aes(log2FC_shrunk, negLog10)) +
  geom_hline(yintercept = -log10(FDR_CUT), linetype = "dashed", colour = "grey55", linewidth = 0.35) +
  geom_vline(xintercept = c(-LFC_CUT, LFC_CUT), linetype = "dashed", colour = "grey55", linewidth = 0.35) +
  geom_point(aes(colour = class, shape = capped), size = 1.05, alpha = 0.7) +
  geom_text_repel(data = lab, aes(label = symbol), size = 2.5, colour = "grey15",
                  max.overlaps = 25, min.segment.length = 0, segment.size = 0.2) +
  facet_wrap(~ contrast_label, nrow = 2) +
  scale_colour_manual(values = c(Up = "#D55E00", Down = "#0072B2", `n.s.` = "grey78"), name = NULL) +
  scale_shape_manual(values = c(`FALSE` = 16, `TRUE` = 17), guide = "none") +
  labs(title = "Differential expression, MCF7 xenografts (GSE260485)",
       subtitle = expression("ashr-shrunken log"[2]*"FC vs Benjamini-Hochberg FDR; cutoffs |LFC|>1, padj<0.05; y-axis capped at 60 (triangles)"),
       x = expression("shrunken log"[2]*" fold change"),
       y = expression("-log"[10]*" adjusted p-value")) +
  theme_pub() + theme(legend.position = "top")

save_fig(p_volc, "fig04_volcano_panels", 11, 9)

message("== Fig 5: MA plot ============================================")
p_ma <- de |>
  filter(!is.na(padj)) |>
  mutate(sig = ifelse(padj < FDR_CUT & abs(log2FC_shrunk) > LFC_CUT,
                      ifelse(log2FC_shrunk > 0, "Up", "Down"), "n.s.")) |>
  ggplot(aes(baseMean, log2FC_shrunk, colour = sig)) +
  geom_hline(yintercept = 0, colour = "grey40", linewidth = 0.4) +
  geom_point(size = 0.85, alpha = 0.6) +
  facet_wrap(~ contrast_label, nrow = 2) +
  scale_x_log10(labels = scales::label_log()) +
  scale_colour_manual(values = c(Up = "#D55E00", Down = "#0072B2", `n.s.` = "grey78"), name = NULL) +
  labs(title = "MA plots (shrinkage tames low-count noise)",
       x = "mean of normalized counts", y = expression("shrunken log"[2]*" fold change")) +
  theme_pub() + theme(legend.position = "top")

save_fig(p_ma, "fig05_ma_panels", 11, 8)

message("== Fig 6: DE counts barplot ==================================")
sm <- read.csv(file.path(res_dir, "DE_summary.csv")) |>
  mutate(contrast = factor(contrast, levels = c("TMX_vs_Control", "Fasting_vs_Control",
                                                "TMXplusFasting_vs_Control", "TMXplusFasting_vs_TMX"),
                           labels = names(contrast_files))) |>
  pivot_longer(c(sig_up, sig_down), names_to = "dir", values_to = "n") |>
  mutate(dir = ifelse(dir == "sig_up", "Up", "Down"),
         nn  = ifelse(dir == "Up", n, -n))

p_bar <- ggplot(sm, aes(contrast, nn, fill = dir)) +
  geom_col(width = 0.65) +
  geom_hline(yintercept = 0, colour = "grey25") +
  geom_text(aes(label = n, vjust = ifelse(dir == "Up", -0.4, 1.3)), size = 3.2) +
  scale_fill_manual(values = c(Up = "#D55E00", Down = "#0072B2"), name = NULL) +
  scale_y_continuous(labels = abs) +
  labs(title = "Significant genes per contrast",
       subtitle = "padj < 0.05 and |shrunken log2FC| > 1",
       x = NULL, y = "number of genes") +
  theme_pub() + theme(axis.text.x = element_text(angle = 15, hjust = 1))

save_fig(p_bar, "fig06_de_counts", 7.5, 5)

message("== Fig 7: top-variable-gene heatmap ==========================")
vmat <- assay(vsd)
topv <- head(order(rowVars(vmat), decreasing = TRUE), 50)
z <- t(scale(t(vmat[topv, ])))
rownames(z) <- make.unique(gene_anno[rownames(z), "symbol"])
gene_ord   <- rownames(z)[hclust(dist(z))$order]
sample_ord <- colnames(z)[hclust(dist(t(z)))$order]

hm <- as.data.frame(as.table(z)) |> setNames(c("gene", "sample", "z")) |>
  mutate(gene = factor(gene, levels = gene_ord),
         sample = factor(sample, levels = sample_ord),
         condition = coldata[as.character(sample), "condition"])

p_hm <- ggplot(hm, aes(sample, gene, fill = z)) +
  geom_tile() +
  facet_grid(~ condition, scales = "free_x", space = "free_x",
             labeller = labeller(condition = cond_labs)) +
  scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B",
                       midpoint = 0, limits = c(-2.5, 2.5), oob = scales::squish,
                       name = "row z-score") +
  scale_x_discrete(labels = function(x) sub("MCF7_.*_Rep", "R", x)) +
  labs(title = "Top 50 most variable genes (VST, row z-scored)",
       x = NULL, y = NULL) +
  theme_pub(9) +
  theme(axis.text.y = element_text(size = 6), panel.grid = element_blank(),
        panel.spacing = unit(2, "pt"))

save_fig(p_hm, "fig07_heatmap_top50", 8.5, 9)

message("== Fig 8: glucocorticoid-receptor target genes ===============")
# Paper's claim: fasting activates GR/PR programmes. Canonical GR targets:
gr_targets <- c("FKBP5", "TSC22D3", "PER1", "KLF15", "SGK1", "ZBTB16",
                "DDIT4", "TXNIP", "CEBPD", "NFKBIA", "PNMT", "IRS2")
norm <- read.csv(file.path(res_dir, "normalized_counts.csv.gz"), check.names = FALSE)
gr <- norm |> filter(symbol %in% gr_targets) |>
  pivot_longer(-c(gene_id, symbol), names_to = "sample", values_to = "count") |>
  mutate(condition = factor(coldata[sample, "condition"], levels = names(cond_cols)),
         symbol = factor(symbol, levels = gr_targets))

p_gr <- ggplot(gr, aes(condition, log2(count + 1), colour = condition, fill = condition)) +
  geom_boxplot(alpha = 0.25, outlier.shape = NA, width = 0.65, linewidth = 0.4) +
  geom_jitter(width = 0.14, size = 1.5, alpha = 0.9) +
  facet_wrap(~ symbol, scales = "free_y", ncol = 4) +
  scale_colour_manual(values = cond_cols, labels = cond_labs, name = NULL) +
  scale_fill_manual(values = cond_cols, guide = "none") +
  scale_x_discrete(labels = c("Ctrl", "TMX", "Fast", "TMX+Fast")) +
  labs(title = "Glucocorticoid-receptor target genes",
       subtitle = "DESeq2 median-of-ratios normalized counts, log2(x+1)",
       x = NULL, y = expression("log"[2]*"(normalized count + 1)")) +
  theme_pub() + theme(legend.position = "top",
                      axis.text.x = element_text(angle = 35, hjust = 1, size = 7))

save_fig(p_gr, "fig08_GR_targets", 10, 8)

message("== Fig 9: composite figure ===================================")
composite <- (p_pca | p_bar) /
  (p_volc + theme(legend.position = "bottom")) +
  plot_annotation(
    title = "GSE260485 - fasting + endocrine therapy in MCF7 breast-cancer xenografts",
    subtitle = "DESeq2 (~condition, Control reference), ashr shrinkage, BH FDR",
    caption = "Data: NCBI GEO GSE260485 (Padrao et al., Nature 2026). Pipeline built with bioSkills.",
    tag_levels = "A") &
  theme(plot.tag = element_text(face = "bold", size = 13))

save_fig(composite, "fig09_composite", 13, 14)

writeLines(capture.output(sessionInfo()), file.path(res_dir, "sessionInfo_figures.txt"))
message("03_ggplot_figures.R done.")
