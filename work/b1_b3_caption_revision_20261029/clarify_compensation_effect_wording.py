from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree as E
import copy,hashlib,json,re

BASE=Path(__file__).resolve().parent
receipt=json.loads((BASE/'compensation_effect_wording_source.json').read_text(encoding='utf-8'))
TARGET=Path(receipt['target']);raw=(BASE/'before_compensation_effect_wording.docx').read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(raw)==receipt['before_sha256']==sha(TARGET.read_bytes()),'The original changed; rebase first'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
q=lambda n:'{'+NS['w']+'}'+n
z=ZipFile(BytesIO(raw));xml=z.read('word/document.xml');doc=E.fromstring(xml);body=doc.find('w:body',NS)
text=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=NS))
matches=[(i,p) for i,p in enumerate(body) if text(p).startswith('估计输入与训练步骤。因素估计读取')]
assert len(matches)==1
i,original=matches[0];old=text(original)
label='补偿影响估计的输入与计算步骤。'
intro='这部分属于B1算法，用来估计补偿从低档提高到高档时，累计减载时长平均变化多少。输入是训练用户已记录的事前期限余量X、需求紧迫度W、补偿档位D，以及2.1节从观测曲线提取的累计时长R。事前因素是已知输入，本步不估计这些因素本身。'
steps='算法先依据声明的结构假设确定需调整的事前因素。在非随机分配场景中，按X、W将用户分为四类，用训练数据分别计算、保存各类用户在高、低补偿下的平均时长。应用时先求各类的高低补偿时长差，再按目标测试人群中各类用户的比例加权，得到该人群的平均补偿影响。这里的“训练”就是用训练数据计算并保存各组均值，不涉及神经网络训练。未参加用户仍计入总体，结果不表示每个参加者都改变相同时长。'
p1=copy.deepcopy(original);nodes=p1.xpath('.//w:t',namespaces=NS);assert len(nodes)==2
nodes[0].text=label;nodes[1].text=intro
p2=copy.deepcopy(original)
for child in list(p2):
    if child.tag!=q('pPr'):p2.remove(child)
run=copy.deepcopy(original.findall('w:r',NS)[1]);run.find('w:t',NS).text=steps;p2.append(run)
nsdecl=b' '.join(('xmlns:'+prefix+'="'+uri+'"').encode() for prefix,uri in doc.nsmap.items() if prefix)
spans=[]
for m in re.finditer(rb'<w:p(?:\s[^>]*)?>.*?</w:p>',xml,re.S):
    try:p=E.fromstring(b'<root '+nsdecl+b'>'+m.group()+b'</root>')[0]
    except E.XMLSyntaxError:continue
    if text(p)==old:spans.append(m)
assert len(spans)==1;m=spans[0]
def fragment(p):return re.sub(r' xmlns(?::[\w]+)?="[^"]*"','',E.tostring(p,encoding='unicode',with_tail=False)).encode()
newpart=fragment(p1)+fragment(p2);newxml=xml[:m.start()]+newpart+xml[m.end():]
after=E.fromstring(newxml);ab=after.find('w:body',NS);canon=lambda p:E.tostring(p,method='c14n')
assert len(ab)==len(body)+1
assert [canon(p) for p in list(body)[:i]]==[canon(p) for p in list(ab)[:i]]
assert [canon(p) for p in list(body)[i+1:]]==[canon(p) for p in list(ab)[i+2:]]
out=BytesIO()
with ZipFile(out,'w') as dest:
    for item in z.infolist():dest.writestr(copy.copy(item),newxml if item.filename=='word/document.xml' else z.read(item.filename))
staged=BASE/'compensation_effect_wording_staged.docx';staged.write_bytes(out.getvalue())
with ZipFile(staged) as check:assert all(check.read(n)==z.read(n) for n in z.namelist() if n!='word/document.xml')
receipt.update({'staged':str(staged),'staged_sha256':sha(staged.read_bytes()),'old':old,'new_paragraphs':[label+intro,steps],'only_section22_one_original_paragraph_replaced':True,'all_other_body_elements_and_package_members_identical':True})
(BASE/'compensation_effect_wording_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
export=(BASE/'humanizer_zh_export.ps1').read_text(encoding='utf-8').replace('humanizer_zh_staged.docx','compensation_effect_wording_staged.docx').replace('humanizer_zh_preview.pdf','compensation_effect_wording_preview.pdf').replace('humanizer_zh_export.json','compensation_effect_wording_export.json')
(BASE/'compensation_effect_wording_export.ps1').write_text(export,encoding='utf-8')
render=(BASE/'humanizer_zh_render.py').read_text(encoding='utf-8').replace('humanizer_zh_export.json','compensation_effect_wording_export.json').replace('humanizer_zh_render','compensation_effect_wording_render')
(BASE/'compensation_effect_wording_render.py').write_text(render,encoding='utf-8')
print('Only the ambiguous paragraph in section 2.2 replaced with two clear paragraphs; all other saved content preserved.')
