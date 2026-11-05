"""First common false event in original panel order, not maximum-error selection."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import csv,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
W=Path(__file__).resolve().parent;R=W.parents[1];F=R/'work/b1_finish_ev_20261030/final_chain'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
rows=list(csv.DictReader((W/'detection/event_join.csv').open(encoding='utf-8-sig')))
row=next(a for a in rows if a['no_action']=='1' and a['common_revised_cpop_detection']=='1')
seed=int(row['seed']);scenario=row['scenario'];tid=row['task_id']
fact=next(a for a in read(R/f'data/B1_finish_chain_v1_20261030/{seed}_{scenario}_facts.json') if a['task']['task_id']==tid)
truth=next(a for a in read(F/f'evaluator/{seed}_{scenario}_truth.json') if a['task_id']==tid)
native=pd.read_csv(R/row['native_input_relative_path']);n=native[native.case_id==int(row['native_case_id'])]
raw=n.y.to_numpy();s=np.asarray(truth['relative_starts_min']);t=s+.5;power=np.asarray(fact['power_kw']);reference=power+raw
fits={m:next(a for a in read(F/f'events/{seed}_{scenario}_{m}.json') if a['task']['task_id']==tid)['process'] for m in ('ride_revised','cpop')}
font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')
with plt.rc_context({'font.family':['SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10}):
    fig,axes=plt.subplots(2,1,figsize=(9.4,6.4),sharex=True,layout='constrained')
    ax=axes[0]
    ax.plot(t,reference,color='#c77c27',lw=2,label='预测的未调节参考功率')
    ax.plot(t,truth['true_reference_kw'],color='#27804a',lw=2,label='模拟真实未调节功率')
    ax.plot(t,power,color='#444444',lw=1.2,alpha=.7,label='实测功率（含噪声）')
    ax.set(ylabel='功率（kW）',title='首个共同误检例：实际没有响应，预测参考持续偏高')
    ax.legend(loc='best',fontsize=9)
    ax=axes[1]
    ax.plot(t,raw,color='#a7acb0',lw=1,label='预测参考－实测功率')
    ax.plot(t,fits['ride_revised']['reduction_interval_kw'],color='#1668ac',lw=2,label='修复版拟合减载')
    ax.plot(t,fits['cpop']['reduction_interval_kw'],color='#ad5d7d',lw=1.5,ls='--',label='CPOP拟合减载')
    ax.axhline(.15,color='#c43b32',ls=':',label='时长判据0.15 kW')
    ax.axhline(0,color='#27804a',lw=1,label='真实减载＝0')
    ax.set(xlabel='相对任务开始时间（分钟）',ylabel='减载功率（kW）')
    ax.legend(loc='best',fontsize=9)
    for ax in axes:
        ax.axvspan(0,30,color='#1668ac',alpha=.045);ax.axvline(0,color='#888888',lw=.7);ax.axvline(30,color='#888888',lw=.7);ax.grid(alpha=.15)
    path=W/'reference_false_example.png'
    if path.exists():raise RuntimeError('preserve old figure')
    fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig)
(W/'example_receipt.json').write_text(json.dumps(dict(task_id=tid,scenario=scenario,selection='first common false event in original event_join order',true_duration=truth['cumulative_response_seconds'],predicted_duration={m:p['features']['selected_curve']['cumulative_response_seconds'] for m,p in fits.items()},no_performance_selection=True),ensure_ascii=False,indent=2),encoding='utf-8')
print(tid)
