#!/bin/bash
#SBATCH --job-name=fire_mpi
#SBATCH --partition=mpi        # 根据 ~/job_example/mpijob 修改
#SBATCH --nodes=2
#SBATCH --ntasks=8
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=2:00:00
#SBATCH --output=logs/%j_mpi.out

module load mpi/openmpi 2>/dev/null
module load python/3.12 2>/dev/null || true

mpirun --version
mpicc -o fire_mpi fire_mpi_fixed.c forest.c -lm 2>&1 | head -n 20
mpirun -np 8 ./fire_mpi 60000

# 深度学习DDP同理: torchrun --nproc_per_node=4 train.py
