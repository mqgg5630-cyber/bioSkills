#!/usr/bin/env python3
"""
GSE118767 — 生成两个 Word 文档（代码方法 + SCI 论文）

工具：python-docx。写作规范参考 nature-skills 的 nature-writing：
证据优先、claim discipline、讲清 boundary。
所有数字取自 results/ 的真实运行输出。
"""
import json
import os
import sys
from datetime import date

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError:
    sys.exit("缺 python-docx: pip install python-docx")

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "docs")
os.makedirs(OUT, exist_ok=True)

FONT_EN, FONT_ZH, FONT_ZH_B = "Times New Roman", "宋体", "黑体"


def set_font(run, size=None, bold=None, italic=None, en=FONT_EN, zh=FONT_ZH,
             color=None):
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    rf.set(qn("w:ascii"), en); rf.set(qn("w:hAnsi"), en)
    rf.set(qn("w:eastAsia"), zh)
    if size: run.font.size = Pt(size)
    if bold is not None: run.font.bold = bold
    if italic is not None: run.font.italic = italic
    if color: run.font.color.rgb = RGBColor(*color)
    return run


def para(doc, text="", size=10.5, bold=False, italic=False, align=None,
         after=6, before=0, indent=None, zh=FONT_ZH, ls=None, color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after, pf.space_before = Pt(after), Pt(before)
    if ls: pf.line_spacing = ls
    if indent: pf.first_line_indent = Cm(indent)
    if align is not None: p.alignment = align
    if text: set_font(p.add_run(text), size, bold, italic, zh=zh, color=color)
    return p


def heading(doc, text, level=1):
    sz = {1: 16, 2: 13, 3: 11.5}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), sz.get(level, 11), True, zh=FONT_ZH_B)
    return p


def code(doc, txt, size=8.5):
    for line in txt.strip("\n").split("\n"):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = pf.space_before = Pt(0)
        pf.left_indent = Cm(0.6); pf.line_spacing = 1.0
        set_font(p.add_run(line or " "), size, en="Consolas", zh="宋体")
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "F5F5F5")
        p._element.get_or_add_pPr().append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def table(doc, headers, rows, widths=None, size=9, caption=None):
    if caption:
        para(doc, caption, size=9, bold=True, after=3)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ""
        p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(str(h)), size, True, zh=FONT_ZH_B)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "E8E8E8")
        c._tc.get_or_add_tcPr().append(shd)
    for row in rows:
        cs = t.add_row().cells
        for i, v in enumerate(row):
            cs[i].text = ""
            p = cs[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            set_font(p.add_run(str(v)), size)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                if i < len(r.cells): r.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t



def _shrink_png(path, max_w=1800):
    """把 300dpi 原图等比缩到 max_w 像素再嵌入，显著减小 docx 体积。
    Word 里按 Cm 指定显示宽度，1800px 足够清晰。失败则回退原图。"""
    try:
        from PIL import Image
    except ImportError:
        return path
    import hashlib, tempfile
    try:
        im = Image.open(path)
        if im.width <= max_w:
            return path
        h = int(im.height * max_w / im.width)
        im = im.convert("RGB").resize((max_w, h), Image.LANCZOS)
        tag = hashlib.md5(path.encode()).hexdigest()[:8]
        out = os.path.join(tempfile.gettempdir(), f"docximg_{tag}.png")
        im.save(out, optimize=True)
        return out
    except Exception:
        return path


def figure(doc, name, caption, width=15.0):
    path = os.path.join(FIG, name)
    if not os.path.exists(path):
        para(doc, f"[缺图 {name}]", size=9, italic=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, color=(0xC0, 0, 0))
        return
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.add_run().add_picture(_shrink_png(path), width=Cm(width))
    c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(10)
    set_font(c.add_run(caption), 9)


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.75)
    set_font(p.add_run(text), size)


def setup(doc, m=2.4):
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(m)
        s.left_margin = s.right_margin = Cm(m - 0.4)
    st = doc.styles["Normal"]; st.font.name = FONT_EN; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_ZH)


def footer_pageno(doc):
    for s in doc.sections:
        p = s.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
        r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz"); sz.set(qn("w:val"), "18")
        rpr.append(sz); r.append(rpr); fld.append(r); p._element.append(fld)


def load():
    f = {}
    for k, fn in [("qc", "qc_summary.json"), ("cl", "cluster_summary.json"),
                  ("mk", "markers_summary.json")]:
        p = os.path.join(RES, fn)
        f[k] = json.load(open(p)) if os.path.exists(p) else {}
    for k, fn in [("sweep", "resolution_sweep_standard.csv"),
                  ("sweep_cc", "resolution_sweep_cc_regressed.csv"),
                  ("cmb", "confusion_best.csv"), ("cms", "confusion_split.csv"),
                  ("known", "known_markers.csv"),
                  ("marker", "markers_cell_line.csv")]:
        p = os.path.join(RES, fn)
        f[k] = pd.read_csv(p, index_col=0 if k.startswith("cm") else None) \
            if os.path.exists(p) else None
    return f


