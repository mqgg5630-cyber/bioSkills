# 资源自适应深度学习训练指南 - 针对 wh-login02 容器 / HPC

本目录为你在 `scnlizwblw@wh-login02 ~]$ ls -> job_example` 这种 HPC 登录节点环境下提供的完整解决方案。

## 1. 在容器内查看资源配置

登录后立即运行：

```bash
# 克隆本项目
git clone https://github.com/mqgg5630-cyber/bioSkills.git
cd bioSkills

# 一键检测
bash examples_resource_aware_training/01_check_resources.sh
```

该脚本会自动检测：

| 检测项 | 命令 | 关键输出 |
|--------|------|----------|
| CPU | `lscpu`, `nproc` | 核数、型号、主频 |
| 内存 | `free -h`, `/proc/meminfo` | 总内存、可用 |
| GPU | `nvidia-smi`, `torch.cuda` | 型号、显存、驱动、CUDA |
| 磁盘 | `df -h`, `quota -s` | 剩余空间 |
| SLURM | `sinfo`, `squeue`, `scontrol show partition` | 分区、QOS、G资源 |
| 示例作业 | `ls -R job_example` | 你集群提供的模板 |

### 典型 wh-login02 集群你应该看到：

```bash
ls job_example
# 可能包含:
# gpu_job.sh  cpu_job.sh  pytorch_example.sh  tensorflow_example.sh

cat job_example/*  # 查看官方推荐的 #SBATCH 参数
sinfo --format="%P %G %m %c"  # 查看所有分区GPU类型和内存
```

`job_example` 通常告诉你：
- 分区名是 `gpu` 还是 `gpus` 还是 `A100`
- 提交是 `sbatch gpu_job.sh` 还是 `srun --gres=gpu:1 --pty bash`
- 是否需要 `module load cuda`

## 2. 克隆后目录结构

```
bioSkills/
├── machine-learning/          # omics分类、生物标志物 (可用小GPU)
├── single-cell/               # scArches/scANVI (需 16GB+)
├── structural-biology/        # ESMFold (150aa~8GB, 400aa~24GB, 800aa~80GB)
├── chip-seq/chip-deep-learning  # chromBPNet 训练 (A100 80G + 80GB RAM)
├── atac-seq/deep-learning-atac  # 同上
└── examples_resource_aware_training/  # 本次新增的资源自适应示例
    ├── 01_check_resources.sh
    ├── 02_train_pytorch_adaptive.py
    ├── 03_train_biology_dl_examples.py
    ├── 04_slurm_templates.sh
    └── 05_clone_and_run.sh
```

## 3. 根据资源配置进行深度学习训练

### 决策树

```
检测到GPU?
├─ 无GPU (登录节点) -> 用 CPU 预处理，或 srun 申请GPU节点
│  srun --gres=gpu:1 --partition=gpu --pty bash
│  nvidia-smi
├─ 显存 <10GB (T4, 1080)
│  batch=16 + grad_accum=4 + fp16
│  推荐: machine-learning/omics-classifiers, QSAR, 小MLP
├─ 显存 24GB (3090, A10, V100)
│  batch=64, fp16, num_workers=4-8
│  推荐: scArches 100k cells, ESMFold <=400aa, CellTypist, Atac
└─ 显存 80GB (A100)
   batch=128+, bf16, DDP多卡
   推荐: chromBPNet训练, Enformer推理1M变体, scVI 200k+, ESMFold 800aa+
```

### 3.1 通用 PyTorch 自适应模板

`02_train_pytorch_adaptive.py` 已实现：
- 自动检测显存 -> 自动 batch_size
- 自动混合精度 `torch.amp.autocast`
- 梯度累积解决显存不足
- 多卡 DDP 支持 (`torchrun`)

直接运行：

```bash
python examples_resource_aware_training/02_train_pytorch_adaptive.py
# 多卡:
torchrun --nproc_per_node=2 examples_resource_aware_training/02_train_pytorch_adaptive.py
```

迁移到你的数据：把 `DummyOmicsDataset` 换成 `adata.X` 或 `one-hot DNA` 即可。

### 3.2 3个生物真实例子

见 `03_train_biology_dl_examples.py` :

1. **scRNA-seq 注释迁移 (scArches)**
   - 对应 skill: `single-cell/cell-annotation`, `batch-integration`
   - 资源: `n_latent` 和 `batch_size` 按显存自适应
   ```python
   scvi.model.SCVI(..., n_latent=256)
   model.train(batch_size=512, accelerator='gpu')
   ```

2. **ESMFold 蛋白结构预测**
   - 对应 skill: `structural-biology/modern-structure-prediction`
   - 显存公式 ~ L²: 150aa 8GB, 400aa 24GB, 800aa 80GB
   - 自动截断 + fp16 推理
   ```python
   with torch.autocast('cuda', dtype=torch.float16):
       pdb = model.infer_pdb(seq[:400])
   ```

3. **chromBPNet 变体效应**
   - 对应 skill: `atac-seq/deep-learning-atac`, `chip-seq/chip-deep-learning`
   - 训练需 A100 1天，推理 16GB即可
   ```bash
   bash atac-seq/deep-learning-atac/examples/chrombpnet_pipeline.sh ...
   ```

4. **QSAR 小分子**
   - 对应 skill: `chemoinformatics/qsar-modeling`
   - 轻量级，CPU/小GPU均可，ChemBERTa embedding

### 3.3 SLURM 提交

本项目已根据 `job_example` 推断生成5个模板：

```bash
bash examples_resource_aware_training/04_slurm_templates.sh
# 生成:
# slurm_small_gpu.sh  (8GB)
# slurm_medium_gpu.sh (24GB)
# slurm_large_gpu.sh  (A100 80GB)
# slurm_multi_gpu.sh  (2x GPU DDP)
# slurm_cpu_preprocess.sh

sbatch slurm_small_gpu.sh
squeue -u $USER
tail -f logs/*.out
```

**注意**: 在你的 wh-login02 上务必先 `cat job_example/*.sh` 把里面的 `#SBATCH --partition=xxx` 和 `#SBATCH --gres=gpu:xxx` 改成你集群真实的名称。运行 `sinfo` 查看。

## 4. 完整一键流程 (复制到 wh-login02)

```bash
pwd; ls job_example; cat job_example/*
sinfo -O "Partition,Avail,Gres,Memory,CPUs"

git clone https://github.com/mqgg5630-cyber/bioSkills.git
cd bioSkills
bash examples_resource_aware_training/01_check_resources.sh

conda create -n bio python=3.10 -y
conda activate bio
pip install torch scvi-tools scanpy esm biopython

python examples_resource_aware_training/02_train_pytorch_adaptive.py
python examples_resource_aware_training/03_train_biology_dl_examples.py
```

## 5. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `nvidia-smi` not found | 在登录节点 | `srun --gres=gpu:1 --pty bash` 申请计算节点 |
| OOM `CUDA out of memory` | batch太大 | 降低 batch_size, 开启 `fp16` + `grad_accum`，代码已自适应 |
| `sbatch: Invalid partition` | 分区名错误 | `sinfo` 查看真实分区名，改模板 |
| ESMFold 预测慢 | 无GPU或序列太长 | 限长 <400aa 或用 CPU 预处理 |
| chromBPNet 训练 killed | 内存不足 | `--mem=80G` 以上, 需 A100 分区 |

---

作者: bioSkills 项目，已适配 HPC 资源感知训练。
