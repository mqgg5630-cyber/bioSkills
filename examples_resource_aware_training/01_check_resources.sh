#!/bin/bash
# ===============================
# 容器/服务器 资源配置一键检测脚本
# 适用于 wh-login02 这种 HPC 登录节点 + GPU 节点
# ===============================
echo "========== 1. 主机名与系统 =========="
hostname; uname -a; cat /etc/os-release 2>/dev/null | head -n 10

echo ""
echo "========== 2. CPU 配置 =========="
lscpu | grep -E "Model name|Architecture|CPU\(s\)|Thread|Core|MHz"
echo "--- nproc ---"
nproc
echo "--- load average ---"
cat /proc/loadavg

echo ""
echo "========== 3. 内存配置 =========="
free -h
echo "--- /proc/meminfo 前20行 ---"
head -n 20 /proc/meminfo

echo ""
echo "========== 4. 磁盘与配额 =========="
df -h | head -n 20
echo "--- 当前目录大小 ---"
du -sh . 2>/dev/null
echo "--- home 配额 (若有) ---"
quota -s 2>&1 | head -n 20

echo ""
echo "========== 5. GPU 配置 (nvidia-smi) =========="
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    echo "--- GPU 详细拓扑 ---"
    nvidia-smi topo -m 2>&1 | head -n 30
else
    echo "nvidia-smi 未找到，当前节点可能无GPU，或需在计算节点执行:"
    echo "  srun --gres=gpu:1 nvidia-smi"
fi

echo ""
echo "========== 6. CUDA / 驱动 =========="
echo "CUDA compiler:"
which nvcc && nvcc --version || echo "nvcc 未找到"
echo "Python torch cuda:"
python3 -c "import torch; print(f'torch {torch.__version__}, cuda available: {torch.cuda.is_available()}, count: {torch.cuda.device_count()}'); [print(f'  GPU{i}: {torch.cuda.get_device_name(i)}, mem: {torch.cuda.get_device_properties(i).total_memory/1024**3:.1f}GB') for i in range(torch.cuda.device_count())]" 2>&1

echo ""
echo "========== 7. SLURM 集群资源 =========="
if command -v sinfo &> /dev/null; then
    echo "--- sinfo 分区 ---"
    sinfo --format="%P %a %l %D %T %C %m %G" | head -n 50
    echo "--- sinfo 详细 ---"
    sinfo -o "%P %a %G %m %c %D %N" | head -n 100
else
    echo "sinfo 未找到，非SLURM集群"
fi
if command -v squeue &> /dev/null; then
    echo "--- squeue 我的作业 ---"
    squeue -u $USER | head -n 50
fi
if command -v scontrol &> /dev/null; then
    echo "--- 常用GPU分区详情 (尝试 gpus, gpu, A100 等) ---"
    for part in gpu gpus A100 V100 3090; do scontrol show partition $part 2>&1 | head -n 30; done
fi

echo ""
echo "========== 8. job_example 目录 =========="
if [ -d "job_example" ]; then
    ls -R job_example
    echo "--- 示例脚本内容 ---"
    find job_example -type f | xargs -I{} sh -c 'echo "----- {} -----"; cat {} | head -n 100; echo'
else
    echo "未找到 job_example (在 $(pwd))"
    find ~ -maxdepth 3 -type d -name "*job*" 2>/dev/null | head -n 20
fi

echo ""
echo "========== 9. Conda / 环境 =========="
which python; python --version
which conda 2>&1; conda info 2>&1 | head -n 40 || echo "conda未激活"
pip list 2>&1 | grep -E "torch|tensorflow|jax|transformers|scvi|scanpy|esm" | head -n 40

echo ""
echo "========== 10. 建议的资源使用策略 =========="
python3 << 'PY'
import psutil, os
try:
    import torch
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    if gpu_count>0:
        for i in range(gpu_count):
            prop = torch.cuda.get_device_properties(i)
            mem_gb = prop.total_memory/1e9
            print(f"GPU {i} {prop.name}: {mem_gb:.1f} GB")
            if mem_gb < 10:
                print("  -> 小显存卡 (8GB): 建议 batch_size 8-32, 梯度累积, fp16 必须, 模型小")
            elif mem_gb < 30:
                print("  -> 中显存卡 (24GB 3090/A10): batch_size 32-128, fp16/bf16, 可跑 ESMFold 400aa, scVI")
            else:
                print("  -> 大显存卡 (40-80GB A100): batch_size 128+, 可跑 chromBPNet, ESMFold 长序列, 多GPU DDP")
    else:
        print("未检测到GPU，建议先申请GPU节点: srun --gres=gpu:1 --partition=gpu --pty bash")
except Exception as e:
    print(e)

print(f"\nCPU核数: {os.cpu_count()}, 建议 DataLoader num_workers = {max(1, os.cpu_count()//4)}")
PY

echo "检测完成！"
