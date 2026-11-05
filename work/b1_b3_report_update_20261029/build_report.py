"""Revise the retained Word report using existing scientific evidence only."""
import copy,json,hashlib,math
from pathlib import Path
import numpy as np
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pymupdf as fitz

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];FIG=BASE/'figures';FIG.mkdir(exist_ok=True)
REFERENCE=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx'
OUT=ROOT/'outputs/课题一B1至B3算法阶段研究报告_20261029.docx'
TITLE='课题一B1至B3算法阶段研究报告'
def rd(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pdfmetrics.registerFont(TTFont('ZH',r'C:\Windows\Fonts\simhei.ttf'))
def txt(c,x,y,s,size=11,color='#17232e'):
    from reportlab.lib.colors import HexColor
    c.setFillColor(HexColor(color));c.setFont('ZH',size);c.drawString(x,y,s)
def arrow(c,a,b,dashed=False):
    c.setStrokeColorRGB(.32,.38,.44);c.setLineWidth(1);c.setDash(4,3) if dashed else c.setDash();c.line(*a,*b);c.setDash();ang=math.atan2(b[1]-a[1],b[0]-a[0])
    for d in [-.45,.45]:c.line(b[0],b[1],b[0]-6*math.cos(ang+d),b[1]-6*math.sin(ang+d))
def box(c,x,y,w,h,lines):
    c.setStrokeColorRGB(.45,.52,.59);c.setLineWidth(.7);c.rect(x,y,w,h)
    for i,s in enumerate(lines):txt(c,x+8,y+h-18-i*16,s,10)
def fig(name,draw,height):
    p=FIG/(name+'.pdf');c=canvas.Canvas(str(p),pagesize=(650,height));c.setFillColorRGB(1,1,1);c.rect(0,0,650,height,fill=1,stroke=0);draw(c,650,height);c.save()
    d=fitz.open(p);d[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(FIG/(name+'.png'));d.close()

def make_figures(example):
    def overview(c,w,h):
        box(c,12,74,192,69,['B1 过程特征与因素分析','参考及观测功率 → 过程特征','事前条件及激励 → 平均作用'])
        box(c,230,74,192,69,['B2 单体容量与响应评估','需求  期限  许可  行为条件','物理可行性  情景及概率'])
        box(c,448,74,190,69,['B3 组合协同与连续调用','源荷储边界  共享恢复约束','任务准入  反馈及失效处理'])
        arrow(c,(204,109),(230,109),True);arrow(c,(422,109),(448,109))
        arrow(c,(544,74),(544,48));arrow(c,(544,48),(108,48));arrow(c,(108,48),(108,74))
        txt(c,205,29,'执行后观测与实际状态回传',10)
        txt(c,12,6,'虚线：B1历史为经检验决定采用的可选信息。B2预测不构成控制许可，动作仍需实际接受。',9)
    fig('overview',overview,155)
    def timeline(c,w,h):
        left,right=70,624
        def x(t):return left+(right-left)*t/180
        for y,label in [(76,'站级状态'),(43,'EV会话')]:
            txt(c,7,y-3,label,10);c.setStrokeColorRGB(.45,.5,.55);c.line(left,y,right if label=='站级状态' else x(120),y)
        for a,z,label in [(0,30,'任务一'),(60,90,'任务二')]:
            c.setFillColorRGB(.88,.93,.96);c.rect(x(a),85,x(z)-x(a),21,fill=1,stroke=0);txt(c,x(a)+9,91,label,10)
        for t in [0,30,60,90,120,180]:
            c.setStrokeColorRGB(.65,.68,.7);c.line(x(t),27,x(t),80);txt(c,x(t)-7,12,str(t),9)
        txt(c,x(120)-37,48,'原离站期限',9);txt(c,right-89,82,'储能末端恢复',9);txt(c,70,115,'第二次调用按实际剩余期限和欠账查询，不重置状态',11);txt(c,550,0,'时间  min',9)
    fig('timeline',timeline,132)
    c=example['case']['public'];r=example['run'];power=np.array(r['paths_kw']);b=sum(v['declaration']['b'] for v in c['evs']);ref=c['fixed_kw']+b*(np.arange(180)<120)-.6*np.array(c['pv_forecast_kw']);delivery=ref-c['fixed_kw']-power.sum(axis=1)
    debt=np.array([sum(s['backlog']) for s in r['states']]);energy=np.array([s['energy'] for s in r['states']])
    def curves(cv,w,h):
        left,right=70,630;panels=[(174,228,'EV欠账  kWh',debt,(0,max(debt)*1.13)),(94,148,'储能电量 kWh',energy,(min(energy)-.1,c['initial_kwh']+.16)),(18,72,'净减购  kW',delivery,(min(delivery)-.2,max(delivery)+.35))]
        for bot,top,label,values,(lo,hi) in panels:
            xx=lambda t:left+(right-left)*t/180;yy=lambda v:bot+(top-bot)*(v-lo)/(hi-lo)
            for a,z in [(0,30),(60,90)]:cv.setFillColorRGB(.94,.96,.98);cv.rect(xx(a),bot,xx(z)-xx(a),top-bot,fill=1,stroke=0)
            cv.setStrokeColorRGB(.66,.69,.72);cv.rect(left,bot,right-left,top-bot)
            for v in [lo,(lo+hi)/2,hi]:txt(cv,18,yy(v)-3,f'{v:.2f}',8)
            txt(cv,3,top+6,label,9)
            cv.setStrokeColorRGB(.13,.40,.61);cv.setLineWidth(1.1);path=cv.beginPath();path.moveTo(xx(0),yy(values[0]))
            for k,v in enumerate(values[1:],1):path.lineTo(xx(k),yy(v))
            cv.drawPath(path)
            if label.startswith('净'):
                cv.setDash(3,2);cv.setStrokeColorRGB(.45,.45,.45)
                for a,z in [(0,30),(60,90)]:cv.line(xx(a),yy(1.8),xx(z),yy(1.8))
                cv.setDash();txt(cv,398,top+6,'虚线为两次任务的1.8 kW要求',8)
            for t in [0,30,60,90,120,150,180]:
                if bot==18:txt(cv,xx(t)-7,3,str(t),8)
        txt(cv,565,0,'时间 min',8)
    fig('continuous_curves',curves,248)

def E(tag,text=None):
    e=OxmlElement('m:'+tag)
    if text is not None:e.text=text
    return e
def mr(s):r=E('r');r.append(E('t',s));return r
def sub(a,b):
    e=E('sSub');x=E('e');x.append(mr(a));y=E('sub');y.append(mr(b));e.extend([x,y]);return e
def frac(a,b):
    f=E('f');n=E('num');d=E('den')
    for target,values in [(n,a),(d,b)]:
        for v in (values if isinstance(values,list) else [values]):target.append(mr(v) if isinstance(v,str) else v)
    f.extend([n,d]);return f

class Report:
    def __init__(self):
        self.d=Document(REFERENCE);self.pages=[[]]
        for el in self.d.element.body:
            if el.tag==qn('w:sectPr'):continue
            if any(b.get(qn('w:type'))=='page' for b in el.findall('.//'+qn('w:br'))):self.pages.append([])
            else:self.pages[-1].append(copy.deepcopy(el))
        for el in list(self.d.element.body):
            if el.tag!=qn('w:sectPr'):self.d.element.body.remove(el)
    def p(self,s,size=None,bold=False):
        p=self.d.add_paragraph();r=p.add_run(s);r.bold=bold
        if size:r.font.size=Pt(size)
        return p
    def h(self,s,level=1):return self.d.add_paragraph(s,'Heading '+str(level))
    def page(self):self.d.add_page_break()
    def reuse(self,n,replacements=None):
        for el in self.pages[n-1]:
            self.d.element.body.insert(len(self.d.element.body)-1,el)
            if el.tag==qn('w:p'):
                p=Paragraph(el,self.d._body)
                for a,b in (replacements or {}).items():
                    if a in p.text:
                        rpr=copy.deepcopy(p.runs[0]._element.rPr) if p.runs and p.runs[0]._element.rPr is not None else None
                        text=p.text.replace(a,b);p.text=text
                        if rpr is not None:p.runs[0]._element.insert(0,rpr)
    def image(self,name,caption,width=6.82):
        p=self.d.add_paragraph();p.paragraph_format.space_after=Pt(3);p.paragraph_format.keep_with_next=True;p.add_run().add_picture(str(FIG/(name+'.png')),width=Inches(width));cp=self.d.add_paragraph(caption,'Caption');cp.paragraph_format.keep_with_next=False
    def table(self,head,rows,widths,small=10):
        t=self.d.add_table(rows=1,cols=len(head));t.autofit=False
        for j,(s,w) in enumerate(zip(head,widths)):t.columns[j].width=Inches(w);t.rows[0].cells[j].width=Inches(w);t.rows[0].cells[j].text=s
        for values in rows:
            cells=t.add_row().cells
            for j,s in enumerate(values):cells[j].width=Inches(widths[j]);cells[j].text=str(s)
        for i,row in enumerate(t.rows):
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            if i==0:row._tr.trPr.append(OxmlElement('w:tblHeader'))
            for j,cell in enumerate(row.cells):
                mar=OxmlElement('w:tcMar')
                for edge in ['top','left','bottom','right']:
                    e=OxmlElement('w:'+edge);e.set(qn('w:w'),'90');e.set(qn('w:type'),'dxa');mar.append(e)
                cell._tc.get_or_add_tcPr().append(mar)
                if i==0:e=OxmlElement('w:shd');e.set(qn('w:fill'),'ECEFF2');cell._tc.tcPr.append(e)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(1);p.paragraph_format.line_spacing=1.08
                    for r in p.runs:r.font.size=Pt(small);r.bold=i==0
        self.p('',size=1).paragraph_format.space_after=Pt(1)
        return t
    def eq(self,items):
        p=self.d.add_paragraph();p.paragraph_format.space_after=Pt(5);p.paragraph_format.space_before=Pt(3);para=E('oMathPara');m=E('oMath')
        for item in items:m.append(mr(item) if isinstance(item,str) else item)
        para.append(m);p._p.append(para)
    def finalize(self):
        def fonts(rpr):
            f=rpr.find(qn('w:rFonts'))
            if f is None:f=OxmlElement('w:rFonts');rpr.insert(0,f)
            f.attrib.clear()
            for key in ['ascii','hAnsi','eastAsia','cs']:f.set(qn('w:'+key),'黑体')
        names={'Title','Subtitle','Caption',*[f'Heading {i}' for i in range(1,10)]}
        for s in self.d.styles:
            if s.name in names:fonts(s.element.get_or_add_rPr());s.font.color.rgb=RGBColor(0,0,0)
        for p in self.d.paragraphs:
            if p.style.name in names:
                for r in p.runs:fonts(r._element.get_or_add_rPr());r.font.color.rgb=RGBColor(0,0,0)
        for t in self.d.tables:
            for cell in t.rows[0].cells:
                for p in cell.paragraphs:
                    for r in p.runs:fonts(r._element.get_or_add_rPr());r.font.color.rgb=RGBColor(0,0,0)
        self.d.core_properties.title=TITLE;self.d.core_properties.subject='B1至B3算法方法与连续调用阶段进展';self.d.core_properties.author='刘文轩';self.d.core_properties.keywords='B1;B2;B3;阶段研究;模拟验证'
        self.d.save(OUT)

def main():
    example=rd('work/b1_b3_report_update_20261029/selected_continuous_example.json');make_figures(example);r=Report();hist=rd('work/b1_b2_history_20261028/results.json');summary=hist['summary']['all']
    r.d.add_paragraph(TITLE,'Title');r.p('汇报人  刘文轩    汇报日期  2026年10月29日',size=10);r.p('研究内容与实验结果截至2026年10月28日。',size=9)
    r.h('研究目标与阶段结论')
    r.p('面向虚拟电厂的资源响应评估与组合调用，B1研究响应过程如何表征、激励作用如何与事前差异区分；B2评估指定单体任务的物理边界、参加概率和预计执行；B3研究共享约束下的源荷储组合及连续调用。服务功率、任务时窗和恢复期限共同构成任务条件。')
    r.p('目前已形成以EV为主要行为研究对象的B1与B2原型，以及假设源荷储组合的B3原型。指定条件下的输入输出衔接、连续状态和失效处理已完成有限模拟验证。历史表示未显示稳定预测增量，保留原B2默认模型；现有证据尚不足以给出现场可靠性承诺。')
    r.image('overview','图1 三项算法的职责及信息关系。B1提供解释和观测，B2提供单体预测，B3处理组合约束与实际状态。')
    r.table(['算法','主要输入','主要输出'],[
      ['B1 行为与过程分析','事前因素、激励、参考及观测曲线','过程特征、条件均值、平均作用及限制'],
      ['B2 单体容量与响应','需求、期限、任务、许可、收益风险及执行条件','物理可行性、参加及服务概率、条件轨迹和期望'],
      ['B3 组合与连续调用','相容单体结果、源储边界、共享约束及实际状态','准入、组合轨迹、欠账与恢复、拒接及失效状态']],widths=[1.5,2.7,2.78],small=10)
    r.p('任务对应：B1对应行为影响因素和关键时序特征，B2对应融合行为经济及绿色因素的单体能力分析，B3对应多智能体源荷储交互与组合潜力。以下结果均按各自模拟机制、数据划分和任务口径解释。',size=9)
    r.page();r.reuse(2,{'一条可以逐步解释的样例':'单事件计算样例','先选单向充电EV作为代表机制。':'以单向充电EV为代表机制。'})
    r.page();r.reuse(3,{'我们先声明结构假设，再确定总效应需要调整的事前因素。':'分析先声明结构假设，再确定总效应需要调整的事前因素。'})
    r.page();r.h('三 B1方法取舍与历史信息增量')
    r.p('特征提取与因素分析采用独立比较确定适用范围。复杂候选的局部改善不作为统一替换原方法的依据。')
    r.table(['比较问题','已有证据及方法判断'],[
      ['抗噪与慢爬升','高噪声误检8/25降至0/25，恢复时点MAE 38.16降至1.68 s；低噪声慢爬升的达标MAE 13.6增至27.2 s，平滑法不能统一替换规则。'],
      ['激励非线性与交点','平滑机制直线/分段RMSE为1.272/0.774个百分点，零作用为0.585/0.862；平台后上升的交点集合100/100含真位置，但均不能唯一定位。'],
      ['结构学习与识别','非随机正/零/负场景完整图恢复9/20、9/20、8/20；方向依赖时序先验，图筛选不能替代必要混杂调整。']],widths=[1.65,5.33],small=9.8)
    r.h('三次已完成历史是否改善B2预测',2)
    r.p('新增比较实际调用B1提取前三次完整历史，并与PCA及非线性自编码器表示比较。20个新独立种子，每次400用户12事件、3个配对机制，共288000变体/96000基础事件；用户按240/80/80隔离，训练、验证、测试目标时段分开，当前结果不进入当前预测。',size=10)
    r.table(['同一下游预测方法的输入方案','平均交付RMSE kW','任务Brier'],[[label,f"{summary[name]['rmse']:.6f}",f"{summary[name]['brier']:.6f}"] for name,label in [('C0','仅当前条件'),('C1','当前条件加6项历史统计'),('C2','当前条件加PCA 6维'),('C3','当前条件加非线性6维表示'),('selected','按验证集选择后的方案')]],widths=[3.7,1.75,1.53],small=9.8)
    r.p('表2 各种子测试指标的平均，RMSE与Brier越低越好。后三种历史方案均增加6维，当前条件对照的输入更少；比较不满足总参数量完全一致的条件。',size=9)
    r.p('自编码器采用90→24→6→24→90结构，4752参数、固定60轮。验证集14次保留当前条件、6次选历史统计；选择后交付MSE差为+0.000539724 kW²，20块95%区间[−0.001061459，+0.002140906]，无稳定总体增量。标准化曲线重建MSE为0.022895，低于PCA的0.028739，下一响应预测未随之改善。',size=10)
    r.p('表中均为本轮新拟合预测头；原冻结B2另作诊断，RMSE为0.579374 kW、Brier为0.087983。因训练结构不同，不将其与新头的差别归于历史信息。历史分支未替换默认模型；本结果不否定其他历史或深度方法。',size=10)
    r.page();r.reuse(5,{'一条实际查询怎样得到预计交付':'单体预测计算样例','真正动作仍需实际接受。':'控制动作以实际接受为前提。'})
    r.page();r.reuse(6,{'先检验分层是否有用':'分层预测的作用','再检验参考点和风险表达的增量':'参考点和风险表达的增量'})
    r.page();r.reuse(7,{'六 B2补齐基本动态响应与恢复过程':'六 B2动态响应与恢复过程','来自上一页查询的条件状态概率':'来自第四节单体样例的条件状态概率','阶段判断：B2已补齐指定任务族的主要分层、基本动态响应和融合输出，可转入B3组合问题准备。真实偏好与绿色属性、实际控制可靠性、跨机制及复杂时序仍保留缺口；正式90%验收尚未通过。':'阶段判断：B2已形成指定任务族的分层预测与基本动态输出，并已在共同支持域进入B3组合和连续调用验证。真实偏好、绿色属性、执行可靠性及跨机制证据仍需补充；正式90%验收尚未通过。'})
    r.page();r.h('七 B3组合容量与共享恢复约束')
    r.p('B3研究同一任务下两EV、光伏和储能怎样共同服务，以及事件后回补是否受站级限额约束。资源统一采用AC侧计量，并分别给出功率边界、任务期限及许可；当前组合为明确假设的小站，尚未形成同站实测验证。')
    r.table(['主体','资源表达','相容性条件'],[
      ['EV','参考与可调功率、累计少充电量、离站需求','不得预充；实际欠账带入下一次规划'],
      ['光伏','声明可发功率、参考出力与预留','可发量和参考的差决定可增发量'],
      ['储能及站级','电量、充放电功率、效率、接入及共享限额','事件服务与末端恢复同时满足']],widths=[.95,2.8,3.23],small=10)
    r.eq([sub('P','grid'),' = ',sub('P','fixed'),' + ∑ ',sub('P','EV,i'),' − ',sub('P','PV'),' + ',sub('P','B,ch'),' − ',sub('P','B,dis')])
    r.eq([sub('P','ref,grid'),' − ',sub('P','grid'),' ≥ Q  （服务窗内）'])
    r.eq([sub('E','B,k+1'),' = ',sub('E','B,k'),' + ',frac([sub('η','ch'),' ',sub('P','B,ch,k'),' Δt'],'60'),' − ',frac([sub('P','B,dis,k'),' Δt'],['60 ',sub('η','dis')])])
    r.p('功率单位为kW，电量为kWh，Δt以分钟计，η为充放电效率，Q为组合任务幅度。共享站限与EV充电限额约束同一时刻的资源总量。单体可行轨迹相加，可能违反共享回补条件，因此单体容量不能直接相加。',size=10)
    r.h('组合方法与参照结果',2)
    r.p('首轮采用本地主体轨迹与协调价格迭代的列生成方法，并以相同信息、相同约束的集中式线性规划为参照。20个新种子、每种子4个基础抽样及4个配对条件，共320情景；本地子问题和共享约束均为声明的线性模型。',size=10)
    r.table(['检验','结果与含义'],[
      ['容量一致性','320情景获得最优性证书，与集中式最大容量差8.89×10⁻¹⁴ kW。串行协调未显示速度优势。'],
      ['单体直接相加','268条相加轨迹违反联合条件，203项容量数值高估；一组受限无预留配置中，均值由相加6.597降至联合2.352 kW。'],
      ['条件解释','上述受限配置同时收紧站级回补和EV共享限额，容量变化不能全部归因于一个因素。']],widths=[1.5,5.48],small=10)
    r.p('单次学习输出联调另在共同120分钟域开展：20组新声明形成80个条件上下文，32个因共享恢复不足未发方案，其余48个上下文共848个正权重情景完成物理与恢复检查。该结果证明接口及条件相容，不代表848次真实试验或现场履约可靠性。',size=10)
    r.page();r.h('八 连续任务中的剩余需求与状态传递')
    r.p('站级运行180分钟，EV原离站期限保持120分钟。两次任务各30分钟，第一项从0分钟开始，第二项在60或90分钟到来。剩余需求由实际充电过程更新，储能电量和EV少充电量均连续传递。')
    r.image('timeline','图5 连续任务与恢复时限示意。图示第二次任务在60分钟到来，90分钟到来的变体另行评价。')
    r.eq([sub('d','i,k+1'),' = ',sub('d','i,k'),' + ',frac([sub('b','i,k'),' − ',sub('P','EV,i,k')],'60'),' Δt,     ',sub('d','i,k'),' ≥ 0'])
    r.eq([sub('E','rem,i'),' = ',sub('b','i'),' · ',frac([sub('T','rem,i')],'60'),' + ',sub('d','i')])
    r.p('Trem,i以分钟计，di为实际累计少充电量kWh。第60分钟剩余60分钟，只有当前需求仍满足原B2适用关系时才发送该EV的新方案；正欠账或剩余30分钟时不外推行为模型。源储能否继续接站级任务，仍需连同既有EV恢复义务一起检查。',size=10)
    r.image('continuous_curves','图6 已保存的下界内连续调用实例。浅色区域为两次服务窗；该条曲线用于解释状态传递，不代表总体表现。')
    state=example['run']['states'][60];b=[e['declaration']['b'] for e in example['case']['public']['evs']];debt=state['backlog']
    r.p(f'该运行两EV参考功率为{b[0]:.6f}和{b[1]:.6f} kW。第60分钟实际少充电量为{debt[0]:.6f}和{debt[1]:.6f} kWh，剩余需求分别为{b[0]+debt[0]:.6f}和{b[1]+debt[1]:.6f} kWh，不能把欠账置零后再次查询。两EV的新方案被阻断，第二项站级任务由光伏和储能承担；EV在原期限前恢复，储能按站级期限恢复。',size=10)
    r.p('本轮明确任务后的充电恢复控制权限，允许B3比B2原恒定回补预测更早恢复；原预测保留为见证，不宣称实际控制曲线与其相同。多次任务共用观测后窗时，单任务恢复归因标记为不可识别。',size=9)
    r.page();r.h('九 联合验证与算法稳定性')
    r.p('连续验证使用20个新独立基础站点，分别改变两种共享余量、两种第二次到来时刻及三种执行机制，共240配对变体、43200分钟。行为按独立固定机制产生，模型不读取未来接受、执行状态或扰动；预测期望不直接充当控制。')
    r.table(['执行机制','运行数','接任务\n拒任务','已接任务\n全分钟达标','EV按时恢复\n站级末端恢复'],[
      ['理想执行','80','84 / 76','84 / 84','80 / 80\n80 / 80'],['声明下界内偏差','80','84 / 76','84 / 84','80 / 80\n80 / 80'],['下界外严重降额','80','44 / 116','0 / 44','76 / 80\n76 / 80']],widths=[1.55,.65,1.15,1.5,2.13],small=10)
    r.p('表4 每种机制均有160项任务请求。接任务和拒任务合计为请求总数；达标率仅针对已接任务。EV按120分钟离站期限检查，站级末端另核储能180分钟恢复。配对变体不作为独立样本扩大置信度。',size=9)
    r.p('理想及声明下界内共168项已接任务达标、160次运行恢复。严重降额下44项已接服务失败，4条运行末端未恢复，结果完整保留。实际观测推翻执行下界后，控制保持欠账及电量，并阻断后续新任务；物理安全处理不等于保证服务或恢复成功。',size=10)
    r.h('稳定性完善及独立核验',2)
    r.table(['环节','已落实的处理'],[
      ['B1与B2调用','二元原值先校验，合法旧结果一致；固定模型版本及文件指纹，分别返回物理上界、期望、条件轨迹与模型概率。'],
      ['B3连续与失效','资源、声明、任务、方案和许可时点绑定；重叠与重复任务拒绝；实际状态不重置，未发、拒接、退出与未恢复分开。'],
      ['复核与再现','独立重算能量、状态、约束和预测消费；未来扰动、未来任务及后续退出不影响既往控制；复核另存新目录。']],widths=[1.5,5.48],small=10)
    r.p('另对24条既有场景完成新防护策略的全程回放，并覆盖服务中故障后的退出和新任务阻断。内部数值类型误拒问题已修正，原模型及既有实验成绩保持。独立复核检查计算与状态一致性，预测性能仍按独立测试指标评价。',size=10)
    r.h('阶段判断与后续工作',2)
    r.p('当前已具备指定EV任务族与假设源储组合的稳定研究接口，完成受限连续调用验证。下一阶段应按实际使用需求确定扩展任务族和代表性差异机制，并补同对象事前需求、许可、指令及同步计量。正式精度评价还需确定输出、真值、容差和不可用样本分母；现有模拟结果不构成103规定精度达到90%的验收结论。',size=10)
    r.page();r.h('附录 计算补充与研究依据')
    r.h('B1分层调整计算',2)
    old=rd('work/b1_b2_meeting_report_20261029/source_evidence.json')['b1_example'];r.p('取第1次重复的非随机正作用场景。训练集按X、W分层估计高低激励均值，再按400个测试用户的事前构成加权。单次计算与正文20次平均结果分开。',size=10)
    r.table(['X W','低激励均值 s','高激励均值 s','层内差 s','测试权重'],[[label,f'{a:.2f}',f'{b:.2f}',f'{b-a:.2f}',f'{w:.4f}'] for label,a,b,w in zip(['0 0','1 0','0 1','1 1'],old['strata_low'],old['strata_high'],old['test_weights'])],widths=[.7,1.5,1.5,1.5,1.78],small=10)
    r.p('四层加权结果为211.71146 s，同次未调整均值差为122.94426 s。差异来自组内比较和测试人群标准化；识别仍依赖事前结构及无遗漏混杂条件。',size=10)
    r.h('模型状态与结果使用',2)
    r.p('B1特征、平均作用与B2单体预测分别交付；默认B2未采用无稳定增量的历史分支。B3采用固定模型版本和明确的任务合同。尚未接入现场平台，物理可行值、模型期望和可承诺量分开，可承诺量保留为空。真实绿色价值和履约可靠性均未独立校准。',size=10)
    r.h('研究依据与结果索引',2)
    for s in [
      '[1] 103任务书下达稿，第5、6、12、13文件页；《课题一需求分析与研究框架》与《课题一技术路线与模型设计方案》，2026年10月11日版本。',
      '[2] B1因素与过程主链及补充实验，2026年10月26日；B2首轮分层比较，2026年10月26日；选择与动态补强，2026年10月27日。原始数据、冻结协议、模型与独立核验均保留。',
      '[3] B1历史信息增量、B2至B3共同域联调、B3组合及连续稳定性实验，2026年10月28日。证据目录分别为work/b1_b2_history_20261028、work/b2_b3_integration_20261028、work/b3_coordination_20261028、work/b1_b3_stability_20261028。',
      '[4] Tversky A, Kahneman D. Advances in prospect theory: Cumulative representation of uncertainty. Journal of Risk and Uncertainty, 1992, 5: 297–323. DOI: 10.1007/BF00122574。',
      '[5] 统一研究函数入口为b123_api.py；输出定义、支持条件及独立复核方式随接口说明保存。不同实验的误差、概率、服务与恢复指标不合并成总体准确率。']:
        r.p(s,size=9.5)
    r.finalize()
    sources=['outputs/课题一B1与B2算法阶段汇报_20261029.docx','outputs/课题一B1与B2算法阶段汇报_20261029.pdf','work/b1_b2_meeting_report_20261029/source_evidence.json','work/b1_b2_history_20261028/results.json','work/b1_b2_history_20261028/selection.json','work/b3_coordination_20261028/evaluation.json','work/b2_b3_integration_20261028/evaluation.json','work/b1_b3_stability_20261028/results.json','work/b1_b3_stability_20261028/runs.json','work/b1_b3_stability_20261028/independent_checks.json','work/b1_b3_stability_20261028/final_checks.json']
    # D119 uses case_metrics when no aggregate evaluation file exists.
    assert all((ROOT/p).exists() for p in sources)
    manifest={p:sha(ROOT/p) for p in sources}
    (BASE/'source_manifest.json').write_text(json.dumps(dict(as_of='2026-10-28',reference=str(REFERENCE),sources=manifest,output_docx=str(OUT),output_sha=sha(OUT),selected_trace_index=example['index'],retained_reference=True,expected_pages=11),ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(OUT));print('body paragraphs',len(r.d.paragraphs),'tables',len(r.d.tables))

if __name__=='__main__':main()
