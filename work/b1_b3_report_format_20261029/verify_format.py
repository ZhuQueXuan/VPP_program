import json,re,hashlib
from pathlib import Path
from zipfile import ZipFile
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.enum.text import WD_ALIGN_PARAGRAPH
from lxml import etree
import pymupdf
from format_report import signature
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];TARGET=ROOT/'outputs/课题一B1至B3算法阶段研究报告_20261029.docx';PDF=TARGET.with_suffix('.pdf')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert signature(BASE/'before_format.docx')==signature(TARGET)
    d=Document(TARGET);counts=dict(headings=0,body=0,captions=0,table_paragraphs=0);headings={'Title','Subtitle',*[f'Heading {i}' for i in range(1,10)]}
    for el in d.element.body.iter(qn('w:p')):
        p=Paragraph(el,d._body);table=any(x.tag==qn('w:tc') for x in el.iterancestors());pf=p.paragraph_format
        assert pf.page_break_before is False
        if not p.text.strip() or el.find('.//'+qn('m:oMath')) is not None or el.find('.//'+qn('w:drawing')) is not None:continue
        if p.style.name in headings:
            kind='headings';east=latin='黑体';size=None
        elif p.style.name=='Caption':
            kind='captions';east='宋体';latin='Times New Roman';size=20;assert pf.alignment==WD_ALIGN_PARAGRAPH.CENTER and pf.line_spacing==1.25
            assert p._p.pPr.ind.get(qn('w:firstLineChars'))=='0'
            for r in p.runs:assert r.bold is False
        else:
            kind='table_paragraphs' if table else 'body';east='宋体';latin='Times New Roman';size=21;assert pf.line_spacing==1.25
            expected='0' if table or p.text.startswith(('汇报人','研究内容与实验结果截至')) else '200';assert p._p.pPr.ind.get(qn('w:firstLineChars'))==expected
            if expected=='200':assert p._p.pPr.ind.get(qn('w:firstLine'))=='420';assert pf.space_before.pt==0 and pf.space_after.pt==0
        counts[kind]+=1
        for r in p.runs:
            if not r.text:continue
            f=r._element.rPr.rFonts;assert f.get(qn('w:eastAsia'))==east and f.get(qn('w:ascii'))==latin and f.get(qn('w:hAnsi'))==latin
            if size is not None:assert r._element.rPr.sz.get(qn('w:val'))==str(size)
    assert len(d.sections)==1 and not d.element.body.xpath('.//w:br[@w:type="page"]');assert counts['captions']==10
    word=json.loads((BASE/'word_export.json').read_text(encoding='utf-8-sig'));assert word['input_sha256']==sha(TARGET) and word['pdf_sha256']==sha(PDF)
    pdf=pymupdf.open(PDF);assert len(pdf)==word['page_count']==10;bounds=[];positions=[]
    major=[p.text for p in d.paragraphs if p.style.name=='Heading 1']
    for i,page in enumerate(pdf):
        text=page.get_text();assert '�' not in text and len(text)>100
        body=[b for b in page.get_text('blocks') if b[4].strip() and not (b[4].strip()==str(i+1) and b[1]>page.rect.height-60 and abs((b[0]+b[2])/2-page.rect.width/2)<15)];assert body
        assert min(b[0] for b in body)>35 and max(b[2] for b in body)<page.rect.width-25,(i+1,'horizontal overflow')
        assert max(b[3] for b in body)<page.rect.height-44,(i+1,'body/footer overlap')
        bounds.append(dict(page=i+1,characters=len(text),bottom=max(b[3] for b in body)))
        for b in body:
            for heading in major:
                if re.sub(r'\s+','',heading) in re.sub(r'\s+','',b[4]):positions.append(dict(heading=heading,page=i+1,y=b[1]))
    with ZipFile(BASE/'before_format.docx') as a,ZipFile(TARGET) as b:changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert set(changed)=={'word/document.xml','word/styles.xml'}
    result=dict(status='passed_pending_visual_signoff',pages=len(pdf),counts=counts,body_size_pt=10.5,body_fonts='宋体 Chinese and Times New Roman Latin',line_spacing=1.25,first_line_chars=2,heading_font='黑体',caption_font='宋体 Chinese and Times New Roman Latin',caption_size_pt=10,caption_alignment='center',caption_bold=False,manual_page_breaks=0,content_math_media_identical=True,other_package_parts_identical=True,pdf_from_exact_word=True,docx_sha=sha(TARGET),pdf_sha=sha(PDF),major_heading_positions=positions,page_bounds=bounds)
    (BASE/'qa_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('format verified',len(pdf),'pages',counts)
if __name__=='__main__':main()
