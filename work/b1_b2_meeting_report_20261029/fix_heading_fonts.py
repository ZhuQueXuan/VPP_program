"""Uniform SimHei for heading scripts, captions and table header rows only."""
from pathlib import Path
from zipfile import ZipFile
import json,hashlib,shutil,re
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
TARGET=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def set_fonts(rpr):
    fonts=rpr.find(qn('w:rFonts'))
    if fonts is None:
        from docx.oxml import OxmlElement
        fonts=OxmlElement('w:rFonts');rpr.insert(0,fonts)
    fonts.attrib.clear()
    for key in ['ascii','hAnsi','eastAsia','cs']:fonts.set(qn('w:'+key),'黑体')
def apply_fonts(doc):
    names={'Title','Subtitle','Caption',*[f'Heading {n}' for n in range(1,10)]}
    for style in doc.styles:
        if style.name in names or style.name.startswith('Heading ') or style.name.startswith('Title '):set_fonts(style.element.get_or_add_rPr())
    changed=[]
    for p in doc.paragraphs:
        if (p.style.name in names or re.match(r'^表\s*\d+',p.text)) and p.text.strip():
            for run in p.runs:set_fonts(run._element.get_or_add_rPr())
            changed.append(dict(kind='table_caption' if re.match(r'^表\s*\d+',p.text) else p.style.name,text=p.text))
    for idx,table in enumerate(doc.tables):
        if table.rows:
            for cell in table.rows[0].cells:
                for p in cell.paragraphs:
                    for run in p.runs:set_fonts(run._element.get_or_add_rPr())
            changed.append(dict(kind='table_header',table=idx+1,text=' | '.join(c.text for c in table.rows[0].cells)))
    return changed
def content(path):
    with ZipFile(path) as z:
        xml=etree.fromstring(z.read('word/document.xml'))
        return dict(text=xml.xpath('//w:t/text()|//m:t/text()',namespaces=NS),math=[etree.tostring(x) for x in xml.xpath('//m:oMath',namespaces=NS)],media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')})
def main():
    backup=BASE/'before_heading_font_fix_20261028.docx'
    if not backup.exists():shutil.copy2(TARGET,backup)
    before=content(TARGET);doc=Document(TARGET);changes=apply_fonts(doc);doc.save(TARGET);after=content(TARGET)
    assert before==after,'content or scientific figure changed'
    for p in doc.paragraphs:
        if p.style.name in {'Title','Subtitle','Caption','Heading 1','Heading 2'} and p.text.strip():
            for run in p.runs:
                rf=run._element.rPr.rFonts
                assert all(rf.get(qn('w:'+k))=='黑体' for k in ['ascii','hAnsi','eastAsia','cs'])
                assert len(rf.attrib)==4
    receipt=dict(status='passed',font='黑体 SimHei',scope='document title, all section headings, captions and table header rows; all scripts incl Latin letters and numbers',content_unchanged=True,math_unchanged=True,figures_unchanged=True,paragraphs_and_headers=changes,before_sha=sha(backup),after_sha=sha(TARGET))
    (BASE/'heading_font_fix.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print('font fix applied',len(changes),'heading/caption/header groups; all text/math/figures unchanged')
if __name__=='__main__':main()
