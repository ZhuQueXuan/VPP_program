"""Narrow, in-place terminology edit to the user's two moved Word files."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import ast,copy,hashlib,json,re
from lxml import etree

ROOT=Path(__file__).resolve().parents[2]
BASE=Path(__file__).resolve().parent
FOLDER=ROOT/'04_汇报与调研资料'
FILES=[('课题一B1至B3算法阶段研究报告_20261029.docx',BASE),('课题一B1至B3算法汇报讲解稿_个人理解版_20261029.docx',ROOT/'work/b123_personal_briefing_20261029')]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
W='{'+NS['w']+'}';M='{'+NS['m']+'}'
sha=lambda b:hashlib.sha256(b).hexdigest()

# The figures were generated from vector drawing code. Regenerate identical
# geometry and scientific arrays with only the two source label literals changed.
source=ROOT/'work/b1_b3_report_update_20261029/build_report.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
keep=[]
for n in tree.body:
    if isinstance(n,(ast.Import,ast.ImportFrom)):keep.append(n)
    elif isinstance(n,ast.FunctionDef) and n.name in ['txt','arrow','box','fig','make_figures']:keep.append(n)
class Labels(ast.NodeTransformer):
    def visit_Constant(self,n):
        if isinstance(n.value,str):
            n.value={'EV会话':'充电桩会话','EV欠账  kWh':'充电欠账 kWh'}.get(n.value,n.value)
        return n
mod=ast.fix_missing_locations(Labels().visit(ast.Module(body=keep,type_ignores=[])))
figdir=BASE/'charging_wording_figures';figdir.mkdir(exist_ok=True)
env={'__file__':str(source),'ROOT':ROOT,'BASE':BASE,'FIG':figdir}
exec(compile(mod,str(source),'exec'),env)
env['pdfmetrics'].registerFont(env['TTFont']('ZH',r'C:\Windows\Fonts\simhei.ttf'))
example=json.loads((ROOT/'work/b1_b3_report_update_20261029/selected_continuous_example.json').read_text(encoding='utf-8-sig'))
env['make_figures'](example)

SPECIAL=[
('以EV为主要行为研究对象','以充电桩侧充电响应为主要行为研究对象'),
('以单向充电EV为代表机制','以充电桩单向充电为代表机制'),
('针对单EV的','针对单个充电桩的'),
('两EV参考功率','两个充电桩的参考功率'),
('两EV的新方案','两个充电桩的新方案'),
('两EV、光伏和储能','两个充电桩、光伏和储能'),
('EV原离站期限','充电桩所接车辆的原离站期限'),
('EV仍在原来的120分钟离站','充电桩所接车辆仍在原来的120分钟离站'),
('EV按120分钟离站期限检查','充电桩所接车辆按120分钟离站期限检查'),
('EV在原期限前恢复','充电桩所接车辆在原期限前补齐电量'),
('当前用EV做主要行为研究','当前以充电桩侧充电响应做主要行为研究'),
('B1和B2主要研究EV','B1和B2主要研究充电桩侧充电响应'),
('EV最多欠电','充电桩所接车辆最多欠电'),
('EV减载通常指','充电桩减载通常指'),
]
def replace(s):
    for a,b in SPECIAL:s=s.replace(a,b)
    return s.replace('EV','充电桩')

def patch_text(par):
    nodes=par.xpath('.//w:t',namespaces=NS)
    old=''.join(n.text or '' for n in nodes)
    new=replace(old)
    if old==new:return None
    # Distribute replacements over the existing runs, preserving every run's
    # properties, original unchanged text and equations in the same paragraph.
    import difflib
    arr=[n.text or '' for n in nodes]
    offsets=[];o=0
    for t in arr:offsets.append((o,o+len(t)));o+=len(t)
    for tag,a,b,c,e in reversed(difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes()):
        if tag=='equal':continue
        start=next((i for i,(lo,hi) in enumerate(offsets) if lo<=a<hi),len(nodes)-1)
        end=next((i for i,(lo,hi) in enumerate(offsets) if lo<b<=hi),start) if b>a else start
        sl=a-offsets[start][0];el=b-offsets[end][0]
        if start==end:arr[start]=arr[start][:sl]+new[c:e]+arr[start][el:]
        else:
            arr[start]=arr[start][:sl]+new[c:e]
            for i in range(start+1,end):arr[i]=''
            arr[end]=arr[end][el:]
    assert ''.join(arr)==new
    for n,t in zip(nodes,arr):
        n.text=t
        if t.startswith(' ') or t.endswith(' '):n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return {'before':old,'after':new}

receipt=[]
for index,(name,work) in enumerate(FILES):
    target=FOLDER/name;original=(work/'before_charging_wording.docx').read_bytes()
    assert target.read_bytes()==original,'Target changed since backup'
    z=ZipFile(BytesIO(original));newparts={};changes=[];math_changes=[]
    for nm in z.namelist():
        if nm.startswith('word/') and nm.endswith('.xml'):
            xml=etree.fromstring(z.read(nm));changed=False
            # Use innermost paragraphs only, so each text is edited once.
            for p in xml.xpath('//w:p[not(.//w:p)]',namespaces=NS):
                change=patch_text(p)
                if change:changes.append({'part':nm,**change});changed=True
            for mt in xml.xpath('//m:t',namespaces=NS):
                if 'EV' in (mt.text or ''):
                    old=mt.text;mt.text=old.replace('EV','桩');math_changes.append({'before':old,'after':mt.text});changed=True
            if changed:newparts[nm]=etree.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True)
    if index==0:
        for part,filename in [('word/media/image6.png','timeline.png'),('word/media/image7.png','continuous_curves.png')]:
            newparts[part]=(figdir/filename).read_bytes()
    out=BytesIO()
    with ZipFile(out,'w') as zw:
        for inf in z.infolist():zw.writestr(copy.copy(inf),newparts.get(inf.filename,z.read(inf.filename)))
    staged=work/'charging_wording_staged.docx';staged.write_bytes(out.getvalue())
    # Validate shape/format/number preservation before touching live document.
    zz=ZipFile(staged)
    assert set(z.namelist())==set(zz.namelist())
    changed_parts=[nm for nm in z.namelist() if z.read(nm)!=zz.read(nm)]
    assert set(changed_parts)==set(newparts)
    for nm in ['word/styles.xml','word/settings.xml']:
        assert z.read(nm)==zz.read(nm)
    ox=etree.fromstring(z.read('word/document.xml'));nx=etree.fromstring(zz.read('word/document.xml'))
    assert re.findall(r'\d+(?:\.\d+)?',''.join(ox.itertext()))==re.findall(r'\d+(?:\.\d+)?',''.join(nx.itertext()))
    def formatting(x):
        x=copy.deepcopy(x)
        for n in x.xpath('//w:t|//m:t',namespaces=NS):n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
        return etree.tostring(x,method='c14n')
    assert formatting(ox)==formatting(nx),'Formatting changed'
    assert not nx.xpath('//w:t[contains(text(),"EV")]|//m:t[contains(text(),"EV")]',namespaces=NS)
    with target.open('wb') as f:f.write(staged.read_bytes())
    receipt.append({'file':str(target),'work':str(work),'before_sha256':sha(original),'after_sha256':sha(target.read_bytes()),'changed_parts':changed_parts,'text_changes':changes,'math_subscript_changes':math_changes,'styles_identical':True,'numbers_identical':True,'formatting_identical':True})
    print('Updated in place',name,'text paragraphs',len(changes),'math labels',len(math_changes))
(BASE/'charging_wording_changes.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
