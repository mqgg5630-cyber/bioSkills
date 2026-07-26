# push 报 403：Permission denied

```
remote: Permission to mqgg5630-cyber/bioSkills.git denied to shaohuawen03-cyber.
fatal: ... The requested URL returned error: 403
```

## 好消息

**数据已经处理完并 commit 了**，只差推送这一步：

```
瘦身: 112 MB -> 48 MB (43%)
保留: 90,617 核 x 4,015 基因  (AD 48,570 / NC 42,047)
commit: 722f9db  ← 在你本地，安全
```

体积检查全绿：
```
✓ 26MB GSE23586_CEL.tar
✓ 48MB gse157827_prepared.h5ad
✓  0MB gse157827_qc_per_sample.csv
```

---

## 原因

你的 git 凭据是 **`shaohuawen03-cyber`** 账号，
但仓库属于 **`mqgg5630-cyber`**。这个账号对该仓库没有写权限。

大概率是 WSL 里缓存了另一个 GitHub 账号的凭据。

---

## 方案 A：换成正确账号的凭据（推荐）

### A1. 先看当前用的是什么凭据

```bash
# 查凭据助手配置
git config --list | grep -i credential

# 如果用的是 store，看缓存文件
cat ~/.git-credentials 2>/dev/null
```

### A2. 清掉旧凭据

```bash
# 清 store 里的
rm -f ~/.git-credentials

# 清 cache 里的
git credential-cache exit 2>/dev/null

# 如果配了 Windows 凭据管理器，也清一下
git config --global --unset credential.helper
```

Windows 侧还要清：**控制面板 → 凭据管理器 → Windows 凭据 →
找到 `git:https://github.com` → 删除**。

### A3. 用 mqgg5630-cyber 账号的 PAT 重新推

```bash
cd ~/projects/bioSkills
git push origin arena/019f9c4c-bioskills
# 提示输入时：
#   Username: mqgg5630-cyber
#   Password: <粘贴 PAT，不是登录密码>
```

PAT 生成：GitHub → Settings → Developer settings →
Personal access tokens → Tokens (classic) → Generate new token →
**勾选 `repo` 权限** → 复制。

> ⚠️ GitHub 从 2021 年起不接受账号密码推送，必须用 PAT。

想让它记住：
```bash
git config --global credential.helper store
# 下次输入一遍就会存到 ~/.git-credentials（明文，注意安全）
```

---

## 方案 B：把 shaohuawen03-cyber 加为协作者

如果 `shaohuawen03-cyber` 也是你的账号，直接给它权限最省事：

1. 用 **mqgg5630-cyber** 登录 GitHub
2. 进 `mqgg5630-cyber/bioSkills` 仓库
3. Settings → Collaborators → Add people
4. 输入 `shaohuawen03-cyber`，选 **Write** 权限
5. 用 shaohuawen03-cyber 账号接受邀请（邮件或 GitHub 通知里）
6. 回 WSL 重推：

```bash
cd ~/projects/bioSkills
git push origin arena/019f9c4c-bioskills
```

---

## 方案 C：改用 SSH（一劳永逸）

HTTPS 的凭据管理在 WSL 里经常出岔子，SSH 更干净，
而且顺带解决你之前遇到的 `Connection reset by peer`。

```bash
# 1. 生成密钥（如果还没有）
ssh-keygen -t ed25519 -C "wsl-bioskills"
# 一路回车即可

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub
```

3. 把输出粘到 **mqgg5630-cyber 账号**的
   GitHub → Settings → SSH and GPG keys → New SSH key

```bash
# 4. 测试（应显示 Hi mqgg5630-cyber!）
ssh -T git@github.com

# 5. 切换 remote
cd ~/projects/bioSkills
git remote set-url origin git@github.com:mqgg5630-cyber/bioSkills.git

# 6. 推送
git push origin arena/019f9c4c-bioskills
```

若 22 端口被封，走 443：
```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  Hostname ssh.github.com
  Port 443
  User git
EOF
```

---

## 关于你装的 Git LFS

**这次用不上了。** 瘦身后最大文件只有 48 MB，远低于 100 MB 上限，
普通 git 就能传，不用 LFS、不用买 Data Pack。

装了也没坏处，留着以后用。但**别对这批文件启用 LFS** ——
会平白消耗你 1 GB 的免费额度。

如果之前已经 `git lfs track` 了 `.h5ad` 或 `.tar`，检查一下：

```bash
cat .gitattributes 2>/dev/null
```

看到 `*.h5ad filter=lfs ...` 之类的就撤销：

```bash
git lfs untrack "*.h5ad"
git lfs untrack "*.tar"
rm -f .gitattributes        # 若里面只有 LFS 规则
git add -A && git commit -m "disable LFS, files are under 100MB"
```

---

## 顺带：几个不相关的改动混进来了

你的 `git status` 里有这些：

```
 M .gitignore
 M analysis/GSE118767/docs/*.docx
 D combined_raw/GSE781/GSE781_family.soft
 M wsl_push/push_raw.sh
?? .gitattributes
?? analysis/push_raw.sh
```

- `docx` 被改是因为你本地重跑过 `06_make_docx.py`（重新生成会改字节）
- `.gitattributes` 是 Git LFS 装完自动建的
- `wsl_push/`、`analysis/push_raw.sh` 是你自己的脚本

这些**不影响数据推送**（commit 722f9db 只含 3 个数据文件）。
推送成功后想清理：

```bash
# 丢弃 docx 的本地改动（远端版本一样，重跑会再生成）
git checkout -- analysis/GSE118767/docs

# 你自己的脚本想留就 commit，不想留就删
```

---

## 推送成功后

告诉我一声，我会：

1. 拉取 `gse157827_prepared.h5ad`（90,617 核）与 `GSE23586_CEL.tar`
2. 单细胞：QC → 聚类 → 细胞类型注释 → 小胶质细胞亚群 →
   cGAS-STING 通路打分 AD vs NC
3. 芯片：GSE23586 limma 差异表达（牙周炎 vs 健康牙龈）
4. 机器学习：Random Forest / Boruta / SVM-RFE / SHAP 对通路排序
5. 生成两个 docx（代码方法 + SCI 论文）
