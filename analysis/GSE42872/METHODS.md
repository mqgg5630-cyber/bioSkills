# GSE42872 完整流程方法学文档

芯片差异表达分析的**全流程、全参数、全依赖**说明。写给三类人：想复现的、想改参数的、想知道"这数据还能干什么"的。

---

## 目录

1. [数据规模：这数据到底大不大](#1-数据规模这数据到底大不大)
2. [软件依赖与版本](#2-软件依赖与版本)
3. [流程总览](#3-流程总览)
4. [Step 1 — 取数](#4-step-1--取数)
5. [Step 2 — 解析与样本表](#5-step-2--解析与样本表)
6. [Step 3 — 探针注释](#6-step-3--探针注释)
7. [Step 4 — limma 差异表达](#7-step-4--limma-差异表达)
8. [Step 5 — 可视化](#8-step-5--可视化)
9. [Step 6 — 验证](#9-step-6--验证)
10. [参数速查表](#10-参数速查表)
11. [还能做什么分析](#11-还能做什么分析)
12. [做不了什么（及原因）](#12-做不了什么及原因)
13. [常见问题](#13-常见问题)

---

## 1. 数据规模：这数据到底大不大

**很小。这是它最大的优点，不是缺点。**

| 指标 | 数值 |
|---|---|
| 下载体积 | **751 KB**（series matrix，gz 压缩） |
| 解压后 | 约 8 MB 文本，33,358 行 |
| 探针数 | 33,297 |
| 样本数 | **6**（Control ×3, Vemurafenib ×3） |
| 内存峰值 | < 300 MB |
| 全流程耗时 | **26.6 秒**（实测，含取数+limma+8张图+验证） |
| 产出体积 | figures 约 2 MB，results 约 7 MB |

### 横向对比

| 数据类型 | 典型体积 | 本数据 |
|---|---|---|
| 芯片 series matrix | 0.5–5 MB | ✅ 751 KB |
| bulk RNA-seq counts | 2–50 MB | — |
| bulk RNA-seq FASTQ | 5–100 GB | — |
| 单细胞 10x (h5ad) | 0.5–20 GB | — |
| scATAC / 空间转录组 | 10–500 GB | — |

**结论**：这是生物信息学里最轻量的一档数据。用笔记本、甚至树莓派都能跑。
非常适合用来学流程、调试代码、做教学演示 —— 你不用等半小时才知道脚本写错了。

### 代价是什么

小的代价是**统计功效低**：

- n=3/组，残差自由度只有 **4**。这正是必须用 limma 经验贝叶斯的原因 ——
  它把 33,297 个探针的方差信息汇总成先验（d0=3.0），把有效自由度从 4 抬到 **7**，
  等于凭空多了 3 个自由度的信息量。没有这步，t 检验在 n=3 时几乎测不出东西。
- 不足以支撑需要大样本的分析（WGCNA、生存分析、机器学习建模），
  详见[第 12 节](#12-做不了什么及原因)。

---

## 2. 软件依赖与版本

### Python 路线（推荐，5 分钟装完）

```bash
bash analysis/setup/setup_python.sh    # conda 建 bioskills 环境
conda activate bioskills
```

| 包 | 实测版本 | 用途 | 必需？ |
|---|---|---|---|
| `python` | 3.11 | — | ✅ |
| `pandas` | 2.3.3 | 数据表操作 | ✅ |
| `numpy` | 2.4.6 | 数值计算、线性代数 | ✅ |
| `scipy` | 1.17.1 | `stats.t`（t 分布）、`special.digamma/polygamma`（先验估计）、`cluster.hierarchy`（聚类） | ✅ |
| `plotnine` | 0.15.7 | **Python 版 ggplot2**，语法完全一致 | ✅ |
| `adjustText` | 1.3+ | 火山图标签自动避让（等价 R 的 ggrepel） | ✅ 出图需要 |
| `pyreadr` | 0.5.6 | 读 `.Rdata`（仅注释兜底和验证用） | ⭕ 可选 |
| `gseapy` | 1.3.1 | GSEA / ORA 富集分析（[第 11 节](#11-还能做什么分析)） | ⭕ 扩展 |

### R 路线

```bash
bash analysis/setup/setup_r.sh conda   # 推荐 conda，比 apt 快
conda activate bioskills-r
```

| 包 | 来源 | 用途 |
|---|---|---|
| `limma` | Bioconductor | **核心**：lmFit + eBayes |
| `ggplot2` | CRAN | 出图 |
| `dplyr` / `tidyr` | CRAN | 数据整理 |
| `ggrepel` | CRAN | 标签避让 |
| `hugene10sttranscriptcluster.db` | Bioconductor | GPL6244 官方探针注释 |
| `GEOquery` | Bioconductor | 可选，另一种取数方式 |
| `clusterProfiler` + `org.Hs.eg.db` | Bioconductor | 富集分析（扩展） |

> **为什么推荐 conda 而不是 `apt install r-base-core`**：apt 装完 R 本体后，
> 每个 R 包都要从源码编译（limma、DESeq2 这类要 10–30 分钟）。conda 有预编译
> 二进制包，几分钟搞定，而且不需要 sudo、不污染系统。

---

## 3. 流程总览

```
                    ┌──────────────────────────┐
                    │ 01_fetch.sh              │
                    │ 通道A: NCBI FTP          │
                    │ 通道B: GitHub 镜像(兜底) │
                    └───────────┬──────────────┘
                                │ GSE42872_series_matrix.txt.gz (751KB)
                                │ GPL6244.annot.gz (探针注释)
                                ▼
                    ┌──────────────────────────┐
                    │ 02_limma_de.py           │
                    │  ① 解析 series matrix    │
                    │  ② 构建样本表 colData    │
                    │  ③ annotate.py 三级注释  │
                    │  ④ lmFit + eBayes        │
                    │  ⑤ BH 校正 + 分类        │
                    └───────────┬──────────────┘
                                │ DE_*.csv, expression_matrix.csv.gz
                    ┌───────────┴──────────────┐
                    ▼                          ▼
        ┌───────────────────────┐  ┌───────────────────────┐
        │ 03_ggplot_figures.py  │  │ 04_validate.py        │
        │ 8 张 plotnine 图      │  │ vs 作者 R/limma 结果  │
        └───────────────────────┘  └───────────────────────┘
                    │
                    ▼  （可选扩展）
        ┌───────────────────────────────────┐
        │ 05_enrichment.py                  │
        │ GSEA preranked (排序用 t) + ORA   │
        └───────────────────────────────────┘
```

一键跑完：
```bash
bash analysis/GSE42872/run_all.sh        # Python 路线，26.6 秒
bash analysis/GSE42872/run_all.sh r      # R 路线

# 可选：富集分析
python analysis/GSE42872/scripts/05_enrichment.py --offline
```

---

## 4. Step 1 — 取数

**脚本**：`scripts/01_fetch.sh`

### 双通道设计

```bash
通道 A（首选）：https://ftp.ncbi.nlm.nih.gov/geo/series/GSE42nnn/GSE42872/matrix/
通道 B（兜底）：git sparse-checkout from github.com/jmzeng1314/GEO
```

为什么要兜底：国内网络直连 NCBI 经常超时，公司/校园防火墙也常拦。两个通道拿到的是
**同一个文件**，md5 一致。

### 关键参数

| 参数 | 值 | 说明 |
|---|---|---|
| `--retry` | 3 | 网络抖动重试 |
| `--connect-timeout` | 20 | 20 秒连不上就切通道 B |
| `gzip -t` | — | **完整性校验**。下载截断的 gz 文件在后面解析时才报错，很难查，所以下载完立刻验 |

### 顺带下载的注释文件

```
https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL6nnn/GPL6244/annot/GPL6244.annot.gz
```

这是 NCBI 官方平台注释，带 `Gene symbol` / `Gene ID` 列。比装 Bioconductor 的
`hugene10sttranscriptcluster.db`（约 100 MB）轻量得多。

> ⚠️ **踩过的坑**：早期版本只在通道 B 下载注释文件。用户网络好走了通道 A，
> 注释没下 → symbol 全 NaN → 热图筛选后为空 → `pdist` 抛
> `empty distance matrix`。现在两条通道都取注释，且下游全面加了空值防御。

---

## 5. Step 2 — 解析与样本表

**脚本**：`scripts/02_limma_de.py`（第 1–2 节）

### series matrix 文件结构

```
!Series_title = "Expression data from BRAFV600E A375 melanoma cells..."
!Sample_title = "A375 cells 24h Control rep1"  "A375 cells 24h Control rep2" ...
!Sample_geo_accession = "GSM1052615"  "GSM1052616" ...
...
!series_matrix_table_begin        ← 表达值从这里开始
"ID_REF"  "GSM1052615"  "GSM1052616" ...
7892501   7.24559       6.80686     ...
...
!series_matrix_table_end
```

解析逻辑：以 `!series_matrix_table_begin` / `_end` 为界切分，
前面是元数据（`!` 开头的 key-value），中间是表达矩阵。

### 数据形态确认（这步决定了后面用什么方法）

```
表达矩阵: 33297 探针 x 6 样本
值域: 2.67 ~ 14.56  (log2 RMA)
```

**值域 2.67–14.56 是判断依据**：这是 log2 空间的连续值，不是整数 counts。
如果看到 0、5、127、3841 这样的整数，那才是 RNA-seq counts，要换 DESeq2。

### 样本分组

从 `!Sample_title` 正则提取，不手写死：

```python
group = ["Vemurafenib" if "Vemurafenib" in t else "Control" for t in titles]
rep   = [int(t.rstrip()[-1]) for t in titles]
```

结果：
```
GSM1052615  A375 cells 24h Control rep1      Control      1
GSM1052616  A375 cells 24h Control rep2      Control      2
GSM1052617  A375 cells 24h Control rep3      Control      3
GSM1052618  A375 cells 24h Vemurafenib rep1  Vemurafenib  1
GSM1052619  A375 cells 24h Vemurafenib rep2  Vemurafenib  2
GSM1052620  A375 cells 24h Vemurafenib rep3  Vemurafenib  3
```

---

## 6. Step 3 — 探针注释

**脚本**：`scripts/annotate.py`

### 三级自动降级

| 级别 | 来源 | 覆盖率 | 说明 |
|---|---|---|---|
| **1** | NCBI 官方 `GPL6244.annot.gz` | 最高 | 权威。`Gene symbol` 列，`ID` 对应探针 |
| **2** | `anno_DEG.Rdata` 反查 | 16,575 / 33,297 | 靠 `AveExpr` 唯一匹配，有少量歧义 |
| **3** | 无注释 | 0 | **流程不中断**，改用探针 ID 出图 |

运行时会打印实际用了哪级，`results/run_summary.json` 里也记录了
`annotation_source` 和 `n_annotated`。

### 解析要点

```python
# 一个探针可能对多个基因，用 /// 分隔，取第一个
tab["Gene symbol"] = tab["Gene symbol"].str.split("///").str[0].str.strip()
```

R 读这个文件必须关掉引号和注释符，否则会读错行：
```r
read.delim(..., quote = "", comment.char = "")   # 基因描述里含 " 和 #
```

---

## 7. Step 4 — limma 差异表达

**脚本**：`scripts/limma_py.py`（算法） + `02_limma_de.py`（调用）

### 🔴 为什么是 limma 不是 DESeq2

这是整个流程最重要的一个判断。

| | RNA-seq (如 GSE260485) | **芯片 (本数据)** |
|---|---|---|
| 数据 | 整数 counts (0, 5, 127...) | **RMA log2 强度 (2.67–14.56)** |
| 分布 | 负二项 (Negative Binomial) | **近似正态** |
| 方法 | DESeq2 / edgeR | **limma lmFit + eBayes** |

**把 log2 强度值喂给 DESeq2 在统计上是错的** —— 负二项模型假设的是计数数据的
均值-方差关系（方差随均值增大），连续型的 log2 强度不满足这个假设。

### 算法：经验贝叶斯方差收缩（Smyth 2004）

n=3/组时残差自由度只有 4，单个基因的方差估计极不稳定。limma 的解法是
**跨基因借力**：

```
第 1 步  逐基因线性模型         → 每个基因的 σ²ᵍ (自由度 df=4)
第 2 步  fitFDist 拟合先验      → s₀² = 0.01080, d₀ = 3.000
第 3 步  后验方差 = 加权平均
         s²post = (d₀·s₀² + df·σ²ᵍ) / (d₀ + df)
第 4 步  moderated t = β / (SE · √s²post)
         有效自由度 = df + d₀ = 4 + 3 = 7
```

**自由度从 4 → 7**，这就是 limma 在小样本下的威力来源。

### 设计矩阵

```python
X = [1, group]      # 截距 + 处理效应
# 等价 R: model.matrix(~ group)
```

系数 `β₁` 就是 `log2(Vemurafenib) - log2(Control)`，即 logFC。
因为数据已在 log2 空间，**直接相减就是 log fold change**，不需要再取对数。

### 参数

| 参数 | 值 | 依据 |
|---|---|---|
| 设计公式 | `~ group` | 单因素两水平 |
| 参考水平 | `Control` | logFC 正值 = 处理组上调 |
| 多重检验 | **Benjamini-Hochberg** | 基因组尺度的标准做法，控制 FDR |
| `FDR` 阈值 | **0.05** | 常规 |
| `|log2FC|` 阈值 | **1.0**（即 2 倍变化） | 常规。生物学意义 + 统计显著双重要求 |

> **两个阈值为什么要一起用**：n=3 时 padj<0.05 有 9,877 个探针（占 30%），
> 光看 p 值会淹没在噪音里。加上 2 倍变化的要求后剩 1,303 个，才是真正值得看的。

### 输出

```
padj<0.05            : 9,877
padj<0.05 且 |LFC|>1 : 1,303   (上调 701 / 下调 602)
```

结果表 `DE_Vemurafenib_vs_Control.csv` 字段：

| 列 | 含义 |
|---|---|
| `probe` | 探针 ID |
| `symbol` | 基因符号 |
| `logFC` | log2 倍数变化（Vem − Ctrl） |
| `AveExpr` | 该探针在所有样本的平均表达 |
| `t` | **moderated t 统计量**（GSEA 排序就用这个） |
| `P.Value` | 原始 p 值 |
| `adj.P.Val` | BH 校正后（FDR） |
| `direction` | Up / Down / n.s. |

---

## 8. Step 5 — 可视化

**脚本**：`scripts/03_ggplot_figures.py`（plotnine = Python 版 ggplot2）

| 图 | 内容 | 关键参数 |
|---|---|---|
| `fig01` | 各样本表达分布箱线图 | 检查 RMA 归一化，中位数应齐平 |
| `fig02` | PCA | `top 5000` 可变探针；**PC1 = 82.4% 方差** |
| `fig03` | 样本相关性热图 | Pearson r，层次聚类排序 |
| `fig04` | **火山图** | x=logFC, y=−log10(padj)，标注 top 18 |
| `fig05` | MA 图 | x=AveExpr, y=logFC |
| `fig06` | top50 热图 | **行内 z-score**，双向层次聚类 |
| `fig07` | **MAPK 通路基因** | 12 个基因分面箱线图（生物学阳性对照） |
| `fig08` | 上下调计数 | |

### 配色

统一用 **Okabe–Ito 色盲友好**方案：

```python
Up   = "#D55E00"   # 橙红
Down = "#0072B2"   # 蓝
n.s. = "#CCCCCC"   # 灰
```

### 输出格式

- PNG @ **300 dpi**（投稿够用）
- PDF 矢量（火山图/MA 图除外 —— 3 万个点的矢量 PDF 有 5 MB，不值得）

### plotnine 的三个坑

1. **不认 R 的颜色名**：`'grey80'` 抛 `Unknown name for a color`，必须用十六进制。
2. **中文变方块**：DejaVu Sans 无 CJK 字形，图内文字一律用英文。
3. **`geom_text(adjust_text=)` 需额外装 `adjustText`**，不装会在画图时才报错。

---

## 9. Step 6 — 验证

**脚本**：`scripts/04_validate.py`

不能只说"我跑出来了"，得证明跑对了。两重验证：

### 6.1 与原作者的真 R/limma 结果比对

对照来源：`jmzeng1314/GEO` 仓库中作者用 **R 的 limma** 跑出的 `anno_DEG.Rdata`。

```
可对齐             : 17,239 条
logFC 相关系数     : 0.998603
logFC 逐位相同     : 17,202 / 17,239 = 99.79%    ← 关键指标
t 统计量相关系数   : 0.995569
Top50 基因重叠     : 42 / 50
```

**99.79% 的 logFC 精确到小数点后 9 位完全一致**（CD36 两边都是 5.780170）。

剩余 37 条偏差的来源已查清：是用 `AveExpr` 反查探针时的**匹配歧义**
（几个探针的 AveExpr 数值相撞配错了行），**不是计算差异**。用官方
PROBEID→SYMBOL 映射即可消除。

### 6.2 生物学阳性对照

维罗非尼抑制 BRAF-V600E，MAPK/ERK 通路输出基因**必须**下调。这是硬约束：

```
OK  DUSP6    logFC=-4.213  padj=4.61e-07
OK  SPRY2    logFC=-3.802  padj=1.02e-06
OK  ETV4     logFC=-3.843  padj=3.01e-06
OK  ETV5     logFC=-4.079  padj=3.26e-06
OK  CCND1    logFC=-2.488  padj=3.26e-06
OK  SPRY4    logFC=-3.753  padj=6.12e-06
OK  MYC      logFC=-1.348  padj=8.37e-05
OK  PHLDA1   logFC=-1.450  padj=1.67e-04
-> 全部下调，符合 BRAF-V600E 抑制的预期
```

`fig07` 里 12 个基因**无一例外全部下调**。方法学正确性和生物学合理性都站得住。

---

## 10. 参数速查表

想改参数直接看这张表。

| 参数 | 当前值 | 位置 | 调整建议 |
|---|---|---|---|
| FDR 阈值 | `0.05` | `02_limma_de.py: FDR` | 严格→0.01；探索→0.1 |
| logFC 阈值 | `1.0` | `02_limma_de.py: LFC` | 1.0 = 2倍；1.585 = 3倍；0.585 = 1.5倍 |
| 多重检验方法 | BH | `limma_py.py: bh()` | 极端保守可换 Bonferroni |
| PCA 用探针数 | `5000` | `03_ggplot: np.argsort(v)[-5000:]` | 1000–10000 都合理 |
| 热图基因数 | `50` | `03_ggplot: .head(50)` | 20–100 |
| 火山图标注数 | `18` | `03_ggplot: nlargest(18)` | 太多会糊成一片 |
| 热图 z-score 范围 | `±1.6` | `03_ggplot: limits=(-1.6,1.6)` | 对比度不够就调小 |
| 聚类方法 | `average` | `03_ggplot: order_rows()` | 可换 `ward`, `complete` |
| 图片 DPI | `300` | `03_ggplot: save()` | 投稿 300；预览 150 |

---

## 11. 还能做什么分析

**能做的还有很多。** 差异表达只是起点，下面按"投入产出比"排序，
每一条都标注了在这个数据上是否**实测可行**。

### ⭐ 11.1 富集分析 GSEA / ORA（最推荐，已实测跑通）

有了 `t` 统计量排序向量，富集分析是最自然的下一步。

已封装成脚本，**直接能跑**：

```bash
python scripts/05_enrichment.py --offline   # 内置基因集，离线可跑
python scripts/05_enrichment.py             # 加上 MSigDB/KEGG/GO 在线库
```

**实测输出**（gseapy 1.3.1，1000 次置换，seed=42）：

```
                      Term        ES       NES  NOM p-val  FDR q-val  Tag %
           MAPK_ERK_OUTPUT -0.973913 -2.539912   0.000000   0.000000  15/15
            CELL_CYCLE_G2M -0.946209 -2.220061   0.000000   0.000000  11/11
MELANOCYTE_DIFFERENTIATION  0.860352  1.774187   0.002012   0.002890    2/7
   CHOLESTEROL_HOMEOSTASIS -0.751089 -1.595084   0.028953   0.026507    4/8
```

这四条结果**全部符合已知生物学**，而且刚好复现了原文的核心发现：

| 基因集 | NES | 解读 |
|---|---|---|
| MAPK_ERK_OUTPUT | **−2.54** | 靶点通路被抑制。15/15 基因全部落在下调端，这是药效的直接证据 |
| CELL_CYCLE_G2M | **−2.22** | 细胞周期停滞 —— BRAF 抑制的下游表型 |
| MELANOCYTE_DIFFERENTIATION | **+1.77** | MITF/TYR/DCT 上调，黑色素细胞**重新分化**。这是 BRAF 抑制剂的经典表型（去分化状态逆转） |
| CHOLESTEROL_HOMEOSTASIS | **−1.60** | LDLR/HMGCR/SQLE 下调，代谢重编程 |

另外单独测过一个 **随机基因集对照**：NES=1.34, FDR=0.12 **不显著** ——
说明这套方法不是"随便什么集合都能出显著"，结果可信。

输出：`results/enrichment/gsea_builtin.csv`、`figures/fig09_gsea_builtin.png`

**手写版代码**（想自己控制细节）：
```python
import pandas as pd, gseapy as gp

d = pd.read_csv('results/DE_Vemurafenib_vs_Control.csv').dropna(subset=['symbol'])
d = d.sort_values('t', ascending=False).drop_duplicates('symbol')
rnk = d.set_index('symbol')['t']          # 16,575 基因，范围 -71.4 ~ 85.3

res = gp.prerank(rnk=rnk,
                 gene_sets='MSigDB_Hallmark_2020',   # 或 'KEGG_2021_Human'
                 permutation_num=1000,
                 min_size=15, max_size=500,
                 seed=42, threads=4)
print(res.res2d.head(20))
```

> 🔑 **排序统计量必须用 `t`，不能用 p 值** —— p 值丢掉了方向，上调和下调
> 会混在一起，NES 变得无法解释。也不建议用裸 logFC（低表达基因的不稳定
> 大倍数会劫持 leading edge）。`t` 是方差校准过的带符号统计量，是正解。
> （出自 `pathway-analysis/gsea` skill）

**R 版**：`clusterProfiler::gseGO()` / `gseKEGG()` / `GSEA()`

对应 skill：`pathway-analysis/gsea`、`go-enrichment`、`kegg-pathways`、`reactome-pathways`

---

### ⭐ 11.2 ORA 过表达分析（更简单，适合快速看结果）

不用排序，直接把 956 个有 symbol 的显著基因丢进去：

```python
up   = d[(d['adj.P.Val']<0.05) & (d.logFC >  1)].symbol.dropna().tolist()
down = d[(d['adj.P.Val']<0.05) & (d.logFC < -1)].symbol.dropna().tolist()

enr = gp.enrichr(gene_list=down,
                 gene_sets=['KEGG_2021_Human','GO_Biological_Process_2023'],
                 organism='human')
print(enr.results.head(15))
```

**上调、下调要分开做**。混在一起会互相抵消，什么都测不出来。

---

### 11.3 从 CEL 原始文件重新做归一化（进阶）

GEO 上有 **CEL 原始文件**（`GSE42872_RAW.tar`）。submitter 用的是 RMA，
你可以自己重做，甚至换方法：

```r
library(oligo)
cel <- read.celfiles(list.celfiles("GSE42872_RAW/", full.names=TRUE))
eset_rma  <- rma(cel)                    # 标准 RMA
eset_gcrma <- gcrma::gcrma(cel)          # GC 含量校正版
```

**什么时候值得做**：怀疑 submitter 归一化有问题、想加 batch 校正、
想用 alternative CDF（GPL6244 有 20+ 个 alternative CDF 版本，见平台页面）。

对应 skill：`expression-matrix/normalization`

---

### 11.4 ssGSEA 每样本通路打分（n=6 可行）

不做组间检验，只给每个样本打分，6 个样本足够：

```python
ss = gp.ssgsea(data=expr_matrix,          # 基因 × 样本
               gene_sets='MSigDB_Hallmark_2020',
               sample_norm_method='rank')
```

得到"样本 × 通路"矩阵，可以直接画热图，看每个重复的通路活性一致性。

对应 skill：`pathway-analysis/gsea`（ssGSEA / GSVA 部分）

---

### 11.5 转录因子活性推断

MAPK 通路的下游效应器是 **ETV4/ETV5/FOSL1/MYC** 这些转录因子，它们全都下调了。
可以进一步推断 TF 活性变化：

```python
# decoupler-py + CollecTRI
import decoupler as dc
net = dc.get_collectri(organism='human')
tf_acts, tf_pvals = dc.run_ulm(mat=expr.T, net=net)
```

对应 skill：`gene-regulatory-networks/`

---

### 11.6 与其他 BRAF 抑制剂数据集做 meta 分析

GEO 上同类数据集很多（达拉非尼、司美替尼、耐药细胞系……）。
把多个数据集的 t 统计量做 rank aggregation，能找出**跨数据集稳健**的信号。

搜索方式：GEO 检索 `vemurafenib[All Fields] AND "Homo sapiens"[Organism]`

对应 skill：`multi-omics-integration/`、`database-access/geo-data`

---

### 11.7 药物重定位 / CMap 查询

把上调、下调基因列表提交到 [CLUE.io](https://clue.io)（Connectivity Map），
找出能"逆转"这个表达特征的化合物 —— 这是药物联用筛选的常规起手式。

---

### 11.8 简单但有用的补充分析

| 分析 | 说明 | 难度 |
|---|---|---|
| 火山图交互版 | plotly，鼠标悬停显示基因名 | ⭐ |
| 基因家族聚焦 | 只看 DUSP 家族、SPRY 家族的整体变化 | ⭐ |
| 与药物靶点库交叉 | 显著基因 ∩ DrugBank / OpenTargets | ⭐⭐ |
| 蛋白互作网络 | 显著基因丢进 STRING-db，看模块 | ⭐⭐ |
| 剂量/时间序列 | 需要另找有多时间点的数据集 | ⭐⭐⭐ |

---

## 12. 做不了什么（及原因）

诚实地说清楚边界，比堆砌"还能做 XX 分析"有用。

| 分析 | 为什么不行 |
|---|---|
| **WGCNA 共表达网络** | 需要 **15–20+ 样本**才能稳定估计相关性，本数据只有 6。硬跑会得到全是噪音的模块 |
| **生存分析 / 预后模型** | 细胞系体外实验，**没有患者随访数据**。要做得换 TCGA 之类的临床队列 |
| **免疫浸润 / 反卷积**（CIBERSORT 等） | A375 是**纯细胞系培养**，没有免疫细胞。算出来的"免疫细胞比例"没有生物学意义 |
| **机器学习分类器** | n=6 训练分类器必然过拟合，无法做有意义的交叉验证 |
| **可变剪接分析** | GPL6244 是**基因水平**（transcript cluster）芯片，没有外显子级探针。要做得用 exon array (GPL5175) 或 RNA-seq |
| **eQTL / 遗传关联** | 没有基因型数据 |
| **单细胞层面异质性** | bulk 芯片，只有群体平均 |
| **绝对表达量比较** | 芯片信号是**相对**的，不同探针间不可直接比大小（探针亲和力不同）。只能比同一探针的跨样本变化 |

### 关于 n=3 的诚实说明

n=3/组是**发表可接受的最低标准**，但要意识到：

- Schurch 2016 (*RNA* 22:839) 的实测：n=3 时所有 DE 工具都会**漏掉 20–40% 的真阳性**
- 所以"没测出显著"≠"没有变化"
- 本数据的 1,303 个显著基因是**保守估计**，真实的差异基因只多不少

好消息是：这个实验的效应量极大（CD36 上调 55 倍，DUSP6 下调 18 倍），
n=3 完全足够检出主要信号。MAPK 通路 12/12 全中就是证据。

---

## 13. 常见问题

### Q: `Rscript: command not found`

系统没装 R。跑 `bash analysis/setup/setup_r.sh conda`（推荐，不用 sudo）。
或者直接用 Python 路线，功能完全等价。

### Q: `ValueError: empty distance matrix`

探针注释缺失导致热图筛选后为空。**已修复**（三级降级 + 空值防御）。
如果还遇到，`git pull` 确认代码是最新的。

### Q: `git pull` 报 "local changes would be overwritten... Aborting"

产物文件冲突。见 `FIX_PULL_CONFLICT.md`。
简单说：`git checkout -- analysis/GSE42872/figures analysis/GSE42872/results` 后再 pull。

> ⚠️ 注意 `Aborting` 意味着**这次 pull 完全没生效**，别急着跑代码，
> 先 `git log --oneline -1` 确认 commit 变了没有。

### Q: 想换个 GEO 数据集跑这套流程

- **另一个芯片数据集**：改 `01_fetch.sh` 里的 GSE 编号和平台注释 URL，
  再改 `02_limma_de.py` 里的分组正则。其余不用动。
- **RNA-seq 数据集**：**不能直接用这套**，要换 DESeq2。
  参考 `analysis/GSE260485/` 那套流程。

### Q: 图里的中文变成方块了

plotnine 用的 DejaVu Sans 没有中文字形。要中文标题得装中文字体并指定：

```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC']
```

本流程图内文字统一用英文，规避这个问题。

---

## 参考文献

- **Smyth GK (2004)** Linear models and empirical Bayes methods for assessing differential expression in microarray experiments. *Stat Appl Genet Mol Biol* 3:Article3. — limma 经验贝叶斯
- **Ritchie ME et al. (2015)** limma powers differential expression analyses for RNA-sequencing and microarray studies. *NAR* 43:e47.
- **Benjamini Y & Hochberg Y (1995)** Controlling the false discovery rate. *JRSS-B* 57:289. — BH 校正
- **Irizarry RA et al. (2003)** Exploration, normalization, and summaries of high density oligonucleotide array probe level data. *Biostatistics* 4:249. — RMA
- **Subramanian A et al. (2005)** Gene set enrichment analysis. *PNAS* 102:15545. — GSEA
- **Schurch NJ et al. (2016)** How many biological replicates are needed? *RNA* 22:839. — 重复数
- **Parmenter TJ et al. (2014)** Response of BRAF-mutant melanoma to BRAF inhibition is mediated by a network of transcriptional regulators of glycolysis. *Cancer Discov* 4:423. (PMID 24469106) — 本数据集原文
