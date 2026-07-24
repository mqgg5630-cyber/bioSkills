#!/bin/bash
echo "========== wh-login02 资源诊断 v2 =========="
echo "当前目录: $(pwd)"
ls -la
echo ""
echo "=== job_example 详细 ==="
if [ -d ~/job_example ]; then
  echo "Found ~/job_example"
  ls -lhR ~/job_example 2>&1
  find ~/job_example -type f -exec echo "---- {} ----" \; -exec cat {} \; -exec echo "" \;
elif [ -d ./job_example ]; then
  ls -lhR ./job_example
  find ./job_example -type f -exec echo "---- {} ----" \; -exec cat {} \; 
else
  find ~ -maxdepth 3 -type f -name "*.sh" 2>/dev/null | head -n 30
fi

echo ""
echo "=== 调度器检测 ==="
echo "SLURM: $(which sinfo squeue sbatch srun 2>&1)"
echo "PBS/Torque: $(which qstat qsub pbsnodes 2>&1)"
echo "LSF: $(which bjobs 2>&1)"

echo ""
echo "=== SLURM sinfo 尝试多种格式 ==="
sinfo 2>&1 | head -n 100
sinfo --format="%P %a %l %D %T %C %m %G %f" 2>&1 | head -n 100
sinfo -o "%20P %5a %10l %5D %6t %20C %10m %20G %20f %20N" 2>&1 | head -n 100
scontrol show partition 2>&1 | head -n 200
scontrol show config 2>&1 | grep -E "ClusterName|SlurmctldHost|NodeName" | head -n 50

echo ""
echo "=== PBS qstat ==="
qstat -Q 2>&1 | head -n 50
qstat -q 2>&1 | head -n 100
pbsnodes -a 2>&1 | head -n 200

echo ""
echo "=== 环境变量 (PBS/SLURM) ==="
env | grep -E "PBS|SLURM|CUDA|MPI" | sort

echo ""
echo "=== CPU/内存 ==="
lscpu | head -n 30; nproc; free -h

echo ""
echo "=== GPU ==="
nvidia-smi 2>&1 || echo "nvidia-smi 无, 尝试 srun"
which nvidia-smi
ls /usr/local/cuda/bin/ 2>&1 | head
ls /dev/nvidia* 2>&1 | head

echo ""
echo "=== MPI ==="
which mpicc mpirun mpiexec
mpicc --version 2>&1 | head
ompi_info 2>&1 | head -n 30 || mpichversion 2>&1 | head

echo ""
echo "=== Conda/Python ==="
which python python3 conda pip
python3 -c "import sys; print(sys.version)"
pip list 2>&1 | grep -E "torch|mpi|numpy" | head -n 20
