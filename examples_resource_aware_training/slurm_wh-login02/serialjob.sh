#!/bin/bash
#SBATCH --job-name=dl_serial
#SBATCH --partition=serial   # 根据 job_example/serialjob 修改
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=200G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%j_serial.out
# 对应 ~/job_example/serialjob 模板

module load python/3.12 2>/dev/null || export PATH=/usr/local/python3.12/bin:$PATH
python3 --version

# CPU大内存训练例子 (无需GPU)
python3 - << 'PY'
import torch
torch.set_num_threads(32)
print(f"CPU threads: {torch.get_num_threads()}")
# 模拟 omics 分类
import numpy as np
X = np.random.randn(100000, 512)  # 100k样本，251GB内存足够
print(f"Data shape {X.shape}, mem ~ {X.nbytes/1e9:.2f} GB")
PY
