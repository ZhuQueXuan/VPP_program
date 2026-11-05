from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree as E
import copy,hashlib,json,re

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
record=json.loads((BASE/'methods_results_source.json').read_text(encoding='utf-8'))
TARGET=Path(record['target']);raw=(BASE/'before_methods_results_clarification.docx').read_bytes()
sha=lambda v:hashlib.sha256(v).hexdigest()
assert sha(raw)==record['before_sha256']
assert sha(TARGET.read_bytes())==record['before_sha256'],'The user saved newer changes; rebase before editing'
plan=json.loads((BASE/'methods_results_additions.json').read_text(encoding='utf-8'))
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
q=lambda n:'{'+NS['w']+'}'+n
z=ZipFile(BytesIO(raw));xml=z.read('word/document.xml');doc=E.fromstring(xml);body=doc.find('w:body',NS)
txt=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=NS))
template=next(p for p in body if txt(p).startswith('以充电桩单向充电为代表机制。'))
def addprop(parent,name,attrs):
    el=parent.find(q(name))
    if el is None:el=E.SubElement(parent,q(name))
    for k,v in attrs.items():el.set(q(k),str(v))
    return el
def paragraph(text):
    p=E.Element(q('p'),nsmap={'w':NS['w']})
    pp=copy.deepcopy(template.find('w:pPr',NS))
    if pp is None:pp=E.Element(q('pPr'))
    p.append(pp)
    for name in ['pageBreakBefore','keepNext','numPr','sectPr','outlineLvl']:
        for el in pp.findall(q(name)):pp.remove(el)
    addprop(pp,'spacing',{'before':'0','after':'0','line':'300','lineRule':'auto'})
    addprop(pp,'ind',{'firstLineChars':'200','firstLine':'420'})
    addprop(pp,'widowControl',{'val':'1'})
    label,sep,rest=text.partition('。')
    segments=[(label+sep,True),(rest,False)] if sep else [(text,False)]
    for s,bold in segments:
        if not s:continue
        run=E.SubElement(p,q('r'));rp=E.SubElement(run,q('rPr'))
        addprop(rp,'rFonts',{'ascii':'Times New Roman','hAnsi':'Times New Roman','eastAsia':'宋体','cs':'Times New Roman'})
        addprop(rp,'sz',{'val':'21'});addprop(rp,'szCs',{'val':'21'});addprop(rp,'color',{'val':'000000'})
        addprop(rp,'b',{'val':'1' if bold else '0'});addprop(rp,'bCs',{'val':'1' if bold else '0'})
        t=E.SubElement(run,q('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=s
    return p
def fragment(p):
    s=E.tostring(p,encoding='unicode',with_tail=False)
    return re.sub(r' xmlns(?::[\w]+)?="[^"]*"','',s).encode('utf-8')

nsdecl=b' '.join(('xmlns:'+prefix+'="'+uri+'"').encode() for prefix,uri in doc.nsmap.items() if prefix)
spans=[]
for m in re.finditer(rb'<w:p(?:\s[^>]*)?>.*?</w:p>',xml,re.S):
    try:p=E.fromstring(b'<root '+nsdecl+b'>'+m.group()+b'</root>')[0]
    except E.XMLSyntaxError:continue
    spans.append((m,p,txt(p)))
ops=[];inserts=[]
for entry in plan['insertions']:
    matches=[v for v in spans if v[2].startswith(entry['anchor_prefix'])]
    assert len(matches)==1,(entry['anchor_prefix'],len(matches))
    m,p,s=matches[0]
    blocks=[paragraph(t) for t in entry['paragraphs']]
    pos=m.start() if entry['position']=='before' else m.end()
    ops.append((pos,pos,b''.join(fragment(p) for p in blocks)))
    inserts.extend(entry['paragraphs'])
for entry in plan['replacements']:
    matches=[v for v in spans if v[2]==entry['old']];assert len(matches)==1,entry['old']
    m,p,s=matches[0];nodes=p.xpath('.//w:t',namespaces=NS);nodes[0].text=entry['new']
    for node in nodes[1:]:node.text=''
    for node in p.xpath('.//w:proofErr',namespaces=NS):node.getparent().remove(node)
    ops.append((m.start(),m.end(),fragment(p)))
assert len(set(a for a,b,c in ops))==len(ops),'Conflicting insertion positions'
newxml=xml
for a,b,part in sorted(ops,reverse=True):newxml=newxml[:a]+part+newxml[b:]
after=E.fromstring(newxml);ab=after.find('w:body',NS)
added=set(inserts);assert len(added)==len(inserts)
removed_additions=[p for p in ab if not(p.tag==q('p') and txt(p) in added)]
assert len(removed_additions)==len(body)
changes={v['old']:v['new'] for v in plan['replacements']}
canon=lambda p:E.tostring(p,method='c14n')
for i,(a,b) in enumerate(zip(body,removed_additions)):
    if txt(a) in changes:assert txt(b)==changes[txt(a)]
    else:assert canon(a)==canon(b),(i,txt(a)[:50])
for tag in ['//m:oMath','//w:drawing','//w:tbl']:
    assert [canon(p) for p in doc.xpath(tag,namespaces=NS)]==[canon(p) for p in after.xpath(tag,namespaces=NS)],tag
out=BytesIO()
with ZipFile(out,'w') as dest:
    for item in z.infolist():dest.writestr(copy.copy(item),newxml if item.filename=='word/document.xml' else z.read(item.filename))
staged=BASE/'methods_results_staged.docx';staged.write_bytes(out.getvalue())
with ZipFile(staged) as check:assert all(check.read(n)==z.read(n) for n in z.namelist() if n!='word/document.xml')
record.update({'staged':str(staged),'staged_sha256':sha(staged.read_bytes()),'added_paragraphs':len(inserts),'added_characters':sum(map(len,inserts)),'existing_paragraph_replacements':plan['replacements'],'all_other_original_elements_identical':True,'formulas_figures_tables_identical':True,'other_package_members_identical':True,'outline_unchanged':True})
(BASE/'methods_results_receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['METHOD AND RESULT CLARIFICATION DRAFT','']
for p in ab:
    s=txt(p)
    if s:lines.append(s)
(BASE/'methods_results_staged_text.txt').write_text('\n'.join(lines),encoding='utf-8')
export=(BASE/'section22_export.ps1').read_text(encoding='utf-8').replace('section22_clarified_staged.docx','methods_results_staged.docx').replace('section22_clarified_preview.pdf','methods_results_preview.pdf').replace('section22_export.json','methods_results_export.json')
(BASE/'methods_results_export.ps1').write_text(export,encoding='utf-8')
render=(BASE/'section22_render.py').read_text(encoding='utf-8').replace('section22_export.json','methods_results_export.json').replace('section22_clarified_render','methods_results_render')
(BASE/'methods_results_render.py').write_text(render,encoding='utf-8')
print(json.dumps({k:record[k] for k in ['added_paragraphs','added_characters','all_other_original_elements_identical','formulas_figures_tables_identical','outline_unchanged']},ensure_ascii=False))
