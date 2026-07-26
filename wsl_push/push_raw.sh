#!/bin/bash
# WSL2 push script for bioSkills
TARGET_DIR="/mnt/e/0wangyao/wangyao/raw/1"
OUT_DIR="./combined_raw"
mkdir -p "$OUT_DIR"
tar -xf "$TARGET_DIR/GSE157827/GSE157827_RAW.tar" -C "$OUT_DIR"
tar -xf "$TARGET_DIR/GSE23586/GSE23586_RAW.tar" -C "$OUT_DIR"
# For .gz
mkdir -p "$OUT_DIR/GSE781"
gunzip -c "E:/R/R_libs/GEOquery/extdata/GSE781_family.soft.gz" > "$OUT_DIR/GSE781/GSE781_family.soft"
cd "$OUT_DIR"
git init || true
git add .
git commit -m "add extracted raw files"
git push origin arena/019f9c4c-bioskills
