#!/bin/bash
# ========== 在 wh-login02 容器中克隆 bioSkills 并运行资源自适应训练 ==========
# 复制以下命令到 wh-login02 终端直接执行

# ---- 0. 检查当前环境 ----
pwd; ls -la
echo "=== job_example 内容 (你的集群示例) ==="
ls -la job_example 2>/dev/null || echo "没有 job_example, 尝试 find"
find ~ -maxdepth 2 -type f -name "*.sh" | head -n 20

# ---- 1. 一键资源检测 ----
# 下载最新检测脚本 (如果你已经克隆本项目，直接 bash 即可)
curl -fsSL https://raw.githubusercontent.com/mqgg5630-cyber/bioSkills/main/examples_resource_aware_training/01_check_resources.sh -o /tmp/check.sh 2>/dev/null || echo "离线模式，使用本地文件"
if [ -f "/home/user/bioSkills/examples_resource_aware_training/01_check_resources.sh" ]; then
    bash /home/user/bioSkills/examples_resource_aware_training/01_check_resources.sh
else
    echo "请运行: bash 01_check_resources.sh"
fi

# ---- 2. 克隆项目 ----
cd ~
if [ -d "bioSkills" ]; then
    echo "bioSkills 已存在，更新"
    cd bioSkills && git pull && cd ~
else
    git clone https://github.com/mqgg5630-cyber/bioSkills.git
    # 或 git clone git@github.com:mqgg5630-cyber/bioSkills.git (需ssh key)
fi

cd bioSkills
ls | head -n 20

# ---- 3. 创建 conda 环境 (推荐) ----
# conda create -n bio python=3.10 -y
# conda activate bio
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# pip install scanpy scvi-tools fair-esm biopython

# ---- 4. 根据资源配置选择训练例子 ----
echo "=== 根据 GPU 显存选择 ==="
python3 - << 'PY'
import torch
if not torch.cuda.is_available():
    print("无GPU，建议: srun --gres=gpu:1 --pty bash 再跑")
else:
    mem = torch.cuda.get_device_properties(0).total_memory/1024**3
    print(f"显存 {mem:.1f} GB")
    if mem < 10:
        print("推荐: omics-classifiers, biomarker-discovery, QSAR 小模型")
        print("  python examples_resource_aware_training/02_train_pytorch_adaptive.py")
        print("  python machine-learning/omics-classifiers/examples/logistic_regression.py")
    elif mem < 30:
        print("推荐: scArches, ESMFold 400aa, CellTypist")
        print("  python examples_resource_aware_training/03_train_biology_dl_examples.py")
    else:
        print("推荐: chromBPNet训练, Enformer, 大规模 scVI")
        print("  bash structural-biology/modern-structure-prediction - ESMFold 长序列")
        print("  bash atac-seq/deep-learning-atac/examples/chrombpnet_pipeline.sh")
PY

# ---- 5. 运行通用自适应训练 ----
pip install torch -q 2>&1 | tail -n 5
python examples_resource_aware_training/02_train_pytorch_adaptive.py
python examples_resource_aware_training/03_train_biology_dl_examples.py

# ---- 6. 提交 SLURM 作业 (如果有 SLURM) ----
# bash examples_resource_aware_training/04_slurm_templates.sh  # 生成模板
# sbatch slurm_small_gpu.sh
