#!/bin/bash
#SBATCH --job-name=dl_gpu
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%j_dl_gpu.out

mkdir -p logs
nvidia-smi

# 安装 conda (若无)
if ! command -v conda &> /dev/null; then
  echo "conda未找到，尝试module"
  module avail 2>&1 | grep -i conda
  module load miniconda3 2>/dev/null || module load anaconda3 2>/dev/null || echo "需手动安装miniconda到/work"
fi

export PATH=/usr/local/python3.12/bin:$PATH
pip install torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -n 5

python3 ../02_train_pytorch_adaptive.py
python3 ../03_train_biology_dl_examples.py
