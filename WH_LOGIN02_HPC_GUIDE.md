# wh-login02 HPC 集群实战指南 - 从资源检测到深度学习训练

> 适用于 `scnlizwblw@wh-login02` 这种 GridView + SLURM 混合集群，记录 2026-07-24 解决 github 443 被墙全过程

## 1. 资源配置 (来自 `01_check_resources.sh`)

| 项 | 值 | 说明 |
|---|---|---|
| 主机 | wh-login02, CentOS 8, kernel 4.18 | 登录节点 |
| CPU | 128 核 @2.48GHz, load 13 | 胖节点，`nproc=128` |
| 内存 | 251 GiB 总, 145 GiB 可用 | 可一次加载 100万细胞 |
| 磁盘 | /work 20PB, /data 33TB, /public 1.2PB | /work 放模型权重 |
| GPU | 登录节点无，计算节点需 `srun --gres=gpu:1 nvidia-smi` 查 |  |
| 软件 | 默认 python2.7, 有 /usr/local/python3.12/bin, 无 conda | 需自装 miniconda 到 /work |
| 调度 | `sinfo` 返回空表头，`~/job_example` 含 mpijob/ompjob/serialjob | GridView封装的SLURM |
| 路径 | `/opt/gridview/slurm/bin` etc | - |

### job_example 模板查看
```bash
ls -R ~/job_example
find ~/job_example -type f -exec echo "===== {} =====" \; -exec cat {} \;
# 通常含：mpijob/job.sh, ompjob/job.sh, serialjob/job.sh
# 重点看 #SBATCH --partition 和 --gres 配置
```

## 2. 遇到的问题与根因

### 问题1: `sinfo` 空表
```bash
sinfo --format="%P %a %l %D %T %C %m %G %f"
# 只返回表头，无分区
```
**根因**：GridView 管理平台隐藏分区，需 `sinfo -a` 或 `scontrol show partition`; 登录节点权限限制

**解决**：
```bash
sinfo -a
sinfo -a -o "%P %a %l %D %T %C %m %G %N"
scontrol show partition
module avail | grep -i cuda
```

### 问题2: `git pull https://github.com` 超时
```bash
git pull
fatal: 无法访问 'https://github.com/...': Failed to connect to github.com port 443: 连接超时
curl -v https://github.com --connect-timeout 5
# * Trying 20.205.243.166...
# * Connection timed out
ping -c2 github.com  # 却能通
```
**根因**：集群防火墙放行 ICMP (ping)，但拦截 TCP 443 到 `github.com` (20.205.243.166)。上午能克隆是间歇放行或DNS轮询到放行IP。

### 问题3: `ssh -T -p 443 git@ssh.github.com` Permission denied
```bash
debug1: SERVICE_ACCEPT received
debug1: Offering public key: id_rsa RSA SHA256:FEf9...
Permission denied (publickey)
```
**根因**：TCP 443 到 `ssh.github.com` 是通的！GitHub 特意开放 443 端口的SSH给被墙集群。但本地 `~/.ssh/id_rsa.pub` 未添加到 GitHub。

## 3. 解决方案：SSH over 443

这是本指南核心，适用于所有封 443 https 但放行 443 ssh 的HPC。

### 步骤1: 查看本地公钥
```bash
cat ~/.ssh/id_rsa.pub
# 若没有，生成：
ssh-keygen -t rsa -b 4096 -C "scnlizwblw@wh-login02"
```

### 步骤2: 添加到 GitHub
浏览器打开 https://github.com/settings/keys → New SSH key → Title 写 `wh-login02` → 粘贴公钥全文 → Add

### 步骤3: 验证
```bash
ssh -T -p 443 git@ssh.github.com
# 成功显示：Hi xxx! You've successfully authenticated...
```

### 步骤4: 改用443的SSH地址克隆/拉取
```bash
# 新克隆
GIT_SSH_COMMAND="ssh -p 443" git clone ssh://git@ssh.github.com:443/mqgg5630-cyber/bioSkills.git -b arena/019f92fc-bioskills --depth 1

# 已有仓库改远程地址，以后 git pull 都走443
cd ~/project/bioSkills
git remote set-url origin ssh://git@ssh.github.com:443/mqgg5630-cyber/bioSkills.git
git config core.sshCommand "ssh -p 443"
git config pull.rebase false
git pull
```

