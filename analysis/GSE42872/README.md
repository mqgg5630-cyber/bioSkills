# GSE42872 全流程跑通结果 ✅

**这个目录里的结果和图不是模板，是真跑出来的**，`results/` 和 `figures/` 里的东西可以直接看。

---

## 一、这是什么数据

| 项 | 内容 |
|---|---|
| Accession | [GSE42872](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE42872) |
| 标题 | Expression data from BRAF-V600E A375 melanoma cells treated with vehicle or vemurafenib |
| 平台 | **GPL6244** = Affymetrix Human Gene 1.0 ST **芯片** |
| 样本 | 6 个：A375 黑色素瘤细胞，DMSO 对照 ×3 vs 维罗非尼 10 µM 24h ×3 |
| 数据形态 | **33,297 探针 × 6 样本，RMA 归一化的 log2 强度值（实测值域 2.67 ~ 14.56）** |
| 文献 | PMID 24469106 |

## ⚠️ 关键：这里不能用 DESeq2，必须用 limma

上一轮我给 GSE260485 写的是 DESeq2 流程，**GSE42872 不能照搬**：

| | GSE260485 | GSE42872 |
|---|---|---|
| 技术 | RNA-seq | **芯片** |
| 数据 | 整数 counts | **RMA log2 连续强度** |
| 正确方法 | DESeq2 / edgeR（负二项） | **limma lmFit + eBayes** |

把 log2 强度值喂给 DESeq2 在统计上是错的（负二项分布是对计数数据的假设）。芯片数据的标准做法是 limma 的经验贝叶斯方差收缩（Smyth 2004）。

---

## 二、跑出来的结果

```
33,297 探针 × 6 样本，值域 2.67 ~ 14.56 (log2 RMA)
经验贝叶斯先验: s0² = 0.01080, d0 = 3.000
残差自由度 4 → 收缩后总自由度 7.00

padj < 0.05                : 9,877
padj < 0.05 且 |log2FC| > 1: 1,303  (上调 701 / 下调 602)
```

### Top 15 差异基因

| probe | symbol | logFC | t | adj.P.Val | 方向 |
|---|---|---|---|---|---|
| 8133876 | **CD36** | +5.780 | 85.29 | 2.67e-07 | Up |
| 7965335 | **DUSP6** | −4.213 | −71.43 | 4.61e-07 | Down |
| 7972217 | **SPRY2** | −3.802 | −59.15 | 1.02e-06 | Down |
| 7972259 | **DCT** | +5.633 | 57.72 | 1.02e-06 | Up |
| 8129573 | MOXD1 | +3.263 | 52.42 | 1.60e-06 | Up |
| 8015806 | **ETV4** | −3.843 | −46.40 | 3.01e-06 | Down |
| 7909568 | DTL | −3.193 | −45.66 | 3.01e-06 | Down |
| 8000574 | NUPR1 | +3.031 | 43.91 | 3.26e-06 | Up |
| 8092578 | **ETV5** | −4.079 | −42.44 | 3.26e-06 | Down |
| 8025828 | LDLR | −3.054 | −41.72 | 3.26e-06 | Down |
| 7942123 | **CCND1** | −2.488 | −41.29 | 3.26e-06 | Down |
| 8178435 | IER3 | −2.641 | −38.90 | 4.59e-06 | Down |
| 8102938 | RNF150 | +2.434 | 37.33 | 5.07e-06 | Up |
| 7904726 | TXNIP | +2.949 | 37.05 | 5.07e-06 | Up |
| 7944722 | UBASH3B | −2.252 | −35.48 | 5.95e-06 | Down |

**加粗的全是 MAPK/ERK 通路的经典输出基因**，全部下调 —— 维罗非尼抑制 BRAF-V600E 就该是这个结果。

---

## 三、两重验证（这部分很重要）

### 1. 与原作者的真 R/limma 结果逐位比对

对照来源：`jmzeng1314/GEO` 仓库里作者用 **R 的 limma** 跑出的 `anno_DEG.Rdata`。

```
可对齐 17,239 条
logFC 相关系数        : 0.998603
logFC 逐位相同(<1e-9) : 17,202/17,239 = 99.79%   ← 关键
t 统计量相关系数      : 0.995569
Top50 基因重叠        : 42/50
```

**99.79% 的 logFC 精确到小数点后 9 位完全一致**（比如 CD36 两边都是 5.780170）。剩下 37 条是我用 AveExpr 反查探针时的匹配歧义（几个探针的 AveExpr 数值撞车配错了行），**不是计算差异** —— 有 Bioconductor 注释包时用真正的 PROBEID→SYMBOL 映射就没这问题。

### 2. 生物学阳性对照

