#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# GSE42872 — 原生 R 版：GEOquery/series-matrix -> limma -> 结果表 -> ggplot2
#
# 这是 02_limma_de.py + 03_ggplot_figures.py 的 R 等价实现。
# 装好 R 环境后（bash analysis/setup/setup_r.sh conda）跑这个即可。
#
# 为什么是 limma 不是 DESeq2：GPL6244 芯片，数据是 RMA 归一化的 log2 强度，
# 连续型；DESeq2 的负二项模型只适用于整数 counts。
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(limma); library(ggplot2); library(dplyr); library(tidyr); library(ggrepel)
})

root <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])), ".."))
data_dir <- file.path(root, "data"); res_dir <- file.path(root, "results")
fig_dir  <- file.path(root, "figures")
dir.create(res_dir, showWarnings = FALSE); dir.create(fig_dir, showWarnings = FALSE)

matrix_file <- file.path(data_dir, "GSE42872_series_matrix.txt.gz")
stopifnot(file.exists(matrix_file))

message("== 1. 读取 series matrix ==")
# 表达值表从 !series_matrix_table_begin 之后开始
all_lines <- readLines(gzfile(matrix_file))
b <- grep("^!series_matrix_table_begin", all_lines)
e <- grep("^!series_matrix_table_end",   all_lines)
expr <- read.delim(text = all_lines[(b + 1):(e - 1)], row.names = 1, check.names = FALSE)
expr <- as.matrix(expr)
message(sprintf("%d 探针 x %d 样本，值域 %.2f ~ %.2f (log2 RMA)",
                nrow(expr), ncol(expr), min(expr), max(expr)))

get_meta <- function(key) {
  l <- grep(paste0("^!", key, "\t"), all_lines, value = TRUE)[1]
  gsub('"', '', strsplit(l, "\t")[[1]][-1])
}
titles <- get_meta("Sample_title")
group  <- factor(ifelse(grepl("Vemurafenib", titles), "Vemurafenib", "Control"),
                 levels = c("Control", "Vemurafenib"))
coldata <- data.frame(gsm = colnames(expr), title = titles, group = group)
print(coldata)
write.csv(coldata, file.path(res_dir, "sample_metadata_R.csv"), row.names = FALSE)

message("== 2. 探针注释 ==")
symbol <- rep(NA_character_, nrow(expr)); names(symbol) <- rownames(expr)
if (requireNamespace("hugene10sttranscriptcluster.db", quietly = TRUE)) {
  suppressPackageStartupMessages(library(hugene10sttranscriptcluster.db))
  map <- AnnotationDbi::select(hugene10sttranscriptcluster.db,
                               keys = rownames(expr), columns = "SYMBOL", keytype = "PROBEID")
  map <- map[!duplicated(map$PROBEID), ]
  symbol[map$PROBEID] <- map$SYMBOL
  message(sprintf("注释到 symbol: %d / %d", sum(!is.na(symbol)), length(symbol)))
} else {
  # 退而求其次：用 NCBI 官方平台注释文件（01_fetch.sh 会一并下载）
  annot_file <- file.path(data_dir, "GPL6244.annot.gz")
  if (file.exists(annot_file)) {
    al <- readLines(gzfile(annot_file), warn = FALSE)
    ab <- grep("^!platform_table_begin", al); ae <- grep("^!platform_table_end", al)
    at <- read.delim(text = al[(ab + 1):(ae - 1)], check.names = FALSE,
                     quote = "", comment.char = "", colClasses = "character")
    if ("Gene symbol" %in% colnames(at)) {
      sy <- sub("///.*$", "", at[["Gene symbol"]])   # 多基因取第一个
      names(sy) <- at[["ID"]]
      sy <- sy[sy != "" & !is.na(sy)]
      common <- intersect(names(sy), rownames(expr))
      symbol[common] <- sy[common]
      message(sprintf("用 NCBI 官方注释: %d / %d", sum(!is.na(symbol)), length(symbol)))
    }
  } else {
    message("无注释可用，结果以探针 ID 输出")
    message("装法: BiocManager::install('hugene10sttranscriptcluster.db')")
  }
}

message("== 3. limma lmFit + eBayes ==")
design <- model.matrix(~ group)          # 截距 + Vemurafenib 效应
colnames(design) <- c("Intercept", "VemVsCtrl")
fit  <- lmFit(expr, design)
fit2 <- eBayes(fit)
message(sprintf("先验: s0^2 = %.5f, d0 = %.3f", fit2$s2.prior, fit2$df.prior))

res <- topTable(fit2, coef = "VemVsCtrl", number = Inf, sort.by = "P")
res$probe  <- rownames(res)
res$symbol <- symbol[res$probe]

LFC <- 1; FDR <- 0.05
res$direction <- with(res, ifelse(adj.P.Val < FDR & logFC >  LFC, "Up",
                           ifelse(adj.P.Val < FDR & logFC < -LFC, "Down", "n.s.")))
message(sprintf("padj<0.05: %d | 且 |LFC|>1: up %d / down %d",
                sum(res$adj.P.Val < FDR),
                sum(res$direction == "Up"), sum(res$direction == "Down")))

