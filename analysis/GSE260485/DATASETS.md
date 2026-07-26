# 现成 GEO 数据：仓库内查找结果 + 推荐克隆的外部仓库

## 一、bioSkills 仓库里有没有现成数据？

**没有。** 我把整个仓库扫了一遍：

```bash
# 大于 20KB 的非 markdown 文件 —— 只有两个，都是文档配图
./resources/benchmark_performance_20260328.png
./resources/bioskills_eval_20260328.pdf

# 数据类扩展名（csv/tsv/txt/gz/rds/h5ad/mtx/xlsx/RData）—— 只有一个，是空模板
./workflow-management/nf-core-pipelines/examples/samplesheet.csv
```

整个 repo 打包才 6.9 MiB，是一个**纯 skill 文档库**。里面出现的 GSE 编号（GSE123456、GSE12345、GSE52778 等）全是 SKILL.md 里的**代码示例占位符**，不带任何实际数据文件。

所以想跑真数据，必须从外部拿。

---

## 二、推荐的外部仓库（都已实测可克隆、数据已验证）

### ⭐ 首选：`mousepixels/sanbomics_scripts`

```bash
git clone https://github.com/mousepixels/sanbomics_scripts.git
```

| | |
|---|---|
| 体积 | 35 MB（可稀疏检出，只要 2.2 MB 的那个表） |
| Star | 472 |
| 关键文件 | `count_table_for_deseq_example.csv` |
| 内容 | **60,663 基因 × 8 样本**人类 RNA-seq 原始整数 counts，Ensembl ID |
| 分组 | `Ctr_s1/s2/s7/s13`（对照 ×4） vs `RS_s6/s9/s12/s16`（处理 ×4） |
| 文库大小 | 9.0M – 16.5M reads，均衡 |
| 附带教程 | `PyDeseq2_DE_tutorial.ipynb`、`pseudobulk_pyDeseq2.ipynb`、`salmon_to_deseq.Rmd` |

**我已经用它实跑验证过**（pydeseq2 0.5.4 + plotnine 0.15.7）：

```
counts (8, 19611)   # 过滤 sum>=10 后
tested 14447, sig 626 (up 287, down 339)   # padj<0.05 & |LFC|>1
volcano OK
```

火山图正常出图。这是**唯一一个我在本沙箱里从头到尾真跑通了 DESeq2→出图全流程**的数据集，推荐你先用它。

---

### 备选 A：`hbctraining/DGE_workshop_salmon_online`（哈佛 HBC 官方教程）

```bash
git clone https://github.com/hbctraining/DGE_workshop_salmon_online.git
```

| | |
|---|---|
| 体积 | 172 MB（偏大） |
| Star | 221，2026-05 仍在更新 |
| 数据 | `data/raw_counts_mouseKO.csv`（3.6 MB，小鼠 KO counts）、`data/annotations_ahb.csv`（2.4 MB 基因注释）、`data/tx2gene_grch38_ens94.txt`（8.9 MB，salmon→gene 映射）、`data/Mov10_full_meta.txt` |

优点：教材质量最高，DESeq2 讲解配套完整，注释文件齐全（做 ID 映射很方便）。缺点：仓库大，counts 是小鼠的。

---

### 备选 B：`jmzeng1314/GEO`（生信技能树，中文）

```bash
git clone https://github.com/jmzeng1314/GEO.git      # 384 MB，建议稀疏检出
```

| | |
|---|---|
| Star | 879 |
| **真·GEO 原始格式** | `GSE42872_main/GSE42872_series_matrix.txt.gz`（750 KB，**33,297 探针**，GPL6244 芯片） |
| 数据集 | GSE42872：A375 黑色素瘤细胞 DMSO vs 维罗非尼，3v3 |
| 还有 | `airway_RNAseq/`（GSE52778 经典气道平滑肌 dex 数据的 SraRunTable + 表达矩阵 Rdata）、GSE11121 生存分析、TCGA-BRCA 子集 |

**唯一一个带真正 GEO series_matrix 原始格式的**，如果你想练 `GEOquery::getGEO()` / 探针注释 / 芯片流程，选这个。缺点：384 MB，2022 年后不更新，注释是中文。

---

## 三、稀疏检出：只要数据文件，不下整个仓库

三个仓库都有点大。用这招只拉你要的文件：

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/mousepixels/sanbomics_scripts.git
cd sanbomics_scripts
git sparse-checkout set --no-cone /count_table_for_deseq_example.csv
ls    # 只有那 2.2 MB 一个文件
```

我把这个过程封装成了脚本：

```bash
bash analysis/GSE260485/scripts/00_fetch_offline_dataset.sh sanbomics
bash analysis/GSE260485/scripts/00_fetch_offline_dataset.sh airway
```

文件会落到 `analysis/GSE260485/data/`。

---

## 四、为什么要有这个备用数据源

GSE260485 的正式流程（`01_download.sh`）需要访问 `ftp.ncbi.nlm.nih.gov`。在以下情况会失败：

- 公司/校园防火墙拦截 NCBI
- 国内网络直连 NCBI 不稳定
- CI 沙箱出网受限（本 Arena 沙箱就是这种情况，NCBI 全部超时）

这时先用 `00_fetch_offline_dataset.sh` 拿 GitHub 上的现成 counts，照样能把 DESeq2 + ggplot2 全流程跑通、把脚本调试好，等你到能连 NCBI 的机器上再换回真 GSE260485 数据。

**两者的 counts 矩阵格式一致**（行=基因 Ensembl ID，列=样本，值=整数 counts），`02_deseq2.R` 只需改一下读入的文件名和分组解析规则。

---

## 五、Python 路线（如果你不想装 R）

沙箱实测：`pip install pydeseq2 plotnine` 可用，纯 Python 就能做完 DESeq2 + ggplot 语法出图。

```bash
pip install pydeseq2 plotnine pandas numpy
```

```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds  import DeseqStats
from plotnine import *
import pandas as pd, numpy as np

c  = pd.read_csv('count_table_for_deseq_example.csv').set_index('Geneid')
c  = c[c.sum(axis=1) >= 10].T                       # 样本为行
md = pd.DataFrame({'condition': ['C']*4 + ['RS']*4}, index=c.index)

dds = DeseqDataSet(counts=c, metadata=md, design="~condition")
dds.deseq2()
st = DeseqStats(dds, contrast=['condition','RS','C']); st.summary()
r  = st.results_df.dropna(subset=['padj'])

r = r.assign(nlp=-np.log10(r.padj.clip(lower=1e-300)),
             cls=np.where((r.padj<.05)&(r.log2FoldChange> 1),'Up',
                 np.where((r.padj<.05)&(r.log2FoldChange<-1),'Down','n.s.')))
(ggplot(r, aes('log2FoldChange','nlp',color='cls'))
 + geom_point(size=.5, alpha=.6)
 + scale_color_manual({'Up':'#D55E00','Down':'#0072B2','n.s.':'#CCCCCC'})
 + theme_bw()).save('volcano.png', width=6, height=5, dpi=150)
```

⚠️ 两个实测踩到的坑：
1. plotnine **不认 R 的颜色名**（`grey80` 会报 `Unknown name for a color`），必须用十六进制 `#CCCCCC`。
2. pydeseq2 新版参数是 `metadata=` 和 `design=`，不是老教程里的 `clinical=` 和 `design_factors=`（sanbomics 那个 notebook 是旧 API，照抄会报错）。
