"""Paired observed rates; no row-level independent confidence interval."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
W=Path(__file__).resolve().parent
d=json.loads((W/'study/test/assessment.json').read_text(encoding='utf-8'))
def row(s,p):return next(r for r in d['summaries'] if r['scenario']==s and r['path']==p)
metrics=[('无动作：算出正时长','null','raw_false_positive_duration_count','n_no_action'),
 ('弱响应：未算出正时长','weak','raw_positive_duration_miss_count','n_threshold_positive'),
 ('弱响应：证据不足','weak','calibrated_response_inconclusive_count','n_threshold_positive')]
font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')
with plt.rc_context({'font.family':['SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':11}):
    fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained');y=np.arange(3)
    for path,offset,color,label in [('old_cpop',-.18,'#9aa4ad','旧参考＋原CPOP'),('new_cpop',.18,'#1668ac','新参考＋原CPOP')]:
        values=[];counts=[]
        for _,s,num,den in metrics:
            r=row(s,path);values.append(r[num]/r[den]*100);counts.append(f"{r[num]}/{r[den]}")
        ax.barh(y+offset,values,height=.31,color=color,label=label)
        for yy,v,c in zip(y+offset,values,counts):ax.text(v+1,yy,f'{v:.1f}%（{c}）',va='center',fontsize=10)
    ax.set(yticks=y,yticklabels=[a[0] for a in metrics],xlim=(0,116),xlabel='各指标的观测比例（同一行内比较）',title='新参考对误检、弱响应漏检与证据不足的影响')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.legend(loc='lower right',fontsize=10)
    fig.text(.01,-.025,'8个新模拟块；强/弱/无动作配对。证据不足不等于确认无响应，未删除这些记录。',fontsize=9)
    path=W/'reliability_comparison.png'
    if path.exists():raise RuntimeError('preserve existing figure')
    fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig)
print('plot exported')
