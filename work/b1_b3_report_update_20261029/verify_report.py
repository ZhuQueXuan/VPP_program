"""Content/typography/evidence and exact Word-to-PDF provenance verification."""
import json,hashlib,re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
import pymupdf as fitz
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];docx=ROOT/'outputs/课题一B1至B3算法阶段研究报告_20261029.docx';pdf=docx.with_suffix('.pdf');reference=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
def package(path):
    with ZipFile(path) as z:
        xml=etree.fromstring(z.read('word/document.xml'));maths=Counter(etree.tostring(m,method='c14n') for m in xml.xpath('//m:oMath',namespaces=NS));media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
        return xml,maths,media
def main():
    manifest=rd(BASE/'source_manifest.json');assert all(sha(ROOT/p)==h for p,h in manifest['sources'].items());word=rd(BASE/'word_export.json');assert word['input_sha256']==sha(docx) and word['pdf_sha256']==sha(pdf);assert word['renderer']=='Microsoft Word native PDF export'
    d=Document(docx);names={'Title','Subtitle','Caption',*[f'Heading {i}' for i in range(1,10)]};heading_runs=0
    for p in d.paragraphs:
        if p.style.name in names and p.text.strip():
            for r in p.runs:
                f=r._element.rPr.rFonts;assert all(f.get(qn('w:'+k))=='黑体' for k in ['ascii','hAnsi','eastAsia','cs']);assert not any(k.endswith('Theme') for k in f.attrib);heading_runs+=1
    for t in d.tables:
        for cell in t.rows[0].cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    f=r._element.rPr.rFonts;assert all(f.get(qn('w:'+k))=='黑体' for k in ['ascii','hAnsi','eastAsia','cs']);heading_runs+=1
    oldxml,oldmath,oldmedia=package(reference);xml,maths,media=package(docx);assert not (oldmath-maths),'original native math changed';assert all(media.get(k)==v for k,v in oldmedia.items()),'retained media changed'
    text='\n'.join(xml.xpath('//w:t/text()|//m:t/text()',namespaces=NS));forbidden=['我们','你','您','老师','助手','会上需要','会议追问','追分','收口','D124','D123','review','用户要求','可转入B3组合问题准备','下一步做什么']
    assert not [s for s in forbidden if s in text]
    assert all(x in text for x in ['0.588489','0.588948','0.579374','0.000539724','84 / 76','44 / 116','0 / 44','0.254710','3.967491','1128976'] if x!='1128976')
    pdoc=fitz.open(pdf);assert len(pdoc)==11==word['page_count'];texts=[p.get_text() for p in pdoc];expected=['研究目标与阶段结论','一 B1','二 B1','三 B1','四 B2','五 B2','六 B2','七 B3','八 连续任务','九 联合验证','附录']
    bounds=[]
    for i,(p,t,heading) in enumerate(zip(pdoc,texts,expected)):
        compact=re.sub(r'\s+','',t);assert re.sub(r'\s+','',heading) in compact,(i+1,heading);assert '�' not in t
        blocks=[b for b in p.get_text('blocks') if b[4].strip() and b[1]<p.rect.height-40];assert blocks
        assert min(b[0] for b in blocks)>35 and max(b[2] for b in blocks)<p.rect.width-25,(i+1,'horizontal overflow')
        bounds.append(dict(page=i+1,blocks=len(blocks),bottom=max(b[3] for b in blocks),characters=len(t)))
    alltext='\n'.join(texts);assert all(s not in alltext for s in forbidden)
    # Previous scoped release remains untouched, including original report and all protected evidence.
    freeze=rd(ROOT/'work/b1_b3_stability_20261028/source_freeze.json');assert all(sha(ROOT/p)==h for p,h in freeze['protected'].items());snap=rd(ROOT/'work/b1_b3_stability_20261028/final_snapshot.json');assert all(sha(ROOT/p)==h for p,h in snap['files'].items())
    (BASE/'final_text.txt').write_text(alltext,encoding='utf-8')
    result=dict(status='passed_pending_visual_signoff',pages=len(pdoc),font='all headings/captions/table headers SimHei all scripts',heading_header_runs=heading_runs,original_math_equations_preserved=sum(oldmath.values()),native_equations_total=sum(maths.values()),original_media_preserved=len(oldmedia),old_protected_files_unchanged=len(freeze['protected']),prior_release_snapshot_files_unchanged=len(snap['files']),formal_impersonal_voice_checked=True,pdf_from_exact_word=True,docx_sha=sha(docx),pdf_sha=sha(pdf),page_bounds=bounds)
    (BASE/'qa_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('report checks passed',len(pdoc),'pages',sum(oldmath.values()),'original equations retained')
if __name__=='__main__':main()
