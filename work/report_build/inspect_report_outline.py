from pathlib import Path

from docx import Document


def main():
    reports_dir = Path("outputs/reports")
    candidates = sorted(reports_dir.glob("*第三版.docx"))
    if not candidates:
        raise SystemExit("No third-version report found.")
    doc_path = candidates[0]
    doc = Document(doc_path)
    print(doc_path)
    for i, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading") or text.startswith(("1", "2", "3", "4", "5", "6")):
            print(f"{i:03d}\t{style}\t{text[:120]}")


if __name__ == "__main__":
    main()
