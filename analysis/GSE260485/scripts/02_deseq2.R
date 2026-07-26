#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# GSE260485 - counts ingest -> QC -> DESeq2 differential expression
# Skills used:
#   expression-matrix/counts-ingest      (integer matrix + colData contract)
#   expression-matrix/gene-id-mapping    (Ensembl ID -> symbol, kept from file)
#   differential-expression/deseq2-basics(design, explicit contrasts, shrinkage)
#
# Design: ~ condition, 4 levels, Control as reference.
# Wald tests with EXPLICIT contrasts (never bare results(dds), per skill),
# plus an omnibus LRT (~1) because condition has >2 levels.
# LFC shrinkage: ashr (supports contrast=), used for ranking/plots only;
# p-values reported are the unshrunken Wald p-values (deliberate, see skill).
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(DESeq2)
  library(ashr)
  library(matrixStats)
})

root     <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])), ".."))
data_dir <- file.path(root, "data")
res_dir  <- file.path(root, "results")
dir.create(res_dir, showWarnings = FALSE, recursive = TRUE)

counts_file <- file.path(data_dir, "GSE260485_MCF7_xenografts_genecounts.txt.gz")
stopifnot(file.exists(counts_file))

message("== 1. ingest ==================================================")
raw <- read.delim(gzfile(counts_file), stringsAsFactors = FALSE, check.names = FALSE,
                  quote = "", comment.char = "")  # descriptions contain quotes/#
message(sprintf("raw table: %d rows x %d cols", nrow(raw), ncol(raw)))

sample_cols <- grep("^MCF7_", colnames(raw), value = TRUE)
anno_cols   <- setdiff(colnames(raw), sample_cols)
message("samples (", length(sample_cols), "): ", paste(sample_cols, collapse = ", "))
message("annotation cols: ", paste(anno_cols, collapse = ", "))

# drop the unannotated 'NA' feature row (unassigned reads), keep unique gene ids
raw <- raw[!is.na(raw$ensembl_gene_id) & raw$ensembl_gene_id != "NA", ]
raw <- raw[!duplicated(raw$ensembl_gene_id), ]

cts <- as.matrix(raw[, sample_cols])
rownames(cts) <- raw$ensembl_gene_id
storage.mode(cts) <- "integer"   # counts-ingest: DESeq2 demands integers

gene_anno <- data.frame(
  ensembl_gene_id = raw$ensembl_gene_id,
  symbol          = ifelse(is.na(raw$external_gene_id) | raw$external_gene_id == "",
                           raw$ensembl_gene_id, raw$external_gene_id),
  biotype         = raw$gene_biotype,
  chromosome      = raw$chromosome_name,
  stringsAsFactors = FALSE
)
rownames(gene_anno) <- gene_anno$ensembl_gene_id

message("== 2. colData from sample names ===============================")
condition <- sub("^MCF7_(.*)_Rep[0-9]+$", "\\1", sample_cols)
condition <- factor(condition, levels = c("Control", "TMX", "Fasting", "TMXplusFasting"))
coldata <- data.frame(
  sample    = sample_cols,
  condition = condition,
  replicate = as.integer(sub(".*_Rep([0-9]+)$", "\\1", sample_cols)),
  fasting   = factor(ifelse(grepl("Fasting", sample_cols), "yes", "no"), levels = c("no", "yes")),
  tamoxifen = factor(ifelse(grepl("TMX", sample_cols), "yes", "no"), levels = c("no", "yes")),
  row.names = sample_cols
)
print(table(coldata$condition))
stopifnot(identical(colnames(cts), rownames(coldata)))
write.csv(coldata, file.path(res_dir, "sample_metadata.csv"), row.names = FALSE)

message("== 3. DESeqDataSet + filtering ================================")
dds <- DESeqDataSetFromMatrix(cts, coldata, design = ~ condition)
dds$condition <- relevel(dds$condition, ref = "Control")

# filter: >=10 counts in at least the size of the smallest group (n=3)
keep <- rowSums(counts(dds) >= 10) >= 3
message(sprintf("genes: %d -> %d after filtering", nrow(dds), sum(keep)))
dds <- dds[keep, ]

message("== 4. DESeq (Wald) + omnibus LRT ==============================")
dds <- DESeq(dds)
print(resultsNames(dds))

dds_lrt <- DESeq(dds, test = "LRT", reduced = ~ 1)
res_lrt <- results(dds_lrt, alpha = 0.05)
message(sprintf("LRT (any condition effect): %d genes padj<0.05",
                sum(res_lrt$padj < 0.05, na.rm = TRUE)))
