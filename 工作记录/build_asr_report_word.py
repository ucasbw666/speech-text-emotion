"""Build an editable Word edition of the existing ASR report with two appendices."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "outputs" / "ChineseASR"
SOURCE = PROJECT / "report" / "experiment_report.md"
OUTPUT = PROJECT / "report" / "experiment_report.docx"


def set_font(run, *, name="Microsoft YaHei", size=None, bold=None, italic=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    return run


def set_cell_shading(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcpr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110):
    tc = cell._tc
    tcpr = tc.get_or_add_tcPr()
    mar = tcpr.first_child_found_in("w:tcMar")
    if mar is None:
        mar = OxmlElement("w:tcMar")
        tcpr.append(mar)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        tag = qn(f"w:{edge}")
        node = mar.find(tag)
        if node is None:
            node = OxmlElement(f"w:{edge}")
            mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table):
    tblpr = table._tbl.tblPr
    borders = tblpr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblpr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = qn(f"w:{edge}")
        node = borders.find(tag)
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "5")
        node.set(qn("w:color"), "D9D9D9")


def make_styles(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.78)
    section.bottom_margin = Inches(0.78)
    section.left_margin = Inches(0.87)
    section.right_margin = Inches(0.87)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.24

    title = doc.styles["Title"]
    title.font.name = "Microsoft YaHei"
    title.font.size = Pt(18)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    title.paragraph_format.space_before = Pt(5)
    title.paragraph_format.space_after = Pt(5)
    title.paragraph_format.keep_with_next = True
    title_ppr = title._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    clean_border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "nil")
    clean_border.append(bottom)
    title_ppr.append(clean_border)

    for name, size, before, after in (
        ("Heading 1", 14, 14, 7),
        ("Heading 2", 11.5, 11, 5),
    ):
        style = doc.styles[name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    caption = doc.styles["Caption"]
    caption.font.name = "Microsoft YaHei"
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor(55, 55, 55)
    caption._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    caption.paragraph_format.space_before = Pt(2)
    caption.paragraph_format.space_after = Pt(11)
    caption.paragraph_format.keep_together = True

    for list_name in ("List Bullet", "List Number"):
        style = doc.styles[list_name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(10.5)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.paragraph_format.space_after = Pt(2)
        style.paragraph_format.line_spacing = 1.2


INLINE_PATTERN = re.compile(r"(\*\*[^*]+\*\*|" + re.escape(chr(96)) + r"[^" + re.escape(chr(96)) + r"]+" + re.escape(chr(96)) + r")")


def add_inline(paragraph, text):
    cursor = 0
    for match in INLINE_PATTERN.finditer(text):
        if match.start() > cursor:
            set_font(paragraph.add_run(text[cursor:match.start()]))
        value = match.group(0)
        if value.startswith("**"):
            set_font(paragraph.add_run(value[2:-2]), bold=True)
        else:
            set_font(paragraph.add_run(value[1:-1]), name="Consolas", size=9)
        cursor = match.end()
    if cursor < len(text):
        set_font(paragraph.add_run(text[cursor:]))
    if cursor == 0 and not text:
        paragraph.add_run("")


def add_body(doc, text, *, style=None, alignment=None, keep=False):
    p = doc.add_paragraph(style=style)
    if alignment is not None:
        p.alignment = alignment
    p.paragraph_format.keep_together = keep
    add_inline(p, text)
    return p


def add_code(doc, commands):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.22)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.keep_together = True
    for index, line in enumerate(commands):
        if index:
            p.add_run().add_break()
        set_font(p.add_run(line), name="Consolas", size=8.5, color=(30, 30, 30))
    return p


def add_figure(doc, path, *, width=5.5):
    if not path.is_file():
        raise FileNotFoundError(path)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))


def add_caption(doc, text):
    p = doc.add_paragraph(style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run(text), size=9, italic=True)


def add_table(doc, table_lines):
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table_lines]
    if len(rows) < 3:
        raise ValueError("Incomplete markdown table")
    rows = [rows[0]] + rows[2:]
    col_count = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=col_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if col_count == 4 and rows[0][0] == "数据划分":
        widths = [1.0, 1.0, 0.82, 3.55]
    elif col_count == 6:
        widths = [2.12, 0.72, 0.65, 0.47, 0.47, 1.48]
    elif col_count == 4:
        widths = [1.9, 2.05, 1.55, 0.87]
    else:
        widths = [6.37 / col_count] * col_count
    for row_index, row_values in enumerate(rows):
        row = table.rows[row_index]
        if row_index == 0:
            trpr = row._tr.get_or_add_trPr()
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            trpr.append(header)
        for col_index, value in enumerate(row_values):
            cell = row.cells[col_index]
            cell.width = Inches(widths[col_index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if row_index == 0:
                set_cell_shading(cell, "E9EDF2")
            elif row_index % 2 == 0:
                set_cell_shading(cell, "F7F9FB")
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.12
            if col_count == 4 and rows[0][0] == "数据划分":
                p.paragraph_format.keep_with_next = row_index < len(rows) - 1
            if col_index > 0 and (col_count == 6 or col_index == col_count - 1):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(p, value)
            for run in p.runs:
                set_font(run, size=9 if col_count == 6 else 9.4, bold=True if row_index == 0 else None)
    set_table_borders(table)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_original_report(doc):
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    preserved = []
    figures = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            add_table(doc, table_lines)
            for table_line in [table_lines[0]] + table_lines[2:]:
                preserved.extend(cell.strip().replace("**", "") for cell in table_line.strip().strip("|").split("|"))
            continue
        if line.startswith("!["):
            match = re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", line)
            if not match:
                raise ValueError(f"Invalid image line: {line}")
            add_figure(doc, SOURCE.parent / match.group(2), width=5.45)
            figures += 1
        elif line.startswith("# "):
            text = line[2:]
            p = doc.add_paragraph(style="Title")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(p, text)
            preserved.append(text)
        elif line.startswith("## "):
            text = line[3:]
            add_body(doc, text, style="Heading 1")
            preserved.append(text)
        elif line.startswith("### "):
            text = line[4:]
            add_body(doc, text, style="Heading 2")
            preserved.append(text)
        elif line.startswith('<p align="right">') and line.endswith("</p>"):
            text = line.removeprefix('<p align="right">').removesuffix("</p>")
            add_body(doc, text, alignment=WD_ALIGN_PARAGRAPH.RIGHT)
            preserved.append(text)
        elif line.startswith("> "):
            text = line[2:]
            add_body(doc, text)
            preserved.append(text.replace(chr(96), ""))
        elif line.startswith("- "):
            text = line[2:]
            add_body(doc, text, style="List Bullet")
            preserved.append(text.replace(chr(96), ""))
        elif line.startswith("*") and line.endswith("*"):
            text = line[1:-1]
            add_caption(doc, text)
            preserved.append(text)
        else:
            add_body(doc, line)
            preserved.append(line.replace(chr(96), ""))
        i += 1
    if figures != 5:
        raise ValueError(f"Expected five original figures, found {figures}")
    return preserved, figures


def heading(doc, text, level=1):
    add_body(doc, text, style=f"Heading {level}")


def add_appendix_a(doc):
    heading(doc, "附录 A 项目搭建过程")
    add_body(
        doc,
        "本项目按环境检查、基础推理、数据准备、基线评测、参数高效微调、消融分析和最终打包的顺序完成。以下步骤对应仓库中的实际脚本、配置与输出文件，可用于复现实验。",
    )

    heading(doc, "A1 环境检查与工程建立", 2)
    add_body(
        doc,
        "首先检查 Windows 11、Conda、PyTorch、CUDA、显存和磁盘空间，结果记录在 docs/environment.md。考虑到 RTX 4060 Laptop GPU 的 8 GB 显存，选用 Whisper-small 作为唯一主模型，在独立的 chinese-asr 环境中使用 fp16、梯度累积和 LoRA。工程将模型、原始语音、清单、源码、训练记录和图表分开放置。",
    )
    add_code(doc, [
        "conda env create -f environment.yml",
        "conda activate chinese-asr",
        "python -c \"import torch; print(torch.cuda.is_available())\"",
        "python -m pytest",
    ])

    heading(doc, "A2 本地模型与最小推理", 2)
    add_body(
        doc,
        "首次联网运行下载脚本，将 openai/whisper-small 保存到 models/asr_model。随后以示例 WAV 完成单文件中文转写的最小测试。推理代码只读取本地模型文件，下载完成后可离线运行。",
    )
    add_code(doc, [
        "python scripts\\download_model.py",
        "python scripts\\transcribe.py assets\\demo.wav --device cuda",
    ])

    heading(doc, "A3 数据获取与预处理", 2)
    add_body(
        doc,
        "下载 AISHELL-1 的 S0002、S0003、S0004 三个说话人子集及转写文本。prepare_data.py 扫描音频、核对转写、统一文本、检查采样率并生成相对路径 JSONL 清单；train、dev、test 分别对应三个互不相同的说话人。统计结果写入 results/dataset_statistics.json 和同名 Markdown 表。",
    )
    add_code(doc, [
        "python scripts\\download_dataset.py",
        "python scripts\\prepare_data.py " + chr(96),
        "  --dataset-root data\\raw\\aishell1_subset " + chr(96),
        "  --transcript-file data\\raw\\aishell1_subset\\aishell_transcript_v0.8.txt",
    ])

    heading(doc, "A4 基线评测与字符错误率", 2)
    add_body(
        doc,
        "先用未经课程数据微调的预训练模型评测 355 条 test 语音。src/metrics.py 的字符级 Levenshtein 实现统计替换、删除、插入与 CER，逐样本预测和汇总结果分别保存为 CSV 与 JSON。训练、验证和测试使用同一文本规范化模块。",
    )
    add_code(doc, [
        "python scripts\\evaluate_baseline.py --manifest data\\manifests\\test.jsonl --device cuda",
    ])

    heading(doc, "A5 LoRA 微调与消融", 2)
    add_body(
        doc,
        "训练前先用两条样本运行 smoke test，确认音频特征、反向传播和 checkpoint 保存链路。正式训练依照 configs/improved.yaml：三轮、batch size 1、梯度累积 8、学习率 1e-4、fp16、LoRA rank 16。最佳 adapter 保存在 checkpoints/improved/best。增强消融使用相同训练预算和 configs/augmentation_ablation.yaml；由于其 CER 较高，最终模型保留无增强版本。",
    )
    add_code(doc, [
        "python scripts\\train.py " + chr(96),
        "  --train_manifest data\\manifests\\train.jsonl " + chr(96),
        "  --dev_manifest data\\manifests\\dev.jsonl --smoke_test",
        "python scripts\\train.py " + chr(96),
        "  --train_manifest data\\manifests\\train.jsonl " + chr(96),
        "  --dev_manifest data\\manifests\\dev.jsonl " + chr(96),
        "  --config configs\\improved.yaml " + chr(96),
        "  --output_dir checkpoints\\improved --device cuda",
    ])

    heading(doc, "A6 改进模型评测与结果整理", 2)
    add_body(
        doc,
        "在同一 test 清单上评测最终模型，生成逐样本预测、错误案例和图表，再将源码、最终 adapter、数据下载方式、结果和报告整理到 submission。提交包没有重复复制约 1 GB 的基础模型和原始语音，首次复现需按 README 下载。",
    )
    add_code(doc, [
        "python scripts\\evaluate_improved.py --manifest data\\manifests\\test.jsonl --device cuda",
        "python scripts\\error_analysis.py --predictions results\\improved_predictions.csv",
        "python scripts\\plot_results.py --strict",
        "python scripts\\build_submission.py",
    ])


def add_appendix_b(doc):
    heading(doc, "附录 B 网页界面使用方法")
    add_body(
        doc,
        "网页由项目根目录的 app.py 使用 Gradio 创建，模型加载与识别由 src/inference.py 完成。页面提供上传音频、浏览器麦克风、Baseline 与 Improved 模型切换、中文转写结果以及时长、推理耗时和实时因子显示。",
    )

    heading(doc, "B1 启动完整工程", 2)
    add_body(
        doc,
        "在 PowerShell 中进入 ChineseASR 工程目录并激活环境。首次运行时执行下载命令；模型已有时可跳过。启动后浏览器通常会自动打开，默认地址为 http://127.0.0.1:7860。",
    )
    add_code(doc, [
        'cd "C:\\path\\to\\ChineseASR"',
        "conda activate chinese-asr",
        "python scripts\\download_model.py",
        "python app.py --inbrowser",
    ])

    heading(doc, "B2 从课程提交包启动", 2)
    add_body(
        doc,
        "解压 submission 后进入 source_code。若尚未创建环境，先运行 conda env create；基础模型需首次联网下载。最终 LoRA adapter 已放在相邻的 model/improved_adapter，app.py 会自动找到它，无需重新训练或复制权重。",
    )
    add_code(doc, [
        'cd "C:\\path\\to\\submission\\source_code"',
        "conda env create -f environment.yml",
        "conda activate chinese-asr",
        "python scripts\\download_model.py",
        "python app.py --inbrowser",
    ])

    heading(doc, "B3 上传音频与麦克风操作", 2)
    for text in (
        "上传识别：在“音频输入”处选择 WAV、MP3、FLAC 等普通话文件，在模型下拉框中选 Baseline 或 Improved，点击“开始识别”。",
        "录音识别：选择麦克风并允许浏览器访问，开始说话后停止录音；停止事件会自动触发识别，也可以点击“开始识别”重试。",
        "查看结果：页面显示中文识别文本、音频时长、推理耗时、RTF、当前模型和 CPU 或 CUDA 设备。点击“清空”可进行下一条识别。",
    ):
        add_body(doc, text, style="List Number")

    heading(doc, "B4 本地运行与端口处理", 2)
    add_body(
        doc,
        "网页只监听本机地址，share=False；基础模型下载完成后，识别不调用远程语音 API。若 7860 端口已被占用，使用下列命令并改为访问 http://127.0.0.1:7861。演示结束后在启动终端按 Ctrl+C 停止服务。",
    )
    add_code(doc, ["python app.py --port 7861 --inbrowser"])
    add_figure(doc, PROJECT / "report" / "figures" / "ui_screenshot.png", width=6.3)
    add_caption(doc, "图 6　汉语连续语音识别系统网页界面。")


def verify_preservation(doc, expected):
    text_blocks = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            text_blocks.extend(cell.text for cell in row.cells)
    normalized = {s.replace("**", "").replace(chr(96), "") for s in text_blocks}
    missing = [s for s in expected if s not in normalized]
    if missing:
        raise RuntimeError(f"Original report text was not preserved: {missing[:8]}")
    return len(expected)


def main():
    doc = Document()
    make_styles(doc)
    doc.core_properties.title = "汉语连续语音识别实验"
    doc.core_properties.author = "庞博文"
    expected, figures = add_original_report(doc)
    add_appendix_a(doc)
    add_appendix_b(doc)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    preserved = verify_preservation(Document(OUTPUT), expected)
    print(f"Saved {OUTPUT}")
    print(f"Preserved {preserved} original text blocks and {figures} original figures; added one UI figure.")


if __name__ == "__main__":
    main()
