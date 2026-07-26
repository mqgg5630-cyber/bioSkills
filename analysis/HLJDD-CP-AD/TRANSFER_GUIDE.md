# 数据传输指南：从 Windows 到 WSL 再到 git

## 先说结论：你的三个文件

| 文件 | 大小 | 能用吗 |
|---|---|---|
| `GSE157827_RAW.tar` | **1.2 GB** | ✅ 能用，但**不能直接传 git**，需先预处理 |
| `GSE23586_RAW.tar` | 约 30 MB | ✅ 能用，可直接传 |
| `GSE781_family.soft.gz` | — | ❌ **用不上**，这是肾癌数据，且是 GEOquery 包的示例文件，与本课题无关 |

---

## ⚠️ 关于 Git LFS：你选了 LFS，但这条路会卡住

GSE157827_RAW.tar 是 **1.2 GB**，而 GitHub LFS 免费额度是：

| 项目 | 免费额度 | 你的需求 |
|---|---|---|
| LFS 存储 | 1 GB | 1.2 GB ❌ **直接超限** |
| LFS 流量 | 1 GB / 月 | 你上传 1.2 GB + 我下载 1.2 GB = **2.4 GB** ❌ |

超出需购买 Data Pack（$5/月 = 50 GB 存储 + 50 GB 流量）。

**更划算的办法**：先在本地做预处理，只传压缩后的分析对象。

原始 tar 里 90% 以上是稀疏零值和低表达基因。做完标准 QC 与高变基因筛选后，
分析所需的全部信息可压到 **<100 MB，普通 git 就能传，不用 LFS、不用花钱**。

---

## 推荐方案：本地预处理后再传（约 20 分钟）

### 第 1 步：把数据从 Windows 挪到 WSL

WSL 里 Windows 盘挂载在 `/mnt/`，`E:\` 就是 `/mnt/e/`：

```bash
# 建工作目录（放在 WSL 原生文件系统，比 /mnt/ 快 5-10 倍）
mkdir -p ~/geodata && cd ~/geodata

# 复制（注意 Windows 路径里的反斜杠要换成正斜杠）
cp /mnt/e/0wangyao/wangyao/raw/1/GSE157827/GSE157827_RAW.tar .
cp /mnt/e/0wangyao/wangyao/raw/1/GSE23586/GSE23586_RAW.tar .

ls -lh
```

> 💡 **别在 `/mnt/e/` 里直接解压和计算**。WSL 访问 Windows 盘走的是 9p 协议，
> 慢得多。复制到 `~/`（WSL 原生 ext4）能快好几倍。

### 第 2 步：解压

```bash
cd ~/geodata
mkdir -p gse157827 gse23586
tar -xf GSE157827_RAW.tar -C gse157827
tar -xf GSE23586_RAW.tar  -C gse23586

ls gse157827 | head        # 应看到 GSM4775561_AD1_barcodes.tsv.gz 等
du -sh gse157827 gse23586
```

### 第 3 步：装依赖

```bash
conda activate bioskills          # 或你之前建的环境
pip install scanpy anndata scipy pandas numpy
```

### 第 4 步：预处理（关键的一步）

```bash
cd ~/projects/bioSkills           # 先把仓库拉到最新
git pull origin arena/019f9c4c-bioskills

