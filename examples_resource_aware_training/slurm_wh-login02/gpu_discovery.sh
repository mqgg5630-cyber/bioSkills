#!/bin/bash
#SBATCH --job-name=gpu_probe
#SBATCH --partition=gpu        # 尝试 gpu, gpus, A100, V100, 3090, 4个都试试
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%j_gpu_probe.out

nvidia-smi
nvidia-smi -L
nvcc --version || /usr/local/cuda/bin/nvcc --version
python3 -c "import torch; print(torch.cuda.get_device_properties(0))" 2>&1 || echo "torch未安装"
env | grep -i cuda
