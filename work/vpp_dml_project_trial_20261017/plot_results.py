"""Plot all 16 held-out resource-type means for the prespecified high contrast."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font.get_name()
plt.rcParams['axes.unicode_minus']=False
d=pd.read_csv(HERE/'runs/RUN01/metrics_by_group.csv')
d=d[(d.split=='test')&(d.contrast_price==1.6)&(d.group_kind=='type')]
names=pd.read_csv(ROOT/'data/驱动因素解耦模拟数据集_v2/01_entities.csv').drop_duplicates('resource_type_id')
order=names.resource_type_id.tolist()
labels=names.resource_type.tolist()
fig,ax=plt.subplots(figsize=(11.8,8.3))
for i,k in enumerate(order):
    if k in ['distributed_pv','battery_storage']:ax.axhspan(i-.45,i+.45,color='#eeeeee',zorder=0)
true=d[d.model=='B_ZERO'].set_index('group').loc[order,'true_mean_pp']
ax.scatter(true,range(len(order)),s=55,color='#111111',marker='D',label='模拟真值',zorder=4)
for method,color,marker,label in [('B_OLS','#26805c','s','同特征线性回归'),('DML_SERIES','#3577b7','o','DML线性基函数'),('DML_FOREST','#cf6b34','^','DML因果森林')]:
    values=d[d.model==method].set_index('group').loc[order,'estimated_mean_pp']
    ax.scatter(values,range(len(order)),s=34,color=color,marker=marker,label=label,zorder=3,alpha=.9)
ax.set_yticks(range(len(order)),labels,fontsize=10)
ax.invert_yaxis();ax.axvline(0,color='#888888',linewidth=.8)
ax.set_xlabel('任务完成率的平均增量（百分点）',fontsize=11)
ax.set_title('已有模拟数据接入DML：补贴从0.4升至1.6元/kWh',fontsize=14,pad=43)
ax.legend(loc='lower center',bbox_to_anchor=(.5,1.01),ncol=4,frameon=False,fontsize=9)
ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
for s in ['top','right']:ax.spines[s].set_visible(False)
fig.text(.03,.025,'测试：2个未参加训练的模拟聚合体，共1152个任务；每类72个。灰底为预设零效应对象。\n各点为模型对类型平均效应的估计，不是置信区间；不是实测资源能力。',fontsize=9,color='#444444')
fig.subplots_adjust(left=.20,right=.98,bottom=.13,top=.85)
fig.savefig(HERE/'heldout_type_effects.png',dpi=170)
fig.savefig(HERE/'heldout_type_effects.svg')
print(HERE/'heldout_type_effects.png')
