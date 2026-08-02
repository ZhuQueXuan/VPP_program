from pathlib import Path
import re
import sys

from docx import Document


DEFAULT_REPORT = Path("outputs/reports/技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二三四深度扩写版.docx")


def visible_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def latin_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", text))


def main():
    report = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    doc = Document(report)
    sections = []
    current = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style is not None else ""
        if style == "Heading 1":
            current = {"title": text, "paras": []}
            sections.append(current)
        elif current is not None:
            # Exclude generated table-of-contents list items from the TOC section count? Keep them,
            # because the question asks chapter/section size and front matter is useful context.
            current["paras"].append(text)

    print(str(report))
    print("章节\t段落数\t字符数(去空白)\t中文字符数\t英文词数")
    for sec in sections:
        body = "\n".join(sec["paras"])
        print(f"{sec['title']}\t{len(sec['paras'])}\t{visible_len(body)}\t{cjk_len(body)}\t{latin_words(body)}")

    numbered = [s for s in sections if re.match(r"^\d+\s", s["title"])]
    total_body = "\n".join("\n".join(s["paras"]) for s in numbered)
    print(f"正文合计(1-8章)\t{sum(len(s['paras']) for s in numbered)}\t{visible_len(total_body)}\t{cjk_len(total_body)}\t{latin_words(total_body)}")


if __name__ == "__main__":
    main()
