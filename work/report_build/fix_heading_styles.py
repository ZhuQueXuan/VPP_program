from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "outputs" / "reports" / "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-初稿.docx"
DST = ROOT / "outputs" / "reports" / "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-标题格式修正版.docx"


HEADING_TOKENS = {
    "Heading 1": {"size": 16, "color": "2E74B5", "bold": True, "font": "黑体"},
    "Heading 2": {"size": 13, "color": "2E74B5", "bold": True, "font": "黑体"},
    "Heading 3": {"size": 12, "color": "1F4D78", "bold": True, "font": "黑体"},
}


def set_run_font(run, font_name, size_pt, color_hex, bold):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    run._element.rPr.rFonts.set(qn("w:ascii"), font_name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), font_name)
    run.font.size = Pt(size_pt)
    run.font.color.rgb = RGBColor.from_string(color_hex)
    run.bold = bold


def clear_paragraph_runs(paragraph):
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)


def normalize_heading_style(style, token):
    style.font.name = token["font"]
    style._element.rPr.rFonts.set(qn("w:eastAsia"), token["font"])
    style._element.rPr.rFonts.set(qn("w:ascii"), token["font"])
    style._element.rPr.rFonts.set(qn("w:hAnsi"), token["font"])
    style.font.size = Pt(token["size"])
    style.font.color.rgb = RGBColor.from_string(token["color"])
    style.font.bold = token["bold"]
    style.paragraph_format.keep_with_next = False
    style.paragraph_format.keep_together = False
    style.paragraph_format.page_break_before = False


def normalize_heading_paragraph(paragraph, token):
    text = paragraph.text.strip()
    clear_paragraph_runs(paragraph)
    run = paragraph.add_run(text)
    set_run_font(run, token["font"], token["size"], token["color"], token["bold"])
    paragraph.paragraph_format.keep_with_next = False
    paragraph.paragraph_format.keep_together = False
    paragraph.paragraph_format.page_break_before = False


def main():
    doc = Document(SRC)

    for style_name, token in HEADING_TOKENS.items():
        normalize_heading_style(doc.styles[style_name], token)

    for paragraph in doc.paragraphs:
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name in HEADING_TOKENS:
            normalize_heading_paragraph(paragraph, HEADING_TOKENS[style_name])

    doc.save(DST)
    print(DST)


if __name__ == "__main__":
    main()
