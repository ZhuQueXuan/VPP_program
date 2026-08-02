from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


DOC = Path("技术报告-课题一v1.docx")


def iter_blocks(parent):
    for child in parent.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def table_text(table):
    rows = []
    for row in table.rows[:3]:
        cells = [" ".join(p.text.strip() for p in cell.paragraphs if p.text.strip()) for cell in row.cells]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def main():
    doc = Document(DOC)
    print(DOC)
    print("=== repeated paragraphs ===")
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if "真实数据支撑与后续替换口径" in text:
            print(f"{i:03d}\t{para.style.name}\t{text[:160]}")

    print("\n=== body order around tables ===")
    blocks = list(iter_blocks(doc))
    table_no = 0
    for idx, block in enumerate(blocks):
        if isinstance(block, Table):
            table_no += 1
            prev_texts = []
            next_texts = []
            for j in range(idx - 1, max(-1, idx - 5), -1):
                if isinstance(blocks[j], Paragraph) and blocks[j].text.strip():
                    prev_texts.append(blocks[j].text.strip())
                    if len(prev_texts) >= 2:
                        break
            for j in range(idx + 1, min(len(blocks), idx + 5)):
                if isinstance(blocks[j], Paragraph) and blocks[j].text.strip():
                    next_texts.append(blocks[j].text.strip())
                    if len(next_texts) >= 2:
                        break
            print(f"\nTABLE {table_no} at block {idx}")
            print("prev:", " || ".join(reversed(prev_texts)))
            print("sample:\n" + table_text(block))
            print("next:", " || ".join(next_texts))


if __name__ == "__main__":
    main()
