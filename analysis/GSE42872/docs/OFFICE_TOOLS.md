# 三个 Office 工具的定位与用法

你给的三个仓库解决的是**不同问题**，不是三选一的替代关系。

| 仓库 | 是什么 | 本任务用得上吗 |
|---|---|---|
| [python-docx](https://github.com/python-openxml/python-docx) | Python 库，直接读写 .docx | ✅ **本次用它生成** |
| [iOfficeAI/OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) | 单二进制 CLI，AI agent 操作 Office | ⭕ 适合**二次编辑/转 PDF** |
| [vgrem/office365-rest-python-client](https://github.com/vgrem/office365-rest-python-client) | Microsoft Graph / SharePoint API 客户端 | ❌ 云端 API，本地生成用不上 |
| [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) | 学术写作规范 skill 集 | ✅ **论文写作规范参考** |

---

## 1. python-docx —— 本次实际使用

**为什么选它**：纯 Python，跨平台，不需要安装 Office，能精确控制中文字体、
表格、图片、页码。生成脚本见 `scripts/06_make_docx.py`。

```bash
pip install python-docx        # 实测 1.2.0
python analysis/GSE42872/scripts/06_make_docx.py
```

### 中文排版的关键坑

python-docx **不会自动设置中文字体**。只设 `run.font.name` 只影响西文，
中文会 fallback 到默认字体。必须手动写 `w:eastAsia` 属性：

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_run_font(run, en="Times New Roman", zh="宋体"):
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    rfonts.set(qn("w:eastAsia"), zh)   # ← 这行决定中文字体
```

验证方法（解压 docx 看 XML）：
```bash
python -c "
import zipfile,re
xml=zipfile.ZipFile('doc.docx').read('word/document.xml').decode()
print(re.search(r'<w:rFonts[^>]*>',xml).group())
"
# 应看到 w:eastAsia=\"宋体\"
```

### 页码域

页码不是普通文本，是 Word 的域（field），要插 `fldSimple`：

```python
fld = OxmlElement("w:fldSimple")
fld.set(qn("w:instr"), "PAGE")
section.footer.paragraphs[0]._element.append(fld)
```

---

## 2. OfficeCLI —— 生成之后的二次处理

**定位**：单个二进制文件（33 MB），无需装 Office，专为 AI agent 设计的
Word/Excel/PPT 命令行工具。**适合对已有 docx 做批量编辑、格式转换**。

### 安装

```bash
# Linux x64
curl -L -o officecli \
  https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.142/officecli-linux-x64
chmod +x officecli
sudo mv officecli /usr/local/bin/

# 其他平台把文件名换成：
#   officecli-linux-arm64 / officecli-mac-x64 / officecli-mac-arm64
#   officecli-win-x64.exe / officecli-win-arm64.exe
```

> ⚠️ 我的沙箱访问不了 `release-assets.githubusercontent.com`，
> 所以没能在这边实测。你本地网络正常应该能装上。
> 校验：`curl -L .../SHA256SUMS` 比对哈希。

### 常用操作

```bash
# 查看文档内容
officecli word read analysis/GSE42872/docs/GSE42872_论文.docx

# 转 PDF（投稿常需要）
officecli word convert GSE42872_论文.docx --to pdf

# 批量替换（比如把占位的作者信息换掉）
officecli word replace GSE42872_论文.docx \
  --find "作者姓名" --replace "张三"
officecli word replace GSE42872_论文.docx \
  --find "email@institution.edu" --replace "zhangsan@xxx.edu.cn"

# 追加内容
officecli word append GSE42872_论文.docx --text "补充说明……"
```

具体子命令以 `officecli --help` 为准（版本迭代较快）。

### 什么时候用它而不是 python-docx

| 场景 | 推荐 |
|---|---|
| 从零生成结构化文档 | python-docx（代码可控） |
| 改已有 docx 的几处文字 | OfficeCLI（一行命令） |
| docx → PDF | OfficeCLI |
| 批处理几十个文件 | OfficeCLI |
| 需要精细控制样式/字体/域 | python-docx |

---

## 3. office365-rest-python-client —— 云端场景

**定位**：Microsoft Graph / SharePoint / OneDrive 的 Python API 客户端。
它**不生成文档**，是把文档传到 M365 或从云端读取。

本任务是本地生成 docx，用不上它。但如果你需要把成品同步到组织的 SharePoint：

```python
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential

ctx = ClientContext("https://yourorg.sharepoint.com/sites/research") \
        .with_credentials(ClientCredential(client_id, client_secret))

with open("GSE42872_论文.docx", "rb") as f:
    ctx.web.get_folder_by_server_relative_url("Shared Documents") \
       .upload_file("GSE42872_论文.docx", f.read()).execute_query()
```

需要 Azure AD 应用注册和权限配置，属于 IT 侧工作。

---

## 4. nature-skills —— 论文写作规范

31k star 的学术写作 skill 集，含 19 个 skill：

```
nature-writing        论文各章节起草（本次参考）
nature-polishing      语言润色
nature-statistics     统计报告规范
nature-figure         科研绘图
nature-citation       引用管理
nature-reviewer       模拟同行评审
nature-response       审稿意见回复
...
```

### 本次实际采用的规则

从 `skills/nature-writing/static/core/stance.md` 提取：

1. **作者证据优先** —— 不编造结果、机制、引用、样本量、统计量。
   论文里每个数字都来自 `results/` 的真实输出，我逐条核对过。
2. **先写论证链再写句子** —— 先确定 claim / evidence / boundary 三要素。
3. **Claim discipline** —— 动词分级（show / demonstrate / suggest / indicate），
   删除无支撑的"首次""前所未有""革命性"。
   > 实测检查：生成的论文中这类词汇出现 **0 次**。
4. **讲清 boundary** —— claim 到哪里为止。

### 这条规则如何影响了论文内容

最典型的一处：GSEA 显示"黑色素细胞分化"基因集 FDR=0.003 显著，
按常规写法可以写成"维罗非尼诱导黑色素细胞重新分化"。但我查了前沿基因构成：

```
MELANOCYTE_DIFFERENTIATION  NES=+1.77  FDR=0.003  Tag 2/7  Lead: DCT;MITF
```

集合内 7 个基因只有 2 个进入前沿，而且：
- TYR: padj=0.18（不显著）
- PMEL: padj=0.46（不显著）
- MLANA: padj=1.00（完全无变化）
- MITF: logFC 仅 +0.75

**信号几乎全由 DCT 单基因驱动**。所以论文 3.4 节如实写成：

> "该信号主要由 DCT 单基因的大幅上调驱动，尚不足以支持'黑色素细胞整体重新分化'的结论。"

并在讨论中借此说明"GSEA 的 FDR 应与前沿基因占比联合解读"。

这就是 claim discipline 的实际作用——**有显著性不等于有结论**。

### 安装完整 skill 集

```bash
git clone https://github.com/Yuan1z0825/nature-skills.git
# 各 skill 目录下有 install.sh，按你的 agent 环境安装
```

---

## 小结

本次的工具组合：

```
真实分析结果 (results/)
      │
      ├── nature-skills 的写作规范  ──┐
      │                              ├──► python-docx ──► 两个 .docx
      └── 图件 (figures/)  ───────────┘                        │
                                                               ▼
                                                    OfficeCLI（可选）
                                                    转 PDF / 替换作者信息
```