python analysis/HLJDD-CP-AD/scripts/00_prepare_local.py ~/geodata/gse157827
```

脚本会：
- 逐样本读入 21 个 10x 三件套，加样本前缀防 barcode 冲突
- QC 过滤（基因数 ≥200，线粒体 <20%）
- 合并 → 归一化 → 选 4000 高变基因
- **强制保留 cGAS-STING 通路基因和各细胞类型标记基因**（即使不在 HVG 里）
- 存成压缩 h5ad

预计 5–15 分钟，需要约 16 GB 内存。输出：

```
gse157827_prepared.h5ad          ← 目标 <100 MB
gse157827_qc_per_sample.csv      ← 逐样本 QC 统计
```

**如果输出 >95 MB**，减少基因数重跑：
```bash
python analysis/HLJDD-CP-AD/scripts/00_prepare_local.py ~/geodata/gse157827 --n-hvg 2000
```

### 第 5 步：GSE23586 直接传

芯片数据小，不用预处理：

```bash
cp ~/geodata/GSE23586_RAW.tar analysis/HLJDD-CP-AD/data/
du -h analysis/HLJDD-CP-AD/data/GSE23586_RAW.tar    # 确认 <100MB
```

### 第 6 步：提交

```bash
cd ~/projects/bioSkills
mkdir -p analysis/HLJDD-CP-AD/data
cp ~/geodata/gse157827_prepared.h5ad      analysis/HLJDD-CP-AD/data/
cp ~/geodata/gse157827_qc_per_sample.csv  analysis/HLJDD-CP-AD/data/

# .gitignore 里对 data/ 有豁免规则，需要 -f 强制添加
git add -f analysis/HLJDD-CP-AD/data/
git status                                  # 确认没有 >100MB 的文件
git commit -m "add GSE157827 prepared + GSE23586 raw"
git push origin arena/019f9c4c-bioskills
```

推送成功后告诉我，我就能开始分析。

---

## 备选：确实想用 Git LFS

如果你坚持传原始 1.2 GB tar，或者预处理后仍超 100 MB：

```bash
# 安装
sudo apt update && sudo apt install -y git-lfs
git lfs install

cd ~/projects/bioSkills
git lfs track "analysis/HLJDD-CP-AD/data/*.tar"
git lfs track "analysis/HLJDD-CP-AD/data/*.h5ad"
git add .gitattributes
git commit -m "configure LFS"

cp ~/geodata/GSE157827_RAW.tar analysis/HLJDD-CP-AD/data/
git add analysis/HLJDD-CP-AD/data/GSE157827_RAW.tar
git commit -m "add raw tar via LFS"
git push origin arena/019f9c4c-bioskills
```

**注意**：
- 免费额度 1 GB 存储 / 1 GB 月流量，1.2 GB 会**直接超**
- 需在 GitHub 仓库 Settings → Billing 买 Data Pack（$5/月）
- 你上传 + 我下载共约 2.4 GB 流量
- 你上次已经遇到 `Connection reset by peer`，传 1.2 GB 断线概率很高

**所以还是推荐预处理方案。**

---

## 再备选：完全不传，我写脚本你本地跑

你的网络能直连 NCBI（上次 GSE42872 走通道 A 成功）。
我可以只写脚本，数据你本地下载、本地跑，最后只把 `results/` 里的
小体积结果表（几 MB）传上来，我据此生成两个 docx。

优点：零大文件传输。缺点：中间调试轮次会多一些。

想走这条路告诉我一声。

---

## 常见问题

**Q: WSL 里找不到 E 盘**
```bash
ls /mnt/            # 看有哪些盘挂载了
# 若没有 e，手动挂载：
sudo mkdir -p /mnt/e && sudo mount -t drvfs E: /mnt/e
```

**Q: 复制很慢**
`/mnt/` 走 9p 协议本来就慢。1.2 GB 大约 1–3 分钟属正常。
解压和计算务必在 `~/` 下做。

**Q: 内存不够（预处理被 killed）**
WSL 默认最多用一半物理内存。在 Windows 用户目录建 `.wslconfig`：
```ini
[wsl2]
memory=16GB
```
然后 PowerShell 里 `wsl --shutdown` 重启 WSL。

**Q: git push 时报文件超 100 MB**
```
remote: error: File ... is 123.00 MB; this exceeds GitHub's file size limit of 100.00 MB
```
说明预处理输出还是太大，用 `--n-hvg 2000` 重跑。
若已经 commit 了大文件，需要撤销：
```bash
git reset --soft HEAD~1
git restore --staged analysis/HLJDD-CP-AD/data/xxx
```
