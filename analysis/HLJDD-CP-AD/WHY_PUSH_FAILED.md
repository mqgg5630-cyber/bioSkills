# 为什么 push_raw.sh 推送失败

```
error: src refspec arena/019f9c4c-bioskills does not match any
error: failed to push some refs to 'origin'
```

## 好消息：数据没丢

76 个文件都解压出来了，在 `~/projects/bioSkills/combined_raw/`。
只是**推送这一步**失败，重新做就行。

---

## 三个问题

### 问题 1（致命）：`git init` 建了个无关的新仓库

你脚本里这两行：

```bash
cd "$OUT_DIR"        # 进入 combined_raw/
git init || true     # ← 问题在这
```

`git init` 在 `combined_raw/` 里建了一个**全新的空仓库**。它和你的 bioSkills 仓库
完全无关：

- 没有 `origin` remote（虽然 `git push origin` 能找到父目录配置，但…）
- **没有 `arena/019f9c4c-bioskills` 这个分支** —— 新仓库只有 `master`
- 所以 `git push origin arena/019f9c4c-bioskills` 找不到这个本地分支名

`src refspec ... does not match any` 的字面意思就是：
**你让我推的这个分支，我在本地找不到。**

我复现了完全一样的报错：
```
$ mkdir combined_raw && cd combined_raw && git init && git add . && git commit -m x
$ git push origin arena/019f9c4c-bioskills
error: src refspec arena/019f9c4c-bioskills does not match any
```

**正确做法**：不要 `git init`，直接在已有的 bioSkills 仓库里 `git add`。

---

### 问题 2：就算修好问题 1 也推不上去

你 commit 的 76 个文件里：

| 内容 | 体积 | 判断 |
|---|---|---|
| GSE157827：21 样本 × 3 文件 | **约 1.2 GB** | ❌ 单个 `matrix.mtx.gz` 就 50–60 MB，总量远超仓库限制 |
| GSE23586：6 样本 × (CEL + CHP) | 约 30 MB | ✅ 没问题 |
| GSE781_family.soft | **0 字节** | ❌ 见问题 3 |

GitHub 限制：单文件 100 MB 硬上限，仓库 1 GB 软上限。
1.2 GB 的原始 mtx 一定会被拒。

**解决**：先跑预处理压到 <100 MB（见下）。

---

### 问题 3：Windows 路径在 WSL 里不认

```bash
gunzip -c "E:/R/R_libs/GEOquery/extdata/GSE781_family.soft.gz" > ...
# gzip: E:/R/...: No such file or directory
```

WSL 里 Windows 盘挂在 `/mnt/`，`E:\` 要写成 `/mnt/e/`：

```bash
gunzip -c "/mnt/e/R/R_libs/GEOquery/extdata/GSE781_family.soft.gz" > ...
```

因为 gunzip 失败，`GSE781/GSE781_family.soft` 是个 **0 字节空文件**，
却仍被 commit 了进去。

不过**这个数据集本来就不需要** —— GSE781 是肾透明细胞癌，
和牙周炎/阿尔茨海默无关，它只是 R 的 GEOquery 包自带的示例文件。

---

## 怎么办：跑修正版脚本

```bash
cd ~/projects/bioSkills
git pull origin arena/019f9c4c-bioskills     # 先拿到新脚本

bash analysis/HLJDD-CP-AD/scripts/push_data.sh
```

这个脚本会：

1. **在正确的仓库里操作**（不 `git init`），并确保你在 `arena/019f9c4c-bioskills` 分支
2. 问你要不要删掉上次那个没用的 `combined_raw/`
3. 解压到 `~/geodata/`（WSL 原生盘，比 `/mnt/` 快 5–10 倍）
4. **GSE157827 跑预处理**：QC → 合并 → 高变基因裁剪 → 压缩 h5ad（<100 MB）
   同时强制保留 cGAS-STING 通路和细胞类型标记基因
5. **GSE23586 只打包 CEL**（CHP 是 Affymetrix 软件的二次产物，分析用不上）
6. **提交前逐个检查文件体积**，有超 100 MB 的直接停下并给出修复命令
7. 提交并推送

预计 15–25 分钟，主要耗在解压和预处理。

---

## 手动清理（如果你想先自己收拾）

```bash
cd ~/projects/bioSkills

# 那个独立的空仓库没有任何价值，直接删
rm -rf combined_raw

# 确认自己在对的分支上
git branch --show-current       # 应显示 arena/019f9c4c-bioskills
git remote -v                   # 应显示 github.com/mqgg5630-cyber/bioSkills
```

`combined_raw/` 里的解压文件删掉不可惜 —— 修正版脚本会重新解压到
`~/geodata/`，而且原始 tar 还在你的 E 盘里。

---

## 一个通用经验

`git init` 只在**新建仓库**时用。往已有仓库加文件时永远不要跑它 ——
一旦在子目录里 `git init`，那个子目录就变成了独立仓库，
外层仓库会完全忽略它的内容（甚至可能被当成 submodule）。

判断自己在哪个仓库里：

```bash
git rev-parse --show-toplevel    # 显示当前仓库的根目录
```

如果输出是 `.../bioSkills/combined_raw` 而不是 `.../bioSkills`，
说明你在错误的仓库里。
