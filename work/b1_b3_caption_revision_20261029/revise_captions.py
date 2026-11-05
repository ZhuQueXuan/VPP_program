"""Short descriptive captions; explanatory information moves into adjacent body prose."""
import json,re,copy,hashlib
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
from lxml import etree
from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];SOURCE=BASE/'before_caption.docx';TARGET=ROOT/'outputs/课题一B1至B3算法阶段研究报告_图注修订版_20261029.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
REVISIONS={
 '图1':('三项算法的职责及信息关系','图1中，B1提供解释和观测，B2提供单体预测，B3处理组合约束与实际状态。'),
 '图2':('EV响应与回补功率曲线','图2采用已保存的带噪模拟测试样例。灰线为参考，蓝线为观测功率；功率和时间单位分别为kW和s。'),
 '图3':('EV响应因素的简化结构假设','图3中，X与W是事前因素，A是激励后的参加结果。'),
 '图4':('五种预设EV响应模板','图4的纵向幅度按任务归一化，条件状态概率对应第四节的单体查询样例。该模型采用预设模板，尚不能表示任意连续时序。'),
 '图5':('连续任务与恢复时限','图5所示的第二次任务在60分钟到来，90分钟到来的变体另行评价。'),
 '图6':('连续调用的状态与功率变化','图6采用已保存的一条下界内连续调用实例。浅色区域为两次服务窗；该条曲线用于解释状态传递，不代表总体表现。'),
 '表1':('激励平均效应估计结果','表1汇总测试总体的20次重复结果。G0为未调整比较，G1为合法事前调整；均值与RMSE分别报告，参考真效应由模拟机制计算。'),
 '表2':('历史信息增量比较结果','表2给出各种子测试指标的平均值，RMSE与Brier越低越好。后三种历史方案均增加6维，当前条件对照的输入更少；比较不满足总参数量完全一致的条件。'),
 '表3':('分层预测的测试结果','表3为首轮20次重复的全部测试事件结果；每次600用户8事件，360/120/120用户隔离。包含不可发送、拒绝和执行失败，另评价可发送子集。RMSE与Brier均越低越好，Brier是概率与实际0/1结果之差的均方。'),
 '表4':('连续任务的服务与恢复结果','表4中，每种机制均有160项任务请求。接任务和拒任务合计为请求总数；达标率仅针对已接任务。EV按120分钟离站期限检查，站级末端另核储能180分钟恢复。配对变体不作为独立样本扩大置信度。')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def properties(path):
    with ZipFile(path) as z:
        x=etree.fromstring(z.read('word/document.xml'))
        return dict(math=[etree.tostring(v,method='c14n') for v in x.xpath('//m:oMath',namespaces=NS)],tables=[etree.tostring(v,method='c14n') for v in x.xpath('//w:tbl',namespaces=NS)],media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')})
def body_paragraph(d,after,text):
    el=OxmlElement('w:p');after._p.addnext(el);p=Paragraph(el,d._body);p.style='Normal';p.paragraph_format.line_spacing=1.25;p.paragraph_format.first_line_indent=Pt(21);p._p.get_or_add_pPr().get_or_add_ind().set(qn('w:firstLineChars'),'200');p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0);p.paragraph_format.page_break_before=False;p.paragraph_format.widow_control=True
    r=p.add_run(text);r.font.name='Times New Roman';r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体');r.font.size=Pt(10.5);r.bold=False
    return p
def main():
    d=Document(SOURCE);before=properties(SOURCE);records=[];captions=[p for p in d.paragraphs if p.style.name=='Caption'];assert len(captions)==10
    for p in captions:
        match=re.match(r'^(图\d+|表\d+)\s+',p.text);assert match;key=match[1];title,note=REVISIONS[key];old=p.text
        # Keep the exact current caption paragraph/run formatting while replacing its wording.
        run_properties=copy.deepcopy(p.runs[0]._element.rPr);p.text=key+' '+title;p.runs[0]._element.insert(0,run_properties);p.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p._p.pPr.ind.set(qn('w:firstLineChars'),'0')
        for r in p.runs:r.bold=False;r.font.size=Pt(10)
        body_paragraph(d,p,note)
        records.append(dict(id=key,before=old,caption=p.text,body_explanation=note,placement='immediately after caption in body style'))
    patch=etree.tostring(d.element,encoding='UTF-8',xml_declaration=True,standalone=True)
    with ZipFile(SOURCE) as a,ZipFile(TARGET,'w') as b:
        for info in a.infolist():b.writestr(info,patch if info.filename=='word/document.xml' else a.read(info.filename))
    assert properties(TARGET)==before,'scientific formula, table or image altered'
    with ZipFile(SOURCE) as a,ZipFile(TARGET) as b:assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==['word/document.xml']
    # Original non-caption paragraphs are byte-identical, including all numbers and formatting.
    a=Document(SOURCE);b=Document(TARGET);old=[etree.tostring(p._p,method='c14n') for p in a.paragraphs if p.style.name!='Caption'];new=Counter(etree.tostring(p._p,method='c14n') for p in b.paragraphs if p.style.name!='Caption');assert not (Counter(old)-new)
    (BASE/'revision_receipt.json').write_text(json.dumps(dict(status='revised_pending_render',source_sha=sha(SOURCE),target_sha=sha(TARGET),figures=6,tables=4,unchanged_original_body_paragraphs=True,formulas_tables_images_identical=True,styles_and_other_parts_identical=True,revisions=records),ensure_ascii=False,indent=2),encoding='utf-8');print('shortened10 captions, moved10 explanations to body; scientific objects unchanged')
if __name__=='__main__':main()
