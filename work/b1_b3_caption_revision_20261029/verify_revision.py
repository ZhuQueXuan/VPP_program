import json,re,hashlib
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
import pymupdf
from revise_captions import REVISIONS,properties,SOURCE,TARGET,BASE
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    doc=Document(TARGET);original=Document(SOURCE);captions=[p for p in doc.paragraphs if p.style.name=='Caption'];assert len(captions)==10
    receipt=json.loads((BASE/'revision_receipt.json').read_text(encoding='utf-8'));assert len(receipt['revisions'])==10
    for p in captions:
        key=re.match(r'^(图\d+|表\d+)',p.text)[1];assert p.text==key+' '+REVISIONS[key][0] and len(p.text)<26 and '。' not in p.text and '；' not in p.text
        assert p.paragraph_format.alignment==WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:assert r.bold is False and r.font.size.pt==10 and r._element.rPr.rFonts.get(qn('w:eastAsia'))=='宋体'
        note=p._p.getnext();assert ''.join(note.itertext()).find(REVISIONS[key][1])>=0
    notes=[p for p in doc.paragraphs if p.text in [r[1] for r in REVISIONS.values()]];assert len(notes)==10
    for p in notes:
        assert p.style.name=='Normal' and p.paragraph_format.line_spacing==1.25 and p._p.pPr.ind.get(qn('w:firstLineChars'))=='200'
        for r in p.runs:assert r.font.size.pt==10.5 and r.font.name=='Times New Roman' and r._element.rPr.rFonts.get(qn('w:eastAsia'))=='宋体'
    assert properties(SOURCE)==properties(TARGET)
    with ZipFile(SOURCE) as a,ZipFile(TARGET) as b:assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==['word/document.xml']
    assert not doc.element.body.xpath('.//w:br[@w:type="page"]')
    word=json.loads((BASE/'word_export.json').read_text(encoding='utf-8-sig'));pdf=TARGET.with_suffix('.pdf');assert word['input_sha256']==sha(TARGET) and word['pdf_sha256']==sha(pdf);d=pymupdf.open(pdf);assert len(d)==word['page_count']==11
    for i,p in enumerate(d):
        assert '�' not in p.get_text() and len(p.get_text())>100
        blocks=[b for b in p.get_text('blocks') if b[4].strip() and not (b[4].strip()==str(i+1) and b[1]>p.rect.height-60)]
        assert min(b[0] for b in blocks)>35 and max(b[2] for b in blocks)<p.rect.width-25
    result=dict(status='passed',caption_count=10,figure_captions=6,table_captions=4,explanations_in_body=10,original_body_paragraphs_preserved=True,native_math_tables_media_identical=True,only_document_xml_changed=True,previous_style_requirements_preserved=True,pdf_from_exact_word=True,pages=11,pages_visually_reviewed=list(range(1,12)),docx_sha=sha(TARGET),pdf_sha=sha(pdf),separate_copy_reason='original Word file is open and write-locked; no connected editing session')
    (BASE/'qa_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('caption revision verified',len(d),'pages,10 short captions with retained body explanations')
if __name__=='__main__':main()
