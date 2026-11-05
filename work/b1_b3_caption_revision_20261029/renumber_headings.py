from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree as E
import copy, hashlib, json

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
TARGET=ROOT/'04_汇报与调研资料/课题一B1至B3算法阶段研究报告_20261029.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W,'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
q=lambda n:'{'+W+'}'+n
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=TARGET.read_bytes()
backup=BASE/'before_heading_numbering.docx'
if backup.exists():assert backup.read_bytes()==raw, 'The original changed since backup'
else:backup.write_bytes(raw)
inventory={p.name:sha(p.read_bytes()) for p in TARGET.parent.iterdir() if p.is_file()}
(BASE/'heading_directory_before.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
source=ZipFile(BytesIO(raw));doc=E.fromstring(source.read('word/document.xml'))
body=doc.find(q('body'))
text=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=NS))
mapping={
'研究目标与阶段结论':('1 研究目标与阶段结论','Heading1'),
'一 B1如何从功率曲线得到过程特征':('2.1 从功率曲线提取过程特征','Heading2'),
'单事件计算样例':('2.1.1 单事件计算样例','Heading3'),
'二 B1如何区分激励作用与原有差异':('2.2 激励作用与事前差异分析','Heading2'),
'三 B1方法取舍与历史信息增量':('2.3 方法取舍与历史信息增量','Heading2'),
'三次已完成历史是否改善B2预测':('2.3.1 三次已完成历史对B2预测的增量检验','Heading3'),
'四 B2怎样把能力与意愿连接起来':('3.1 单体能力与用户意愿的融合','Heading2'),
'单体预测计算样例':('3.1.1 单体预测计算样例','Heading3'),
'五 B2分层预测和行为模型的实验结果':('3.2 分层预测与行为模型实验结果','Heading2'),
'分层预测的作用':('3.2.1 分层预测的作用','Heading3'),
'参考点和风险表达的增量':('3.2.2 参考点和风险表达的增量','Heading3'),
'六 B2动态响应与恢复过程':('3.3 动态响应与恢复过程','Heading2'),
'七 B3组合容量与共享恢复约束':('4.1 组合容量与共享恢复约束','Heading2'),
'组合方法与参照结果':('4.1.1 组合方法与参照结果','Heading3'),
'八 连续任务中的剩余需求与状态传递':('4.2 连续任务中的剩余需求与状态传递','Heading2'),
'九 联合验证与算法稳定性':('4.3 联合验证与算法稳定性','Heading2'),
'稳定性完善及独立核验':('4.3.1 稳定性完善及独立核验','Heading3'),
'阶段判断与后续工作':('5 阶段判断与后续工作','Heading1'),
'附录 计算补充与研究依据':('6 附录 计算补充与研究依据','Heading1'),
'B1分层调整计算':('6.1 B1分层调整计算','Heading2'),
'模型状态与结果使用':('6.2 模型状态与结果使用','Heading2'),
'研究依据与结果索引':('6.3 研究依据与结果索引','Heading2'),
}
insertions={
'一 B1如何从功率曲线得到过程特征':'2 B1算法 行为影响因素与全过程特征分析',
'四 B2怎样把能力与意愿连接起来':'3 B2算法 单体容量与响应评估',
'七 B3组合容量与共享恢复约束':'4 B3算法 多资源组合协同与连续调用',
}
template=next(p for p in body if text(p)=='研究目标与阶段结论')
def set_heading(p,s,style):
    p.find('w:pPr/w:pStyle',NS).set(q('val'),style)
    nodes=p.xpath('.//w:t',namespaces=NS)
    nodes[0].text=s
    for n in nodes[1:]:n.text=''
    for node in p.xpath('./w:pPr/w:numPr',namespaces=NS):node.getparent().remove(node)

unchanged=[];changed=[]
for p in list(body):
    old=text(p)
    if p.tag==q('p') and old in mapping:
        if old in insertions:
            added=copy.deepcopy(template);set_heading(added,insertions[old],'Heading1');p.addprevious(added)
        new,style=mapping[old];set_heading(p,new,style);changed.append({'old':old,'new':new,'style':style})
    else:unchanged.append(E.tostring(p,method='c14n'))
assert len(changed)==len(mapping)
newxml=E.tostring(doc,encoding='UTF-8',xml_declaration=True,standalone=True)
out=BytesIO()
with ZipFile(out,'w') as z:
    for item in source.infolist():z.writestr(copy.copy(item),newxml if item.filename=='word/document.xml' else source.read(item.filename))
staged=BASE/'heading_numbering_staged.docx';staged.write_bytes(out.getvalue())
with ZipFile(staged) as z:
    assert z.namelist()==source.namelist()
    assert all(z.read(n)==source.read(n) for n in z.namelist() if n!='word/document.xml')
    after=E.fromstring(z.read('word/document.xml'));ab=after.find(q('body'))
    excluded={x[0] for x in mapping.values()}|set(insertions.values())
    after_unchanged=[E.tostring(p,method='c14n') for p in ab if not(p.tag==q('p') and text(p) in excluded)]
    assert unchanged==after_unchanged,'A body, table, figure, equation, or caption changed'
    assert doc.xpath('count(//m:oMath)',namespaces=NS)==after.xpath('count(//m:oMath)',namespaces=NS)
    outline=[{'text':text(p),'style':p.find('w:pPr/w:pStyle',NS).get(q('val'))} for p in ab if p.tag==q('p') and p.find('w:pPr/w:pStyle',NS) is not None and p.find('w:pPr/w:pStyle',NS).get(q('val')).startswith('Heading')]
receipt={'target':str(TARGET),'before_sha256':sha(raw),'staged_sha256':sha(staged.read_bytes()),'changes':changed,'inserted_chapter_headings':list(insertions.values()),'outline':outline,'only_zip_member_changed':'word/document.xml','non_heading_elements_identical':True,'formulas':int(after.xpath('count(//m:oMath)',namespaces=NS)),'media_unchanged':True,'other_folder_files_before':inventory}
(BASE/'heading_numbering_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'staged':str(staged),'changed_headings':len(changed),'added_chapters':3,'formulas':receipt['formulas'],'outline':outline},ensure_ascii=False,indent=2))
