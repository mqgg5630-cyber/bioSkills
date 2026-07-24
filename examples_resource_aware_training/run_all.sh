#!/bin/bash
# 一键运行，不需要手动输入带括号的文件名（避免终端自动链接渲染干扰）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "DIR=$DIR"
echo "文件列表(原始):"
ls -1 "$DIR" | cat -A

echo ""
echo "=== 1. 资源检测 v1 ==="
bash "$DIR/01_check_resources.sh" 2>&1 | head -n 200

echo ""
echo "=== 2. 资源检测 v2 (调度器) ==="
bash "$DIR/01_check_resources_v2.sh" 2>&1 | head -n 400

echo ""
echo "=== 3. PyTorch 自适应训练 (无GPU也可用CPU跑) ==="
python3 "$DIR/02_train_pytorch_adaptive.py" 2>&1 | tail -n 100 || python "$DIR/02_train_pytorch_adaptive.py" 2>&1 | tail -n 100

echo ""
echo "=== 4. 生物DL例子代码展示 ==="
python3 "$DIR/03_train_biology_dl_examples.py" 2>&1 | head -n 200

echo ""
echo "Done. 若需看SLURM模板: bash $DIR/04_slurm_templates.sh"
