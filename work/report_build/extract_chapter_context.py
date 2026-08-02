from pathlib import Path

from docx import Document


def print_between(doc_path: Path, start_prefix: str, end_prefix: str, label: str) -> None:
    doc = Document(doc_path)
    print(f"\n===== {label} =====")
    print(doc_path)
    capture = False
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style is not None else ""
        if style == "Heading 1" and text.startswith(start_prefix):
            capture = True
        if capture:
            if style == "Heading 1" and text.startswith(end_prefix):
                break
            print(f"{i:03d}\t{style}\t{text}")


def print_outline(doc_path: Path, label: str) -> None:
    doc = Document(doc_path)
    print(f"\n===== {label} OUTLINE =====")
    print(doc_path)
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style is not None else ""
        if style.startswith("Heading"):
            print(f"{i:03d}\t{style}\t{text}")


def main():
    report = Path("outputs/reports/技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一深度扩写版.docx")
    print_between(report, "3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究", "4 虚拟电厂资源可调容量与响应能力特征建模方法研究", "CURRENT REPORT CHAPTER 3")

    candidates = sorted(Path(".").glob("**/02_调节意愿与动态调节能力影响机理模型研究报告_核校稿.docx"))
    if not candidates:
        candidates = sorted(Path(".").glob("**/02_调节意愿与动态调节能力影响机理模型研究报告_草案.docx"))
    for doc_path in candidates[:2]:
        print_outline(doc_path, "STAGE REPORT")


if __name__ == "__main__":
    main()
