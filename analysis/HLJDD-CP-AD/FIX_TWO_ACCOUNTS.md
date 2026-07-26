# 两个 GitHub 账号共存配置

`mqgg5630-cyber`（仓库所有者）和 `shaohuawen03-cyber` 都是你的号，
**不需要二选一**。下面按推荐度排序。

---

## 方案 1：URL 里指定用户名（最简单，改一行）

把 remote 改成带用户名的形式，git 就知道这个仓库该用哪个账号：

```bash
cd ~/projects/bioSkills

git remote set-url origin \
  https://mqgg5630-cyber@github.com/mqgg5630-cyber/bioSkills.git

git remote -v      # 确认变成了 https://mqgg5630-cyber@github.com/...
```

再配上按路径区分凭据：

```bash
git config --global credential.useHttpPath true
git config --global credential.helper store
```

然后推送，只会问一次密码：

```bash
git push origin arena/019f9c4c-bioskills
# Username 会自动填 mqgg5630-cyber，不用输
# Password: 贴 mqgg5630-cyber 的 PAT
```

以后这个仓库永远用 `mqgg5630-cyber`，
其他仓库用 `shaohuawen03-cyber`，互不干扰。

> `credential.useHttpPath true` 是关键：
> 默认 git 只按域名（github.com）存一份凭据，两个账号会互相覆盖；
> 开启后按完整路径存，每个仓库一份。

---

## 方案 2：直接写凭据文件（一次配好，永不再问）

```bash
# 先删掉可能冲突的旧配置
rm -f ~/.git-credentials
git config --global credential.helper store
git config --global credential.useHttpPath true

# 写入两个账号（把 ghp_xxx 换成各自的 PAT）
cat > ~/.git-credentials <<'EOF'
https://mqgg5630-cyber:ghp_你的TOKEN_A@github.com
https://shaohuawen03-cyber:ghp_你的TOKEN_B@github.com
EOF

chmod 600 ~/.git-credentials     # 明文存储，限制权限
```

配合方案 1 的 remote URL 使用效果最好。

只有 mqgg5630-cyber 的 PAT 也没关系，写一行就够：

```bash
echo "https://mqgg5630-cyber:ghp_你的TOKEN@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
```

---

## 方案 3：SSH 多账号（最干净，一劳永逸）

顺带解决你之前遇到的 `Connection reset by peer`。

### 3.1 为两个账号各生成一把密钥

```bash
ssh-keygen -t ed25519 -C "mqgg5630" -f ~/.ssh/id_mqgg -N ""
ssh-keygen -t ed25519 -C "shaohuawen03" -f ~/.ssh/id_shaohua -N ""
```

### 3.2 把公钥加到对应账号

```bash
cat ~/.ssh/id_mqgg.pub       # 加到 mqgg5630-cyber
cat ~/.ssh/id_shaohua.pub    # 加到 shaohuawen03-cyber
```

GitHub → Settings → SSH and GPG keys → New SSH key

> 同一把公钥不能加到两个账号，所以必须生成两把。

### 3.3 配置 ssh config

```bash
cat >> ~/.ssh/config <<'EOF'

Host github-mqgg
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_mqgg
  IdentitiesOnly yes

Host github-shaohua
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_shaohua
  IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config
```

### 3.4 测试

```bash
ssh -T git@github-mqgg       # 应显示 Hi mqgg5630-cyber!
ssh -T git@github-shaohua    # 应显示 Hi shaohuawen03-cyber!
```

### 3.5 切换本仓库的 remote

注意主机名用的是上面定义的别名 `github-mqgg`：

```bash
cd ~/projects/bioSkills
git remote set-url origin git@github-mqgg:mqgg5630-cyber/bioSkills.git
git push origin arena/019f9c4c-bioskills
```

其他属于 shaohuawen03-cyber 的仓库就用：
```bash
git remote set-url origin git@github-shaohua:shaohuawen03-cyber/某仓库.git
```

若 22 端口被封，在两个 Host 块里各加：
```
  Port 443
  HostName ssh.github.com
```

---

## 方案 4：让 shaohuawen03-cyber 也有权限

如果你想用当前凭据直接推，给它加协作者权限即可。

**注意路径**：是**仓库**的 Settings，不是账号的 Settings。

直达链接：
```
https://github.com/mqgg5630-cyber/bioSkills/settings/access
```

或者：仓库主页 → 顶部 **Settings** 标签页 → 左侧 **Collaborators**

> 你之前截图的是账号设置页（`github.com/settings/profile`），
> 那里没有 Collaborators，它属于仓库级设置。

加完后用 shaohuawen03-cyber 账号接受邀请（邮件或 GitHub 通知），
然后直接 push 即可。

---

## 我的建议

**先用方案 1**，三条命令，几分钟搞定：

```bash
cd ~/projects/bioSkills
git remote set-url origin https://mqgg5630-cyber@github.com/mqgg5630-cyber/bioSkills.git
git config --global credential.useHttpPath true
git config --global credential.helper store
git push origin arena/019f9c4c-bioskills
```

**PAT 在哪生成**（用 mqgg5630-cyber 登录）：
```
https://github.com/settings/tokens
→ Tokens (classic) → Generate new token (classic)
→ Note: wsl-bioskills
→ Expiration: 90 days
→ Scopes: 勾 repo
→ Generate token → 立刻复制 ghp_xxx（刷新后不再显示）
```

以后想长期省心，再花十分钟配方案 3 的 SSH。

---

## 排查：搞不清当前用的哪个账号

```bash
# 看 remote
git remote -v

# 看凭据配置
git config --list | grep -i credential

# 看存了哪些凭据
cat ~/.git-credentials 2>/dev/null

# 测试 HTTPS 认证身份（需要 gh 或直接 push 试）
curl -s -H "Authorization: token ghp_你的TOKEN" \
  https://api.github.com/user | grep '"login"'
```

Windows 凭据管理器也可能插一脚：
**控制面板 → 凭据管理器 → Windows 凭据 → `git:https://github.com`**

如果 WSL 用了 Windows 的凭据助手（`credential.helper` 里含 `manager`
或 `wincred`），删掉那条记录，或直接改用上面的 store 方式。

---

## ⚠️ 安全提醒

- **PAT 不要贴到任何聊天框**（包括发给我），它等同账号密码
- `~/.git-credentials` 是**明文**，务必 `chmod 600`
- PAT 泄露了就去 `https://github.com/settings/tokens` 点 Delete 撤销
- 建议设 90 天过期，到期换一次
