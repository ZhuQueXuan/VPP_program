"""Plot the predeclared first final block; no selection by observed score."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'B1算法'))
from b1_api import load_continuous_model,query_continuous_model,export_incentive_curve
W=R/'work/b1_finish_ev_20261030';F=W/'final_chain';O=W/'figures';O.mkdir(exist_ok=True)
model=load_continuous_model(F/'models/7240200_positive_ride_revised_duration.json')
q=query_continuous_model(model,np.linspace(.4,2.,41))
if q['status']!='causal':raise RuntimeError('first declared example unsupported; preserve refusal, no cherry-picked replacement')
export_incentive_curve(q,O/'连续金额查询_首个独立模拟块.png',title='B1连续金额查询（模拟；固定30分钟、1.5 kW任务）')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')
with plt.rc_context({'font.family':['SimHei','DejaVu Sans'],'axes.unicode_minus':False}):
    fig,ax=plt.subplots(figsize=(8.4,5.1),layout='constrained')
    s=q['sensitivity'];a=np.asarray(s['incentive_values']);band=s['inference']
    ax.plot(a,s['values'],color='#1668ac',lw=2.3,label='冻结平滑曲线的导数')
    ax.fill_between(a,band['lower'],band['upper'],color='#1668ac',alpha=.14,label='条件抽样波动带')
    ax.axhline(0,color='#888888',lw=.8);ax.grid(alpha=.15)
    ax.set(xlabel='事先告知的补偿标准（元/千瓦时）',ylabel='平均响应变化幅度（秒/补偿标准单位）',title='B1敏感性查询（首个独立模拟块）')
    ax.legend();fig.text(.01,-.025,'仅为冻结平滑曲线导数；未传播平滑、参考、过程与辅助估计的全部误差。',fontsize=9)
    path=O/'连续敏感性_首个独立模拟块.png'
    if path.exists():raise RuntimeError('preserve old figure')
    fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig)
(W/'plot_receipt.json').write_text(json.dumps(dict(predeclared_block=7240200,scenario='positive',model_id=model.sha256,grid_points=41,refit=False,source='saved final artifact',figures=[str(p) for p in O.glob('*.png')]),ensure_ascii=False,indent=2),encoding='utf-8')
print('2 figures exported from saved model, no fit')
