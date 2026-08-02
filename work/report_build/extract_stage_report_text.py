from pathlib import Path

from docx import Document


def main():
    candidates = sorted(Path(".").glob("**/02_调节意愿与动态调节能力影响机理模型研究报告_核校稿.docx"))
    if not candidates:
        candidates = sorted(Path(".").glob("**/02_调节意愿与动态调节能力影响机理模型研究报告_草案.docx"))
    if not candidates:
        raise SystemExit("No stage report found.")
    doc_path = candidates[0]
    doc = Document(doc_path)
    keep = False
    wanted_starts = ("五、调节意愿形成机理", "六、动态调节能力形成机理", "七、意愿与能力影响机理模型", "八、典型资源的专属作用机理", "九、研究假设与验证路径")
    next_stop = ("十、多维行为特征库映射",)
    print(doc_path)
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        if any(text.startswith(x) for x in wanted_starts):
            keep = True
        if any(text.startswith(x) for x in next_stop):
            break
        if keep:
            print(f"{i:03d}\t{para.style.name}\t{text}")


if __name__ == "__main__":
    main()
