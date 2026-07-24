# wh-login02 资源分析报告 (基于 01_check_resources.sh 输出)

## 已确认资源
- 主机: wh-login02, CentOS 8, kernel 4.18.0-305
- CPU: 128 核 (nproc=128), 2.48GHz, load 13.75 (空闲)
- 内存: 总 251 GiB, 已用100Gi, 可用 145Gi, Free 128Gi -> 大内存节点
- 磁盘:
  - /data 33T (8.3G已用)
  - /work 20P (856T已用)
  - /public 1.2P
  - /opt 1.8T
  - / 438G
- 登录节点无GPU, 无nvcc, 无torch, 默认 python 2.7.18, 但有 /usr/local/python3.12/bin
- SLURM: `sinfo` 返回空表头，说明分区隐藏或需 `sinfo -a`，或使用 GridView (`/opt/gridview/slurm/bin`)
- job_example: 存在于 ~/job_example, 含 mpijob / ompjob / serialjob 三类

## 待查
- GPU型号: 需 `srun --gres=gpu:1 nvidia-smi` 或 `sinfo -a -o "%P %G %m"` 查看计算节点
- job_example 内容: 需 cat
- module 系统: `module avail` 查看 cuda, conda, python
- conda: 未安装，需自行安装 miniconda 到 /work

## 深度学习训练建议 (基于 128核/251GB)

### 情况A: 仅CPU (当前登录节点可直接跑小训练)
- 适合: QSAR, omics分类器 (logistic, RF, XGBoost), scRNA-seq预处理, 小MLP
- 配置: 
  - num_workers = 32 (你CPU/4)
  - batch = 256-1024 (内存大)
  - torch 用 CPU: `device=cpu`, 可用 `torch.set_num_threads(32)`

### 情况B: GPU计算节点 (需sbatch提交)
- 必须先查GPU: 常见 V100 32GB, A100 40/80GB, 3090 24GB
- 若是 V100/A100: 可跑 ESMFold 400aa+, scVI 200k细胞, chromBPNet 推理
- 若是 80GB A100: 可跑 chromBPNet 训练
- 登录节点禁止直接训练，需写 SLURM 脚本

### HPC特化优化
- 251GB内存可一次性加载 100万细胞 x 2000基因 矩阵
- 128核适合 `scanpy` 高并行预处理: `sc.pp.* n_jobs=32`
- /work 20P 适合存大模型权重

