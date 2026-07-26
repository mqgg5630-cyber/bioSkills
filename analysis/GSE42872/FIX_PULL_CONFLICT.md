# git pull 报 "local changes would be overwritten" 怎么办

## 你遇到的情况

```
error: Your local changes to the following files would be overwritten by merge:
        analysis/GSE42872/figures/fig01_sample_distribution.pdf
        ...
Please commit your changes or stash them before you merge.
Aborting
```

**关键点：`Aborting` 意味着 pull 完全没生效**，代码还是旧的。所以你后面跑出来的
错误和之前一模一样 —— 因为跑的根本就是旧脚本。

## 原因（我的锅）

我早期把 `figures/` 和 `results/` 提交进了 git。你本地跑一次流程，这些文件就被
重新生成（PNG 连字节都不一样），git 认为「你改了这些文件」，于是拒绝用远端版本
覆盖它们。

**已根治**：这些目录现在全部移出 git 跟踪，写进 `.gitignore`。以后你跑多少次
`git status` 都是干净的，再也不会冲突。

## 一次性恢复命令

```bash
cd ~/projects/bioSkills

# 丢弃产物文件的本地改动（这些文件重跑就有，丢了不可惜）
git checkout -- analysis/GSE42872/figures analysis/GSE42872/results

# 现在能正常拉了
git pull origin arena/019f9c4c-bioskills
```

拉完确认一下修复代码到位了：

```bash
ls analysis/GSE42872/scripts/annotate.py    # 应该存在
git ls-files analysis/GSE42872/figures | wc -l   # 应该是 0
```

然后重新跑：

```bash
conda activate bioskills
rm -f analysis/GSE42872/data/*.gz
bash analysis/GSE42872/run_all.sh
```

## 如果上面还不行（比如产物文件被 git 认为是"新增"）

用更强力的方式，但**只针对这两个目录**，不碰你其他文件：

```bash
cd ~/projects/bioSkills
git stash push -u -- analysis/GSE42872/figures analysis/GSE42872/results
git pull origin arena/019f9c4c-bioskills
git stash drop        # 产物不要了，重跑即可
```

## 通用排查思路

```bash
git status              # 先看清到底哪些文件被改了
git diff --stat         # 改动规模
git log --oneline -3    # 确认自己在哪个 commit
```

`git pull` 输出里如果出现 **Aborting**，就说明这次拉取**完全没发生**，
别急着跑代码 —— 先解决冲突，确认 `git log` 已经指向新 commit 再说。

## 安全 / 危险命令对照

| 安全 | 说明 |
|---|---|
| `git checkout -- <路径>` | 只丢弃指定路径的改动，其他文件不动 |
| `git stash push -u -- <路径>` | 只暂存指定路径 |
| `git fetch` / `git status` / `git diff` | 只读，永远安全 |

| ⚠️ 危险 | 后果 |
|---|---|
| `git reset --hard` | 丢弃**所有**未提交改动 |
| `git checkout .` | 同上（不限路径） |
| `git clean -fd` | **删除所有未跟踪文件** ← 最容易误删你自己的东西 |
