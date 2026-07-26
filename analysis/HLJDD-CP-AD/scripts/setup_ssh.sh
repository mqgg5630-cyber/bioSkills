#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 配置 SSH 推送（替代反复出问题的 HTTPS + PAT）
#
# 为什么用 SSH：
#   - 私钥留在本机，只需要复制"公钥"（公开也无妨），不会像 token 那样误泄露
#   - 不会过期，配一次长期有效
#   - 顺带缓解此前遇到的 Connection reset by peer
#   - 不影响 shaohuawen03-cyber 账号的任何现有配置
#
# 用法：
#   bash analysis/HLJDD-CP-AD/scripts/setup_ssh.sh
# ---------------------------------------------------------------------------
set -euo pipefail

KEY="$HOME/.ssh/id_mqgg"
REPO="$HOME/projects/bioSkills"
BRANCH="arena/019f9c4c-bioskills"

echo "=================================================="
echo " 1. 生成 SSH 密钥"
echo "=================================================="
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"

if [[ -f "$KEY" ]]; then
  echo "密钥已存在: $KEY（跳过生成）"
else
  ssh-keygen -t ed25519 -C "wsl-bioskills-mqgg" -f "$KEY" -N ""
  echo "已生成: $KEY"
fi
chmod 600 "$KEY"; chmod 644 "$KEY.pub"

echo
echo "=================================================="
echo " 2. 写入 ssh config"
echo "=================================================="
CFG="$HOME/.ssh/config"
touch "$CFG"; chmod 600 "$CFG"

if grep -q "^Host github-mqgg\$" "$CFG" 2>/dev/null; then
  echo "config 里已有 github-mqgg 条目（跳过）"
else
  cat >> "$CFG" <<EOF

# bioSkills 仓库专用（mqgg5630-cyber 账号）
Host github-mqgg
  HostName github.com
  User git
  IdentityFile $KEY
  IdentitiesOnly yes
EOF
  echo "已追加 github-mqgg 到 $CFG"
fi
echo "（不影响你其他仓库和 shaohuawen03-cyber 账号的配置）"

echo
echo "=================================================="
echo " 3. 复制下面这段公钥"
echo "=================================================="
echo
cat "$KEY.pub"
echo
echo "=================================================="
cat <<'GUIDE'
把上面 ssh-ed25519 开头的【整行】复制，然后：

  1. 用 mqgg5630-cyber 账号登录 GitHub
  2. 打开 https://github.com/settings/keys
  3. 点 New SSH key
  4. Title 随便填，比如 wsl-bioskills
  5. Key 粘贴刚才复制的整行
  6. Add SSH key

公钥是公开信息，贴出来没有安全问题（私钥才要保密，它不会离开你的电脑）。

GUIDE
read -rp "加好了吗？按回车继续测试 " _

echo
echo "=================================================="
echo " 4. 测试连接"
echo "=================================================="
set +e
OUT=$(ssh -o StrictHostKeyChecking=accept-new -T git@github-mqgg 2>&1)
set -e
echo "$OUT"

if echo "$OUT" | grep -q "successfully authenticated"; then
  WHO=$(echo "$OUT" | grep -oP '(?<=Hi )[^!]+' || true)
  echo
  echo "✓ 认证成功，身份: $WHO"
  if [[ "$WHO" != "mqgg5630-cyber" ]]; then
    echo "⚠ 但这不是 mqgg5630-cyber！公钥可能加到了错误的账号下。"
    exit 1
  fi
else
  echo
  echo "✗ 认证失败。检查："
  echo "  - 公钥是否完整复制（ssh-ed25519 开头到结尾）"
  echo "  - 是否加到了 mqgg5630-cyber 账号下"
  echo
  echo "若提示 Connection timed out（22 端口被封），执行下面命令改走 443："
  cat <<'P443'

  cat >> ~/.ssh/config <<'EOF'

Host github-mqgg-443
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_mqgg
  IdentitiesOnly yes
EOF
  ssh -T git@github-mqgg-443
  # 通了的话，第 5 步的 remote 用 github-mqgg-443 替代 github-mqgg
P443
  exit 1
fi

echo
echo "=================================================="
echo " 5. 切换 remote 并推送"
echo "=================================================="
cd "$REPO"
git remote set-url origin "git@github-mqgg:mqgg5630-cyber/bioSkills.git"
echo "remote 已切换: $(git remote get-url origin)"
echo
echo "待推送的提交:"
git log --oneline origin/"$BRANCH"..HEAD 2>/dev/null | head -5 || git log --oneline -3
echo
git push origin "$BRANCH"

echo
echo "=================================================="
echo " 完成"
echo "=================================================="
git log --oneline -1
echo
echo "已上传的数据:"
ls -lh analysis/HLJDD-CP-AD/data/ 2>/dev/null || true
echo
echo "现在告诉我数据传好了，我开始分析。"
