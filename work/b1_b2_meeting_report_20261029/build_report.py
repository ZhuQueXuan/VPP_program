"""Meeting report from existing frozen evidence. No new scientific experiment."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import fitz

ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent;FIG=BASE/'figures';FIG.mkdir(exist_ok=True)
OUT=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx'
pdfmetrics.registerFont(TTFont('ZH',r'C:\Windows\Fonts\simhei.ttf'))
def rd(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def savefig(name,draw,w=650,h=205):
    pdf=FIG/(name+'.pdf');c=canvas.Canvas(str(pdf),pagesize=(w,h));c.setFillColorRGB(1,1,1);c.rect(0,0,w,h,fill=1,stroke=0);draw(c,w,h);c.save()
    d=fitz.open(pdf);d[0].get_pixmap(matrix=fitz.Matrix(2.8,2.8),alpha=False).save(FIG/(name+'.png'));d.close()
    return FIG/(name+'.png')
def txt(c,x,y,s,size=11,color='#17232e'):
    from reportlab.lib.colors import HexColor
    c.setFillColor(HexColor(color));c.setFont('ZH',size);c.drawString(x,y,s)
def arrow(c,a,b,dashed=False):
    from reportlab.lib.colors import HexColor
    c.setStrokeColor(HexColor('#475d70'));c.setLineWidth(1.1);c.setDash(4,3) if dashed else c.setDash()
    c.line(*a,*b);c.setDash();ang=math.atan2(b[1]-a[1],b[0]-a[0]);L=6
    for delta in [-.45,.45]:c.line(b[0],b[1],b[0]-L*math.cos(ang+delta),b[1]-L*math.sin(ang+delta))
def box(c,x,y,w,h,lines):
    c.setStrokeColorRGB(.45,.52,.59);c.setLineWidth(.7);c.rect(x,y,w,h,stroke=1,fill=0)
    for i,s in enumerate(lines):txt(c,x+10,y+h-20-i*17,s,10.5)

def evidence():
    raw=ROOT/'data/驱动因素解耦模拟数据集_B1_ev_factor_chain_v1_20261026/observations.npz'
    z=np.load(raw);r,s,i=0,1,2;curve=z['power_obs_kw'][r,s,i];ref=z['reference_kw'][r,i];X=int(z['X'][r,i]);W=int(z['W'][r,i]);T=int(z['declared_deadline_s'][r,i]);spl=z['user_split'][r]
    h=np.load(ROOT/'work/b1_ev_factor_chain_20261026/hidden_evaluator.npz');delay=int(h['delay_s'][r,i]);duration=float(h['duration_s'][r,s,i]);feat=np.load(ROOT/'work/b1_ev_factor_chain_20261026/observed_features.npz')
    models=rd('work/b1_ev_factor_chain_20261026/models.json');table=np.array(models[0][1][1]['table']);code=z['X'][r]+2*z['W'][r];weights=np.bincount(code[spl==2],minlength=4)/400
    estimate=float(weights@(table[1,:,0]-table[0,:,0]));unadj=float(np.array(models[0][1][0]['table'])[1,0,0]-np.array(models[0][1][0]['table'])[0,0,0])
    assert X==0 and W==0 and T==2780 and delay==50 and duration==980 and abs(estimate-211.71146)<1e-5
    np.savez_compressed(BASE/'b1_selected_curve.npz',power=curve,reference=ref,time_s=np.arange(360)*10)
    info=dict(rep=0,scenario='observed_positive',user_index=2,X=X,W=W,deadline_s=T,hidden_delay_s=delay,hidden_duration_s=duration,
      observed_cumulative_s=float(feat['cumulative_s'][r,s,i]),observed_net_kwh=float(feat['net_kwh'][r,s,i]),observed_debt_kwh=float(feat['debt_end_kwh'][r,s,i]),
      strata_low=table[0,:,0].tolist(),strata_high=table[1,:,0].tolist(),test_weights=weights.tolist(),one_rep_adjusted_effect_s=estimate,one_rep_unadjusted_effect_s=unadj)
    sources=['work/b1_ev_factor_chain_20261026/protocol.json','work/b1_ev_factor_chain_20261026/evaluation.json','work/b1_fullcycle_features_20261026/README.md','work/b1_history_prediction_20261026/README.md','work/b1_crossing_uncertainty_20261026/README.md','work/b2_single_ev_baseline_20261026/evaluation.json','work/b2_completion_20261027/choice/evaluation.json','work/b2_completion_20261027/dynamic/evaluation.json','work/b2_completion_20261027/example_output.json','work/b2_completion_20261027/stage_gate.json']
    (BASE/'source_evidence.json').write_text(json.dumps(dict(as_of='2026-10-28',meeting='2026-10-29',b1_example=info,sources={p:sha(ROOT/p) for p in sources}),ensure_ascii=False,indent=2),encoding='utf-8')
    return info

def figures():
    def overview(c,w,h):
        txt(c,16,h-20,'B1解释行为差异，B2估计指定任务的交付',14)
        box(c,16,86,178,64,['B1 事前因素与历史曲线','余量  紧迫度  激励','参考功率与观测功率'])
        box(c,235,86,178,64,['结构假设与合法调整','提取累计与连续时长','比较激励的平均作用'])
        box(c,454,86,178,64,['B1输出','特征  平均效应  适用条件','供后续检验的候选信息'])
        arrow(c,(194,118),(235,118));arrow(c,(413,118),(454,118))
        txt(c,18,49,'B2：声明状态与任务 → 物理与许可 → 用户选择 → 条件执行 → 预计交付与任务概率',11)
        txt(c,18,22,'B1本次事后结果不进入B2同一事件的调用前输入；已有许可和实际接受仍是控制前提。',9.5)
    savefig('overview',overview,h=192)
    data=np.load(BASE/'b1_selected_curve.npz');t=data['time_s'];p=data['power'];ref=data['reference']
    def curve(c,w,h):
        x0,x1,y0,y1=48,w-18,39,h-24
        def xy(tt,pp):return x0+(x1-x0)*tt/3600,y0+(y1-y0)*pp/5
        for val in [0,1.5,3,4.5]:
            a=xy(0,val);c.setStrokeColorRGB(.86,.88,.90);c.line(a[0],a[1],x1,a[1]);txt(c,9,a[1]-3,str(val),9)
        for val in [0,600,1200,1800,2400,3000,3600]:txt(c,xy(val,0)[0]-10,20,str(val),9)
        for arr,color,width in [(ref,(.38,.44,.49),1.1),(p,(.13,.40,.61),.85)]:
            c.setStrokeColorRGB(*color);c.setLineWidth(width);path=c.beginPath();path.moveTo(*xy(t[0],arr[0]))
            for tt,pp in zip(t[1:],arr[1:]):path.lineTo(*xy(tt,pp))
            c.drawPath(path)
        c.setStrokeColorRGB(.5,.5,.5);c.setLineWidth(.7);c.rect(x0,y0,x1-x0,y1-y0,stroke=1,fill=0)
        txt(c,7,h-12,'kW',9);txt(c,w-88,4,'时间  s',9)
        txt(c,90,h-17,'灰线  声明参考',10,'#626e78');txt(c,220,h-17,'蓝线  已保存的带噪模拟功率',10,'#226799')
        txt(c,135,87,'减载 980 s',10);txt(c,363,151,'回补 980 s',10);txt(c,486,70,'T = 2780 s',10)
    savefig('b1_curve',curve,h=205)
    def graph(c,w,h):
        pos={'X':(100,115),'W':(100,42),'D':(280,112),'A':(435,112),'S':(570,42)}
        labels={'X':'余量 X','W':'紧迫度 W','D':'激励 D','A':'参加 A','S':'过程判据 S'}
        for node,(x,y) in pos.items():box(c,x-43,y-17,86,38,[labels[node]])
        for a,b,d in [('X','D',True),('W','D',True),('W','A',False),('D','A',False),('A','S',False),('X','S',False),('W','S',False)]:
            xa,ya=pos[a];xb,yb=pos[b];arrow(c,(xa+44,ya),(xb-44,yb),d)
        txt(c,25,4,'虚线为非随机分配路径；图为冻结假设。S = I(累计时长 ≥ 600 s)，效应主结果为累计时长 R。',9)
    savefig('b1_graph',graph,h=159)
    example=rd('work/b2_completion_20261027/example_output.json');sc=example['output']['dynamic_scenarios'];b=example['input']['b'];q=example['input']['q']
    def states(c,w,h):
        names=['立即全程','延迟2分钟','延迟5分钟','15分钟退出','全程70%幅度']
        x0,x1=122,w-25;rowh=33
        for i,v in enumerate(sc):
            y=h-34-i*rowh;arr=(b-np.array(v['event_charging_kw']))/q
            txt(c,6,y+8,names[i],10);txt(c,6,y-4,'条件概率 '+f"{v['conditional_probability']:.3f}",8.5,'#58646d')
            c.setStrokeColorRGB(.83,.86,.88);c.line(x0,y,x1,y)
            path=c.beginPath();path.moveTo(x0,y+arr[0]*20)
            for k,a in enumerate(arr):
                xx=x0+(x1-x0)*k/30;nx=x0+(x1-x0)*(k+1)/30;path.lineTo(xx,y+a*20);path.lineTo(nx,y+a*20)
            c.setStrokeColorRGB(.13,.40,.61);c.setLineWidth(1.5);c.drawPath(path)
            txt(c,x1+1,y+5,'1' if i<4 else '0.7',8)
        for a in [0,5,10,15,20,25,30]:txt(c,x0+(x1-x0)*a/30-5,8,str(a),8.5)
        txt(c,w-100,0,'时间  min',9)
    savefig('b2_states',states,h=205)

def E(tag,text=None):
    e=OxmlElement('m:'+tag)
    if text is not None:e.text=text
    return e
def mr(t):
    r=E('r');r.append(E('t',t));return r
def sub(a,b):
    e=E('sSub');x=E('e');x.append(mr(a));y=E('sub');y.append(mr(b));e.extend([x,y]);return e
def frac(a,b):
    e=E('f');n=E('num');d=E('den')
    for z in (a if isinstance(a,list) else [mr(a)]):n.append(z)
    for z in (b if isinstance(b,list) else [mr(b)]):d.append(z)
    e.extend([n,d]);return e
def summation(index):
    e=E('nary');pr=E('naryPr');ch=E('chr');ch.set(qn('m:val'),'∑');pr.append(ch);hide=E('supHide');hide.set(qn('m:val'),'1');pr.append(hide);e.append(pr);su=E('sub');su.append(mr(index));e.append(su);e.append(E('sup'));e.append(E('e'));return e

class Report:
    def __init__(self):
        self.d=Document();sec=self.d.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11);sec.top_margin=Inches(.64);sec.bottom_margin=Inches(.64);sec.left_margin=Inches(.76);sec.right_margin=Inches(.76)
        for n in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
            st=self.d.styles[n];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0);st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
        for st in self.d.styles:
            for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
        norm=self.d.styles['Normal'];norm.font.size=Pt(11);norm.paragraph_format.line_spacing=1.16;norm.paragraph_format.space_after=Pt(6)
        for n,size in [('Title',21),('Heading 1',16),('Heading 2',12)]:
            st=self.d.styles[n];st.font.size=Pt(size);st.font.bold=n!='Title';st._element.rPr.rFonts.set(qn('w:eastAsia'),'黑体');st.paragraph_format.space_before=Pt(12 if n=='Heading 2' else (9 if n!='Title' else 0));st.paragraph_format.space_after=Pt(8)
        self.d.styles['Caption'].font.size=Pt(9);self.d.styles['Caption'].paragraph_format.space_after=Pt(6)
        sec.footer.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
        p=sec.footer.paragraphs[0];rr=p.add_run();rr.font.size=Pt(9);fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
        self.d.core_properties.author='刘文轩';self.d.core_properties.title='课题一B1与B2算法阶段汇报';self.d.core_properties.subject='2026年10月29日会议汇报';self.d.core_properties.keywords='B1;B2;单EV;模拟研究'
    def p(self,s,bold=False,size=None):
        p=self.d.add_paragraph();r=p.add_run(s);r.bold=bold
        if size:r.font.size=Pt(size)
        return p
    def h(self,s,level=1):return self.d.add_paragraph(s,'Heading '+str(level))
    def image(self,name,caption,width=6.82):
        p=self.d.add_paragraph();p.paragraph_format.space_after=Pt(3);p.add_run().add_picture(str(FIG/(name+'.png')),width=Inches(width));self.d.add_paragraph(caption,'Caption')
    def table(self,head,rows,widths=None,small=10,aligns=None):
        t=self.d.add_table(rows=1,cols=len(head));t.autofit=False
        widths=widths or [6.98/len(head)]*len(head)
        for j,(s,w) in enumerate(zip(head,widths)):t.columns[j].width=Inches(w);t.rows[0].cells[j].width=Inches(w);t.rows[0].cells[j].text=s
        for row in rows:
            for j,s in enumerate(row):t.add_row() if False else None
            cells=t.add_row().cells
            for j,s in enumerate(row):cells[j].width=Inches(widths[j]);cells[j].text=str(s)
        for i,row in enumerate(t.rows):
            pr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');pr.append(cant)
            if i==0:pr.append(OxmlElement('w:tblHeader'))
            for j,cell in enumerate(row.cells):
                tcpr=cell._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
                for edge in ['top','left','bottom','right']:
                    el=OxmlElement('w:'+edge);el.set(qn('w:w'),'90');el.set(qn('w:type'),'dxa');mar.append(el)
                tcpr.append(mar)
                if i==0:
                    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'ECEFF2');tcpr.append(sh)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(1);p.paragraph_format.line_spacing=1.08
                    p.alignment=WD_ALIGN_PARAGRAPH.LEFT if (aligns and aligns[j]=='left') or j==0 else WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:r.font.size=Pt(small);r.bold=i==0
        self.d.add_paragraph().paragraph_format.space_after=Pt(1)
        return t
    def eq(self,elements):
        p=self.d.add_paragraph();p.paragraph_format.space_after=Pt(5);p.paragraph_format.space_before=Pt(3)
        para=E('oMathPara');m=E('oMath')
        for e in elements:m.append(mr(e) if isinstance(e,str) else e)
        para.append(m);p._p.append(para)
    def page(self):self.d.add_page_break()
    def save(self):
        from fix_heading_fonts import apply_fonts
        apply_fonts(self.d)
        self.d.save(OUT)

def main():
    info=evidence();figures();r=Report();ex=rd('work/b2_completion_20261027/example_output.json');eo=ex['output'];prob=[v['conditional_probability'] for v in eo['dynamic_scenarios']]
    # 1. Framing and the actual achieved state.
    r.d.add_paragraph('课题一B1与B2算法阶段汇报','Title')
    r.p('汇报人  刘文轩    会议日期  2026年10月29日',size=10)
    r.p('研究内容截至2026年10月28日，实验结果截至2026年10月27日。',size=9)
    r.h('本次汇报的两个问题')
    r.p('B1研究调节行为为什么不同：在用户期限余量、需求紧迫度等条件不同的情况下，怎样提取响应过程，并估计激励对响应的平均作用。B2研究一次任务预计能交付多少：把物理能力、已有许可、用户选择和接受后的执行分开，再计算预计交付和任务满足概率。')
    r.p('目前，B1已完成同一EV机制的因素与过程特征贯通，B2已完成单EV指定任务族的选择、基本动态响应及融合原型。两项工作均有透明基线、留出评价和独立复算。当前证据来自明确假设的模拟，尚不能给出真实资源容量承诺。')
    r.image('overview','图1 两项算法的职责及信息边界。B1解释平均作用，B2预测指定任务的交付。')
    r.table(['算法','主要输入','目前输出'],[
      ['B1 行为影响因素分析','事前余量与紧迫度、激励、参考与观测功率','过程特征、平均效应、辅助结构与限制'],
      ['B2 单体容量与响应评估','声明需求与期限、任务、许可、选择条件、执行条件','物理可行性、预计交付、任务概率、条件轨迹']],widths=[1.52,2.7,2.76],aligns=['left','left','left'])
    r.p('与正式任务的对应：B1落实103任务书中的行为影响因素分析和关键调节时序特征提取；B2落实融合行为经济学、绿色因素的单体容量与响应能力分析。多智能体组合协同归入B3，本报告不把它计为已完成内容。',size=10)
    # 2. A real stored B1 sample.
    r.page();r.h('一 B1如何从功率曲线得到过程特征')
    r.p('先选单向充电EV作为代表机制。模拟参考功率为3 kW，上限4.5 kW，请求窗为600—1800 s，目标减载1.5 kW；采样间隔10 s。需求与离站期限在调用前声明，执行后按实际少充电量回补。')
    r.image('b1_curve','图2 已保存测试样例的参考与带噪模拟功率。灰线为参考，蓝线为观测功率；单位为kW和s。')
    r.p('特征提取器只读取参考与观测曲线。请求窗内，两者之差达到0.15 kW的时间累计为R；最长连续时长另外计算，并要求至少连续3格。0.15 kW和30 s驻留均是本实验的数值判据。')
    r.eq(['R = Δt ',summation('k∈请求窗'),' I(',sub('P','ref,k'),' − ',sub('P','k'),' ≥ 0.15 kW),     Δt = 10 s'])
    r.h('一条可以逐步解释的样例',2)
    r.p('该测试事件的事前期限为2780 s。模拟隐藏延迟为50 s，允许减载时长取min(1200−50，2780−1800)=980 s：前一项受请求窗限制，后一项受离站前回补余量限制。于是650—1630 s以1.5 kW充电，1800—2780 s以4.5 kW回补。')
    r.eq(['少充电量 = 1.5 kW × ',frac('980 s','3600 s/h'),' = 0.40833 kWh'])
    r.p(f"从带噪曲线实际提取的累计时长和最长连续时长均为980 s，净交付电量为{info['observed_net_kwh']:.6f} kWh。它与潜在少充电量略有差别，来自计量噪声。截止观测积分残差约{info['observed_debt_kwh']:.6f} kWh，不能据此判定真实恢复失败。",size=10)
    r.p('样例中的隐藏延迟和潜在动作时长只用于解释生成机制，没有传给特征提取器。累计时长可以包含多个片段，不能直接当连续服务持续时间。',size=10)
    # 3. Causal assumptions, estimated effects.
    r.page();r.h('二 B1如何区分激励作用与原有差异')
    r.p('高激励可能更常分给某些用户。若这些用户原本更紧迫或余量不同，高低激励组的时长差就会混入事前条件的影响。我们先声明结构假设，再确定总效应需要调整的事前因素。')
    r.image('b1_graph','图3 分析使用的简化结构假设。X与W是事前因素，A是激励后的参加结果。')
    r.p('随机分配场景直接比较两臂均值；非随机场景按X、W分层，用训练用户估计各层均值，再按测试用户的事前构成加权。A处在激励后的参与路径上，不能加入本次总效应调整。')
    r.eq(['τ̂ = ',summation('x,w'),sub('p̂','test'),'(x,w) [',sub('μ̂','train'),'(1,x,w) − ',sub('μ̂','train'),'(0,x,w)]'])
    r.table(['场景','参考真效应\ns','G0均值\ns','G1均值\ns','G0误差\nRMSE s','G1误差\nRMSE s'],[
      ['随机正作用','200.58','209.10','209.10','25.05','25.05'],['非随机正作用','200.58','120.45','211.24','84.41','27.59'],
      ['非随机零作用','0','−73.50','12.73','77.97','30.95'],['非随机负作用','−162.57','−221.01','−147.94','63.96','31.00']],widths=[1.38,1.12,1.08,1.08,1.16,1.16],small=9.3)
    r.p('表1 测试总体的20次重复结果。G0为未调整比较，G1为合法事前调整；均值与RMSE分别报告，参考真效应由模拟机制计算。',size=9)
    r.p('非随机三场景中，合法调整降低了平均效应估计误差。零作用仍估为12.73 s，说明残余误差存在。故意加入参加结果A的错误对照，会把非零总作用压到接近零，验证了本生成器中“控制中介变量”的风险。')
    r.p('数据为20次重复，每次2000用户各1事件、4个配对机制，共40000基础事件和160000变体；按1200/400/400用户分训练、验证、测试。因果解释依赖声明结构和无遗漏混杂假设。',size=10)
    # 4. Additional evidence and choices.
    r.page();r.h('三 B1补充实验支持哪些方法取舍')
    r.p('围绕主链，还比较了特征抗噪、非线性激励、交点不确定性和历史表示。这些实验分别回答一个问题，不把局部改善合并成“所有方法都有效”。')
    r.table(['研究问题','主要证据','目前判断'],[
      ['抗噪提取','高噪声10 s采样：无动作误检8/25降至0/25；恢复时点MAE由38.16降至1.68 s','常均值变点平滑有局部价值'],
      ['缓慢爬升','低噪声10 s采样：90%幅度达标时点MAE由13.6增至27.2 s','不能统一替换原规则'],
      ['激励非线性','平滑机制中，直线与固定分段曲线RMSE为1.272与0.774个百分点；零作用时为0.585与0.862','不同机制各有优劣，不全面升级分段法'],
      ['交点不确定性','平台后上升场景，100/100候选集合含真位置，但0/100唯一定位','多候选改善表达，不等于精确定位'],
      ['历史表示','稳定场景：当前条件、加历史统计、再加PCA的测试RMSE为24.131、24.248、24.911个百分点','本配置无稳定增量，保留简单基线']],widths=[1.18,3.8,2.0],small=10,aligns=['left','left','left'])
    r.p('表2 各实验的单位和参照不同，不作跨指标总分。抗噪实验的基础重复数为25，交点实验为100；配对观测变体不作为独立重复。',size=9)
    r.h('结构学习和复杂表示仍有哪些限制',2)
    r.p('五节点二元图使用给定时间顺序的离散BIC父集筛选，箭头方向依赖先验。非随机正、零、负场景完整图恢复分别为9/20、9/20、8/20，仍会漏掉混杂路径。因此，学习图只作辅助，不能因为未筛出某条边就取消必要调整。')
    r.p('历史试验只比较“三条完整历史＋固定二次Ridge＋线性PCA”，训练误差下降、测试误差上升，且模型展开容量不同。它不能否定历史信息或深度表示本身。早期正交AIPW候选也未形成稳定优势，已保留为对照。')
    r.p('B1已把结构假设、观测过程特征和平均效应估计接起来，范围目前限于同一EV机制。正式深度表示、跨资源机制及真实因果证据尚未完成；现阶段不再为追求小图全对或小幅分数改善反复调参。')
    # 5. B2 physical/behavioral connection and example.
    r.page();r.h('四 B2怎样把能力与意愿连接起来')
    r.p('B2针对单EV的30分钟减载任务，幅度为1.5或3 kW。调用前给出AC电量需求、离站期限、参考功率、许可、收益风险和技术执行条件。连续调功、上限7.2 kW及需求E=bT均为明确假设，T以小时计。')
    r.eq([sub('q','max'),' = min [ b, ',frac('(7.2 − b)(T − 0.5)','0.5'),' ]'])
    r.p('物理不可行或无许可则不发送，A=−1表示未观察选择。模型用接受概率pA、条件状态概率πs和整窗平均执行比例f̄s计算输出；I可发送是0/1标记。真正动作仍需实际接受。')
    r.eq(['E[Q] = ',sub('I','可发送'),' · q · ',sub('p','A'),' · ',summation('s'),sub('π','s'),sub('f̄','s')])
    r.eq(['P(任务满足) = ',sub('I','可发送'),' · ',sub('p','A'),' · ',summation('s∈满足任务的状态'),sub('π','s')])
    r.h('一条实际查询怎样得到预计交付',2)
    r.p('已保存样例：b=3.71999 kW，T=1.5 h，E=5.57999 kWh，已取得控制许可。减载1.5 kW、30 min任务可行，物理最大减载为3.71999 kW，预计接受概率为0.5004095。')
    names=['立即全程','延迟2分钟','延迟5分钟','15分钟退出','全程70%幅度'];fractions=['1','28/30','25/30','1/2','0.7']
    r.table(['接受后的执行情景','条件概率','整窗平均执行比例'],[[a,f'{p:.4f}',b] for a,p,b in zip(names,prob,fractions)],widths=[2.8,1.6,2.58],small=10)
    r.p('接受后平均比例为0.8602049，故预计交付1.5×0.5004095×0.8602049=0.6456821 kW，电量0.3228410 kWh；由预计减载电量计算，预计后窗功率4.04283 kW。',size=10)
    r.p('当前可承诺量为空。物理最大值、任务幅度和预计均值分别返回，真实可靠性尚未独立校准。',size=10)
    # 6. Baseline and prospect comparison.
    r.page();r.h('五 B2分层预测和行为模型的实验结果')
    r.h('先检验分层是否有用',2)
    r.table(['首轮模型','实际交付\nRMSE kW','条件均值\nRMSE kW','严格全30分钟\n任务Brier'],[
      ['M0 已许可物理上界','1.056','0.852','0.304'],['M1 加用户接受概率','0.619','0.137','0.115'],['M2 再加条件执行','0.605','0.040','0.096']],widths=[2.68,1.35,1.35,1.6],small=10)
    r.p('表3 首轮20次重复的全部测试事件；每次600用户8事件，360/120/120用户隔离。包含不可发送、拒绝和执行失败，另评价可发送子集。RMSE与Brier均越低越好，Brier是概率与实际0/1结果之差的均方。',size=9)
    r.p('区分接受与执行后，模拟交付估计有改善。0.040 kW衡量对隐藏条件均值的估计误差，对实际事件交付的测试RMSE仍为0.605 kW。该轮生成机制与普通logit匹配，不能直接推广为真实用户预测效果。')
    r.h('再检验参考点和风险表达的增量',2)
    r.p('比较普通效用、固定非线性logit和受限前景价值后接logit，分别包含或不包含绿色项。前景候选以事前参考点区分收益与损失，使用累计决策权重评价两种收益结果，并计算“不参加”的参考价值；价值曲率固定为1，只估少量共享参数。')
    r.eq(['v(x) = x  (x ≥ 0),      v(x) = λx  (x < 0)'])
    r.p('普通效用绿色零作用、前景匹配绿色非零、异质偏好且参考点误测三个场景共同评价。两轮补强各为20新重复、600用户8事件、3个配对机制；每轮均为288000变体、96000基础事件，配对机制不当独立样本。')
    r.table(['比较口径','测试结果','解释'],[
      ['预定主比较\n验证所选方案对普通效用','接受Brier差 +0.000165\n95%区间 [−0.000743, +0.001073]','没有稳定整体优势'],
      ['前景匹配场景的辅助比较','普通→前景\n0.201520→0.199841','匹配改善不能推成通用优势'],
      ['绿色系数的模拟核查','零作用均值 −0.0175\n非零匹配均值0.6099，生成值0.6','不代表真实绿色价值']],widths=[2.1,3.02,1.86],small=9.7,aligns=['left','center','left'])
    r.p('保留普通模型和受限前景候选，不以复杂模型必须胜出为目标。用户绿色偏好与假设方案属性分列，本轮没有实际减碳量或真实绿色支付意愿证据。',size=10)
    # 7. Dynamic results and scope.
    r.page();r.h('六 B2补齐基本动态响应与恢复过程')
    r.p('原整窗比例难以区分晚开始与提前结束。本轮在1分钟尺度预设五种执行模板，用多项logit估计条件状态概率，形成情景轨迹和期望；每种轨迹按实际少充电量回补，检验功率和离站需求。')
    r.image('b2_states','图4 五种声明执行模板。纵向幅度按任务归一化；来自上一页查询的条件状态概率，尚非任意连续时序学习。')
    r.p('新服务判据要求2分钟内达到90%任务幅度、连续至少28分钟、末格仍达标，并在离站前满足能量需求。前两种状态满足，因此样例任务概率为0.5004095×(0.3492033+0.2772968)=31.35%。这里的幅度90%不是103的模型精度90%。')
    r.table(['结果','已保存数值','应如何理解'],[
      ['全过程轨迹RMSE','标量0.442535 kW\n固定动态候选0.439388 kW\n按验证选择后0.440280 kW','增量小，主要补齐时间过程'],
      ['预定主任务Brier比较','差 −0.00006266\n95%区间 [−0.00010030, −0.00002502]','本机制内小幅改善'],
      ['实际事件时序误差','持续时长MAE 7.62 min\n达到时点条件MAE 1.59 min','仍不能精确预知单次行为']],widths=[1.66,3.34,1.98],small=9.6,aligns=['left','center','left'])
    r.p('14/20次验证选择采用动态，6/20回退标量；选择在测试计分前固定。动态轮的财务选择机制固定为前景匹配，不能算前景跨机制有效的第二次证据。严格全30分钟任务另报，不与新服务混算。',size=10)
    r.p('阶段判断：B2已补齐指定任务族的主要分层、基本动态响应和融合输出，可转入B3组合问题准备。真实偏好与绿色属性、实际控制可靠性、跨机制及复杂时序仍保留缺口；正式90%验收尚未通过。',bold=True,size=10.5)
    # 8. Calculation backup, speaker preparation and evidence map.
    r.page();r.h('附录 会议追问时的计算与证据')
    r.h('B1分层调整的单次计算样例',2)
    r.p('取第1次重复的非随机正作用场景。训练集按X、W分为四层，各层先算高低激励均值差，再用400个测试用户的事前构成加权。此表是一次重复，和正文20次平均结果分开。',size=10)
    lows=info['strata_low'];highs=info['strata_high'];weights=info['test_weights']
    r.table(['X W','低激励均值 s','高激励均值 s','层内差 s','测试权重'],[[a,f'{lo:.2f}',f'{hi:.2f}',f'{hi-lo:.2f}',f'{wt:.4f}'] for a,lo,hi,wt in zip(['0 0','1 0','0 1','1 1'],lows,highs,weights)],widths=[.7,1.5,1.5,1.5,1.3],small=10)
    r.p(f"四层加权结果为{info['one_rep_adjusted_effect_s']:.5f} s；同次直接两臂均值差为{info['one_rep_unadjusted_effect_s']:.5f} s。差异来自组内比较和测试人群标准化，不是把总体均值简单乘一个修正系数。",size=10)
    r.h('会上需要讲清的四个判断',2)
    for s in [
      '为什么先用模拟：便于隔离已知作用、零作用和混杂，并检查物理约束与计算。它能检验方法在声明机制下的表现，真实结论还需同对象事前需求、许可、指令和计量记录。',
      '为什么没有一直换复杂模型：合法调整和分层融合已有明确用途；图筛选、PCA、前景等候选的失败与适用范围已记录，继续追小幅分数不足以支持通用升级。',
      '现在能交付什么：B1特征提取及平均效应研究函数，B2指定任务的分层查询、条件轨迹和概率；已有物理、积分、预测和指标的独立复算，尚未接入现场平台。',
      '下一步做什么：进入B3，先定义小型源荷储组合的共同任务、AC计量边界、完整恢复窗和共享约束，再建立同信息集中式参照与主体协调过程；不把不同公开设备拼成真实同站。']:
        r.p(s,size=10)
    r.h('依据与结果入口',2)
    refs=[
      '[1] 103任务书下达稿，第5、6、12、13页；现用需求框架与技术路线，两份均为2026-10-11版本。',
      '[2] B1主链：work/b1_ev_factor_chain_20261026；辅助：b1_fullcycle_features、b1_multidose、b1_crossing_uncertainty、b1_history_prediction对应20261026目录。',
      '[3] B2首轮：work/b2_single_ev_baseline_20261026；补强：work/b2_completion_20261027。各目录README、protocol、evaluation及独立核验收据可复查。',
      '[4] Tversky A, Kahneman D. Advances in prospect theory: Cumulative representation of uncertainty. Journal of Risk and Uncertainty, 1992, 5: 297–323. DOI: 10.1007/BF00122574。']
    for s in refs:r.p(s,size=9)
    r.p('本报告只整理既有研究与证据，未新增实验或改变现用模型。',size=9)
    r.save();print(str(OUT));print('report built; word count',sum(len(p.text) for p in r.d.paragraphs))
if __name__=='__main__':main()
