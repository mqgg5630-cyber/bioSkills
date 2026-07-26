# 怎么同步我的结果，又不删掉你自己的文件

结论先说：**只要不用 `git checkout .` / `git reset --hard` / `git clean -fd`，你本地的文件一个都不会丢。**
Git 的 `pull` / `merge` 永远不会删除**未被 Git 跟踪**的文件（untracked files）。

我的改动全部在新目录 `analysis/GSE260485/` 里，**没有动你仓库里任何一个已有文件**，所以冲突风险基本为零。

分支名：`arena/019f9c4c-bioskills`

---

## 方案 A（推荐）：在你已有的 bioSkills 目录里直接拉分支

```bash
cd ~/projects/bioSkills

# 0) 先看一眼你自己有没有没提交的改动
git status

# 1) 如果有未提交的改动，先存起来（可选但安全）
git stash push -u -m "my local work"

# 2) 拉取远端分支信息（只下载，不改工作区）
git fetch origin arena/019f9c4c-bioskills

# 3) 切到我的分支看结果
git checkout arena/019f9c4c-bioskills
git pull origin arena/019f9c4c-bioskills

# 4) 想回自己的分支
git checkout main
git stash pop      # 如果第 1 步 stash 过
```

> `git checkout` 在有未提交改动且会被覆盖时会**报错拒绝执行**，不会静默覆盖。所以它是安全的。

---

## 方案 B：不切分支，把我的结果合并进你的 main

```bash
cd ~/projects/bioSkills
git fetch origin arena/019f9c4c-bioskills
git merge origin/arena/019f9c4c-bioskills
```

因为只新增了 `analysis/GSE260485/`，这会是一个干净的 fast-forward 或简单 merge。
不放心可以先预览会动哪些文件：

```bash
git diff --stat main origin/arena/019f9c4c-bioskills
```

---

## 方案 C：完全隔离，clone 到另一个目录（零风险）

你原来的 `~/projects/bioSkills` 一个字节都不碰：

```bash
cd ~/projects
git clone -b arena/019f9c4c-bioskills \
  https://github.com/mqgg5630-cyber/bioSkills.git bioSkills-gse260485

cd bioSkills-gse260485/analysis/GSE260485
ls
```

---

## 方案 D：只想要那一个目录，别的都不要

```bash
cd ~/projects/bioSkills
git fetch origin arena/019f9c4c-bioskills
git checkout origin/arena/019f9c4c-bioskills -- analysis/GSE260485
```

这条命令只把 `analysis/GSE260485/` 检出到你当前工作区，其他文件完全不动。

---

## 拿到之后怎么跑

```bash
cd ~/projects/bioSkills     # 或 bioSkills-gse260485
Rscript analysis/GSE260485/scripts/setup_r_packages.R   # 装依赖，一次即可
bash    analysis/GSE260485/run_all.sh                   # 下载 + DESeq2 + 出图
```

跑完看 `analysis/GSE260485/figures/`（9 张图，PNG + PDF）和 `analysis/GSE260485/results/`（结果表）。

---

## 危险命令清单（别用）

| 命令 | 后果 |
|---|---|
| `git reset --hard` | 丢弃所有未提交的改动 |
| `git checkout .` | 同上（对已跟踪文件） |
| `git clean -fd` | **删除所有未跟踪的文件和目录** ← 最容易误伤你自己的文件 |
| `git pull --force` / `git fetch --force` + reset | 可能覆盖本地提交 |

安全命令：`git fetch`、`git status`、`git diff`、`git stash`、`git merge`、`git checkout <branch>`。
