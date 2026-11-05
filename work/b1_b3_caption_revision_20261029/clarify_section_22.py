from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree as E
import copy,hashlib,json,re

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
TARGET=ROOT/'04_汇报与调研资料/课题一B1至B3算法阶段研究报告_20261029.docx'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=TARGET.read_bytes();backup=BASE/'before_section22_clarification.docx'
assert not backup.exists(),'Preserve prior backups'
backup.write_bytes(raw)
inv={p.name:sha(p.read_bytes()) for p in TARGET.parent.iterdir() if p.is_file() and not p.name.startswith('~$')}
z=ZipFile(BytesIO(raw));xml=z.read('word/document.xml')
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
doc=E.fromstring(xml);body=doc.find('w:body',NS)
txt=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=NS))
start=next(i for i,p in enumerate(body) if txt(p).startswith('2.2 '))
end=next(i for i,p in enumerate(body) if i>start and txt(p).startswith('2.3 '))
old=body[start+1];oldtext=txt(old)
assert oldtext.startswith('高激励可能更常分给某些用户。')
newtexts=[
'本节的激励指用户配合充电桩降低充电功率所获得的调节补偿。“高激励”和“低激励”分别表示较高和较低的假设补偿水平。本轮只设置两档相对水平，未设定具体金额，也未对应实际市场补偿标准。',
'高补偿可能更常分给充电需求紧迫或离站时间余量不同的用户。因此，高低补偿组的响应时长差，既可能来自补偿水平，也可能来自用户原有条件。本节先声明因素之间的结构假设；在非随机分配场景中，按事前需求和期限余量比较相近用户，估计补偿从低档提高到高档对累计减载时长的平均作用。',
]
replacements=[]
for s in newtexts:
    p=copy.deepcopy(old)
    texts=p.xpath('.//w:t',namespaces=NS);texts[0].text=s
    for node in texts[1:]:node.text=''
    for node in p.xpath('.//w:proofErr',namespaces=NS):node.getparent().remove(node)
    # Namespace bindings remain inherited from the original document root.
    replacements.append(p)
spans=list(re.finditer(rb'<w:p(?:\s[^>]*)?>.*?</w:p>',xml,re.S))
matches=[]
for m in spans:
    try:
        wrapped=b'<root '+b' '.join(('xmlns:'+prefix+'="'+uri+'"').encode() for prefix,uri in doc.nsmap.items() if prefix)+b'>'+m.group()+b'</root>'
        candidate=E.fromstring(wrapped)[0]
        if txt(candidate)==oldtext:matches.append(m)
    except E.XMLSyntaxError:pass
assert len(matches)==1
m=matches[0]
def fragment(p):
    s=E.tostring(p,encoding='unicode',with_tail=False)
    return re.sub(r' xmlns(?::[\w]+)?="[^"]*"','',s).encode('utf-8')
replacement=b''.join(fragment(p) for p in replacements)
newxml=xml[:m.start()]+replacement+xml[m.end():]
after=E.fromstring(newxml);ab=after.find('w:body',NS)
canon=lambda p:E.tostring(p,method='c14n')
assert len(ab)==len(body)+1
assert [canon(p) for p in list(body)[:start+1]]==[canon(p) for p in list(ab)[:start+1]]
assert [canon(p) for p in list(body)[start+2:]]==[canon(p) for p in list(ab)[start+3:]]
assert newxml[:m.start()]==xml[:m.start()]
assert newxml[m.start()+len(replacement):]==xml[m.end():]
out=BytesIO()
with ZipFile(out,'w') as dest:
    for item in z.infolist():dest.writestr(copy.copy(item),newxml if item.filename=='word/document.xml' else z.read(item.filename))
staged=BASE/'section22_clarified_staged.docx';staged.write_bytes(out.getvalue())
with ZipFile(staged) as check:
    assert all(check.read(n)==z.read(n) for n in z.namelist() if n!='word/document.xml')
receipt={'target':str(TARGET),'before_sha256':sha(raw),'staged_sha256':sha(staged.read_bytes()),'old_paragraph':oldtext,'new_paragraphs':newtexts,'only_edit':'Replace the opening paragraph of section 2.2 with two explanatory paragraphs','all_other_document_xml_bytes_identical':True,'all_other_zip_members_identical':True,'folder_before':inv}
(BASE/'section22_clarification_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
export=(BASE/'heading_export.ps1').read_text(encoding='utf-8')
for a,b in [('heading_numbering_staged.docx','section22_clarified_staged.docx'),('heading_numbering_preview.pdf','section22_clarified_preview.pdf'),('heading_export.json','section22_export.json')]:export=export.replace(a,b)
(BASE/'section22_export.ps1').write_text(export,encoding='utf-8')
render=(BASE/'heading_render.py').read_text(encoding='utf-8').replace('heading_export.json','section22_export.json').replace('heading_numbering_render','section22_clarified_render')
(BASE/'section22_render.py').write_text(render,encoding='utf-8')
print(json.dumps({'staged':str(staged),'preserved_user_version_sha256':sha(raw),'edit':'Only the opening paragraph of 2.2 changed; all other XML bytes and package members identical'},ensure_ascii=False))