res <- res[, c("probe","symbol","logFC","AveExpr","t","P.Value","adj.P.Val","B","direction")]
write.csv(res, file.path(res_dir, "DE_Vemurafenib_vs_Control_R.csv"), row.names = FALSE)
print(head(res, 15))

message("== 4. ggplot2 出图 ==")
DIR_COLS <- c(Up = "#D55E00", Down = "#0072B2", `n.s.` = "#CCCCCC")
theme_pub <- theme_bw(11) +
  theme(panel.grid.minor = element_blank(),
        panel.grid.major = element_line(linewidth = .25, colour = "grey90"),
        plot.title = element_text(face = "bold"),
        plot.subtitle = element_text(colour = "grey35", size = rel(.85)))

v <- res %>% mutate(nlp = -log10(adj.P.Val))
lab <- v %>% filter(direction != "n.s.", !is.na(symbol)) %>%
  slice_max(nlp * abs(logFC), n = 18)

p_volc <- ggplot(v, aes(logFC, nlp, colour = direction)) +
  geom_hline(yintercept = -log10(FDR), linetype = "dashed", colour = "grey55", linewidth = .35) +
  geom_vline(xintercept = c(-LFC, LFC), linetype = "dashed", colour = "grey55", linewidth = .35) +
  geom_point(size = .6, alpha = .6) +
  geom_text_repel(data = lab, aes(label = symbol), size = 2.6, colour = "grey15",
                  max.overlaps = 30, min.segment.length = 0, segment.size = .2) +
  scale_colour_manual(values = DIR_COLS, name = NULL) +
  labs(title = "Volcano: Vemurafenib vs Control (GSE42872)",
       subtitle = sprintf("limma moderated t | |log2FC|>%g and FDR<%g | up %d / down %d",
                          LFC, FDR, sum(res$direction == "Up"), sum(res$direction == "Down")),
       x = "log2 fold change", y = "-log10 adjusted P") + theme_pub
ggsave(file.path(fig_dir, "figR_volcano.png"), p_volc, width = 8, height = 6.5, dpi = 300, bg = "white")
ggsave(file.path(fig_dir, "figR_volcano.pdf"), p_volc, width = 8, height = 6.5)

pca <- prcomp(t(expr[order(apply(expr, 1, var), decreasing = TRUE)[1:5000], ]), scale. = FALSE)
pv  <- round(100 * pca$sdev^2 / sum(pca$sdev^2), 1)
pdf_ <- data.frame(PC1 = pca$x[,1], PC2 = pca$x[,2], group = coldata$group,
                   label = sub("A375 cells 24h ", "", coldata$title))
p_pca <- ggplot(pdf_, aes(PC1, PC2, colour = group)) +
  geom_point(size = 3.5) +
  geom_text_repel(aes(label = label), size = 2.7, colour = "grey25") +
  scale_colour_manual(values = c(Control = "#0072B2", Vemurafenib = "#D55E00"), name = NULL) +
  labs(title = "PCA (top 5000 variable probes)",
       x = sprintf("PC1: %.1f%% variance", pv[1]),
       y = sprintf("PC2: %.1f%% variance", pv[2])) + theme_pub
ggsave(file.path(fig_dir, "figR_pca.png"), p_pca, width = 7, height = 5.5, dpi = 300, bg = "white")

mapk <- c("DUSP6","SPRY2","SPRY4","ETV4","ETV5","PHLDA1","CCND1","MYC","FOSL1","EPHA2","IER3","DUSP4")
sel <- res %>% filter(symbol %in% mapk) %>% distinct(symbol, .keep_all = TRUE)
if (nrow(sel) > 0) {
  md <- as.data.frame(expr[sel$probe, , drop = FALSE])
  md$symbol <- sel$symbol
  md <- md %>% pivot_longer(-symbol, names_to = "gsm", values_to = "expr") %>%
    left_join(coldata, by = "gsm") %>% mutate(symbol = factor(symbol, levels = mapk))
  p_mapk <- ggplot(md, aes(group, expr, fill = group)) +
    geom_boxplot(alpha = .35, outlier.shape = NA, width = .6) +
    geom_point(aes(colour = group), size = 1.8) +
    facet_wrap(~ symbol, scales = "free_y", ncol = 4) +
    scale_fill_manual(values = c(Control = "#0072B2", Vemurafenib = "#D55E00"), guide = "none") +
    scale_colour_manual(values = c(Control = "#0072B2", Vemurafenib = "#D55E00"), name = NULL) +
    scale_x_discrete(labels = c("Ctrl", "Vem")) +
    labs(title = "MAPK/ERK pathway output genes",
         subtitle = "Vemurafenib inhibits BRAF-V600E: outputs go down (positive control)",
         x = NULL, y = "log2 intensity") + theme_pub + theme(legend.position = "top")
  ggsave(file.path(fig_dir, "figR_MAPK.png"), p_mapk, width = 10, height = 7.5, dpi = 300, bg = "white")
}

writeLines(capture.output(sessionInfo()), file.path(res_dir, "sessionInfo_R.txt"))
message("R 版流程完成。结果 -> ", res_dir, "，图 -> ", fig_dir)
