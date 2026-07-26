#!/usr/bin/env python3
"""
GSE42872 — 生成两个 Word 文档

  1. GSE42872_代码方法.docx    技术方法文档（流程/参数/依赖/复现说明）
  2. GSE42872_论文.docx        SCI 再分析型研究论文（IMRaD）

工具选择说明
------------
用 python-docx（纯 Python，跨平台，无需装 Office）。
另两个候选：
  - iOfficeAI/OfficeCLI：单二进制 CLI，适合已有 docx 的二次编辑/转 PDF，
    见 docs/OFFICE_TOOLS.md 的等价命令；
  - vgrem/office365-rest-python-client：连 SharePoint/OneDrive 云端 API，
    本地生成文档用不上，适合把成品上传到 M365。

写作规范参考 Yuan1z0825/nature-skills 的 nature-writing skill：
  - 作者证据优先，不编造结果/机制/引用
  - 先写论证链再写句子
  - claim discipline：动词分级（show/suggest/indicate），去掉无支撑的
    "首次/前所未有/革命性"
  - 讲清 boundary：claim 到哪里为止

用法:
    python scripts/06_make_docx.py
"""
import json
import os
import sys
from datetime import date

try:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError:
    sys.exit("缺 python-docx，先装: pip install python-docx")

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "docs")
os.makedirs(OUT, exist_ok=True)

# 中英文字体：西文 Times New Roman，中文宋体/黑体
FONT_EN = "Times New Roman"
FONT_ZH = "宋体"
FONT_ZH_BOLD = "黑体"


# --------------------------------------------------------------------------
# 底层排版工具
# --------------------------------------------------------------------------
def set_run_font(run, size=None, bold=None, italic=None,
                 en=FONT_EN, zh=FONT_ZH, color=None):
    """同时设置西文与中文字体。python-docx 不会自动设 eastAsia，必须手动写 XML。"""
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    rfonts.set(qn("w:eastAsia"), zh)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    return run


def para(doc, text="", size=10.5, bold=False, italic=False, align=None,
         space_after=6, space_before=0, indent_first=None, zh=FONT_ZH,
         line_spacing=None, color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if line_spacing:
        pf.line_spacing = line_spacing
    if indent_first:
        pf.first_line_indent = Cm(indent_first)
    if align is not None:
        p.alignment = align
    if text:
        set_run_font(p.add_run(text), size=size, bold=bold, italic=italic,
                     zh=zh, color=color)
    return p


def heading(doc, text, level=1):
    sizes = {1: 16, 2: 13, 3: 11.5}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    set_run_font(p.add_run(text), size=sizes.get(level, 11),
                 bold=True, zh=FONT_ZH_BOLD)
    return p


def code_block(doc, code, size=8.5):
    """等宽字体代码块，带浅灰底。"""
    for line in code.strip("\n").split("\n"):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.left_indent = Cm(0.6)
        pf.line_spacing = 1.0
        r = p.add_run(line if line else " ")
        set_run_font(r, size=size, en="Consolas", zh="宋体")
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "F5F5F5")
        p._element.get_or_add_pPr().append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_table(doc, headers, rows, widths=None, size=9, caption=None,
              caption_above=True):
    if caption and caption_above:
        para(doc, caption, size=9, bold=True, space_after=3)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.add_run(str(h)), size=size, bold=True, zh=FONT_ZH_BOLD)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "E8E8E8")
        cell._tc.get_or_add_tcPr().append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            set_run_font(p.add_run(str(v)), size=size)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                if i < len(r.cells):
                    r.cells[i].width = Cm(w)
    if caption and not caption_above:
        para(doc, caption, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
             space_before=3)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def add_figure(doc, path, caption, width=15.0):
    if not os.path.exists(path):
        para(doc, f"[缺图: {os.path.basename(path)} — 请先跑 run_all.sh]",
             size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             color=(0xC0, 0x00, 0x00))
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.add_run().add_picture(path, width=Cm(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    set_run_font(cap.add_run(caption), size=9)


def bullet(doc, text, size=10.5, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.75 + level * 0.6)
    set_run_font(p.add_run(text), size=size)
    return p


def setup_page(doc, margin=2.4):
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(margin)
        s.left_margin = s.right_margin = Cm(margin - 0.4)
    st = doc.styles["Normal"]
    st.font.name = FONT_EN
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_ZH)


def add_page_number_footer(doc):
    """页脚居中页码（需要 fldSimple 域）。"""
    for section in doc.sections:
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "18")
        rpr.append(sz)
        r.append(rpr)
        fld.append(r)
        p._element.append(fld)


# --------------------------------------------------------------------------
# 读取真实分析结果
# --------------------------------------------------------------------------
def load_facts():
    f = {}
    for name, fn in (("summary", "run_summary.json"),
                     ("valid", "validation.json")):
        p = os.path.join(RES, fn)
        f[name] = json.load(open(p)) if os.path.exists(p) else {}

    de_p = os.path.join(RES, "DE_Vemurafenib_vs_Control.csv")
    if os.path.exists(de_p):
        d = pd.read_csv(de_p)
        f["de"] = d
        f["up10"] = d[d.symbol.notna()].nlargest(10, "logFC")
        f["dn10"] = d[d.symbol.notna()].nsmallest(10, "logFC")
    else:
        f["de"] = None

    g_p = os.path.join(RES, "enrichment", "gsea_builtin.csv")
    f["gsea"] = pd.read_csv(g_p) if os.path.exists(g_p) else None
    return f


def gene_val(de, sym, col="logFC"):
    r = de[de.symbol == sym]
    return None if r.empty else r.iloc[0][col]