### 备选离线方案（无外网时最稳）
笔记本下载 zip → scp 上传 → 集群解压
```bash
# 本地浏览器下载：https://github.com/mqgg5630-cyber/bioSkills/archive/refs/heads/arena/019f92fc-bioskills.zip
scp arena.zip scnlizwblw@wh-login02:/work/home/scnlizwblw/project/
# 集群上
unzip -o arena.zip && cp -r bioSkills-*/examples_resource_aware_training ~/project/bioSkills/
```

## 4. 深度学习训练 - 根据 128核251GB 适配

### 4.1 通用自适应模板
`examples_resource_aware_training/02_train_pytorch_adaptive.py`
- 自动检测显存 → batch_size：
  - <10GB T4 → 16 + grad_accum 4 + fp16
  - 24GB 3090/V100 → 64 + fp16
  - 80GB A100 → 128+ bf16
- `num_workers = 32` (CPU/4), 充分利用128核
- `torch.amp.autocast` 混合精度, `DDP` 多卡支持

```bash
export PATH=/usr/local/python3.12/bin:$PATH
python3 examples_resource_aware_training/02_train_pytorch_adaptive.py
# 多卡DDP
torchrun --nproc_per_node=2 examples_resource_aware_training/02_train_pytorch_adaptive.py
```

### 4.2 生物专用例子
`03_train_biology_dl_examples.py`

| 例子 | 对应bioSkills skill | 显存公式 |
|---|---|---|
| scArches/scANVI 单细胞注释迁移 | single-cell/cell-annotation | 50k细胞 8GB, 100k 24GB, 200k+ 80GB; n_latent 128/256/512 |
| ESMFold 蛋白结构 | structural-biology/modern-structure-prediction | 150aa≈8GB, 400aa≈24GB, 800aa≈80GB, L^2 |
| chromBPNet 变体效应 | chip-seq/chip-deep-learning, atac-seq/deep-learning-atac | 训练需A100 1天, 推理16GB |
| QSAR ChemBERTa | chemoinformatics/qsar-modeling | 轻量CPU即可 |

### 4.3 SLURM模板 (已针对 wh-login02 128核定制)
位于 `examples_resource_aware_training/slurm_wh-login02/`：

- `serialjob.sh`: 32核200GB CPU大内存训练，无需GPU，直接跑 omics 分类
- `gpu_discovery.sh`: 30秒探针任务，查计算节点GPU型号 `nvidia-smi -L`
- `gpu_dl_training.sh`: 16核128GB + 1GPU，跑 PyTorch自适应训练
- `mpi_dl.sh`: 2节点8进程，跑 fire_mpi + DDP

提交：
```bash
mkdir -p logs
sbatch examples_resource_aware_training/slurm_wh-login02/gpu_discovery.sh
squeue -u $USER
cat logs/*gpu*
sbatch examples_resource_aware_training/slurm_wh-login02/serialjob.sh
```

### 4.4 Conda 安装 (你当前无conda)
```bash
cd /work/home/scnlizwblw
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p /work/home/scnlizwblw/miniconda3
export PATH=/work/home/scnlizwblw/miniconda3/bin:$PATH
echo 'export PATH=/work/home/scnlizwblw/miniconda3/bin:$PATH' >> ~/.bashrc
conda create -n bio python=3.10 pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
conda activate bio
pip install scanpy scvi-tools fair-esm biopython
```

## 5. 下一步 TODO

- [ ] `find ~/job_example -type f | xargs cat` → 确认真实分区名
- [ ] `sbatch slurm_wh-login02/gpu_discovery.sh` → 确认GPU型号
- [ ] `module avail` → 确认 cuda / mpi module
- [ ] 安装 miniconda 到 /work
- [ ] 跑 `02_train_pytorch_adaptive.py` CPU版，验证 128核环境
- [ ] 等GPU型号确认后，跑 `esmfold` / `scarches` 中等显存例子

## 6. 参考
- 本分支：`arena/019f92fc-bioskills`
- 检测脚本：`examples_resource_aware_training/01_check_resources.sh`, `01_check_resources_v2.sh`, `run_all.sh`
- 修复的MPI：`fire_mpi_fixed.c` (修正种子和平均)
- GitHub SSH over 443 官方文档：https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port

---
记录人：Arena Agent @ wh-login02, 2026-07-24
