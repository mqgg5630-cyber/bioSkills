# GSE260485 — 禁食 + 内分泌治疗的 MCF7 异种移植瘤 RNA-seq 全流程分析

用 **bioSkills** 的 skill 组装的一条完整流水线：**GEO 下载 → 计数矩阵整理 → DESeq2 差异表达 → ggplot2 出图**。

---

## 1. 数据集背景

| 项 | 内容 |
|---|---|
| Accession | [GSE260485](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE260485)（SuperSeries **GSE260486** 的 RNA-seq SubSeries） |
| 标题 | Fasting boosts breast cancer therapy efficacy via glucocorticoid activation (RNA-Seq) |
| 物种 / 平台 | *Homo sapiens* / GPL24676 Illumina NovaSeq 6000 |
| 样本 | 15 个 MCF7 异种移植瘤：Control ×3、TMX ×3、Fasting ×3、TMX+Fasting ×6 |
| 处理数据 | `GSE260485_MCF7_xenografts_genecounts.txt.gz`（Ensembl 基因 ID 的**原始整数 counts** + biotype/坐标/symbol 注释） |
| 文献 | Padrão N *et al.*, *Nature* 2026;649:1013–1021（PMID 41372410） |

**生物学问题**：禁食是否通过激活糖皮质激素受体（GR）通路增强他莫昔芬（TMX）疗效。

> ⚠️ 两个 `geo-data` skill 里强调的坑，本流程已经避开：
> 1. **SuperSeries 陷阱** — GSE260486 混了 ChIP/ATAC 等多种平台，我们只取 RNA-seq 的 SubSeries GSE260485；
> 2. **processed vs raw** — 提交者给的是原始整数 counts（不是已归一化矩阵），可以直接喂给 DESeq2，无需反推归一化。

---

## 2. 用到的 bioSkills skill

| 步骤 | Skill |
|---|---|
| GEO 检索与下载 | `database-access/geo-data` |
| counts 读入、ID/symbol 映射、metadata 拼接 | `expression-matrix/counts-ingest`、`gene-id-mapping`、`metadata-joins` |
| 差异表达（Wald + LRT + shrinkage） | `differential-expression/deseq2-basics`、`de-results` |
| 火山图 / MA 图 | `data-visualization/volcano-and-ma-plots` |
| PCA | `data-visualization/dimensionality-reduction-plots` |
| 热图 | `data-visualization/heatmaps-clustering` |
| 配色 | `data-visualization/color-palettes`（Okabe–Ito 色盲友好） |
| 拼图 | `data-visualization/multipanel-figures`（patchwork） |
| 主题与保存 | `data-visualization/ggplot2-fundamentals` |

---

## 3. 目录结构

```
analysis/GSE260485/
├── run_all.sh                  # 一键跑完整流程
├── scripts/
│   ├── setup_r_packages.R      # 一次性装依赖
│   ├── 01_download.sh          # 从 GEO 拉 counts（FTP，失败自动切 HTTP）
│   ├── 02_deseq2.R             # 读入 → QC → DESeq2 → 结果表
│   └── 03_ggplot_figures.R     # 9 张 ggplot2 图（PNG 300dpi + 矢量 PDF）
├── ci/gse260485-analysis.yml   # GitHub Actions 工作流（见第 6 节）
├── data/                       # 下载的原始文件（git 忽略）
├── results/                    # 结果表
└── figures/                    # 图
```

---

## 4. 怎么跑

```bash
# 依赖（只需一次）
Rscript analysis/GSE260485/scripts/setup_r_packages.R

# 全流程
bash analysis/GSE260485/run_all.sh
```

需要 R ≥ 4.3 + DESeq2、ashr、ggplot2、dplyr、tidyr、ggrepel、patchwork、scales、matrixStats。
整个流程在普通笔记本上约 3–6 分钟（15 个样本，~6 万基因）。

---

## 5. 分析设计与关键决策

### 统计设计
```r
design = ~ condition          # 4 水平，Control 为 reference
```

