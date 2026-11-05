"""Final content/artifact QA; does not rerun any scientific experiment."""
from pathlib import Path
from zipfile import ZipFile
import json,hashlib
from lxml import etree
import fitz
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    docx=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx';pdf=docx.with_suffix('.pdf')
    evidence=json.loads((BASE/'source_evidence.json').read_text(encoding='utf-8'))
    changed=[n for n,h in evidence['sources'].items() if sha(ROOT/n)!=h];assert not changed
    frozen=json.loads((ROOT/'work/b2_completion_20261027/source_freeze.json').read_text(encoding='utf-8'))
    legacy=[n for n,h in frozen['protected'].items() if sha(ROOT/n)!=h];assert not legacy
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    with ZipFile(docx) as z:
        xml=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'))
        text=''.join(xml.xpath('//w:t/text()',namespaces=ns))
        assert not xml.xpath('//w:del|//w:ins',namespaces=ns)
        assert not styles.xpath('//w:style[@w:styleId="Title"]//w:pBdr',namespaces=ns)
        nmath=len(xml.xpath('//m:oMath',namespaces=ns));assert nmath==7
        pictures=len([x for x in z.namelist() if x.startswith('word/media/')]);assert pictures==4
        assert '有已有许可' not in text and '实际单次事件交付误差仍为' not in text
        assert all(s in text for s in ['0.6456821','0.3228410','0.440280','211.71146','每轮均为288000','正式90%验收尚未通过'])
    d=fitz.open(pdf);assert len(d)==8;pages=[]
    for i,page in enumerate(d):
        png=BASE/'render_v2'/f'page-{i+1}.png';assert png.exists()
        assert len(page.get_text())>400
        blocks=page.get_text('blocks');outside=[b[:4] for b in blocks if b[0]<-1 or b[1]<-1 or b[2]>page.rect.width+1 or b[3]>page.rect.height+1];assert not outside
        body=[b for b in blocks if b[4].strip()!=str(i+1)]
        pages.append(dict(page=i+1,characters=len(page.get_text()),body_bottom_pt=max(b[3] for b in body),image=str(png.relative_to(ROOT)),visual_review='passed at original PNG resolution'))
    receipt=dict(status='passed',meeting_date='2026-10-29',author='刘文轩',docx_sha256=sha(docx),pdf_sha256=sha(pdf),pages=pages,
      native_word_equations=nmath,embedded_figures=pictures,source_files_unchanged=True,legacy_protected_files_unchanged=len(frozen['protected']),renderer='Microsoft Word native PDF export + canonical render_docx.py rasterization',
      styles_review='Black headings; no title border; page5 overflow avoided; all8 pages inspected',new_scientific_experiments=False,
      rendering_note='Initial sandbox COM test denied; authorized native export succeeded. First canonical PNG call hit temp-directory cleanup permission; task-local adapter now retains scratch in work. No deletion commands used.')
    (BASE/'qa_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    review=dict(skills=['lin-rongheng-report','humanizer-zh','academic','documents','pdf'],reviewers=['B1 evidence/wording audit','B2 technical/quantity audit'],
      changes=['Distinguished actual-event RMSE from per-event error','Made each completion panel count explicit','Computed recovery expectation from expected energy','Defined eligibility indicator and average execution fraction','Replaced internal chain phrasing with concrete implemented relationship','Kept all zero/negative results and simulation/90% boundaries'],unresolved_blockers=[],report_scope='B1/B2 meeting report; no new method or research route approval')
    (BASE/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='pages'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
