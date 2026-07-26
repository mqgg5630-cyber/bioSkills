#!/usr/bin/env bash
# GSE42872 全流程一键跑。
#   bash analysis/GSE42872/run_all.sh          # Python 路线（默认，无需 R）
#   bash analysis/GSE42872/run_all.sh r        # R 路线（需先装 R）
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-py}"

bash "$HERE/scripts/01_fetch.sh"

if [[ "$MODE" == "r" ]]; then
  command -v Rscript >/dev/null || { echo "没装 R，先跑: bash analysis/setup/setup_r.sh conda"; exit 1; }
  Rscript "$HERE/scripts/02_limma_de.R"
else
  PY="${PYTHON:-python3}"
  $PY -c "import pandas, plotnine" 2>/dev/null || {
    echo "缺依赖，先跑: bash analysis/setup/setup_python.sh"; exit 1; }
  $PY "$HERE/scripts/02_limma_de.py"
  $PY "$HERE/scripts/03_ggplot_figures.py"
  $PY "$HERE/scripts/04_validate.py" || true
fi

echo
echo "结果: $HERE/results"
echo "图  : $HERE/figures"
