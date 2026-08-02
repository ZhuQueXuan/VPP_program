from pathlib import Path
import zipfile

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt


DOCX = Path("outputs/reports/技术报告-课题一v1-二级标题整合-公式乱码修正版.docx")


TOC_ENTRIES = [
    "摘要",
    "ABSTRACT",
    "1 概述",
    "2 虚拟电厂多元异质资源行为影响因素分析技术研究",
    "3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究",
    "4 虚拟电厂资源可调容量与响应能力特征建模方法研究",
    "5 面向多元市场调节需求的资源智能分级分类方法研究",
    "6 多维行为特征库构建与数据治理方案",
    "7 模型验证方案与精度评价体系",
    "8 总结与展望",
    "参考文献",
]


def delete_paragraph(paragraph) -> None:
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def format_toc_paragraph(paragraph) -> None:
    paragraph.style = "Normal"
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_after = Pt(3)
    for run in paragraph.runs:
        run.font.name = "宋体"
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(12)


def restore_static_toc() -> None:
    doc = Document(DOCX)
    toc_idx = None
    first_chapter_idx = None
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 1" and text == "目录":
            toc_idx = idx
        elif toc_idx is not None and style == "Heading 1" and text.startswith("1 "):
            first_chapter_idx = idx
            break
    if toc_idx is None or first_chapter_idx is None:
        raise RuntimeError("TOC boundary not found")

    between = list(doc.paragraphs[toc_idx + 1:first_chapter_idx])
    for paragraph in between:
        delete_paragraph(paragraph)

    first_chapter = None
    for paragraph in doc.paragraphs:
        if (paragraph.style.name if paragraph.style else "") == "Heading 1" and paragraph.text.strip().startswith("1 "):
            first_chapter = paragraph
            break
    if first_chapter is None:
        raise RuntimeError("First chapter not found after cleanup")

    for entry in reversed(TOC_ENTRIES):
        p = first_chapter.insert_paragraph_before(entry)
        format_toc_paragraph(p)

    doc.save(DOCX)


def inspect_formula() -> None:
    data = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8")
    print(f"oMath={data.count('<m:oMath')}")
    print(f"target_formula_ok={'R_i(t,H)=[τ_i, ramp_i, dur_i, acc_i, rec_i, prob_i]' in data}")
    suspicious_tokens = {
        "visible_garbled_cjk": "蟿",
        "visible_garbled_arabic": "د„",
    }
    for label, token in suspicious_tokens.items():
        print(f"{label}={data.count(token)}")


def inspect_toc() -> None:
    doc = Document(DOCX)
    toc = False
    entries = []
    counts = {}
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 1" and text == "目录":
            toc = True
            continue
        if toc and style == "Heading 1" and text.startswith("1 "):
            toc = False
        if toc and text:
            entries.append(text)
        if style == "Heading 2" and text and text[0] in "2345":
            counts[text[0]] = counts.get(text[0], 0) + 1
    print(f"toc_entries={len(entries)}")
    print(f"heading_counts={counts}")


def main() -> None:
    restore_static_toc()
    inspect_formula()
    inspect_toc()


if __name__ == "__main__":
    main()
