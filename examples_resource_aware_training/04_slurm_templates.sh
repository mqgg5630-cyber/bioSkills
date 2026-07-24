#!/bin/bash
# SLURM 模板 - 根据 wh-login02 集群的 job_example 改编
# 你需要查看 job_example 目录里真实的 partition 名称
# 常见命名: gpu, gpus, A100, V100, 3090, cpu, medium

# ==================== 公共检查: 查看分区 ====================
# 在 wh-login02 终端运行:
# sinfo -o "%P %a %l %D %T %C %m %G %f"
# scontrol show partition gpu
# sacctmgr show qos

# ==================== 模板1: 小显存GPU (T4/8GB) 训练 omics分类 ====================
cat > slurm_small_gpu.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=dl_small
#SBATCH --partition=gpu          # 改成你 sinfo 看到的实际分区，如 gpus, gpu, small-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%j_small.out
#SBATCH --error=logs/%j_small.err

module load cuda/11.8 2>/dev/null || module load cuda 2>/dev/null
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bio  # 你的环境

mkdir -p logs
nvidia-smi

# 自适应小batch
python examples_resource_aware_training/02_train_pytorch_adaptive.py

# 或跑 bioSkills 例子:
# python machine-learning/omics-classifiers/examples/rf_xgboost_classifier.py --use-gpu
EOF

# ==================== 模板2: 中显存GPU (24GB 3090/A10) 单细胞/scArches/ESMFold ====================
cat > slurm_medium_gpu.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=dl_medium
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%j_medium.out
# #SBATCH --constraint=3090   # 如果集群用 constraint 区分卡型

module load cuda/12.1
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bio

nvidia-smi

# ESMFold 400aa以内
python - << 'PY'
import esm, torch
model = esm.pretrained.esmfold_v1().eval().cuda()
seq = "M"*350
with torch.autocast('cuda', dtype=torch.float16):
    pdb = model.infer_pdb(seq)
open("esmfold_350.pdb","w").write(pdb)
PY

# scArches 例子
python examples_resource_aware_training/03_train_biology_dl_examples.py
EOF

# ==================== 模板3: 大显存GPU (A100 80GB) chromBPNet / Enformer 训练 ====================
cat > slurm_large_gpu.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=dl_large
#SBATCH --partition=gpu
#SBATCH --gres=gpu:A100:1       # 或 gpu:1 + --constraint=A100
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=72:00:00
#SBATCH --output=logs/%j_large.out

module load cuda/12.1
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bio

nvidia-smi

# chromBPNet 训练 (需预先准备 BAM + peaks)
# 直接用 bioSkills workflow:
# bash atac-seq/deep-learning-atac/examples/chrombpnet_pipeline.sh atac.bam peaks.narrowPeak nonpeaks.bed hg38.fa hg38.chrom.sizes chrombpnet_out

# 大batch训练
torchrun --nproc_per_node=1 examples_resource_aware_training/02_train_pytorch_adaptive.py
EOF

# ==================== 模板4: 多卡 DDP (2x GPU) ====================
cat > slurm_multi_gpu.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=dl_ddp
#SBATCH --partition=gpu
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%j_ddp.out

module load cuda/12.1
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bio

nvidia-smi

# DDP启动，需要节点间通信, 单节点多卡用 torchrun
export OMP_NUM_THREADS=4
torchrun --nproc_per_node=2 examples_resource_aware_training/02_train_pytorch_adaptive.py

# 或多节点: 
# srun torchrun --nproc_per_node=2 --nnodes=2 --node_rank=$SLURM_NODEID --master_addr=$(scontrol show hostnames $SLURM_JOB_NODELIST | head -n1) examples_resource_aware_training/02_train_pytorch_adaptive.py
EOF

# ==================== 模板5: 只在CPU的预处理/特征工程 ====================
cat > slurm_cpu_preprocess.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=dl_pre
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=6:00:00
#SBATCH --output=logs/%j_cpu.out

source ~/miniconda3/etc/profile.d/conda.sh
conda activate bio

# 例如: scanpy 预处理, 生成 h5ad
python - << 'PY'
import scanpy as sc
adata = sc.read_h5ad("raw.h5ad")
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.write("preprocessed.h5ad")
PY
EOF

echo "已生成 5 个 SLURM 模板:"
ls -lh slurm_*.sh
echo ""
echo "下一步在 wh-login02 上:"
echo "  cat slurm_small_gpu.sh"
echo "  sbatch slurm_small_gpu.sh"
echo "  squeue -u \$USER"
echo "  tail -f logs/*.out"

