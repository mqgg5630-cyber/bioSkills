#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# GSE260485 - download processed gene counts from GEO
# Skill: database-access/geo-data
#
# Series: "Fasting boosts breast cancer therapy efficacy via glucocorticoid
#          activation (RNA-Seq)"  (SubSeries of SuperSeries GSE260486)
# Platform: GPL24676 Illumina NovaSeq 6000, Homo sapiens
# 15 samples: MCF7 xenografts, Control / TMX / Fasting / TMX+Fasting
#
# NOTE (geo-data skill, "SuperSeries trap"): GSE260486 is the SuperSeries and
# mixes RNA-seq with ChIP/ATAC SubSeries. We deliberately pull the RNA-seq
# SubSeries GSE260485 only.
#
# NOTE (geo-data skill, "processed vs raw"): the submitter deposited raw
# integer gene counts (featureCounts-style, Ensembl IDs + biotype/coords),
# not a normalized matrix -> safe to feed directly to DESeq2.
# ---------------------------------------------------------------------------
set -euo pipefail

GSE="GSE260485"
FILE="GSE260485_MCF7_xenografts_genecounts.txt.gz"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data"
mkdir -p "$OUT_DIR"

FTP="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE260nnn/${GSE}/suppl/${FILE}"
HTTP="https://www.ncbi.nlm.nih.gov/geo/download/?acc=${GSE}&format=file&file=GSE260485%5FMCF7%5Fxenografts%5Fgenecounts%2Etxt%2Egz"

if [[ -s "${OUT_DIR}/${FILE}" ]]; then
  echo "[01] already present: ${OUT_DIR}/${FILE}"
  exit 0
fi

echo "[01] downloading ${FILE} ..."
curl -fL --retry 5 --retry-delay 5 --connect-timeout 30 -o "${OUT_DIR}/${FILE}" "$FTP" \
  || curl -fL --retry 5 --retry-delay 5 --connect-timeout 30 -o "${OUT_DIR}/${FILE}" "$HTTP"

echo "[01] done:"
ls -lh "${OUT_DIR}/${FILE}"
gzip -t "${OUT_DIR}/${FILE}" && echo "[01] gzip integrity OK"
