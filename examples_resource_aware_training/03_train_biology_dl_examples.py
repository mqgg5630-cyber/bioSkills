"""
基于 bioSkills 的 3 个真实生物深度学习例子，全部资源自适应

1. scRNA-seq 注释迁移: scArches / scANVI (single-cell/cell-annotation)
2. 蛋白结构预测: ESMFold (structural-biology/modern-structure-prediction)
3. ChIP-seq 深度学习: chromBPNet + 变体效应 (chip-seq/chip-deep-learning, atac-seq/deep-learning-atac)

每个例子都展示如何根据 GPU 显存自动调整
"""

import torch, os, sys

def get_gpu_mem_gb():
    if torch.cuda.is_available():
        return torch.cuda.get_device_properties(0).total_memory / (1024**3)
    return 0

# ========== 例子1: scArches / scANVI 单细胞注释 ==========
"""
适用: 你有一个参考图谱(已标注), 想把query映射上去
资源需求:
- 小卡 8GB: latent_dim 128, batch 256, 只能做 <50k cells
- 中卡 24GB: latent_dim 256, batch 512, 可做 100k
- 大卡 80GB: latent_dim 512, batch 1024, >200k cells
对应 bioSkills: single-cell/cell-annotation, batch-integration
"""
def example_scarche():
    print("\n=== Example 1: scArches/scANVI ===")
    mem = get_gpu_mem_gb()
    n_latent = 128 if mem < 10 else 256 if mem < 30 else 512
    batch_size = 256 if mem < 10 else 512 if mem < 30 else 1024

    code = f'''
import scvi
import scanpy as sc

# 参考图谱需 raw counts 在 adata.layers['counts']
ref = sc.read_h5ad('reference_annotated.h5ad')
query = sc.read_h5ad('query.h5ad')

scvi.model.SCVI.setup_anndata(ref, layer='counts', batch_key='batch')
model = scvi.model.SCVI(ref, n_latent={n_latent}, n_layers=2, gene_likelihood='nb')
model.train(max_epochs=20, batch_size={batch_size}, accelerator='gpu' if torch.cuda.is_available() else 'cpu')

# scArches迁移
scvi.model.SCVI.prepare_query_anndata(query, model)
query_model = scvi.model.SCVI.load_query_data(query, model)
query_model.train(max_epochs=10, plan_kwargs=dict(weight_decay=0))

query.obsm['X_scVI'] = query_model.get_latent_representation()
# 再用 scANVI 做半监督标注: scvi.model.SCANVI.from_scvi_model(...)
'''
    print(code)
    print(f"根据显存 {mem:.1f}GB 自动设置 n_latent={n_latent}, batch={batch_size}")

# ========== 例子2: ESMFold 蛋白结构预测 ==========
"""
资源需求: ESMFold 显存 ~ 序列长度²
- 150aa ~ 8GB
- 400aa ~ 24GB
- 800aa+ ~ 40GB+ 需要 A100
超长需分段或用 ESMFold API

bioSkills: structural-biology/modern-structure-prediction
"""
def example_esmfold():
    print("\n=== Example 2: ESMFold ===")
    mem = get_gpu_mem_gb()
    max_len = 150 if mem < 10 else 400 if mem < 30 else 800
    code = f'''
import torch, esm

# 自动检测: 若 mem={mem:.1f}GB, 建议 max_len < {max_len}
model = esm.pretrained.esmfold_v1().eval()
model = model.to('cuda' if torch.cuda.is_available() else 'cpu')

sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH..."
if len(sequence) > {max_len}:
    print("序列过长，建议截断或分段，避免OOM")
    sequence = sequence[:{max_len}]

with torch.no_grad():
    # fp16 推理省显存
    with torch.autocast('cuda', dtype=torch.float16):
        pdb_str = model.infer_pdb(sequence)

open('esmfold_pred.pdb','w').write(pdb_str)
print("pLDDT 在 B-factor 列")
'''
    print(code)

# ========== 例子3: chromBPNet / Enformer 变体效应 ==========
"""
资源需求:
- chromBPNet 训练: 1x A100 24h, 80GB RAM
- 推理: 16GB 即可, batch_size自适应
- Enformer: 推理需 V100+, 196kb 窗口

bioSkills: atac-seq/deep-learning-atac, chip-seq/chip-deep-learning
"""
def example_chrombpnet():
    print("\n=== Example 3: chromBPNet variant effect ===")
    mem = get_gpu_mem_gb()
    batch = 8 if mem < 10 else 32 if mem < 30 else 64
    code = f'''
# 假设已有训练好的 chromBPNet model.h5
import tensorflow as tf
# 限制显存增长
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)

model = tf.keras.models.load_model('chrombpnet_nobias.h5', compile=False)

# 自适应 batch: {batch}
def encode_one_hot(seq):
    mapping = dict(A=[1,0,0,0],C=[0,1,0,0],G=[0,0,1,0],T=[0,0,0,1])
    return __import__('numpy').array([mapping.get(b,[0,0,0,0]) for b in seq]).T

# ref/alt 2114bp 窗口，变体居中
ref_seq = "N"*1000 + "C" + "N"*1000  # 替换为真实序列
alt_seq = "N"*1000 + "T" + "N"*1000

import numpy as np
ref_ohe = encode_one_hot(ref_seq)[None,...].transpose(0,2,1)
alt_ohe = encode_one_hot(alt_seq)[None,...].transpose(0,2,1)

ref_prof, ref_counts = model.predict(ref_ohe, batch_size={batch})
alt_prof, alt_counts = model.predict(alt_ohe, batch_size={batch})
log2fc = np.log2(alt_counts/ref_counts)
print(f"log2FC={{log2fc[0]}}  |log2FC|>1 为强效应")
'''
    print(code)

# ========== 例子4: QSAR / chemoinformatics 小分子性质预测 ==========
"""
bioSkills: chemoinformatics/qsar-modeling, admet-prediction
资源小，可在 CPU或小GPU跑
"""
def example_qsar():
    print("\n=== Example 4: QSAR (小分子) - 轻量级 ===")
    code = '''
from rdkit import Chem
from rdkit.Chem import Descriptors
import torch, torch.nn as nn

# 传统描述符 + MLP，几GB显存即可
# 更大模型 (ChemBERTa, Uni-Mol) 需大显存
# 可用 HuggingFace transformers + torch amp

from transformers import AutoTokenizer, AutoModel
tok = AutoTokenizer.from_pretrained("seyonec/ChemBERTa-zinc-base-v1")
model = AutoModel.from_pretrained("seyonec/ChemBERTa-zinc-base-v1").to('cuda' if torch.cuda.is_available() else 'cpu')

smiles = ["CCO", "CC(=O)O", "c1ccccc1"]
inputs = tok(smiles, padding=True, truncation=True, return_tensors='pt').to(model.device)
with torch.no_grad():
    with torch.autocast('cuda', dtype=torch.float16, enabled=torch.cuda.is_available()):
        out = model(**inputs).last_hidden_state[:,0,:]
print(out.shape)  # embedding
'''
    print(code)

if __name__ == "__main__":
    example_scarche()
    example_esmfold()
    example_chrombpnet()
    example_qsar()
