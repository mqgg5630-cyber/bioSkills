# pull 失败：combined_raw/GSE781_family.soft

```
error: Your local changes to the following files would be overwritten by merge:
  combined_raw/GSE781/GSE781_family.soft
warning: 16788 lines add whitespace errors.
Merge with strategy ort failed.
```

## 先说结论

**不用切换分支。** 你在正确的分支上（`arena/019f9c4c-bioskills`）。

问题是 `combined_raw/` 这个目录 —— 它是你第一次跑 `push_raw.sh` 时留下的残留。
我查过了：**远端所有分支（包括 main 和四个 arena 分支）都没有 `combined_raw`**，
它纯粹是你本地的东西。

那个 `GSE781_family.soft` 还是个**空文件**（当时 gunzip 因为 Windows 路径失败了），
而且 GSE781 是肾癌数据，跟本课题无关。**删掉毫无损失。**

---

## 一条命令解决

```bash
cd ~/projects/bioSkills

# 如果它被 git 跟踪了，先从索引移除
git rm -r --cached combined_raw 2>/dev/null || true

# 删掉目录本身
rm -rf combined_raw

# 现在可以正常拉取
git pull origin arena/019f9c4c-bioskills
```

如果 `git pull` 还报有未提交改动，说明上面 `git rm --cached` 产生了暂存变更：

```bash
git commit -m "remove stray combined_raw"
git pull origin arena/019f9c4c-bioskills
```

---

## 如果还不行：核弹级方案（安全）

你的所有工作都在远端，本地这个目录出问题时重来最省事：

```bash
cd ~/projects
mv bioSkills bioSkills-broken          # 旧的先留着，别删
git clone -b arena/019f9c4c-bioskills \
  https://github.com/mqgg5630-cyber/bioSkills.git bioSkills
cd bioSkills
git log --oneline -1                    # 应显示 813c5fb 或更新
```

**你辛苦解压和预处理的数据不会丢** —— 它们在 `~/geodata/`，
不在仓库目录里。新 clone 完直接跑：

```bash
bash analysis/HLJDD-CP-AD/scripts/push_data.sh
```

脚本是幂等的，会自动跳过已解压、已预处理的步骤，只做瘦身和推送。

---

## 先诊断再动手（推荐）

想搞清楚到底怎么回事，跑这几条：

```bash
cd ~/projects/bioSkills

echo "--- 当前分支 ---"
git branch --show-current

echo "--- combined_raw 被跟踪了吗 ---"
git ls-files combined_raw | head -5
# 有输出 = 被跟踪（需要 git rm --cached）
# 无输出 = 只是未跟踪的普通目录（rm -rf 即可）

echo "--- 有几个提交没推 ---"
git log --oneline origin/arena/019f9c4c-bioskills..HEAD 2>/dev/null | head

echo "--- 工作区状态 ---"
git status --short | head -10
```

把输出发我，我能给更精确的指令。

---

## 关于"切换了另外的分支"

远端确实有多个 arena 分支：

```
arena/019f92fc-bioskills
arena/019f9317-bioskills
arena/019f9c4c-bioskills   ← 我们的
arena/019f9ce2-bioskills
main
```

这些是 Arena 不同会话产生的。**我们这个会话固定用 `arena/019f9c4c-bioskills`**，
所有 HLJDD-CP-AD 的代码都在它上面。

确认自己在对的分支：
```bash
git branch --show-current      # 必须是 arena/019f9c4c-bioskills
```

不对就切回来：
```bash
git checkout arena/019f9c4c-bioskills
```

---

## 为什么会有 16788 行 whitespace 警告

那个 `.soft` 文件里有大量行尾空格（`!Series_summary = ` 后面跟空格）。
git 合并时会检查空白字符问题并逐行警告。

这本身不是错误，只是噪音。真正的失败原因是前面那句
`Your local changes ... would be overwritten`。

删掉这个文件，警告和错误一起消失。