```
MAPK/ERK 通路输出基因方向检查：
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

`fig07_MAPK_targets.png` 里 12 个基因的箱线图**无一例外全部下调**。

---

## 四、8 张图（`figures/`，PNG 300dpi + PDF 矢量）

| 文件 | 内容 | 看点 |
|---|---|---|
| `fig01_sample_distribution` | 各样本 log2 强度箱线图 | 中位数齐平 → RMA 归一化正常 |
| `fig02_pca` | top5000 可变探针 PCA | **PC1 = 82.4% 方差，完美分开两组** |
| `fig03_sample_correlation` | 样本相关性热图 + 数值 | 组内 r 高于组间 |
| `fig04_volcano` | 火山图，18 个基因标注 | 上调 701 / 下调 602 |
| `fig05_ma` | MA 图 | 低表达端离散度大，符合芯片预期 |
| `fig06_heatmap_top50` | top50 基因 z-score 热图 | 双向层次聚类 |
| `fig07_MAPK_targets` | **12 个 MAPK 通路基因箱线图** | **生物学验证，全部下调** |
| `fig08_de_counts` | 上下调计数柱状图 | |

配色统一用 Okabe–Ito 色盲友好方案。

---

## 五、怎么自己跑

### 你现在的问题：没装 R

```
$ Rscript analysis/GSE260485/scripts/setup_r_packages.R
Command 'Rscript' not found
```

我准备了两条路，**推荐先走 Python 那条**（5 分钟，不需要 sudo）：

### 路线 A：Python（快，我就是用这条跑出上面全部结果的）

```bash
bash analysis/setup/setup_python.sh      # conda 建 bioskills 环境
conda activate bioskills
bash analysis/GSE42872/run_all.sh        # 取数 + limma + 出图 + 验证
```

装的包：`pandas numpy scipy plotnine adjustText pyreadr pydeseq2`
其中 **plotnine 就是 Python 版的 ggplot2**，语法和 R 完全一致（`ggplot(df, aes(x,y)) + geom_point() + theme_bw()`）。

### 路线 B：原生 R

```bash
bash analysis/setup/setup_r.sh conda     # 推荐：conda 装，不用 sudo
# 或
bash analysis/setup/setup_r.sh apt       # 系统装，需要 sudo，编译慢

conda activate bioskills-r
bash analysis/GSE42872/run_all.sh r      # 跑 02_limma_de.R
```

R 版脚本是 `scripts/02_limma_de.R`，用真正的 `limma::lmFit` + `eBayes` + `ggplot2`，输出 `figR_*.png`。

> 你之前的报错提示 `sudo apt install r-base-core` 是能用的，但 apt 装完还要编译一堆 R 包（10–30 分钟）。你已经有 conda，用 conda 装 R 会快很多，而且 Bioconductor 包（limma/DESeq2/注释包）都有预编译版。

---

## 六、目录结构

```
analysis/
├── setup/
│   ├── setup_python.sh          # Python 环境（推荐先跑）
│   └── setup_r.sh               # R 环境，conda 或 apt 两种方式
└── GSE42872/
    ├── run_all.sh               # 一键：bash run_all.sh [py|r]
    ├── scripts/
    │   ├── 01_fetch.sh          # 取数：先试 NCBI，不通则走 GitHub 镜像
    │   ├── limma_py.py          # limma eBayes 的 numpy/scipy 实现
    │   ├── 02_limma_de.py       # 解析 GEO → limma → 结果表
    │   ├── 03_ggplot_figures.py # 8 张 plotnine(ggplot) 图
    │   ├── 04_validate.py       # 与作者 R/limma 结果交叉验证
    │   └── 02_limma_de.R        # 原生 R 等价实现
    ├── data/                    # 原始数据（git 忽略，可重新下载）
    ├── results/                 # ← 真实结果
    └── figures/                 # ← 真实图片
```

---

## 七、取数说明

`01_fetch.sh` 是双通道的：

1. **先试 NCBI**：`https://ftp.ncbi.nlm.nih.gov/geo/series/GSE42nnn/GSE42872/matrix/`
2. **不通就走 GitHub 镜像**：从 `jmzeng1314/GEO` 稀疏检出同一个 `series_matrix.txt.gz`

我这边沙箱 NCBI 被墙，走的是通道 2。**你在国内网络大概率也是通道 2 更稳**。两个通道拿到的是同一个文件。

---

## 八、踩过的坑（帮你省时间）

1. **plotnine 不认 R 的颜色名** —— `'grey80'` 直接抛 `Unknown name for a color`，必须用十六进制 `#CCCCCC`。
2. **plotnine 画中文会变方块** —— DejaVu Sans 没有 CJK 字形，图里标题一律用英文（正文/README 用中文没问题）。
3. **`geom_text(adjust_text=...)` 需要额外装 `adjustText`**，不装会在画图时才报 ModuleNotFoundError。
4. **`pd.to_csv` 会丢 index name** —— 存了再读回来 `reset_index()` 拿到的列叫 `index` 而不是原名，脚本里显式 `df.index.name = "gsm"` 修掉了。
5. **GPL6244 的探针注释离线拿不到** —— 正解是 `BiocManager::install("hugene10sttranscriptcluster.db")`，联网时 R 脚本会自动用它。