* **过滤**：至少 3 个样本（= 最小组样本量）counts ≥ 10。
* **Wald 检验 + 显式 contrast**：绝不用裸 `results(dds)`（它默认返回 `resultsNames` 的最后一项，随因子顺序悄悄变化）。四个对比：

  | contrast | 生物学含义 |
  |---|---|
  | `TMX_vs_Control` | 单纯内分泌治疗效应 |
  | `Fasting_vs_Control` | 单纯禁食效应 |
  | `TMXplusFasting_vs_Control` | 联合 vs 基线 |
  | `TMXplusFasting_vs_TMX` | **禁食在 TMX 之上带来的增益**（文章核心问题） |

* **omnibus LRT**（`reduced = ~1`）：condition 有 4 个水平，"任意组间有差异"必须用 LRT，不能把多个 Wald p 值凑一起。只读 LRT 的 padj，不解读它的 LFC。
* **LFC shrinkage**：`ashr`（支持 `contrast=`，还给出 s-value / local false sign rate）。
  结果表里同时保留 `log2FC_MLE`（未收缩）和 `log2FC_shrunk`（收缩后）。
  **画图和排序用收缩值；p 值是未收缩的 Wald p 值** —— 这是 DESeq2 的有意设计，不是 bug。
* **VST**（`blind = FALSE`）用于 PCA / 热图 / 距离矩阵；原始 counts 做 PCA 会让 PC1 变成"文库大小"。

### 输出结果表 (`results/`)

| 文件 | 内容 |
|---|---|
| `DE_<contrast>.csv` | 每个对比的完整结果：baseMean、log2FC_MLE、lfcSE、Wald stat、pvalue、padj、log2FC_shrunk、svalue、gene symbol、biotype |
| `LRT_condition_omnibus.csv` | LRT 全局检验 |
| `DE_summary.csv` | 每个对比的显著基因计数（padj<0.05 且 \|shrunk LFC\|>1） |
| `normalized_counts.csv.gz` | median-of-ratios 归一化 counts |
| `vst_matrix.csv.gz` | VST 矩阵 |
| `library_qc.csv` | 文库大小、检出基因数、size factor |
| `sample_metadata.csv` | 从样本名解析出的 colData |
| `sessionInfo_*.txt` | 可复现性记录 |

### 图 (`figures/`，PNG 300 dpi + PDF 矢量)

| 文件 | 内容 |
|---|---|
| `fig01_library_qc` | 文库大小柱状图 + size factor 箱线图 |
| `fig02_pca` | VST top-2000 可变基因 PCA，标注样本名与解释方差 |
| `fig03_sample_distance` | 样本间欧氏距离热图（层次聚类排序） |
| `fig04_volcano_panels` | 4 个对比的火山图分面，收缩 LFC vs BH-FDR，top-10 基因标注，y 轴截断至 60（三角形标记被截断点） |
| `fig05_ma_panels` | MA 图分面（展示 shrinkage 对低表达噪声的压制） |
| `fig06_de_counts` | 各对比上调/下调基因数的对称柱状图 |
| `fig07_heatmap_top50` | top-50 可变基因行 z-score 热图，按处理分面 |
| `fig08_GR_targets` | 12 个经典 GR 靶基因（FKBP5、TSC22D3、PER1、KLF15、SGK1、ZBTB16 …）的表达箱线+散点图——直接对应文章的核心假说 |
| `fig09_composite` | patchwork 拼成的 A/B/C 总图 |

---

## 6. 关于 GitHub Actions 工作流

`ci/gse260485-analysis.yml` 是一份现成的 GitHub Actions 工作流：装 R + Bioconductor、下载 GEO 数据、跑完整流程、上传 artifacts，并把 `results/` 和 `figures/` 提交回分支。

当前 Arena 的 GitHub App 没有 `workflows` 权限，无法代为写入 `.github/workflows/`，所以文件先放在这里。**要启用，你在本地执行：**

```bash
mkdir -p .github/workflows
cp analysis/GSE260485/ci/gse260485-analysis.yml .github/workflows/
git add .github/workflows/gse260485-analysis.yml
git commit -m "enable GSE260485 CI"
git push
```

然后在 GitHub 的 Actions 页面点 *Run workflow* 即可在云端跑出全部结果和图。

---

## 7. 复现性说明

* 下载脚本会做 gzip 完整性校验，FTP 失败自动回退到 NCBI 的 HTTP 下载端点。
* `data/` 与 `deseq2_objects.rds` 已在 `.gitignore` 中（原始数据不入库，符合仓库既有约定）。
* 两个 R 脚本都会写出 `sessionInfo()`，方便对齐包版本。
