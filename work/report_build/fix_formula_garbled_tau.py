from pathlib import Path
import shutil
import zipfile


SRC = Path("outputs/reports/技术报告-课题一v1-二级标题整合修正版.docx")
DST = Path("outputs/reports/技术报告-课题一v1-二级标题整合-公式乱码修正版.docx")


def main() -> None:
    shutil.copyfile(SRC, DST)
    tmp = DST.with_suffix(".tmp")
    replaced = 0

    with zipfile.ZipFile(DST, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                text = data.decode("utf-8")
                anchor = "ramp_i, dur_i, acc_i, rec_i, prob_i"
                anchor_pos = text.find(anchor)
                if anchor_pos == -1:
                    raise RuntimeError("Target formula anchor not found")
                start = text.rfind("<m:oMath>", 0, anchor_pos)
                end = text.find("</m:oMath>", anchor_pos)
                if start == -1 or end == -1:
                    raise RuntimeError("Target formula boundary not found")
                end += len("</m:oMath>")
                new_formula = (
                    '<m:oMath><m:r><w:rPr><w:rFonts w:ascii="Cambria Math" '
                    'w:eastAsia="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
                    "<m:t>R_i(t,H)=[τ_i, ramp_i, dur_i, acc_i, rec_i, prob_i]</m:t>"
                    "</m:r></m:oMath>"
                )
                text = text[:start] + new_formula + text[end:]
                text = text.replace("蟿", "τ")
                replaced = 1
                data = text.encode("utf-8")
            zout.writestr(item, data)

    tmp.replace(DST)
    print(f"output={DST}")
    print(f"replaced={replaced}")


if __name__ == "__main__":
    main()