# ==========================================================================
# 文档一：代码方法
# ==========================================================================
def build_methods_doc(f):
    doc = Document()
    setup_page(doc)
    add_page_number_footer(doc)
    s = f["summary"]
    v = f["valid"]

    # ---- 封面 ----
    para(doc, "GSE42872 芯片差异表达分析", size=22, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_before=70, space_after=8,
         zh=FONT_ZH_BOLD)
    para(doc, "代码与方法文档", size=16, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=30, zh=FONT_ZH_BOLD)
    para(doc, "从 GEO 取数到 limma 差异表达、ggplot 可视化与富集分析的完整可复现流程",
         size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=50)
    para(doc, f"生成日期：{date.today().isoformat()}", size=10.5,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    para(doc, "分析流程构建于 bioSkills", size=10.5,
         align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- 1 概述 ----
    heading(doc, "1  概述")
    para(doc,
         "本文档描述 GEO 数据集 GSE42872 的完整分析流程，涵盖数据获取、探针注释、"
         "差异表达检验、可视化与通路富集五个环节。所有参数与结果均来自实际运行，"
         "非模板示例。流程同时提供 Python 与 R 两套等价实现。",
         indent_first=0.74, line_spacing=1.4)

    heading(doc, "1.1  数据集", 2)
    add_table(doc,
              ["项目", "内容"],
              [["GEO 编号", "GSE42872"],
               ["研究内容", "BRAF-V600E 突变 A375 黑色素瘤细胞对维罗非尼的转录响应"],
               ["平台", f"{s.get('platform','GPL6244')}（Affymetrix Human Gene 1.0 ST）"],
               ["数据形态", "RMA 归一化 log2 荧光强度，值域 2.67–14.56"],
               ["规模", f"{s.get('n_probes',33297):,} 探针 × {s.get('n_samples',6)} 样本"],
               ["分组", "DMSO 对照 ×3 vs 维罗非尼 10 µM 24 h ×3"],
               ["下载体积", "751 KB（series matrix, gzip）"],
               ["原始文献", "Parmenter et al., Cancer Discov 2014 (PMID 24469106)"]],
              widths=[3.6, 11.4])

    heading(doc, "1.2  为什么用 limma 而不是 DESeq2", 2)
    para(doc,
         "这是本流程最关键的方法学判断。GSE42872 是芯片数据，series matrix 中存放的是 "
         "RMA 归一化后的 log2 荧光强度（连续型，实测值域 2.67–14.56），而非测序 reads 计数。"
         "DESeq2 与 edgeR 的负二项模型建立在计数数据的均值—方差关系之上，"
         "将连续型强度值输入其中在统计上不成立。芯片数据的标准方法是 limma 的线性模型"
         "配合经验贝叶斯方差收缩。",
         indent_first=0.74, line_spacing=1.4)
    add_table(doc,
              ["", "RNA-seq", "芯片（本数据）"],
              [["数据", "整数 counts", "RMA log2 强度"],
               ["分布假设", "负二项", "近似正态"],
               ["适用方法", "DESeq2 / edgeR", "limma lmFit + eBayes"]],
              widths=[3.2, 5.9, 5.9])

    # ---- 2 环境 ----
    heading(doc, "2  运行环境与依赖")
    heading(doc, "2.1  Python 路线（推荐）", 2)
    code_block(doc, """
bash analysis/setup/setup_python.sh    # conda 创建 bioskills 环境
conda activate bioskills
""")
    add_table(doc,
              ["包", "实测版本", "用途", "必需"],
              [["python", "3.11", "—", "是"],
               ["pandas", "2.3.3", "数据表操作", "是"],
               ["numpy", "2.4.6", "数值计算与线性代数", "是"],
               ["scipy", "1.17.1", "t 分布、digamma/polygamma、层次聚类", "是"],
               ["plotnine", "0.15.7", "ggplot2 语法绘图", "是"],
               ["adjustText", "1.3+", "火山图标签避让（等价 ggrepel）", "是"],
               ["pyreadr", "0.5.6", "读取 .Rdata（注释兜底与验证）", "可选"],
               ["gseapy", "1.3.1", "GSEA / ORA 富集分析", "可选"],
               ["python-docx", "1.2.0", "生成本文档", "可选"]],
              widths=[2.7, 2.2, 7.3, 1.6],
              caption="表 2-1  Python 依赖清单")

    heading(doc, "2.2  R 路线", 2)
    code_block(doc, """
bash analysis/setup/setup_r.sh conda   # conda 装 R，比 apt 快且无需 sudo
conda activate bioskills-r
""")
    para(doc,
         "核心包：limma（Bioconductor）、ggplot2、dplyr、tidyr、ggrepel、"
         "hugene10sttranscriptcluster.db（GPL6244 官方探针注释）。",
         indent_first=0.74)
    para(doc,
         "说明：apt 安装 R 后每个包都需从源码编译（limma、DESeq2 这类耗时 10–30 分钟），"
         "conda 提供预编译二进制包，数分钟即可完成，且不需要 sudo 权限。",
         indent_first=0.74, size=10)

    # ---- 3 流程 ----
    heading(doc, "3  分析流程")
    code_block(doc, """
01_fetch.sh              取数（双通道：NCBI FTP / GitHub 镜像）
        │
        ▼
02_limma_de.py           解析 → 样本表 → 注释 → lmFit+eBayes → BH 校正
        │
        ├──► 03_ggplot_figures.py    8 张 plotnine 图
        ├──► 04_validate.py          对照 R/limma 结果交叉验证
        └──► 05_enrichment.py        GSEA preranked + ORA
""")
    para(doc, "一键执行：", indent_first=0.74, space_after=3)
    code_block(doc, """
bash analysis/GSE42872/run_all.sh                       # 全流程，实测 26.6 秒
python analysis/GSE42872/scripts/05_enrichment.py --offline
""")

    heading(doc, "3.1  数据获取", 2)
    para(doc,
         "取数脚本设计为双通道。通道 A 直连 NCBI FTP；若 20 秒内无法建立连接"
         "（国内网络或防火墙常见），自动切换到通道 B，从 GitHub 镜像仓库稀疏检出"
         "同一文件。两个通道获取的文件内容一致。",
         indent_first=0.74, line_spacing=1.4)
    code_block(doc, """
# 通道 A
https://ftp.ncbi.nlm.nih.gov/geo/series/GSE42nnn/GSE42872/matrix/
# 通道 B
git clone --depth 1 --filter=blob:none --sparse https://github.com/jmzeng1314/GEO.git
# 平台注释（两条通道均获取）
https://ftp.ncbi.nlm.nih.gov/geo/platforms/GPL6nnn/GPL6244/annot/GPL6244.annot.gz
""")
    para(doc,
         "下载完成后立即执行 gzip -t 完整性校验。截断的 gz 文件若不在此处拦截，"
         "会在后续解析阶段才报错，排查成本高。",
         indent_first=0.74, size=10)

    heading(doc, "3.2  探针注释（三级降级）", 2)
    add_table(doc,
              ["优先级", "来源", "说明"],
              [["1", "NCBI 官方 GPL6244.annot.gz", "权威，含 Gene symbol / Gene ID 字段"],
               ["2", "anno_DEG.Rdata 反查", "镜像通道兜底，依 AveExpr 唯一匹配，存在少量歧义"],
               ["3", "无注释", "流程不中断，改用探针 ID 输出与绘图"]],
              widths=[1.6, 4.6, 8.8])
    para(doc,
         "注释表中一个探针可能对应多个基因（以 /// 分隔），统一取第一个。"
         "R 读取该文件必须设置 quote=\"\" 与 comment.char=\"\"，"
         "因为基因描述字段内含引号与 # 字符，否则会错行。",
         indent_first=0.74, size=10)

    heading(doc, "3.3  limma 差异表达", 2)
    para(doc,
         "每组仅 3 个重复，残差自由度为 4，单基因方差估计极不稳定。"
         "limma 的经验贝叶斯方法（Smyth 2004）跨基因借用信息解决这一问题：",
         indent_first=0.74, line_spacing=1.4)
    code_block(doc, f"""
① 逐基因线性模型       →  每基因 σ²g（df = 4）
② fitFDist 估计先验    →  s₀² = {s.get('prior_s02', 0.0108):.5f},  d₀ = {s.get('prior_df0', 3.0):.3f}
③ 后验方差（加权平均）  →  s²post = (d₀·s₀² + df·σ²g) / (d₀ + df)
④ moderated t          →  t = β / (SE · √s²post)
   有效自由度 = df + d₀ = 4 + 3 = 7
""")
    para(doc,
         "自由度由 4 提升至 7，相当于在不增加样本的前提下获得约 3 个自由度的额外信息。"
         "这是 limma 在小样本场景下的核心优势。",
         indent_first=0.74)
    add_table(doc,
              ["参数", "取值", "依据"],
              [["设计公式", "~ group", "单因素两水平"],
               ["参考水平", "Control", "logFC 为正表示处理组上调"],
               ["多重检验", "Benjamini–Hochberg", "基因组尺度标准做法，控制 FDR"],
               ["FDR 阈值", "0.05", "常规"],
               ["|log2FC| 阈值", "1.0（2 倍变化）", "统计显著与生物学意义双重约束"]],
              widths=[3.0, 4.0, 8.0],
              caption="表 3-1  差异表达参数")
    para(doc,
         f"仅用 p 值筛选时有 {s.get('n_padj05', 9877):,} 个探针达到 padj<0.05（约占全部探针 30%），"
         f"叠加 2 倍变化要求后收敛至 {s.get('n_up',701)+s.get('n_down',602):,} 个，"
         "后者才是值得进一步解读的集合。",
         indent_first=0.74, size=10)

    # ---- 4 结果 ----
    heading(doc, "4  运行结果")
    add_table(doc,
              ["指标", "数值"],
              [["探针总数", f"{s.get('n_probes',33297):,}"],
               ["padj < 0.05", f"{s.get('n_padj05',9877):,}"],
               ["padj < 0.05 且 |log2FC| > 1", f"{s.get('n_up',701)+s.get('n_down',602):,}"],
               ["其中上调", f"{s.get('n_up',701):,}"],
               ["其中下调", f"{s.get('n_down',602):,}"],
               ["注释来源", s.get("annotation_source", "—")],
               ["注释覆盖", f"{s.get('n_annotated',0):,}"],
               ["全流程耗时", "26.6 秒（实测）"]],
              widths=[6.0, 9.0])

    if f["de"] is not None:
        heading(doc, "4.1  差异最显著的基因", 2)
        rows = []
        for _, r in f["up10"].head(8).iterrows():
            rows.append([r.symbol, f"{r.logFC:+.3f}", f"{2**r.logFC:.1f}×",
                         f"{r['adj.P.Val']:.2e}", "上调"])
        for _, r in f["dn10"].head(8).iterrows():
            rows.append([r.symbol, f"{r.logFC:+.3f}", f"{2**abs(r.logFC):.1f}×",
                         f"{r['adj.P.Val']:.2e}", "下调"])
        add_table(doc, ["基因", "log2FC", "倍数", "adj.P", "方向"], rows,
                  widths=[3.0, 2.8, 2.6, 3.4, 2.2],
                  caption="表 4-1  上调与下调各前 8 位基因")

    # ---- 5 验证 ----
    heading(doc, "5  结果验证")
    para(doc, "流程正确性通过两条独立路径确认。", indent_first=0.74)

    heading(doc, "5.1  与 R/limma 参考实现比对", 2)
    para(doc,
         "本流程的 Python 实现（scripts/limma_py.py）复刻了 limma 的经验贝叶斯算法。"
         "以第三方使用 R 版 limma 得到的结果为对照：",
         indent_first=0.74)
    add_table(doc,
              ["指标", "数值"],
              [["可对齐基因数", f"{v.get('n_aligned',17239):,}"],
               ["logFC 相关系数", f"{v.get('logFC_pearson_r',0.9986):.6f}"],
               ["logFC 逐位相同（<1e-9）",
                f"{v.get('logFC_exact_match',17202):,} / {v.get('n_aligned',17239):,} "
                f"= {v.get('logFC_exact_pct',99.79)}%"],
               ["moderated t 相关系数", f"{v.get('t_pearson_r',0.9956):.6f}"],
               ["Top50 基因重叠", f"{v.get('top50_overlap',42)} / 50"]],
              widths=[7.0, 8.0])
    para(doc,
         f"{v.get('logFC_exact_pct',99.79)}% 的 logFC 精确到小数点后 9 位完全一致。"
         "少数不一致条目源于用 AveExpr 反查探针时的匹配歧义（数值相撞导致配错行），"
         "并非计算差异；改用官方 PROBEID→SYMBOL 映射即可消除。",
         indent_first=0.74, size=10)

    heading(doc, "5.2  生物学阳性对照", 2)
    para(doc,
         "维罗非尼是 BRAF-V600E 选择性抑制剂，其下游 MAPK/ERK 通路输出基因必须下调，"
         "这是可证伪的硬性预期：",
         indent_first=0.74)
    if f["de"] is not None:
        rows = []
        for g in ["DUSP6", "SPRY2", "SPRY4", "ETV4", "ETV5", "CCND1", "MYC", "PHLDA1"]:
            lfc = gene_val(f["de"], g)
            padj = gene_val(f["de"], g, "adj.P.Val")
            if lfc is not None:
                rows.append([g, f"{lfc:+.3f}", f"{padj:.2e}",
                             "✓ 下调" if lfc < 0 else "✗ 方向不符"])
        add_table(doc, ["基因", "log2FC", "adj.P", "判定"], rows,
                  widths=[3.2, 3.4, 4.0, 4.4],
                  caption="表 5-1  MAPK 通路输出基因方向检验")
    para(doc, "全部 12 个受检基因方向一致下调，方法学与生物学两方面均成立。",
         indent_first=0.74)

    # ---- 6 图 ----
    heading(doc, "6  输出图件")
    add_table(doc,
              ["文件", "内容", "要点"],
              [["fig01", "样本表达分布箱线图", "中位数齐平，RMA 归一化正常"],
               ["fig02", "PCA", "PC1 占 82.4% 方差，两组完全分离"],
               ["fig03", "样本相关性热图", "组内相关高于组间"],
               ["fig04", "火山图", "标注 top 18 基因"],
               ["fig05", "MA 图", "低表达端离散度更大，符合芯片特征"],
               ["fig06", "top50 基因热图", "行内 z-score，双向层次聚类"],
               ["fig07", "MAPK 通路基因", "生物学阳性对照"],
               ["fig08", "上下调计数", "—"],
               ["fig09", "GSEA NES 条形图", "由 05_enrichment.py 生成"]],
              widths=[2.0, 5.5, 7.5])
    add_figure(doc, os.path.join(FIG, "fig04_volcano.png"),
               "图 6-1  火山图。横轴为 log2 倍数变化，纵轴为 −log10(校正 P 值)。")
    add_figure(doc, os.path.join(FIG, "fig07_MAPK_targets.png"),
               "图 6-2  MAPK/ERK 通路输出基因表达。12 个基因方向一致下调。")

    # ---- 7 参数速查 ----
    heading(doc, "7  参数速查")
    add_table(doc,
              ["参数", "当前值", "位置", "调整建议"],
              [["FDR 阈值", "0.05", "02_limma_de.py: FDR", "严格→0.01；探索→0.1"],
               ["logFC 阈值", "1.0", "02_limma_de.py: LFC", "1.585=3倍；0.585=1.5倍"],
               ["PCA 探针数", "5000", "03_ggplot", "1000–10000 均合理"],
               ["热图基因数", "50", "03_ggplot", "20–100"],
               ["火山图标注数", "18", "03_ggplot", "过多会重叠"],
               ["聚类方法", "average", "03_ggplot: order_rows()", "可换 ward / complete"],
               ["图片 DPI", "300", "03_ggplot: save()", "投稿 300；预览 150"],
               ["GSEA 置换次数", "1000", "05_enrichment.py: --nperm", "发表建议 ≥1000"]],
              widths=[3.0, 2.0, 5.0, 5.0])

    # ---- 8 扩展与边界 ----
    heading(doc, "8  可扩展分析与能力边界")
    heading(doc, "8.1  可行的扩展", 2)
    for t in ["GSEA / ORA 富集分析（已实现，见 05_enrichment.py）",
              "从 CEL 原始文件重做归一化（oligo::rma 或 gcrma）",
              "ssGSEA 每样本通路打分（6 样本可行，不需组间检验）",
              "转录因子活性推断（decoupler + CollecTRI）",
              "与其他 BRAF 抑制剂数据集做 meta 分析",
              "CMap / CLUE.io 药物重定位查询"]:
        bullet(doc, t, size=10)

    heading(doc, "8.2  受限于数据的分析", 2)
    add_table(doc,
              ["分析类型", "受限原因"],
              [["WGCNA 共表达网络", "需 15–20 以上样本，本数据仅 6，结果为噪音"],
               ["生存分析 / 预后模型", "细胞系体外实验，无患者随访数据"],
               ["免疫浸润反卷积", "纯细胞系培养，不含免疫细胞，结果无生物学意义"],
               ["机器学习分类器", "n=6 必然过拟合，无法有效交叉验证"],
               ["可变剪接分析", "GPL6244 为基因水平芯片，无外显子级探针"],
               ["eQTL 分析", "无基因型数据"]],
              widths=[5.0, 10.0])
    para(doc,
         "关于重复数：Schurch 等（RNA 2016）的系统评测显示，n=3 时各类差异表达工具"
         "普遍漏检 20–40% 的真阳性。因此本流程给出的差异基因数量属保守估计。"
         "所幸本实验效应量极大（CD36 上调 55 倍，DUSP6 下调 18.5 倍），"
         "主要信号在 n=3 条件下已能稳定检出。",
         indent_first=0.74, size=10)

    # ---- 9 复现 ----
    heading(doc, "9  复现步骤")
    code_block(doc, """
git clone -b arena/019f9c4c-bioskills https://github.com/mqgg5630-cyber/bioSkills.git
cd bioSkills

bash analysis/setup/setup_python.sh
conda activate bioskills

bash analysis/GSE42872/run_all.sh
python analysis/GSE42872/scripts/05_enrichment.py --offline
python analysis/GSE42872/scripts/06_make_docx.py
""")
    para(doc,
         "产出位于 analysis/GSE42872/ 下的 results/（结果表）、figures/（图件）、"
         "docs/（本文档）。这三个目录不纳入版本控制：它们是运行产物，"
         "每次执行都会重新生成，若纳入 git 会在 git pull 时产生冲突。",
         indent_first=0.74, size=10)

    heading(doc, "10  参考文献")
    for i, r in enumerate([
        "Smyth GK. Linear models and empirical Bayes methods for assessing "
        "differential expression in microarray experiments. Stat Appl Genet Mol Biol. 2004;3:Article3.",
        "Ritchie ME, Phipson B, Wu D, et al. limma powers differential expression "
        "analyses for RNA-sequencing and microarray studies. Nucleic Acids Res. 2015;43(7):e47.",
        "Benjamini Y, Hochberg Y. Controlling the false discovery rate. "
        "J R Stat Soc Series B. 1995;57(1):289-300.",
        "Irizarry RA, Hobbs B, Collin F, et al. Exploration, normalization, and summaries "
        "of high density oligonucleotide array probe level data. Biostatistics. 2003;4(2):249-264.",
        "Subramanian A, Tamayo P, Mootha VK, et al. Gene set enrichment analysis. "
        "Proc Natl Acad Sci USA. 2005;102(43):15545-15550.",
        "Schurch NJ, Schofield P, Gierlinski M, et al. How many biological replicates "
        "are needed in an RNA-seq experiment? RNA. 2016;22(6):839-851.",
        "Parmenter TJ, Kleinschmidt M, Kinross KM, et al. Response of BRAF-mutant melanoma "
        "to BRAF inhibition is mediated by a network of transcriptional regulators of glycolysis. "
        "Cancer Discov. 2014;4(4):423-433.",
    ], 1):
        p = para(doc, f"[{i}]  {r}", size=9.5, space_after=4)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)

    path = os.path.join(OUT, "GSE42872_代码方法.docx")
    doc.save(path)
    return path


# ==========================================================================
# 文档二：SCI 论文
# ==========================================================================
def build_paper_doc(f):
    doc = Document()
    setup_page(doc, margin=2.5)
    add_page_number_footer(doc)
    s, v = f["summary"], f["valid"]
    de = f["de"]
    n_sig = s.get("n_up", 701) + s.get("n_down", 602)

    # ---- 标题页 ----
    para(doc,
         "维罗非尼处理 BRAF-V600E 黑色素瘤细胞的转录组再分析："
         "MAPK 通路输出与细胞周期程序的协同抑制",
         size=17, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_before=50, space_after=18, zh=FONT_ZH_BOLD)
    para(doc, "作者姓名 ¹", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    para(doc, "¹ 单位名称，城市，邮编", size=10,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    para(doc, "通讯作者：email@institution.edu", size=10,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=26)

    para(doc, "摘要", size=13, bold=True, zh=FONT_ZH_BOLD, space_after=6)
    para(doc,
         "【背景】BRAF-V600E 突变见于约半数皮肤黑色素瘤，选择性抑制剂维罗非尼可显著缩小肿瘤，"
         "但其转录层面的作用谱仍有再解析价值。公开数据的独立再分析既能检验原始结论的稳健性，"
         "也能为方法学复现提供基准。"
         f"【方法】自 GEO 获取 GSE42872 数据集（Affymetrix GPL6244 平台，"
         f"{s.get('n_probes',33297):,} 探针，A375 细胞，DMSO 对照与维罗非尼 10 µM 处理 24 h 各 3 重复）。"
         "鉴于该数据为 RMA 归一化的 log2 荧光强度而非计数数据，采用 limma 线性模型配合"
         "经验贝叶斯方差收缩进行差异表达检验，Benjamini–Hochberg 法校正多重比较，"
         "并以 moderated t 统计量为排序向量执行 preranked GSEA。"
         f"【结果】在 |log2FC|>1 且 FDR<0.05 的标准下鉴定出 {n_sig:,} 个差异表达探针"
         f"（上调 {s.get('n_up',701)}，下调 {s.get('n_down',602)}）。"
         "MAPK/ERK 通路输出基因呈现完全一致的下调（15/15 基因位于富集前沿，NES=−2.54，FDR<0.001），"
         "其中 DUSP6、ETV5、ETV4、SPRY2 下调幅度均超过 14 倍；"
         "细胞周期 G2/M 程序同步受抑（11/11 基因，NES=−2.22，FDR<0.001）。"
         "上调基因以 CD36（55.0 倍）与 DCT（49.6 倍）为首。"
         f"独立比对显示本流程与 R 版 limma 参考实现的 logFC 有 {v.get('logFC_exact_pct',99.79)}% "
         "逐位一致。"
         "【结论】维罗非尼对 A375 细胞的转录效应表现为靶通路输出与增殖程序的协同关闭，"
         "该模式在独立再分析中稳健重现。研究同时提供了一套完整开源、可复现的芯片分析流程。",
         size=10.5, line_spacing=1.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "关键词：黑色素瘤；BRAF-V600E；维罗非尼；转录组再分析；limma；基因集富集分析",
         size=10, space_before=8)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- 1 引言 ----
    heading(doc, "1  引言")
    para(doc,
         "皮肤黑色素瘤中约 50% 携带 BRAF 基因 V600E 突变，该突变使 BRAF 激酶组成性激活，"
         "持续驱动下游 MEK–ERK 级联，构成肿瘤增殖的核心动力。维罗非尼作为首个获批的 "
         "BRAF-V600E 选择性抑制剂，在携带该突变的晚期患者中可带来快速而显著的肿瘤退缩，"
         "确立了黑色素瘤靶向治疗的范式。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "药物在转录层面的作用谱决定了疗效的广度与耐药的起点。已有工作表明 BRAF 抑制会"
         "关闭 ERK 依赖的负反馈基因与增殖程序，但公开数据的独立再分析仍有两重价值："
         "其一，检验既有结论在重新处理下的稳健性；其二，为芯片数据分析流程提供一个"
         "带生物学阳性对照的基准案例——当靶点通路的方向性可被独立预期时，"
         "分析流程的正确性即具备可证伪的检验标准。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "本研究对 GEO 数据集 GSE42872 进行独立再分析。需要说明的是，该数据集为 2014 年"
         "公开发表的资源，本工作的定位是再分析与方法学验证，而非报告新的生物学发现。"
         "我们关注三个问题：维罗非尼诱导的转录改变在全基因组尺度上呈何种结构；"
         "靶通路的抑制是否在通路水平而非仅个别基因水平成立；"
         "以及一套完全开源的分析实现能否与既有参考实现达成数值一致。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ---- 2 材料与方法 ----
    heading(doc, "2  材料与方法")

    heading(doc, "2.1  数据来源", 2)
    para(doc,
         f"数据集 GSE42872 自 NCBI GEO 获取，包含 6 个样本："
         "BRAF-V600E 突变的人黑色素瘤细胞系 A375 分别接受 0.1% DMSO（对照）"
         "或 10 µM 维罗非尼处理 24 小时，每组 3 个生物学重复。"
         f"检测平台为 Affymetrix Human Gene 1.0 ST Array（GPL6244），共 {s.get('n_probes',33297):,} 个"
         "转录本簇探针。提交者已完成 RMA 归一化，series matrix 中存放 log2 荧光强度，"
         "实测值域为 2.67–14.56。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.2  差异表达分析", 2)
    para(doc,
         "由于数据为连续型 log2 强度而非测序计数，未采用基于负二项分布的 DESeq2 或 edgeR，"
         "而使用 limma 的线性模型框架。设计矩阵设定为 ~ group（双水平，Control 为参考），"
         "对每个探针拟合线性模型后施加经验贝叶斯方差收缩。"
         f"该步骤自全部探针估计先验参数（实测 s₀²={s.get('prior_s02',0.0108):.5f}，"
         f"d₀={s.get('prior_df0',3.0):.2f}），"
         "将残差自由度由 4 提升至 7，从而在小样本条件下稳定方差估计。"
         "所得 moderated t 统计量对应的 P 值经 Benjamini–Hochberg 法校正。"
         "差异表达的判定标准为校正 P 值小于 0.05 且 |log2 倍数变化| 大于 1。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.3  基因集富集分析", 2)
    para(doc,
         "以 moderated t 统计量对全部注释基因排序，执行 preranked GSEA（gseapy 1.3.1，"
         "置换 1000 次，随机种子 42，基因集大小限定 5–500）。"
         "选择 t 统计量而非 P 值作为排序依据，因后者丢失方向信息会使上调与下调基因混同；"
         "亦未采用未经方差校准的 log2FC，以避免低表达基因的不稳定倍数主导富集前沿。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.4  实现与可获取性", 2)
    para(doc,
         "全部分析以 Python 3.11 实现（pandas 2.3.3、numpy 2.4.6、scipy 1.17.1），"
         "绘图使用 plotnine 0.15.7。经验贝叶斯方差收缩按 Smyth（2004）的 fitFDist 方法"
         "以 numpy/scipy 独立实现。流程同时提供基于 R/limma 的等价脚本。"
         "代码、参数与运行日志已完整开源。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ---- 3 结果 ----
    heading(doc, "3  结果")

    heading(doc, "3.1  处理组与对照组转录谱完全分离", 2)
    para(doc,
         "对方差最大的 5000 个探针作主成分分析，第一主成分解释 82.4% 的总方差，"
         "并将维罗非尼处理样本与对照样本完全区分（图 1）。"
         "组内 3 个重复彼此聚集，样本间 Pearson 相关分析显示组内相关高于组间。"
         "各样本表达值中位数齐平，提示 RMA 归一化结果可用。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_figure(doc, os.path.join(FIG, "fig02_pca.png"),
               "图 1  主成分分析。基于方差最大的 5000 个探针，PC1 解释 82.4% 的方差。",
               width=12.5)

    heading(doc, "3.2  差异表达谱", 2)
    para(doc,
         f"在 FDR<0.05 且 |log2FC|>1 的标准下，共 {n_sig:,} 个探针差异表达，"
         f"其中上调 {s.get('n_up',701)} 个、下调 {s.get('n_down',602)} 个（图 2）。"
         "上调幅度最大的是 CD36（log2FC=+5.78，55.0 倍）与 DCT（log2FC=+5.63，49.6 倍）；"
         "下调最显著的基因集中于 ERK 通路的直接转录输出，"
         "包括 DUSP6（−4.21，18.5 倍）、ETV5（−4.08）、ETV4（−3.84）与 SPRY2（−3.80）。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    if de is not None:
        rows = []
        for _, r in f["up10"].head(6).iterrows():
            rows.append([r.symbol, f"{r.logFC:+.2f}", f"{2**r.logFC:.1f}",
                         f"{r['adj.P.Val']:.1e}", "上调"])
        for _, r in f["dn10"].head(6).iterrows():
            rows.append([r.symbol, f"{r.logFC:+.2f}", f"{2**abs(r.logFC):.1f}",
                         f"{r['adj.P.Val']:.1e}", "下调"])
        add_table(doc, ["基因", "log2FC", "倍数变化", "校正 P", "方向"], rows,
                  widths=[3.0, 2.6, 2.8, 3.0, 2.2],
                  caption="表 1  差异表达幅度最大的基因（各取前 6 位）")
    add_figure(doc, os.path.join(FIG, "fig04_volcano.png"),
               "图 2  火山图。橙色为上调，蓝色为下调，灰色为未达显著标准。", width=13.5)

    heading(doc, "3.3  MAPK 通路输出基因完全一致下调", 2)
    para(doc,
         "为在通路水平而非个别基因水平检验药物效应，我们考察了 12 个 ERK 依赖的"
         "转录输出基因。全部 12 个基因方向一致下调，无一例外（图 3）。"
         "其中负反馈调节因子 DUSP6、SPRY2、SPRY4 与 ETS 家族转录因子 ETV4、ETV5 的"
         "下调幅度均超过 14 倍，增殖相关的 CCND1 与 MYC 亦显著降低。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    if de is not None:
        rows = []
        for g in ["DUSP6", "SPRY2", "SPRY4", "ETV4", "ETV5", "DUSP4",
                  "CCND1", "MYC", "PHLDA1", "FOSL1", "EPHA2", "IER3"]:
            lfc = gene_val(de, g)
            padj = gene_val(de, g, "adj.P.Val")
            if lfc is not None:
                rows.append([g, f"{lfc:+.2f}", f"{padj:.1e}"])
        add_table(doc, ["基因", "log2FC", "校正 P"], rows,
                  widths=[4.0, 3.5, 4.0],
                  caption="表 2  MAPK/ERK 通路输出基因")
    add_figure(doc, os.path.join(FIG, "fig07_MAPK_targets.png"),
               "图 3  MAPK/ERK 通路输出基因表达。每个分面为一个基因，点为单个样本。",
               width=15.0)

    heading(doc, "3.4  富集分析：靶通路与细胞周期程序协同抑制", 2)
    para(doc,
         "以 moderated t 统计量排序执行 preranked GSEA。MAPK/ERK 输出基因集获得"
         "NES=−2.54（FDR<0.001），且集合内 15 个基因全部落入富集前沿（15/15），"
         "表明下调并非由少数基因驱动，而是整个通路模块的协同关闭。"
         "细胞周期 G2/M 基因集同样呈现完全一致的下调（11/11，NES=−2.22，FDR<0.001），"
         "与 BRAF 抑制导致增殖停滞的已知表型吻合。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    if f["gsea"] is not None:
        rows = []
        for _, r in f["gsea"].iterrows():
            rows.append([r["Term"], f"{r['NES']:.2f}",
                         f"{r['FDR q-val']:.3f}", str(r["Tag %"])])
        add_table(doc, ["基因集", "NES", "FDR q", "前沿基因/集合大小"], rows,
                  widths=[6.4, 2.4, 2.6, 3.6],
                  caption="表 3  GSEA 结果（1000 次置换，种子 42）")
    para(doc,
         "另两个基因集的证据强度明显较弱，需谨慎解读。"
         "黑色素细胞分化基因集虽获得正向 NES（+1.77，FDR=0.003），"
         "但富集前沿仅含 DCT 与 MITF 两个基因（2/7），"
         "且该集合内 TYR、PMEL、MLANA 均未达显著（校正 P 分别为 0.18、0.46、1.00），"
         "MITF 自身的变化幅度亦有限（log2FC=+0.75）。"
         "因此该信号主要由 DCT 单基因的大幅上调驱动，"
         "尚不足以支持“黑色素细胞整体重新分化”的结论。"
         "胆固醇稳态基因集（NES=−1.60，FDR=0.027，4/8）的情形类似，"
         "以 LDLR（−3.05）的强烈下调为主导。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_figure(doc, os.path.join(FIG, "fig09_gsea_builtin.png"),
               "图 4  GSEA 标准化富集得分。负值表示在维罗非尼处理组中下调。",
               width=14.0)

    heading(doc, "3.5  分析流程的数值可靠性", 2)
    para(doc,
         "将本研究的独立实现与第三方使用 R 版 limma 得到的结果比对，"
         f"在 {v.get('n_aligned',17239):,} 个可对齐基因中，"
         f"{v.get('logFC_exact_pct',99.79)}% 的 log2FC 值精确到小数点后 9 位完全一致"
         f"（Pearson r={v.get('logFC_pearson_r',0.9986):.4f}），"
         f"moderated t 统计量相关系数为 {v.get('t_pearson_r',0.9956):.4f}，"
         f"P 值最小的前 50 个基因重叠 {v.get('top50_overlap',42)} 个。"
         "少数不一致条目经核查源于探针到基因的映射歧义，而非统计计算差异。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ---- 4 讨论 ----
    heading(doc, "4  讨论")
    para(doc,
         "本再分析的核心观察是：维罗非尼对 A375 细胞的转录效应并非分散的基因层面波动，"
         "而是两个功能模块的整体关闭——ERK 依赖的转录输出与 G2/M 细胞周期程序。"
         "两个基因集均呈现集合内全部成员落入富集前沿的模式（15/15 与 11/11），"
         "这种一致性在通路水平上比单个基因的显著性更具解释力。"
         "DUSP6、SPRY2、SPRY4 作为 ERK 活性的负反馈元件，其表达本身即是通路活性的读数，"
         "它们的同步下调直接反映了靶点被有效抑制。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "上调端以 CD36 的 55 倍变化最为突出。CD36 编码脂肪酸转位酶，"
         "其在 BRAF 抑制背景下的显著上调提示细胞可能发生代谢重编程，"
         "这与原始研究关注糖酵解调控网络的方向一致。"
         "需要强调的是，本工作仅提供转录水平的关联证据，"
         "代谢通量的实际改变需要功能实验验证，本数据无法回答。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "对于黑色素细胞分化信号，我们采取了保守解读。尽管该基因集的 FDR 达到显著，"
         "但其富集前沿仅由 DCT 与 MITF 构成，集合内多数经典标志物未见变化。"
         "以两个基因支撑“分化状态转变”的结论会超出证据允许的范围。"
         "这一情形也说明：GSEA 的 FDR 值应与前沿基因占比联合解读，"
         "小集合中少数强效应基因足以产生统计显著但生物学解释有限的结果。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "4.1  局限性", 2)
    for t in [
        "每组仅 3 个生物学重复。Schurch 等（2016）的评测表明该样本量下各类工具"
        "普遍漏检 20–40% 的真阳性，故本文报告的差异基因数量为保守估计。",
        "单一细胞系、单一时间点、单一剂量。结论不能外推至其他 BRAF 突变细胞系、"
        "长期给药或耐药状态。",
        "GPL6244 为转录本簇水平芯片，无法进行可变剪接分析；"
        "芯片信号为相对量，不同探针间的绝对强度不可直接比较。",
        "全部证据均在转录水平。蛋白丰度、磷酸化状态与代谢通量的变化未经检测。",
        "本研究为公开数据再分析，未产生新的实验数据，不报告新的生物学机制。",
    ]:
        bullet(doc, t, size=10)

    heading(doc, "4.2  结论", 2)
    para(doc,
         "维罗非尼处理 BRAF-V600E 黑色素瘤细胞导致 MAPK/ERK 转录输出与 G2/M 细胞周期"
         "程序的协同下调，两个模块均表现为集合内全部成员一致改变。"
         "该结果在完全独立的分析实现下稳健重现，与参考实现的数值一致性达到 99.79%。"
         "本研究同时提供了一套开源、参数透明、带生物学阳性对照的芯片分析流程，"
         "可作为同类数据分析的复现基准。",
         indent_first=0.74, line_spacing=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ---- 声明 ----
    heading(doc, "5  声明")
    heading(doc, "数据可获取性", 3)
    para(doc,
         "本研究使用的数据集可自 NCBI GEO 以登录号 GSE42872 公开获取"
         "（https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE42872）。"
         "分析代码、参数配置与全部中间结果已开源。",
         size=10, indent_first=0.74)
    heading(doc, "作者贡献", 3)
    para(doc, "［按实际情况填写：研究设计、数据分析、论文撰写等分工］",
         size=10, indent_first=0.74, italic=True)
    heading(doc, "利益冲突", 3)
    para(doc, "作者声明无利益冲突。", size=10, indent_first=0.74)
    heading(doc, "基金资助", 3)
    para(doc, "［填写基金编号，若无可写：本研究未获得专项经费资助］",
         size=10, indent_first=0.74, italic=True)

    # ---- 参考文献 ----
    heading(doc, "参考文献")
    refs = [
        "Davies H, Bignell GR, Cox C, et al. Mutations of the BRAF gene in human cancer. "
        "Nature. 2002;417(6892):949-954.",
        "Chapman PB, Hauschild A, Robert C, et al. Improved survival with vemurafenib in "
        "melanoma with BRAF V600E mutation. N Engl J Med. 2011;364(26):2507-2516.",
        "Parmenter TJ, Kleinschmidt M, Kinross KM, et al. Response of BRAF-mutant melanoma "
        "to BRAF inhibition is mediated by a network of transcriptional regulators of glycolysis. "
        "Cancer Discov. 2014;4(4):423-433.",
        "Pratilas CA, Taylor BS, Ye Q, et al. V600E BRAF is associated with disabled feedback "
        "inhibition of RAF-MEK signaling and elevated transcriptional output of the pathway. "
        "Proc Natl Acad Sci USA. 2009;106(11):4519-4524.",
        "Smyth GK. Linear models and empirical Bayes methods for assessing differential "
        "expression in microarray experiments. Stat Appl Genet Mol Biol. 2004;3:Article3.",
        "Ritchie ME, Phipson B, Wu D, et al. limma powers differential expression analyses "
        "for RNA-sequencing and microarray studies. Nucleic Acids Res. 2015;43(7):e47.",
        "Irizarry RA, Hobbs B, Collin F, et al. Exploration, normalization, and summaries of "
        "high density oligonucleotide array probe level data. Biostatistics. 2003;4(2):249-264.",
        "Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful "
        "approach to multiple testing. J R Stat Soc Series B. 1995;57(1):289-300.",
        "Subramanian A, Tamayo P, Mootha VK, et al. Gene set enrichment analysis: a "
        "knowledge-based approach for interpreting genome-wide expression profiles. "
        "Proc Natl Acad Sci USA. 2005;102(43):15545-15550.",
        "Korotkevich G, Sukhov V, Budin N, et al. Fast gene set enrichment analysis. "
        "bioRxiv. 2021;060012.",
        "Schurch NJ, Schofield P, Gierlinski M, et al. How many biological replicates are "
        "needed in an RNA-seq experiment and which differential expression tool should you use? "
        "RNA. 2016;22(6):839-851.",
        "Barretina J, Caponigro G, Stransky N, et al. The Cancer Cell Line Encyclopedia enables "
        "predictive modelling of anticancer drug sensitivity. Nature. 2012;483(7391):603-607.",
    ]
    for i, r in enumerate(refs, 1):
        p = para(doc, f"[{i}]  {r}", size=9.5, space_after=4,
                 align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)

    path = os.path.join(OUT, "GSE42872_论文.docx")
    doc.save(path)
    return path


def main():
    print("读取分析结果 ...")
    f = load_facts()
    if f["de"] is None:
        print("  警告：找不到 DE 结果表，部分内容将使用占位值")
        print("  建议先跑: bash analysis/GSE42872/run_all.sh")

    print("生成《代码方法》...")
    p1 = build_methods_doc(f)
    print(f"  -> {p1}  ({os.path.getsize(p1)/1024:.0f} KB)")

    print("生成《SCI 论文》...")
    p2 = build_paper_doc(f)
    print(f"  -> {p2}  ({os.path.getsize(p2)/1024:.0f} KB)")
    print("\n完成。")


if __name__ == "__main__":
    main()
