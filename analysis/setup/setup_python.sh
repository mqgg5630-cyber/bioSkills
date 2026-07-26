#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Python 环境（推荐先走这条：不需要 sudo，几分钟搞定）
#
# 你机器上已有 conda（提示符里的 (base)），但也可以用纯 venv。
# 这套环境足以跑完 GSE42872 全流程：limma 风格差异分析 + ggplot 出图。
# ---------------------------------------------------------------------------
set -euo pipefail

PKGS="pandas numpy scipy plotnine adjustText pyreadr pydeseq2"

if command -v conda >/dev/null 2>&1 && [[ "${USE_VENV:-0}" != "1" ]]; then
  echo "[*] 用 conda 创建环境 bioskills (python 3.11)"
  conda create -y -n bioskills python=3.11
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate bioskills
  pip install $PKGS
  echo
  echo "完成。以后每次用之前先： conda activate bioskills"
else
  echo "[*] 用 venv 创建环境 ~/.venvs/bioskills"
  python3 -m venv ~/.venvs/bioskills
  ~/.venvs/bioskills/bin/pip install --upgrade pip
  ~/.venvs/bioskills/bin/pip install $PKGS
  echo
  echo "完成。以后每次用之前先： source ~/.venvs/bioskills/bin/activate"
fi

echo
echo "[*] 版本核对："
python - <<'EOF'
for m in ["pandas","numpy","scipy","plotnine","pyreadr"]:
    try:
        mod=__import__(m); print(f"  {m:<10} {getattr(mod,'__version__','?')}")
    except ImportError:
        print(f"  {m:<10} 未安装")
EOF
