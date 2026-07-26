# git pull 报 `Connection reset by peer`

```
fatal: unable to access 'https://github.com/mqgg5630-cyber/bioSkills.git/':
       Recv failure: Connection reset by peer
```

## 先确认：这是网络问题，不是仓库问题

前两次的报错（`Aborting`、`cannot lock ref`）都是本地 git 状态问题，
这次不同 —— **ref 锁已经修好了**（没再报 lock 错），卡在网络传输上。

`Connection reset by peer` = 连接被对端或中间设备中断。
WSL + 国内网络访问 GitHub 时很常见。

远端仓库本身是好的（实测可正常 clone，最新 commit `0608565`）。

---

## 快速修复：分步拉取（推荐先试）

一次 `pull` = `fetch` + `merge`。先只做 `fetch`，失败了可以重试而不影响工作区：

```bash
cd ~/projects/bioSkills

# 1. 先只取数据，失败就重跑这一条（git 会断点续传已有对象）
git fetch origin arena/019f9c4c-bioskills

# 2. 取成功后再合并（纯本地操作，不走网络）
git merge FETCH_HEAD
```

---

## 方案 A：调大缓冲区 + 关闭多路复用

WSL 下最常见的有效组合：

```bash
git config --global http.postBuffer 524288000     # 500MB 缓冲
git config --global http.version HTTP/1.1         # 降到 HTTP/1.1，绕开 HTTP/2 的兼容问题
git config --global http.lowSpeedLimit 0          # 不因低速中断
git config --global http.lowSpeedTime 999999

git fetch origin arena/019f9c4c-bioskills
git merge FETCH_HEAD
```

`http.version HTTP/1.1` 这条对 `Connection reset` 特别有效 ——
部分网络环境对 GitHub 的 HTTP/2 长连接支持不好。

---

## 方案 B：浅克隆，只取最近几个提交

历史提交不需要的话，数据量能减少一大半：

```bash
cd ~/projects
git clone --depth 1 -b arena/019f9c4c-bioskills \
  https://github.com/mqgg5630-cyber/bioSkills.git bioSkills-shallow
```

想在现有目录里做：

```bash
cd ~/projects/bioSkills
git fetch --depth 1 origin arena/019f9c4c-bioskills
git merge FETCH_HEAD
```

---

## 方案 C：换 SSH（长期最稳）

HTTPS 走 443，容易被中间设备干扰；SSH 走 22 端口通常更稳定。

```bash
# 若还没有 SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
# 把输出贴到 GitHub → Settings → SSH and GPG keys → New SSH key

# 测试
ssh -T git@github.com

# 切换 remote
cd ~/projects/bioSkills
git remote set-url origin git@github.com:mqgg5630-cyber/bioSkills.git
git pull origin arena/019f9c4c-bioskills
```

若 22 端口被封，用 GitHub 的 443 通道：

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  Hostname ssh.github.com
  Port 443
  User git
EOF
```

---

## 方案 D：只取需要的文件（应急）

只想拿两个 docx，不做完整同步：

```bash
cd ~/projects/bioSkills
git fetch origin arena/019f9c4c-bioskills
git checkout FETCH_HEAD -- analysis/GSE118767
```

或者直接从网页下载（完全绕开 git）：

```
https://github.com/mqgg5630-cyber/bioSkills/tree/arena/019f9c4c-bioskills/analysis/GSE118767/docs
```

点进 .docx 文件页面 → 右上角 Download。

---

## 方案 E：WSL 特有问题排查

WSL2 的虚拟网卡有时会出 MTU 问题，表现就是大文件传输中断：

```bash
# 查看当前 MTU
ip link show eth0 | grep mtu

# 调小（需要 sudo，重启 WSL 后失效）
sudo ip link set dev eth0 mtu 1400

git fetch origin arena/019f9c4c-bioskills
```

DNS 也可能是诱因：

```bash
cat /etc/resolv.conf
# 若是 WSL 自动生成的地址不稳，可临时改用公共 DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```

---

## 已做的优化：减小传输量

docx 里嵌入的是 300 dpi 原图，体积偏大。已在生成脚本中加入图片压缩
（等比缩到 1800 px 宽再嵌入，Word 中显示清晰度不受影响）：

| 文件 | 优化前 | 优化后 |
|---|---|---|
| GSE118767_论文.docx | 1.9 MB | **1.47 MB** |
| GSE118767_代码方法.docx | 614 KB | **551 KB** |
| GSE42872_论文.docx | 920 KB | **803 KB** |
| GSE42872_代码方法.docx | 776 KB | **617 KB** |
| **合计** | 4.3 MB | **3.36 MB** |

---

## 四种 pull 失败的对照

| 报错 | 性质 | 处理 |
|---|---|---|
| `local changes would be overwritten` + `Aborting` | 本地文件冲突 | `git checkout -- <路径>` |
| `cannot lock ref` | ref 缓存错乱 | 删 `.lock` + `git update-ref -d` |
| **`Connection reset by peer`** | **网络中断** | **分步 fetch / HTTP1.1 / SSH（本文）** |
| `CONFLICT (content)` | 双方改同一处 | 人工合并 |

## 通用判断

```bash
git log --oneline -1
```

commit 没变 = 这次 pull 没生效，别急着跑脚本。
