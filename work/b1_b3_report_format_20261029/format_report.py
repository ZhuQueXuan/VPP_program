"""Formatting-only OOXML patch; preserve text, native math and all media."""
import re,json,hashlib
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.paragraph import Paragraph

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
SOURCE=BASE/'before_format.docx';TARGET=ROOT/'outputs/课题一B1至B3算法阶段研究报告_20261029.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def signature(path):
    with ZipFile(path) as z:
        xml=etree.fromstring(z.read('word/document.xml'))
        return dict(text=xml.xpath('//w:t/text()|//m:t/text()',namespaces=NS),math=[etree.tostring(m,method='c14n') for m in xml.xpath('//m:oMath',namespaces=NS)],media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')})

def font(rpr,east='宋体',latin='Times New Roman',size=None,bold=None):
    f=rpr.find(qn('w:rFonts'))
    if f is None:f=OxmlElement('w:rFonts');rpr.insert(0,f)
    f.attrib.clear()
    for name,value in [('ascii',latin),('hAnsi',latin),('eastAsia',east),('cs',latin)]:f.set(qn('w:'+name),value)
    if size is not None:
        for name in ['sz','szCs']:
            e=rpr.find(qn('w:'+name))
            if e is None:e=OxmlElement('w:'+name);rpr.append(e)
            e.set(qn('w:val'),str(round(size*2)))
    if bold is not None:
        for name in ['b','bCs']:
            e=rpr.find(qn('w:'+name))
            if e is None:e=OxmlElement('w:'+name);rpr.append(e)
            e.set(qn('w:val'),'1' if bold else '0')

def indent(p,chars):
    p.paragraph_format.first_line_indent=Pt(21 if chars==2 else 0)
    ind=p._p.get_or_add_pPr().get_or_add_ind();ind.set(qn('w:firstLineChars'),str(chars*100))
    for a in ['hanging','hangingChars']:ind.attrib.pop(qn('w:'+a),None)

def main():
    before=signature(SOURCE);d=Document(SOURCE);removed=0
    for p in list(d.paragraphs):
        pagebreaks=[e for e in p._p.findall('.//'+qn('w:br')) if e.get(qn('w:type'))=='page']
        for e in pagebreaks:e.getparent().remove(e);removed+=1
        if pagebreaks and not p.text.strip() and p._p.find('.//'+qn('w:drawing')) is None and p._p.find('.//'+qn('m:oMath')) is None:p._p.getparent().remove(p._p)
    for e in list(d.element.body.iter(qn('w:lastRenderedPageBreak'))):e.getparent().remove(e)
    normal=d.styles['Normal'];font(normal.element.get_or_add_rPr(),size=10.5);normal.paragraph_format.line_spacing=1.25;normal.paragraph_format.first_line_indent=Pt(21);normal.element.get_or_add_pPr().get_or_add_ind().set(qn('w:firstLineChars'),'200')
    headings={'Title','Subtitle',*[f'Heading {i}' for i in range(1,10)]}
    for s in d.styles:
        if s.name in headings or s.name.startswith('Heading ') or s.name.startswith('Title '):
            font(s.element.get_or_add_rPr(),east='黑体',latin='黑体');s.font.color.rgb=RGBColor(0,0,0)
            if s.type==1:
                s.paragraph_format.page_break_before=False;s.paragraph_format.first_line_indent=Pt(0);s.element.get_or_add_pPr().get_or_add_ind().set(qn('w:firstLineChars'),'0')
    cap=d.styles['Caption'];font(cap.element.get_or_add_rPr(),size=10,bold=False);cap.font.italic=False;cap.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER;cap.paragraph_format.first_line_indent=Pt(0);cap.paragraph_format.line_spacing=1.25
    cap.element.get_or_add_pPr().get_or_add_ind().set(qn('w:firstLineChars'),'0')
    for name in ['Header','Footer']:
        if name in d.styles:
            s=d.styles[name];s.paragraph_format.first_line_indent=Pt(0);s.element.get_or_add_pPr().get_or_add_ind().set(qn('w:firstLineChars'),'0')
    captions=[];body_count=0;table_count=0;heading_count=0;illustration_count=0
    for el in d.element.body.iter(qn('w:p')):
        p=Paragraph(el,d._body);pf=p.paragraph_format;pf.page_break_before=False;pf.widow_control=True
        is_table=any(a.tag==qn('w:tc') for a in el.iterancestors());is_caption=(p.style.name=='Caption' or re.match(r'^\s*[图表]\s*\d+',p.text)) and not is_table
        is_image=el.find('.//'+qn('w:drawing')) is not None;is_math=el.find('.//'+qn('m:oMath')) is not None
        if is_caption:
            p.style='Caption';pf.alignment=WD_ALIGN_PARAGRAPH.CENTER;pf.line_spacing=1.25;pf.space_before=Pt(3);pf.space_after=Pt(6);pf.keep_together=True;pf.keep_with_next=False;indent(p,0)
            for r in p.runs:font(r._element.get_or_add_rPr(),size=10,bold=False);r.italic=False
            captions.append(p.text)
        elif p.style.name in headings:
            indent(p,0);pf.keep_with_next=True
            for r in p.runs:font(r._element.get_or_add_rPr(),east='黑体',latin='黑体');r.font.color.rgb=RGBColor(0,0,0)
            heading_count+=1
        elif is_image:
            indent(p,0);pf.alignment=WD_ALIGN_PARAGRAPH.CENTER;pf.line_spacing=1.;pf.keep_with_next=True;pf.keep_together=True;illustration_count+=1
        elif is_math:
            indent(p,0);pf.line_spacing=1.25;pf.keep_together=True
        elif is_table:
            indent(p,0);pf.line_spacing=1.25
            for r in p.runs:font(r._element.get_or_add_rPr(),size=10.5)
            table_count+=1
        elif not p.text.strip():
            indent(p,0);pf.line_spacing=1.;pf.space_before=Pt(0);pf.space_after=Pt(0)
            for r in p.runs:r.font.size=Pt(1)
        else:
            pf.line_spacing=1.25;pf.keep_with_next=False;pf.space_before=Pt(0);pf.space_after=Pt(0)
            indent(p,0 if p.text.startswith(('汇报人','研究内容与实验结果截至')) else 2)
            for r in p.runs:font(r._element.get_or_add_rPr(),size=10.5)
            body_count+=1
    # A repeated table header must have at least the first data row on the same page.
    for table in d.tables:
        if table.rows:
            for cell in table.rows[0].cells:
                for p in cell.paragraphs:p.paragraph_format.keep_with_next=True
    # Tie a caption to its preceding table despite an optional empty spacer paragraph.
    for p in d.paragraphs:
        if p.style.name!='Caption':continue
        prev=p._p.getprevious();spacers=[]
        while prev is not None and prev.tag==qn('w:p') and not ''.join(prev.itertext()).strip():spacers.append(prev);prev=prev.getprevious()
        if prev is not None and prev.tag==qn('w:tbl'):
            for spacer in spacers:Paragraph(spacer,d._body).paragraph_format.keep_with_next=True
            rows=prev.findall(qn('w:tr'))
            if rows:
                for pp in rows[-1].iter(qn('w:p')):Paragraph(pp,d._body).paragraph_format.keep_with_next=True
    parts={'word/document.xml':etree.tostring(d.element,encoding='UTF-8',xml_declaration=True,standalone=True),'word/styles.xml':etree.tostring(d.styles.element,encoding='UTF-8',xml_declaration=True,standalone=True)}
    with ZipFile(SOURCE) as z,ZipFile(TARGET,'w') as out:
        for info in z.infolist():out.writestr(info,parts.get(info.filename,z.read(info.filename)))
    after=signature(TARGET);assert before==after,'scientific content/math/media changed'
    with ZipFile(SOURCE) as a,ZipFile(TARGET) as b:changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert set(changed)==set(parts)
    receipt=dict(status='formatted_pending_render',source_sha=sha(SOURCE),target_sha=sha(TARGET),changed_package_parts=changed,content_math_media_identical=True,page_breaks_removed=removed,headings=headings and heading_count,body_paragraphs=body_count,table_paragraphs=table_count,figure_paragraphs=illustration_count,caption_count=len(captions),captions=captions,body_size_pt=10.5,body_line_multiple=1.25,body_first_line_characters=2,body_paragraph_before_after_pt=0,caption_size_pt=10,caption_bold=False,caption_alignment='center',title_fonts='SimHei all scripts',body_fonts='SimSun Chinese; Times New Roman Latin')
    (BASE/'format_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print('format-only patch complete; removed',removed,'manual page breaks; captions',len(captions))

if __name__=='__main__':main()