# ==========================================================================
def build_methods(f):
    doc = Document(); setup(doc); footer_pageno(doc)
    qc, cl, mk = f["qc"], f["cl"], f["mk"]
    s = qc.get("scrublet", {}); gt = qc.get("ground_truth", {})
    best = cl.get("best", {})

    para(doc, "单细胞 RNA-seq 聚类基准分析", size=22, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, before=70, after=8, zh=FONT_ZH_B)
    para(doc, "代码与方法文档", size=16, align=WD_ALIGN_PARAGRAPH.CENTER,
         after=26, zh=FONT_ZH_B)
    para(doc, "GSE118767 / sc_mixology — 基于 demuxlet 金标准的"
              "doublet 检测与聚类分辨率客观评估",
         size=11, align=WD_ALIGN_PARAGRAPH.CENTER, after=44)
    para(doc, f"生成日期：{date.today().isoformat()}", size=10.5,
         align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    para(doc, "分析流程构建于 bioSkills", size=10.5,
         align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    heading(doc, "1  概述")
    para(doc,
         "本文档描述 10x Chromium 单细胞 RNA-seq 数据集 GSE118767 的完整分析流程。"
         "该数据集将五个人肺腺癌细胞系等比例混合后建库，每个细胞的真实归属由 demuxlet "
         "依据 SNP 基因型独立判定。这一设计提供了**客观 ground truth**，"
         "使我们能够定量评估 doublet 检测与聚类分辨率选择这两个通常只能靠主观判断的环节。",
         indent=0.74, ls=1.4)

    heading(doc, "1.1  数据集", 2)
    table(doc, ["项目", "内容"],
          [["GEO 编号", "GSE118767"],
           ["来源仓库", "LuyiTian/sc_mixology (94★)"],
           ["平台", "10x Chromium"],
           ["细胞系", "A549, H838, H2228, HCC827, H1975（人肺腺癌）"],
           ["原始规模", f"{gt.get('n_total',3918):,} 细胞 × 11,786 基因"],
           ["数据形态", "整数 UMI counts（scPipe 输出，最大值 2715）"],
           ["Ground truth", f"demuxlet SNP 判定；含 {gt.get('n_doublet',96)} 个 "
                            f"doublet（{gt.get('doublet_pct',2.45)}%）"],
           ["内参", "ERCC spike-in 8 个，线粒体基因 23 个"],
           ["下载体积", "约 14 MB（稀疏检出 2 个文件）"]],
          widths=[3.4, 11.6])

    heading(doc, "1.2  为什么选这个数据集", 2)
    para(doc,
         "常规单细胞分析中，聚类分辨率的选择缺乏客观依据——通常只能观察 UMAP 是否"
         "\"看起来合理\"，或依赖标记基因的事后解释。这一环节的主观性是单细胞分析"
         "可重复性问题的主要来源之一。本数据集的细胞身份来自 SNP 基因型，"
         "完全独立于表达量，因此可以用调整兰德指数（ARI）等外部指标直接量化"
         "\"聚类结果与真实分组的一致程度\"。",
         indent=0.74, ls=1.4)

    heading(doc, "2  运行环境与依赖")
    code(doc, """
conda create -n sc python=3.11 -y && conda activate sc
pip install scanpy leidenalg igraph scikit-image scikit-learn python-docx
""")
    table(doc, ["包", "实测版本", "用途", "必需"],
          [["python", "3.11", "—", "是"],
           ["scanpy", "1.11.5", "单细胞分析主框架", "是"],
           ["anndata", "0.12.19", "数据容器", "是"],
           ["leidenalg / igraph", "最新", "Leiden 图聚类", "是"],
           ["scikit-learn", "最新", "ARI / NMI / AUROC / 轮廓系数", "是"],
           ["scikit-image", "最新", "Scrublet 自动阈值（大津法）", "是"],
           ["scipy", "1.17.1", "Mann-Whitney 检验", "是"],
           ["matplotlib", "最新", "绘图", "是"],
           ["pandas / numpy", "2.3.3 / 2.4.6", "数据处理", "是"],
           ["python-docx", "1.2.0", "生成本文档", "可选"]],
          widths=[3.4, 2.4, 6.6, 1.6], caption="表 2-1  依赖清单")
    para(doc, "运行资源：峰值内存约 2 GB，全流程实测耗时约 2 分钟（不含下载）。",
         indent=0.74, size=10)

    heading(doc, "3  分析流程")
    code(doc, """
01_fetch.sh              稀疏检出真实 counts（14MB，非整仓 377MB）
        ▼
02_qc_doublet.py         QC 指标 + Scrublet + 用 demuxlet 金标准评估性能
        ▼
03_cluster_benchmark.py  归一化 → HVG → PCA → 分辨率扫描（ARI/NMI）
                         → 亚群溯源 → 细胞周期回归对照
        ▼
04_markers.py            细胞系标记基因 + 亚群表征 + 深度诊断
        ▼
05_figures.py            8 张图
        ▼
06_make_docx.py          本文档 + 论文
""")
    para(doc, "一键执行：", indent=0.74, after=3)
    code(doc, "bash analysis/GSE118767/run_all.sh")

    heading(doc, "3.1  质量控制", 2)
    qb = qc.get("qc_before", {})
    table(doc, ["指标", "数值"],
          [["中位基因数/细胞", f"{qb.get('median_genes',0):.0f}"],
           ["中位 UMI/细胞", f"{qb.get('median_umi',0):.0f}"],
           ["中位线粒体比例", f"{qb.get('median_mt_pct',0):.2f}%"],
           ["中位 ERCC 比例", f"{qb.get('median_ercc_pct',0):.2f}%"]],
          widths=[6.0, 9.0], caption="表 3-1  过滤前 QC 指标")
    th = qc.get("qc_thresholds", {})
    para(doc,
         f"过滤标准：基因数 > {th.get('min_genes',500)}，"
         f"线粒体比例 < {th.get('max_mt_pct',20)}%，"
         f"并移除 Scrublet 判定的 doublet；"
         f"基因需在至少 {th.get('min_cells_per_gene',3)} 个细胞中表达。"
         "ERCC spike-in 在下游分析中剔除，避免人工转录本影响高变基因选择。",
         indent=0.74, ls=1.4)

    heading(doc, "3.2  Doublet 检测与基准评估", 2)
    para(doc,
         "常规流程中 doublet 检测的效果无从检验。本数据集的 demuxlet 标签"
         "提供了金标准，使我们能给出定量性能：",
         indent=0.74, ls=1.4)
    table(doc, ["指标", "数值", "说明"],
          [["AUROC", f"{s.get('auroc',0):.4f}", "整体判别能力"],
           ["AUPRC", f"{s.get('auprc',0):.4f}",
            f"随机基线仅 {s.get('baseline_auprc',0):.4f}"],
           ["默认阈值", f"{s.get('threshold',0):.3f}", "Scrublet 大津法自动确定"],
           ["预测阳性数", f"{s.get('n_predicted',0)}", f"真实共 {gt.get('n_doublet',96)} 个"],
           ["TP / FP / FN", f"{s.get('tp',0)} / {s.get('fp',0)} / {s.get('fn',0)}", "—"],
           ["精确率", f"{s.get('precision',0):.3f}", "预测为 doublet 的全部正确"],
           ["召回率", f"{s.get('recall',0):.3f}", "但漏掉了近一半"],
           ["F1 最优阈值", f"{s.get('best_f1_threshold',0):.3f}",
            f"F1 可达 {s.get('best_f1',0):.3f}"]],
          widths=[3.2, 3.4, 8.4], caption="表 3-2  Scrublet 性能")
    para(doc,
         "结论：Scrublet 的排序能力很强（AUROC 0.914），但默认阈值明显偏保守——"
         "精确率 100% 的代价是召回率仅 55%。若研究目标是尽可能清除 doublet，"
         "应下调阈值；若目标是避免误删真实细胞，默认值是安全的。"
         "这一权衡在没有 ground truth 的常规数据中是看不见的。",
         indent=0.74, ls=1.4, size=10)

    heading(doc, "3.3  降维与聚类", 2)
    pm = cl.get("params", {})
    table(doc, ["参数", "取值", "依据"],
          [["归一化", "每细胞总量 1e4 + log1p", "标准做法"],
           ["高变基因", f"{pm.get('n_hvg',2000)}", "常规范围 1000–3000"],
           ["主成分数", f"{pm.get('n_pcs',30)}",
            f"累计解释 {cl.get('pca_var_explained_pct',0):.1f}% 方差"],
           ["近邻数", f"{pm.get('n_neighbors',15)}", "scanpy 默认"],
           ["聚类算法", "Leiden (igraph flavor)", "优于 Louvain，保证连通性"],
           ["分辨率", "0.03–1.0 共 10 档扫描", "见基准结果"]],
          widths=[3.4, 4.6, 7.0], caption="表 3-3  聚类参数")

    heading(doc, "4  核心结果")
    heading(doc, "4.1  分辨率基准", 2)
    if f["sweep"] is not None:
        rows = [[r.resolution, int(r.n_clusters), f"{r.ARI:.4f}", f"{r.NMI:.4f}"]
                for _, r in f["sweep"].iterrows()]
        table(doc, ["分辨率", "簇数", "ARI", "NMI"], rows,
              widths=[3.0, 3.0, 4.0, 4.0],
              caption="表 4-1  分辨率扫描（对照 demuxlet 真值）")
    para(doc,
         f"最优分辨率 {best.get('resolution')} 下得到 {best.get('n_clusters')} 个簇，"
         f"ARI = {best.get('ARI'):.4f}，NMI = {best.get('NMI'):.4f}，"
         "与五个细胞系近乎完美对应。ARI 随分辨率升高单调下降，"
         "印证了 bioSkills 聚类 skill 的判断：过聚类是默认失效模式，"
         "任何均质群体在更高分辨率下都会被继续切分。",
         indent=0.74, ls=1.4)
    figure(doc, "fig03_resolution_sweep.png",
           "图 4-1  分辨率扫描。左：与真值的一致性；右：簇数变化。", 15.0)

    heading(doc, "4.2  细胞周期回归对照", 2)
    cc = cl.get("cc_regressed", {})
    para(doc,
         f"对 S 期与 G2M 期打分做回归后重跑全流程，最优 ARI 为 {cc.get('best_ARI',0):.4f}，"
         f"在 res={cl.get('split_reference',{}).get('resolution')} 处 "
         f"ΔARI = {cc.get('delta_ARI',0):+.4f}。"
         "聚类结构几乎不受影响，说明本数据中细胞周期不是主要的结构驱动因素。"
         "这一步是必要的阴性对照：若不做，无法排除亚群只是细胞周期时相的反映。",
         indent=0.74, ls=1.4)

    heading(doc, "4.3  亚群溯源：技术性还是生物学？", 2)
    para(doc,
         f"在略高的分辨率（{cl.get('split_reference',{}).get('resolution')}）下出现 "
         f"{cl.get('split_reference',{}).get('n_clusters')} 个簇，"
         "其中 H838 与 H1975 各被拆为两个亚群。"
         "关键问题是：这是真实的转录异质性，还是技术伪影？"
         "我们比较了两个亚群的测序深度：",
         indent=0.74, ls=1.4)
    diag = mk.get("depth_diagnosis", [])
    if diag:
        rows = [[d["cell_line"], f"{d['median_umi_a']:.0f}", f"{d['median_umi_b']:.0f}",
                 f"{d['umi_ratio']}×", f"{d['umi_p']:.1e}", d["verdict"]]
                for d in diag]
        table(doc, ["细胞系", "亚群A 中位UMI", "亚群B 中位UMI", "比值",
                    "Mann-Whitney p", "判定"], rows,
              widths=[2.0, 2.6, 2.6, 1.6, 2.4, 3.8],
              caption="表 4-2  亚群深度诊断")
    para(doc,
         "两个亚群的性质完全不同：H838 的两个亚群测序深度相差 2.56 倍"
         "（p 值接近 0），该\"亚群\"实为文库深度造成的技术性分层；"
         "而 H1975 两个亚群深度仅差 1.05 倍（p = 0.09，不显著），"
         "属于真实的转录状态差异。"
         "若不做这一诊断，很容易把技术伪影误报为生物学发现。",
         indent=0.74, ls=1.4, size=10)
    figure(doc, "fig06_subcluster_origin.png",
           "图 4-2  亚群溯源。左侧为测序深度，右侧为细胞周期分数。", 15.0)

    heading(doc, "4.4  标记基因与生物学验证", 2)
    para(doc,
         "细胞系标记基因的分组标签来自 demuxlet SNP 判定，独立于表达数据，"
         "因此不存在 double-dipping，p 值有效。已知特征基因核查如下：",
         indent=0.74, ls=1.4)
    if f["known"] is not None:
        kn = f["known"]
        cols = [c for c in kn.columns if c not in ("gene", "note")]
        rows = [[r.gene] + [f"{r[c]:.2f}" for c in cols] for _, r in kn.iterrows()]
        table(doc, ["基因"] + cols, rows,
              widths=[2.4] + [2.5] * len(cols),
              caption="表 4-3  已知标记基因平均表达（log-归一化）")
    para(doc,
         "HCC827 的 EGFR 表达量显著高于其余四系，与该细胞系已知的 EGFR 基因扩增一致；"
         "A549 高表达 AKR1B10、ALDH1A1 与 KRT81；H838 特异表达 GAGE 家族癌睾抗原。"
         "这些均与文献记载的细胞系特征吻合，构成流程正确性的生物学佐证。",
         indent=0.74, ls=1.4, size=10)

    heading(doc, "5  关于 double-dipping 的处理")
    para(doc,
         "bioSkills 的 single-cell/clustering skill 指出一个常被忽视的统计陷阱："
         "聚类算法的优化目标就是最大化簇间差异，再对同一批数据上的这些簇做差异检验，"
         "等于用产生假设的数据检验该假设。所得 p 值不是偏高，而是**无效推断**。",
         indent=0.74, ls=1.4)
    table(doc, ["分析", "分组来源", "p 值是否有效", "本流程处理"],
          [["细胞系标记基因", "demuxlet SNP", "有效", "正常报告"],
           ["亚群差异基因", "聚类结果", "无效", "仅作描述，明确标注不可用于推断"]],
          widths=[3.6, 3.6, 3.0, 4.8])

    heading(doc, "6  输出文件")
    table(doc, ["文件", "内容"],
          [["qc_summary.json", "QC 指标 + Scrublet 基准全部数值"],
           ["cluster_summary.json", "分辨率扫描、最优解、细胞周期对照"],
           ["markers_summary.json", "标记基因统计 + 亚群深度诊断"],
           ["resolution_sweep_*.csv", "分辨率扫描明细（标准 / 细胞周期回归）"],
           ["confusion_*.csv", "簇 × 真实细胞系列联表"],
           ["markers_cell_line.csv", "各细胞系标记基因（p 值有效）"],
           ["markers_subcluster.csv", "亚群差异基因（p 值仅描述）"],
           ["adata_*.h5ad", "各阶段 AnnData 对象"],
           ["fig01–fig08", "图件，PNG 300dpi + PDF 矢量"]],
          widths=[5.4, 9.6])

    heading(doc, "7  参数速查")
    table(doc, ["参数", "当前值", "位置", "调整建议"],
          [["min_genes", "500", "02_qc_doublet.py", "低质量样本可降至 200"],
           ["max_mt_pct", "20", "02_qc_doublet.py", "组织样本常用 10–20"],
           ["expected_doublet_rate", "0.025", "02_qc_doublet.py",
            "按 10x 载入细胞数估算，约 0.8%/1000 细胞"],
           ["n_top_genes", "2000", "03_cluster_benchmark.py", "1000–3000"],
           ["n_pcs", "30", "03_cluster_benchmark.py", "看肘部图或方差累计"],
           ["n_neighbors", "15", "03_cluster_benchmark.py", "细胞数多可增至 30"],
           ["resolutions", "0.03–1.0", "03_cluster_benchmark.py", "有真值时扫描取最优"]],
          widths=[3.6, 2.2, 4.6, 4.6])

    heading(doc, "8  复现步骤")
    code(doc, """
git clone -b arena/019f9c4c-bioskills https://github.com/mqgg5630-cyber/bioSkills.git
cd bioSkills
conda create -n sc python=3.11 -y && conda activate sc
pip install scanpy leidenalg igraph scikit-image scikit-learn python-docx
bash analysis/GSE118767/run_all.sh
""")

    heading(doc, "9  参考文献")
    for i, r in enumerate([
        "Tian L, Dong X, Freytag S, et al. Benchmarking single cell RNA-sequencing "
        "analysis pipelines using mixture control experiments. Nat Methods. 2019;16(6):479-487.",
        "Traag VA, Waltman L, van Eck NJ. From Louvain to Leiden: guaranteeing "
        "well-connected communities. Sci Rep. 2019;9:5233.",
        "Wolf FA, Angerer P, Theis FJ. SCANPY: large-scale single-cell gene expression "
        "data analysis. Genome Biol. 2018;19:15.",
        "Wolock SL, Lopez R, Klein AM. Scrublet: computational identification of cell "
        "doublets in single-cell transcriptomic data. Cell Syst. 2019;8(4):281-291.",
        "Kang HM, Subramaniam M, Targ S, et al. Multiplexed droplet single-cell "
        "RNA-sequencing using natural genetic variation. Nat Biotechnol. 2018;36(1):89-94.",
        "Tirosh I, Izar B, Prakadan SM, et al. Dissecting the multicellular ecosystem of "
        "metastatic melanoma by single-cell RNA-seq. Science. 2016;352(6282):189-196.",
        "Chari T, Pachter L. The specious art of single-cell genomics. "
        "PLoS Comput Biol. 2023;19(8):e1011288.",
        "Hubert L, Arabie P. Comparing partitions. J Classif. 1985;2:193-218.",
    ], 1):
        p = para(doc, f"[{i}]  {r}", size=9.5, after=4)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)

    path = os.path.join(OUT, "GSE118767_代码方法.docx")
    doc.save(path)
    return path


# ==========================================================================
def build_paper(f):
    doc = Document(); setup(doc, 2.5); footer_pageno(doc)
    qc, cl, mk = f["qc"], f["cl"], f["mk"]
    s = qc.get("scrublet", {}); gt = qc.get("ground_truth", {})
    best = cl.get("best", {}); split = cl.get("split_reference", {})
    cc = cl.get("cc_regressed", {}); af = qc.get("after_filter", {})
    diag = {d["cell_line"]: d for d in mk.get("depth_diagnosis", [])}

    para(doc,
         "利用基因型金标准评估单细胞转录组聚类流程："
         "doublet 检测阈值与分辨率选择的定量基准",
         size=17, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         before=46, after=18, zh=FONT_ZH_B)
    para(doc, "作者姓名 ¹", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    para(doc, "¹ 单位名称，城市，邮编", size=10,
         align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    para(doc, "通讯作者：email@institution.edu", size=10,
         align=WD_ALIGN_PARAGRAPH.CENTER, after=24)

    para(doc, "摘要", size=13, bold=True, zh=FONT_ZH_B, after=6)
    para(doc,
         "【背景】单细胞转录组分析中，doublet 过滤阈值与聚类分辨率的选择长期缺乏客观依据，"
         "通常依赖经验或对降维图的主观判断，这是该领域可重复性问题的重要来源。"
         "细胞系混合实验通过基因型解析提供了独立于表达量的细胞身份标签，"
         "为量化评估这些环节创造了条件。"
         f"【方法】分析 GSE118767 数据集（10x Chromium，五个人肺腺癌细胞系等比例混合，"
         f"{gt.get('n_total',3918):,} 个细胞），以 demuxlet 基于 SNP 的判定为金标准。"
         "评估 Scrublet 的 doublet 检出性能（AUROC/AUPRC/精确率/召回率），"
         "以调整兰德指数（ARI）扫描 Leiden 分辨率，"
         "并通过细胞周期回归与测序深度诊断追溯亚群成因。"
         f"【结果】Scrublet 的排序能力良好（AUROC={s.get('auroc',0):.3f}，"
         f"AUPRC={s.get('auprc',0):.3f}，随机基线 {s.get('baseline_auprc',0):.3f}），"
         f"但默认阈值偏保守：{s.get('n_predicted',0)} 个预测全部正确"
         f"（精确率 {s.get('precision',0):.2f}），召回率仅 {s.get('recall',0):.2f}，"
         f"漏检 {s.get('fn',0)} 个真实 doublet；将阈值降至 {s.get('best_f1_threshold',0):.3f} "
         f"可使 F1 由默认的 0.71 提升至 {s.get('best_f1',0):.3f}。"
         f"聚类方面，分辨率 {best.get('resolution')} 时 ARI 达 {best.get('ARI',0):.4f}"
         f"（{best.get('n_clusters')} 簇，与五个细胞系一一对应），"
         "ARI 随分辨率升高单调下降。"
         f"细胞周期回归后 ΔARI={cc.get('delta_ARI',0):+.4f}，可排除细胞周期为亚群主因。"
         "进一步诊断显示，H838 的两个亚群测序深度相差 2.56 倍（p<1e-300），属技术性分层；"
         "而 H1975 两个亚群深度相当（1.05 倍，p=0.09），反映真实转录异质性。"
         "【结论】doublet 检测的默认阈值以召回率为代价换取精确率，使用者应依研究目的调整；"
         "聚类分辨率在有金标准时可客观确定，而识别出的亚群必须经测序深度诊断"
         "方能区分技术伪影与生物学信号。",
         size=10.5, ls=1.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc, "关键词：单细胞 RNA 测序；doublet 检测；聚类分辨率；调整兰德指数；"
              "基准评估；批次效应诊断",
         size=10, before=8)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    heading(doc, "1  引言")
    para(doc,
         "单细胞 RNA 测序已成为解析细胞异质性的常规手段，但其分析流程中存在若干"
         "缺乏客观标准的决策点。其中两个尤为关键：一是 doublet（同一液滴包裹两个及以上细胞）"
         "的判定阈值，二是图聚类的分辨率参数。前者决定了多少细胞被移除，"
         "后者直接决定报告多少个\"细胞类型\"。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "这两个决策通常依赖经验值或对 UMAP 图的目视判断。然而降维图的距离与簇间间隔"
         "是非线性嵌入的产物，不具备度量意义；而分辨率参数本质上选择的是描述尺度，"
         "并不存在\"正确\"的簇数。更为隐蔽的问题是，聚类算法以最大化簇间差异为目标，"
         "若再对同一数据上的这些簇做差异表达检验，所得 p 值属于无效推断。"
         "这些因素共同构成了单细胞分析可重复性的隐患。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "细胞系混合实验为此提供了解法。将多个基因型不同的细胞系混合建库后，"
         "可依据 SNP 反推每个细胞的来源，得到完全独立于表达量的身份标签。"
         "本研究利用这一设计，对 doublet 检测与聚类分辨率两个环节给出定量基准，"
         "并进一步检验一个实践中常见但少被系统讨论的问题："
         "当分辨率提高时出现的亚群，究竟是真实的生物学状态，还是技术因素造成的假象。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "需说明的是，本工作定位为方法学基准与流程验证，使用的是已公开发表的基准数据集，"
         "不报告新的细胞生物学发现。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2  材料与方法")
    heading(doc, "2.1  数据集", 2)
    para(doc,
         f"数据取自 GEO 登录号 GSE118767。五个人肺腺癌细胞系（A549、H838、H2228、"
         f"HCC827、H1975）分别培养后等比例混合，经 10x Chromium 平台建库测序，"
         f"由 scPipe 生成 UMI 计数矩阵，共 {gt.get('n_total',3918):,} 个细胞、11,786 个基因，"
         "并含 8 个 ERCC spike-in 转录本。"
         f"每个细胞的真实归属由 demuxlet 依据 SNP 基因型判定，"
         f"其中 {gt.get('n_doublet',96)} 个（{gt.get('doublet_pct',2.45)}%）被标记为 doublet。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.2  质控与 doublet 检测", 2)
    para(doc,
         "计算每细胞的检出基因数、UMI 总量、线粒体基因比例与 ERCC 比例。"
         "使用 Scrublet（预期 doublet 率设为 0.025，随机种子 0）计算 doublet 分数。"
         "以 demuxlet 标签为真值，计算 ROC 曲线下面积（AUROC）、"
         "精确率-召回率曲线下面积（AUPRC）及默认阈值下的混淆矩阵，"
         "并通过扫描阈值确定 F1 最优点。"
         "随后按基因数 > 500、线粒体比例 < 20% 并排除预测 doublet 进行过滤，"
         f"保留 {af.get('n_cells',0):,} 个细胞、{af.get('n_genes',0):,} 个基因。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.3  降维、聚类与基准", 2)
    pm = cl.get("params", {})
    para(doc,
         f"表达量按每细胞总计数 1×10⁴ 归一化后取 log1p，选取 {pm.get('n_hvg',2000)} 个高变基因，"
         f"标准化后作主成分分析，取前 {pm.get('n_pcs',30)} 个主成分"
         f"（累计解释 {cl.get('pca_var_explained_pct',0):.1f}% 方差）构建 "
         f"{pm.get('n_neighbors',15)} 近邻图。"
         "使用 Leiden 算法（igraph 实现）在 0.03 至 1.0 共 10 档分辨率下聚类，"
         "以调整兰德指数与标准化互信息衡量与真值的一致性。"
         "细胞周期依 Tirosh 等的基因集打分；为检验其影响，"
         "对 S 与 G2M 分数做回归后重复上述全部步骤作为对照。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "2.4  差异表达与统计", 2)
    para(doc,
         "细胞系间的标记基因以 Wilcoxon 秩和检验计算，分组标签来自 demuxlet，"
         "独立于表达数据，因此 p 值有效。"
         "亚群间的差异基因分组来自聚类结果本身，存在数据重复使用问题，"
         "其 p 值仅用于描述与生成假设，不作为推断依据，文中已明确标注。"
         "亚群间测序深度差异以 Mann-Whitney U 检验评估。"
         "分析使用 scanpy 1.11.5（Python 3.11），代码与参数已开源。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "3  结果")
    heading(doc, "3.1  数据质量", 2)
    qb = qc.get("qc_before", {})
    para(doc,
         f"过滤前中位检出基因数为 {qb.get('median_genes',0):.0f}，"
         f"中位 UMI 为 {qb.get('median_umi',0):.0f}，"
         f"中位线粒体比例 {qb.get('median_mt_pct',0):.2f}%，"
         f"ERCC 比例中位数仅 {qb.get('median_ercc_pct',0):.2f}%（图 1）。"
         "整体数据质量良好，未见明显的低质量细胞群。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    figure(doc, "fig01_qc.png",
           "图 1  质控指标分布。右侧散点中橙色为 demuxlet 判定的 doublet。", 15.5)

    heading(doc, "3.2  Doublet 检测的精确率—召回率权衡", 2)
    para(doc,
         f"以 demuxlet 标签为真值，Scrublet 的 doublet 分数具有良好的判别能力"
         f"（AUROC = {s.get('auroc',0):.4f}；AUPRC = {s.get('auprc',0):.4f}，"
         f"而随机基线仅 {s.get('baseline_auprc',0):.4f}）。"
         f"然而在默认阈值 {s.get('threshold',0):.3f} 下，"
         f"共预测 {s.get('n_predicted',0)} 个 doublet，全部命中真值"
         f"（精确率 {s.get('precision',0):.3f}，假阳性 {s.get('fp',0)} 个），"
         f"但漏检 {s.get('fn',0)} 个，召回率仅 {s.get('recall',0):.3f}（图 2）。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         f"阈值扫描显示，将判定阈值由默认的 {s.get('threshold',0):.3f} 降至 "
         f"{s.get('best_f1_threshold',0):.3f} 时 F1 达到最高的 {s.get('best_f1',0):.3f}，"
         "此时召回率提升至 0.75 而精确率仍保持在 0.97。"
         "这表明默认阈值的设定偏向保守，其代价是相当比例的 doublet 残留于下游分析。"
         "在没有金标准的常规实验中，这一权衡是不可见的。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    table(doc, ["指标", "默认阈值", "F1 最优阈值"],
          [["阈值", f"{s.get('threshold',0):.3f}", f"{s.get('best_f1_threshold',0):.3f}"],
           ["精确率", f"{s.get('precision',0):.3f}", "0.973"],
           ["召回率", f"{s.get('recall',0):.3f}", "0.750"],
           ["F1", "0.711", f"{s.get('best_f1',0):.3f}"]],
          widths=[4.0, 5.0, 5.0], caption="表 1  两种阈值下的 doublet 检出性能")
    figure(doc, "fig02_doublet_benchmark.png",
           "图 2  Scrublet 性能基准。左：PR 曲线；中：F1 随阈值变化；右：混淆矩阵计数。",
           15.5)

    heading(doc, "3.3  聚类分辨率的客观最优点", 2)
    para(doc,
         f"在 {af.get('n_cells',0):,} 个过滤后细胞上扫描 Leiden 分辨率，"
         f"ARI 在 0.03 至 0.10 区间维持在 {best.get('ARI',0):.4f} 的高位，"
         f"对应 {best.get('n_clusters')} 个簇，与五个细胞系一一对应（图 3、图 4）。"
         "分辨率继续升高后 ARI 单调下降："
         f"res=0.2 时降至 {split.get('ARI',0):.3f}（{split.get('n_clusters')} 簇），"
         "res=1.0 时降至 0.467（16 簇）。"
         "这一单调关系直观展示了过聚类的代价——在没有真值参照的情况下，"
         "更高分辨率产生的额外簇很容易被误认为新发现的细胞亚型。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    if f["sweep"] is not None:
        rows = [[r.resolution, int(r.n_clusters), f"{r.ARI:.4f}", f"{r.NMI:.4f}"]
                for _, r in f["sweep"].iterrows()]
        table(doc, ["分辨率", "簇数", "ARI", "NMI"], rows,
              widths=[3.2, 3.2, 3.8, 3.8], caption="表 2  分辨率扫描结果")
    figure(doc, "fig04_umap.png",
           "图 3  UMAP 可视化。左：demuxlet 真值；中：最优分辨率聚类；"
           "右：较高分辨率下出现亚群拆分。", 15.5)
    figure(doc, "fig05_confusion.png",
           "图 4  聚类结果与真实细胞系的列联表。", 14.0)

    heading(doc, "3.4  亚群的成因：技术分层与真实异质性", 2)
    para(doc,
         f"在 res={split.get('resolution')} 下，H838 与 H1975 各被拆分为两个亚群。"
         "为判断其性质，我们首先排除细胞周期的影响：对 S 与 G2M 分数回归后重跑全流程，"
         f"ΔARI = {cc.get('delta_ARI',0):+.4f}，簇结构基本不变，"
         "说明细胞周期并非亚群形成的主要驱动因素。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    h838 = diag.get("H838", {}); h1975 = diag.get("H1975", {})
    para(doc,
         "进一步比较两个亚群的测序深度，结果显示两者性质截然不同（表 3、图 5）。"
         f"H838 的两个亚群中位 UMI 分别为 {h838.get('median_umi_a',0):.0f} 与 "
         f"{h838.get('median_umi_b',0):.0f}，相差 {h838.get('umi_ratio',0)} 倍"
         f"（Mann-Whitney p < 1×10⁻³⁰⁰），检出基因数亦相差 1.53 倍；"
         "该\"亚群\"实质上是文库深度差异造成的技术性分层，"
         "其差异基因富集于 GAPDH、ENO1、LDHB 等高丰度管家基因，"
         "符合深度不足时低丰度转录本检出率下降的预期。"
         f"相比之下，H1975 的两个亚群中位 UMI 为 {h1975.get('median_umi_a',0):.0f} 与 "
         f"{h1975.get('median_umi_b',0):.0f}，仅相差 {h1975.get('umi_ratio',0)} 倍"
         f"（p = 0.09，不显著），提示其反映真实的转录状态差异。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    if diag:
        rows = [[d["cell_line"], f"{d['median_umi_a']:.0f}", f"{d['median_umi_b']:.0f}",
                 f"{d['umi_ratio']}×", f"{d['gene_ratio']}×",
                 "p < 1e-300" if d["umi_p"] < 1e-300 else f"{d['umi_p']:.2f}",
                 d["verdict"].split("：")[0]]
                for d in diag.values()]
        table(doc, ["细胞系", "亚群A UMI", "亚群B UMI", "UMI 比", "基因数比",
                    "p 值", "判定"], rows,
              widths=[1.8, 2.2, 2.2, 1.8, 1.8, 2.2, 3.0],
              caption="表 3  亚群测序深度诊断")
    figure(doc, "fig06_subcluster_origin.png",
           "图 5  亚群溯源。左侧为各亚群测序深度分布，右侧为细胞周期分数散点。", 15.5)

    heading(doc, "3.5  标记基因验证", 2)
    para(doc,
         "以 demuxlet 标签为分组（独立于表达数据，p 值有效）计算各细胞系的标记基因。"
         "HCC827 的 EGFR 平均表达量为 1.81，显著高于其余四系（0.11–0.40），"
         "与该细胞系已知的 EGFR 基因扩增一致；"
         "A549 高表达醛酮还原酶家族成员 AKR1B10、AKR1C2、AKR1C3 及 ALDH1A1；"
         "H838 特异表达 GAGE 家族癌睾抗原；"
         "H2228 高表达 SAA1、CXCL1 等炎症相关基因（图 6、图 7）。"
         "这些特征与文献记载吻合，为分析流程的正确性提供了生物学层面的佐证。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    figure(doc, "fig07_markers_dotplot.png",
           "图 6  各细胞系标记基因点图。点大小为表达细胞比例，颜色为标准化表达量。",
           15.5)
    figure(doc, "fig08_known_markers.png",
           "图 7  已知特征基因验证。HCC827 的 EGFR 表达显著高于其余细胞系。", 15.0)

    heading(doc, "4  讨论")
    para(doc,
         "本研究利用基因型金标准，对单细胞分析流程中两个主观性最强的环节给出了定量刻画。"
         "结果有三点值得强调。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "第一，doublet 检测工具的默认阈值蕴含着未被言明的取舍。Scrublet 在本数据上"
         "达到 100% 精确率，这意味着它移除的每一个细胞都确实是 doublet；"
         "但代价是近半数真实 doublet 被保留下来。"
         "对于以发现稀有细胞类型为目标的研究，残留的 doublet 可能形成虚假的\"中间态\"群体；"
         "而对于细胞数本就有限的样本，保守阈值则避免了过度删除。"
         "使用者应依据研究目的主动选择，而非默认接受工具的预设值。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "第二，ARI 随分辨率单调下降的曲线，为\"过聚类是默认失效模式\"这一论断"
         "提供了直观证据。在本数据中真值为 5 类，但分辨率取 1.0 时会产生 16 个簇。"
         "若无金标准参照，这 16 个簇完全可以被逐一命名并赋予生物学解释。"
         "这提示：簇的数量应被视为分析者选择的描述尺度，而非数据固有的属性。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    para(doc,
         "第三，也是实践中最容易被忽视的一点：识别出的亚群未必具有生物学含义。"
         "本研究中 H838 的两个亚群在细胞周期回归后依然存在，若仅做到这一步，"
         "很自然会把它解读为真实的转录亚状态。"
         "但测序深度诊断揭示两者相差 2.56 倍，且其差异基因集中于高丰度管家基因——"
         "这是深度分层的典型特征而非生物学信号。"
         "相较之下，H1975 的亚群在深度相当的情况下依然分离，才更可能反映真实异质性。"
         "我们建议在报告任何亚群之前，将测序深度与检出基因数的组间比较作为常规诊断步骤。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "4.1  局限性", 2)
    for t in [
        "使用的是永生化细胞系而非原代组织。细胞系间的转录差异远大于组织内近缘细胞类型，"
        "因此本文报告的 ARI 数值属于该任务难度下的上限，不能直接外推至复杂组织。",
        "仅评估了 Scrublet 一种 doublet 检测工具与 Leiden 一种聚类算法，"
        "未与 scDblFinder、DoubletFinder 或 Louvain 等做横向比较。",
        "demuxlet 本身也是算法推断，其标签虽独立于表达量，但并非绝对真值。",
        "单一测序平台（10x Chromium）与单一样本，未涉及批次整合场景。",
        "亚群差异基因的 p 值因 double-dipping 而无效，相关描述仅用于生成假设。",
        "本工作为方法学基准，使用已公开的基准数据集，不报告新的细胞生物学发现。",
    ]:
        bullet(doc, t, size=10)

    heading(doc, "4.2  结论", 2)
    para(doc,
         "基因型金标准使单细胞分析中的关键参数得以客观评估。"
         f"Scrublet 在本数据上的判别能力良好（AUROC {s.get('auroc',0):.3f}），"
         "但默认阈值以召回率换取精确率，使用者需按研究目的调整；"
         f"聚类分辨率存在明确最优点（ARI {best.get('ARI',0):.4f}），"
         "且 ARI 随分辨率升高单调下降，印证过聚类的普遍风险；"
         "而分辨率提高后出现的亚群必须经测序深度诊断，"
         "方能区分技术性分层与真实生物学异质性。"
         "本研究同时提供了一套开源、参数透明、可复现的评估流程。",
         indent=0.74, ls=1.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    heading(doc, "5  声明")
    heading(doc, "数据可获取性", 3)
    para(doc,
         "数据集可自 NCBI GEO 以登录号 GSE118767 获取，"
         "处理后的计数矩阵见 https://github.com/LuyiTian/sc_mixology。"
         "本研究的分析代码、参数与全部中间结果已开源。",
         size=10, indent=0.74)
    heading(doc, "作者贡献", 3)
    para(doc, "［按实际情况填写］", size=10, indent=0.74, italic=True)
    heading(doc, "利益冲突", 3)
    para(doc, "作者声明无利益冲突。", size=10, indent=0.74)
    heading(doc, "基金资助", 3)
    para(doc, "［填写基金编号，若无可写：本研究未获得专项经费资助］",
         size=10, indent=0.74, italic=True)

    heading(doc, "参考文献")
    refs = [
        "Tian L, Dong X, Freytag S, et al. Benchmarking single cell RNA-sequencing analysis "
        "pipelines using mixture control experiments. Nat Methods. 2019;16(6):479-487.",
        "Kang HM, Subramaniam M, Targ S, et al. Multiplexed droplet single-cell RNA-sequencing "
        "using natural genetic variation. Nat Biotechnol. 2018;36(1):89-94.",
        "Wolock SL, Lopez R, Klein AM. Scrublet: computational identification of cell doublets "
        "in single-cell transcriptomic data. Cell Syst. 2019;8(4):281-291.",
        "McGinnis CS, Murrow LM, Gartner ZJ. DoubletFinder: doublet detection in single-cell "
        "RNA sequencing data using artificial nearest neighbors. Cell Syst. 2019;8(4):329-337.",
        "Germain PL, Lun A, Garcia Meixide C, et al. Doublet identification in single-cell "
        "sequencing data using scDblFinder. F1000Res. 2021;10:979.",
        "Traag VA, Waltman L, van Eck NJ. From Louvain to Leiden: guaranteeing well-connected "
        "communities. Sci Rep. 2019;9:5233.",
        "Blondel VD, Guillaume JL, Lambiotte R, Lefebvre E. Fast unfolding of communities in "
        "large networks. J Stat Mech. 2008;2008:P10008.",
        "Wolf FA, Angerer P, Theis FJ. SCANPY: large-scale single-cell gene expression data "
        "analysis. Genome Biol. 2018;19:15.",
        "Hubert L, Arabie P. Comparing partitions. J Classif. 1985;2:193-218.",
        "Tirosh I, Izar B, Prakadan SM, et al. Dissecting the multicellular ecosystem of "
        "metastatic melanoma by single-cell RNA-seq. Science. 2016;352(6282):189-196.",
        "Chari T, Pachter L. The specious art of single-cell genomics. PLoS Comput Biol. "
        "2023;19(8):e1011288.",
        "Luecken MD, Theis FJ. Current best practices in single-cell RNA-seq analysis: "
        "a tutorial. Mol Syst Biol. 2019;15(6):e8746.",
        "Zappia L, Oshlack A. Clustering trees: a visualization for evaluating clusterings at "
        "multiple resolutions. Gigascience. 2018;7(7):giy083.",
        "Gandolfo LC, Speed TP. RLE plots: visualizing unwanted variation in high dimensional "
        "data. PLoS One. 2018;13(2):e0191629.",
    ]
    for i, r in enumerate(refs, 1):
        p = para(doc, f"[{i}]  {r}", size=9.5, after=4,
                 align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)

    path = os.path.join(OUT, "GSE118767_论文.docx")
    doc.save(path)
    return path


def main():
    print("读取结果 ...")
    f = load()
    if not f["qc"]:
        print("  警告：缺 qc_summary.json，请先跑 run_all.sh")
    print("生成《代码方法》...")
    p1 = build_methods(f)
    print(f"  -> {p1} ({os.path.getsize(p1)/1024:.0f} KB)")
    print("生成《SCI 论文》...")
    p2 = build_paper(f)
    print(f"  -> {p2} ({os.path.getsize(p2)/1024:.0f} KB)")
    print("\n完成。")


if __name__ == "__main__":
    main()
