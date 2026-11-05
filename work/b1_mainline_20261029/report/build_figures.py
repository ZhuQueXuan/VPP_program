"""Scientific figures from saved, frozen result tables; never runs models."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/'figures'
OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.sans-serif':['SimSun','Microsoft YaHei'],'axes.unicode_minus':False,
 'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
colors={'baseline':'#315571','candidate':'#BB632B','average':'#287E76','simple':'#777777'}

def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight')
 fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight')
 plt.close(fig)

# The diagram explicitly separates energy output from process-model fitting.
fig,ax=plt.subplots(figsize=(9.1,3.1));ax.axis('off');ax.set_xlim(0,10);ax.set_ylim(0,3)
def box(x,y,w,h,text):
 ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=10,
         bbox=dict(boxstyle='square,pad=.55',facecolor='white',edgecolor='#536775',linewidth=.8))
def arrow(x1,y1,x2,y2,label=None):
 ax.annotate('',(x2,y2),(x1,y1),arrowprops=dict(arrowstyle='->',color='#536775',lw=1))
 if label:ax.text((x1+x2)/2,(y1+y2)/2+.12,label,ha='center',fontsize=9)
box(.0,1.9,2.1,.6,'历史及通知前信息\n共同参考预测')
box(3.1,1.9,2.2,.6,'区间平均功率差\nr = 参考预测 - P')
box(6.8,1.9,2.5,.6,'过程识别主比较\nCPOP / 任务模板 / 平均适配')
arrow(2.2,2.2,3,2.2);arrow(5.3,2.2,6.7,2.2)
box(6.8,.7,2.5,.6,'统一计量格上的曲线\n阈值与驻留特征')
arrow(8.05,1.85,8.05,1.4)
box(3.1,.7,2.2,.6,'原始差值积分 η\n过程方法共用')
arrow(4.2,1.85,4.2,1.4)
box(.0,.7,2.1,.6,'事前条件 X 与激励 D\n多档 AIPW / 回归对照')
arrow(3,.99,2.2,.99)
ax.text(1.05,.43,'输出：作用曲线、同时带与阈值候选',ha='center',fontsize=9)
ax.text(.1,.12,'过程与激励分别验证；未知参考已作有限过程联调，完整全链区间尚未验证。',fontsize=10)
save(fig,'method')

main=pd.read_csv(ROOT/'process/main/summary.csv')
native=pd.read_csv(ROOT/'process/supplement_native_default/summary.csv')
curves=pd.read_csv(ROOT/'causal/results/curves.csv')
fig,axes=plt.subplots(1,3,figsize=(9.1,2.8),sharey=False)
selection=[('CPOP_default_average_projection','CPOP 区间投影',colors['baseline'],native),
 ('CPOP_default_binned','CPOP 直接格预测', '#8DA3B4',native),
 ('F1_frozen_segment_adapter','原 F1',colors['simple'],main),
 ('Grid_average','通用平均适配',colors['average'],main),
 ('RIDE_template_average','任务模板',colors['candidate'],main)]
for ax,delta,label in zip(axes,[1/6,1.,15.],['10 秒','1 分钟','15 分钟']):
 vals=[]
 for name,lab,color,table in selection:
  row=table[(table.method==name)&np.isclose(table.delta_min,delta)].iloc[0]
  vals.append(float(row.request_rmse))
 ax.bar(np.arange(len(vals)),vals,color=[x[2] for x in selection],width=.68)
 ax.set_xticks(range(len(vals)),[x[1] for x in selection],rotation=48,ha='right',fontsize=8)
 ax.set_title(label);ax.set_ylabel('任务窗曲线 RMSE 均值 / kW');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.tight_layout();save(fig,'process_comparison')

fig,axes=plt.subplots(1,2,figsize=(9.1,2.8),sharey=True)
for ax,scenario,title in zip(axes,['observational_positive','observational_nonmonotone'],['非随机正作用','非随机非单调']):
 g=curves[(curves.rep==0)&(curves.scenario==scenario)]
 a=g[g.method=='AIPW_shared'].sort_values('level');p=g[g.method=='Plugin_shared'].sort_values('level')
 u=g[g.method=='Unadjusted_arm_mean'].sort_values('level')
 ax.plot(a.level,a.truth,color='black',ls='--',lw=1.3,label='模拟真作用')
 ax.fill_between(a.level.to_numpy(),a.lower.to_numpy(),a.upper.to_numpy(),color=colors['baseline'],alpha=.15,label='AIPW 95%同时带')
 ax.plot(a.level,a.estimate,'o-',color=colors['baseline'],ms=3,label='标准 AIPW')
 ax.plot(p.level,p.estimate,'s-',color=colors['candidate'],ms=3,label='共享模型回归')
 ax.plot(u.level,u.estimate,':',color='#777777',label='未调整均值')
 ax.axhline(.1,color='#AAAAAA',lw=.8);ax.set_title(title+'  第1个预定种子')
 ax.set_xlabel('归一化激励档位');ax.set_ylabel('相对零档的净交付比例变化');ax.grid(alpha=.15)
axes[1].legend(fontsize=8,loc='best');fig.tight_layout();save(fig,'dose_curves')

# A fixed prespecified first seed shows both a compatible and a failed template.
events=json.loads((ROOT/'process/main/events.json').read_text(encoding='utf-8'))
z=np.load(ROOT/'process/main/all_curves.npz')
zn=np.load(ROOT/'process/supplement_native_default/curves.npz')
fig,axes=plt.subplots(1,2,figsize=(9.1,2.7),sharey=True)
for ax,mech,title in zip(axes,['slow','multiplateau'],['缓慢爬升','多个不规则平台']):
 event=next(e for e in events if e['rep']==0 and e['mechanism']==mech and e['delta_min']==1 and e['sigma_kw']==.15)
 i=event['event_id'];x=np.arange(-15,45)+.5
 ax.plot(x,z[f'{i}_y'],color='#B9B9B9',lw=.6,label='带噪平均功率差')
 ax.plot(x,z[f'{i}_truth'],color='black',ls='--',lw=1.2,label='无噪平均功率差')
 ax.plot(x,zn[f'{i}_CPOP_default_average_projection'],color=colors['baseline'],lw=1.2,label='默认 CPOP')
 ax.plot(x,z[f'{i}_RIDE_template_average'],color=colors['candidate'],lw=1.2,label='任务模板')
 ax.axvspan(0,30,color='#CCCCCC',alpha=.1);ax.set_title(title+'  同一预定种子')
 ax.set_xlabel('相对请求开始的时间 / min');ax.set_ylabel('减载功率 / kW');ax.grid(alpha=.15)
axes[1].legend(fontsize=8);fig.tight_layout();save(fig,'process_examples')
print('Saved four scientific figures from existing results only.')
