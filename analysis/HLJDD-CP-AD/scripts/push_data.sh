#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 修正版：把 GEO 数据处理好并推送到 arena 分支
#
# 你原脚本 push_raw.sh 的三个问题：
#   1. cd combined_raw && git init  → 建了个全新空仓库，没有 remote、没有分支，
#      所以 push 报 "src refspec arena/019f9c4c-bioskills does not match any"
#   2. 直接提交 1.2 GB 原始 mtx  → 超 GitHub 限制，即使 1 修好也推不上去
#   3. gunzip "E:/R/..."         → WSL 不认 Windows 路径，要写 /mnt/e/...
#      （况且 GSE781 是肾癌数据，与本课题无关，不需要）
#
# 本脚本做的事：
#   - 在你已有的 bioSkills 仓库里操作（不 git init）
#   - GSE157827 先跑预处理压到 <100MB 再提交
#   - GSE23586 体积小，直接提交
#   - 提交前检查有没有超限文件
#
# 用法:
#   bash analysis/HLJDD-CP-AD/scripts/push_data.sh
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="$HOME/projects/bioSkills"
BRANCH="arena/019f9c4c-bioskills"
WIN_RAW="/mnt/e/0wangyao/wangyao/raw/1"      # Windows E: 在 WSL 下的路径
WORK="$HOME/geodata"                          # 工作目录，放 WSL 原生盘（快）
DEST="$REPO/analysis/HLJDD-CP-AD/data"

cd "$REPO"

echo "=================================================="
echo " 0. 环境检查"
echo "=================================================="
# 必须在正确的仓库里
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "错误：$REPO 不是 git 仓库"; exit 1
fi
echo "仓库: $(git remote get-url origin)"
echo "当前分支: $(git rev-parse --abbrev-ref HEAD)"

# 确保在目标分支上
if [[ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]]; then
  echo "切换到 $BRANCH ..."
  git checkout "$BRANCH"
fi

# 清理上次失败留下的 combined_raw（它是个独立仓库，没用）
if [[ -d "$REPO/combined_raw/.git" ]]; then
  echo
  echo "发现上次脚本建的 combined_raw/（独立空仓库，无用）"
  read -rp "删除它？[y/N] " ans
  [[ "${ans,,}" == "y" ]] && rm -rf "$REPO/combined_raw" && echo "已删除"
fi

python -c "import scanpy, anndata, scipy" 2>/dev/null || {
  echo "缺依赖，执行: pip install scanpy anndata scipy"; exit 1; }

echo
echo "=================================================="
echo " 1. 解压到工作目录（WSL 原生盘，比 /mnt/ 快很多）"
echo "=================================================="
mkdir -p "$WORK/gse157827" "$WORK/gse23586" "$DEST"

if [[ -z "$(ls -A "$WORK/gse157827" 2>/dev/null)" ]]; then
  echo "解压 GSE157827 (1.2GB, 需要几分钟) ..."
  tar -xf "$WIN_RAW/GSE157827/GSE157827_RAW.tar" -C "$WORK/gse157827"
else
  echo "GSE157827 已解压，跳过"
fi

if [[ -z "$(ls -A "$WORK/gse23586" 2>/dev/null)" ]]; then
  echo "解压 GSE23586 ..."
  tar -xf "$WIN_RAW/GSE23586/GSE23586_RAW.tar" -C "$WORK/gse23586"
else
  echo "GSE23586 已解压，跳过"
fi

echo "解压结果:"
du -sh "$WORK/gse157827" "$WORK/gse23586"
echo "GSE157827 文件数: $(ls "$WORK/gse157827" | wc -l)"

echo
echo "=================================================="
echo " 2. GSE157827 预处理（1.2GB -> <100MB）"
echo "=================================================="
H5AD="$DEST/gse157827_prepared.h5ad"
if [[ -s "$H5AD" ]]; then
  echo "已存在: $H5AD ($(du -h "$H5AD" | cut -f1))，跳过"
else
  cd "$WORK"
  python "$REPO/analysis/HLJDD-CP-AD/scripts/00_prepare_local.py" \
      "$WORK/gse157827" -o "$H5AD"
  [[ -f "$WORK/gse157827_qc_per_sample.csv" ]] && \
      cp "$WORK/gse157827_qc_per_sample.csv" "$DEST/"
  cd "$REPO"
fi

echo
echo "=================================================="
echo " 3. GSE23586 打包（体积小，直接传）"
echo "=================================================="
CEL_TAR="$DEST/GSE23586_CEL.tar"
if [[ -s "$CEL_TAR" ]]; then
  echo "已存在，跳过"
else
  # 只要 CEL（原始强度），CHP 是 Affymetrix 软件的二次产物，用不上
  tar -cf "$CEL_TAR" -C "$WORK/gse23586" $(cd "$WORK/gse23586" && ls *.CEL.gz)
  echo "已打包: $(du -h "$CEL_TAR" | cut -f1)"
fi

echo
echo "=================================================="
echo " 4. 提交前体积检查"
echo "=================================================="
OVER=0
while IFS= read -r -d '' f; do
  sz=$(stat -c%s "$f")
  mb=$((sz / 1048576))
  if (( sz > 100*1024*1024 )); then
    echo "  ✗ 超限 ${mb}MB: $(basename "$f")"; OVER=1
  else
    echo "  ✓ ${mb}MB $(basename "$f")"
  fi
done < <(find "$DEST" -type f -print0)

if (( OVER )); then
  cat <<'MSG'

有文件超过 GitHub 100MB 上限。请减少高变基因数重跑预处理：

  rm ~/projects/bioSkills/analysis/HLJDD-CP-AD/data/gse157827_prepared.h5ad
  python analysis/HLJDD-CP-AD/scripts/00_prepare_local.py \
      ~/geodata/gse157827 --n-hvg 2000 \
      -o analysis/HLJDD-CP-AD/data/gse157827_prepared.h5ad

然后重跑本脚本。
MSG
  exit 1
fi

echo
echo "=================================================="
echo " 5. 提交并推送"
echo "=================================================="
cd "$REPO"
# data/ 在 .gitignore 里有规则，用 -f 强制加入
git add -f "$DEST"
if git diff --cached --quiet; then
  echo "没有新增内容"
else
  git status --short | head -20
  git commit -m "add GSE157827 prepared h5ad + GSE23586 CEL for HLJDD-CP-AD reanalysis"
  echo
  echo "推送中（大文件，若断线重跑本脚本即可续传）..."
  git push origin "$BRANCH"
fi

echo
echo "=================================================="
echo " 完成"
echo "=================================================="
git log --oneline -1
echo
echo "已上传:"
ls -lh "$DEST"
echo
echo "现在可以告诉我数据传好了，我开始分析。"
