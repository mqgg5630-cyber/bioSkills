"""
资源自适应 PyTorch 深度学习训练模板
- 自动检测 GPU 显存 -> 调整 batch size
- 自动使用 mixed precision (fp16/bf16)
- 支持单卡 / 多卡 DDP
- 适用于生物数据: omics分类, scRNA-seq, 蛋白序列

在 bioSkills 中对应:
- machine-learning/omics-classifiers
- single-cell/cell-annotation (scArches/scANVI)
- structural-biology/modern-structure-prediction (ESMFold)
"""

import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ===== 1. 资源检测 =====
def detect_resources():
    print("=== 资源检测 ===")
    cpu_count = os.cpu_count()
    print(f"CPU cores: {cpu_count}")

    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        for i in range(gpu_count):
            prop = torch.cuda.get_device_properties(i)
            print(f"GPU {i}: {prop.name}, total_mem: {prop.total_memory/1e9:.2f} GB, major:{prop.major}.{prop.minor}")
        # 以0号卡为例估算 batch size
        mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if mem_gb < 10:
            batch_size, accum_steps, precision = 16, 4, "fp16"
        elif mem_gb < 30:
            batch_size, accum_steps, precision = 64, 2, "fp16"
        else:
            batch_size, accum_steps, precision = 128, 1, "bf16"  # A100 支持 bf16
        print(f"推荐配置: batch_size={batch_size}, grad_accum={accum_steps}, precision={precision}")
    else:
        batch_size, accum_steps, precision = 32, 1, "fp32"
        print("无GPU，使用CPU训练")
    return batch_size, accum_steps, precision

# ===== 2. 示例数据集 (替换为你的生物数据) =====
# 例如: gene expression matrix, one-hot encoded DNA, protein sequence embeddings
class DummyOmicsDataset(Dataset):
    def __init__(self, n=1000, features=512, classes=2):
        self.X = torch.randn(n, features)
        self.y = torch.randint(0, classes, (n,))
    def __len__(self): return len(self.X)
    def __getitem__(self, idx): return self.X[idx], self.y[idx]

# ===== 3. 模型 (可替换为 bioSkills 中的模型) =====
class SimpleOmicsClassifier(nn.Module):
    def __init__(self, in_dim=512, hidden=256, out=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, out)
        )
    def forward(self, x): return self.net(x)

# ===== 4. 资源自适应训练循环 =====
def train():
    batch_size, accum_steps, precision = detect_resources()

    # 自动选择 device & mixed precision
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = torch.cuda.is_available()

    # 根据显存自动选择 dtype
    if precision == "bf16" and torch.cuda.is_bf16_supported():
        amp_dtype = torch.bfloat16
    else:
        amp_dtype = torch.float16

    scaler = torch.amp.GradScaler('cuda', enabled=use_amp and precision=="fp16")

    dataset = DummyOmicsDataset()
    # num_workers 自适应: 通常 CPU//4, 但在 HPC 中避免过高导致 IO 爆炸
    num_workers = min(8, max(1, (os.cpu_count() or 4)//2))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True)

    model = SimpleOmicsClassifier().to(device)

    # 多GPU DDP 支持 (在 SLURM 中用 torchrun 启动)
    # torchrun --nproc_per_node=2 02_train_pytorch_adaptive.py
    if torch.cuda.device_count() > 1 and "RANK" in os.environ:
        torch.distributed.init_process_group(backend="nccl")
        local_rank = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(local_rank)
        model = nn.parallel.DistributedDataParallel(model, device_ids=[local_rank])

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    print(f"\n开始训练: device={device}, amp={use_amp}, dtype={amp_dtype}, workers={num_workers}")
    for epoch in range(3):
        model.train()
        total_loss = 0
        optimizer.zero_grad()
        for step, (x, y) in enumerate(loader):
            x, y = x.to(device), y.to(device)
            # autocast 混合精度
            with torch.amp.autocast('cuda', dtype=amp_dtype, enabled=use_amp):
                logits = model(x)
                loss = nn.functional.cross_entropy(logits, y) / accum_steps
            scaler.scale(loss).backward() if use_amp and precision=="fp16" else loss.backward()

            if (step+1) % accum_steps == 0:
                if use_amp and precision=="fp16":
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                optimizer.zero_grad()
            total_loss += loss.item()*accum_steps

        print(f"Epoch {epoch}: loss={total_loss/len(loader):.4f}")

    # 保存时只在 rank0 保存
    if os.environ.get("RANK", "0") == "0":
        torch.save(model.state_dict(), "adaptive_model.pt")
        print("模型已保存 adaptive_model.pt")

if __name__ == "__main__":
    train()
