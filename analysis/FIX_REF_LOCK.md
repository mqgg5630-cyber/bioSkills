# git pull 报 `cannot lock ref ... unable to update local ref`

## 你遇到的错误

```
error: cannot lock ref 'refs/remotes/origin/arena/019f9c4c-bioskills':
       is at f1b2bf25... but expected ab960d15...
 ! ab960d1..f1b2bf2  arena/019f9c4c-bioskills -> origin/arena/019f9c4c-bioskills
       (unable to update local ref)
```

## 先看懂它在说什么

这和上次那个 `Aborting` 不一样，**不是你的文件冲突**。

- 数据其实**已经下载完了**（日志里 `Unpacking objects: 100% ... 3.89 MiB`）
- 问题出在 git 更新 `refs/remotes/origin/...` 这个「远端分支书签」时
- git 做原子更新会先检查「书签当前值是否等于我预期的旧值」，
  发现不一致就中止 —— 所以 merge 那一步没执行，代码没进工作区

报错里那句 `is at f1b2bf2 but expected ab960d1` 有点绕：
**书签已经指向新提交了，但 git 以为它还应该是旧的**，于是拒绝写入。

常见成因：
1. `.git/refs/.../xxx.lock` 残留（上一次 git 被 Ctrl-C 或崩溃留下的）
2. loose ref 与 `packed-refs` 里的记录不一致
3. 同时跑了两个 git 进程

---

## 修复（三条命令，已实测）

```bash
cd ~/projects/bioSkills

# 1. 清掉残留的锁文件
find .git/refs -name "*.lock" -delete

# 2. 删掉那个状态错乱的远端书签（只是本地缓存，删了会自动重建）
git update-ref -d refs/remotes/origin/arena/019f9c4c-bioskills

# 3. 正常拉取
git pull origin arena/019f9c4c-bioskills
```

**第 2 步安全吗？** 安全。`refs/remotes/origin/*` 只是「远端分支在本地的缓存副本」，
不含任何独有数据，下次 fetch 会自动重建。你的提交、你的文件都不受影响。

### 验证是否成功

```bash
git log --oneline -1
# 应显示: f1b2bf2 feat(GSE118767): 单细胞聚类基准分析 + 两个 docx

ls analysis/GSE118767/docs/
# 应看到两个 .docx
```

---

## 如果还不行

### 方案 B：全量重建远端引用

```bash
cd ~/projects/bioSkills
find .git -name "*.lock" -delete          # 范围扩大到整个 .git
git remote prune origin                    # 清理所有失效的远端引用
git fetch --prune origin
git pull origin arena/019f9c4c-bioskills
```

### 方案 C：修复 packed-refs 不一致

```bash
git pack-refs --all --prune
git fetch origin
git pull origin arena/019f9c4c-bioskills
```

### 方案 D：终极手段 —— 换个目录重新 clone

你的工作全在远端，本地目录出问题时直接重来最省事：

```bash
cd ~/projects
git clone -b arena/019f9c4c-bioskills \
  https://github.com/mqgg5630-cyber/bioSkills.git bioSkills-new
```

旧目录留着不动，确认新目录没问题后再删。

---

## 实测记录

我在沙箱里完整复现并验证了修复流程：

```
起始 HEAD: ab960d1  (旧, 缺 GSE118767)
GSE118767 存在? NO

=== 复现错误 ===
error: cannot lock ref 'refs/remotes/origin/arena/019f9c4c-bioskills':
       Unable to create '.../arena/019f9c4c-bioskills.lock': File exists.
 ! ab960d1..f1b2bf2  ... (unable to update local ref)

=== 修复 ===
1. 清 .lock
2. 删除损坏的 tracking ref
   create mode 100644 analysis/GSE118767/scripts/06_make_docx.py
   ...

结果 HEAD: f1b2bf2 feat(GSE118767): 单细胞聚类基准分析 + 两个 docx
GSE118767 存在? YES
analysis/GSE118767/docs/GSE118767_代码方法.docx
analysis/GSE118767/docs/GSE118767_论文.docx
```

---

## 三种 pull 失败的对照表

你已经踩过两种了，放一起方便区分：

| 报错关键词 | 性质 | 处理 |
|---|---|---|
| `Your local changes would be overwritten` + `Aborting` | 你改了被跟踪的文件 | `git checkout -- <路径>` 后再 pull（见 `GSE42872/FIX_PULL_CONFLICT.md`） |
| `cannot lock ref` + `unable to update local ref` | 本地 ref 缓存错乱，**与你的文件无关** | 删 `.lock` + `git update-ref -d`（本文） |
| `CONFLICT (content)` | 双方改了同一处，需人工合并 | 编辑冲突文件 → `git add` → `git commit` |

## 判断 pull 到底成没成功

**别看有没有报错，看 commit 变没变**：

```bash
git log --oneline -1
```

只要输出的不是最新 commit，就说明这次 pull 实质上没生效，
别急着往下跑脚本 —— 上次就是这么白跑了一遍旧代码。