lrt_out <- data.frame(gene_id = rownames(res_lrt),
                      symbol  = gene_anno[rownames(res_lrt), "symbol"],
                      as.data.frame(res_lrt))
lrt_out <- lrt_out[order(lrt_out$padj), ]
write.csv(lrt_out, file.path(res_dir, "LRT_condition_omnibus.csv"), row.names = FALSE)

message("== 5. pairwise contrasts (explicit) ===========================")
contrasts <- list(
  TMX_vs_Control            = c("condition", "TMX", "Control"),
  Fasting_vs_Control        = c("condition", "Fasting", "Control"),
  TMXplusFasting_vs_Control = c("condition", "TMXplusFasting", "Control"),
  TMXplusFasting_vs_TMX     = c("condition", "TMXplusFasting", "TMX")
)

summaries <- list()
for (nm in names(contrasts)) {
  ct  <- contrasts[[nm]]
  res <- results(dds, contrast = ct, alpha = 0.05)
  # ashr shrinkage: works with contrast=, gives svalue (local false sign rate)
  shr <- lfcShrink(dds, contrast = ct, type = "ashr", res = res, quiet = TRUE)

  out <- data.frame(
    gene_id        = rownames(res),
    symbol         = gene_anno[rownames(res), "symbol"],
    biotype        = gene_anno[rownames(res), "biotype"],
    baseMean       = res$baseMean,
    log2FC_MLE     = res$log2FoldChange,   # unshrunken
    lfcSE          = res$lfcSE,
    stat           = res$stat,             # Wald z, good GSEA ranking metric
    pvalue         = res$pvalue,
    padj           = res$padj,
    log2FC_shrunk  = shr$log2FoldChange,   # ashr posterior, for plots/ranking
    svalue         = if ("svalue" %in% colnames(shr)) shr$svalue else NA_real_,
    contrast       = nm,
    stringsAsFactors = FALSE
  )
  out <- out[order(out$padj, -abs(out$log2FC_shrunk)), ]
  write.csv(out, file.path(res_dir, sprintf("DE_%s.csv", nm)), row.names = FALSE)

  sig <- subset(out, !is.na(padj) & padj < 0.05 & abs(log2FC_shrunk) > 1)
  summaries[[nm]] <- data.frame(
    contrast  = nm,
    tested    = sum(!is.na(out$padj)),
    padj05    = sum(out$padj < 0.05, na.rm = TRUE),
    sig_up    = sum(sig$log2FC_shrunk > 0),
    sig_down  = sum(sig$log2FC_shrunk < 0)
  )
  message(sprintf("  %-26s padj<0.05: %5d | |LFC|>1: up %4d / down %4d",
                  nm, summaries[[nm]]$padj05, summaries[[nm]]$sig_up, summaries[[nm]]$sig_down))
}
summary_df <- do.call(rbind, summaries)
write.csv(summary_df, file.path(res_dir, "DE_summary.csv"), row.names = FALSE)

message("== 6. VST for PCA / heatmaps ==================================")
vsd <- vst(dds, blind = FALSE)
vmat <- assay(vsd)
write.csv(data.frame(gene_id = rownames(vmat),
                     symbol  = gene_anno[rownames(vmat), "symbol"],
                     vmat, check.names = FALSE),
          gzfile(file.path(res_dir, "vst_matrix.csv.gz")), row.names = FALSE)

norm <- counts(dds, normalized = TRUE)
write.csv(data.frame(gene_id = rownames(norm),
                     symbol  = gene_anno[rownames(norm), "symbol"],
                     norm, check.names = FALSE),
          gzfile(file.path(res_dir, "normalized_counts.csv.gz")), row.names = FALSE)

lib <- data.frame(sample = colnames(dds),
                  condition = as.character(coldata$condition),
                  total_counts = colSums(counts(dds)),
                  detected_genes = colSums(counts(dds) > 0),
                  size_factor = sizeFactors(dds))
write.csv(lib, file.path(res_dir, "library_qc.csv"), row.names = FALSE)

saveRDS(list(dds = dds, vsd = vsd, gene_anno = gene_anno, coldata = coldata),
        file.path(res_dir, "deseq2_objects.rds"))

message("== 7. sessionInfo ============================================")
writeLines(capture.output(sessionInfo()), file.path(res_dir, "sessionInfo_deseq2.txt"))
message("02_deseq2.R done.")
