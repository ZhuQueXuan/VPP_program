from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
main=pd.read_csv(ROOT/'main/summary.csv')
native=pd.read_csv(ROOT/'supplement_native_default/summary.csv')
data=pd.concat([main,native],ignore_index=True)
methods=['CPOP_default_binned','RIDE_template_average','F1_frozen_segment_adapter','Grid_average']
names=['CPOP default','Task template + average','F1 constant DP','Finite-grid + average']
colors=['#274C77','#E07A3F','#47866F','#A4AAB1']
fig,axes=plt.subplots(1,3,figsize=(10.2,3.2),layout='constrained')
for ax,dt,title in zip(axes,[round(1/6,10),1.,15.],['10 seconds','1 minute','15 minutes']):
    values=[float(data[(data.method==m)&np.isclose(data.delta_min,dt)].request_rmse.iloc[0]) for m in methods]
    bars=ax.bar(np.arange(4),values,color=colors,width=.65)
    ax.set_title(title,fontsize=12);ax.set_xticks([]);ax.set_ylim(0,max(values)*1.25)
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,v,f'{v:.3f}',ha='center',va='bottom',fontsize=10)
axes[0].set_ylabel('Request-window RMSE (kW)')
fig.legend([plt.Rectangle((0,0),1,1,color=c) for c in colors],names,loc='outside lower center',ncol=2,fontsize=9,frameon=False)
for ext in ['png','svg']:fig.savefig(OUT/f'process_default_comparison.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)

curves=np.load(ROOT/'main/all_curves.npz')
extra=np.load(ROOT/'supplement_native_default/curves.npz')
meta=json.loads((ROOT/'main/events.json').read_text(encoding='utf-8'))
selected=[m for m in meta if m['rep']==0 and m['delta_min']==1 and m['sigma_kw']==.15 and m['mechanism'] in ['slow','multiplateau']]
fig,axes=plt.subplots(1,2,figsize=(10.2,3.5),sharey=True,layout='constrained')
for ax,m in zip(axes,selected):
    i=m['event_id'];x=np.arange(-14.5,45,1)
    ax.axvspan(0,30,color='#DDE7F1',alpha=.35,zorder=0)
    ax.scatter(x,curves[f'{i}_y'],color='#9B9FA5',s=10,label='Observed interval means',alpha=.6)
    ax.plot(x,curves[f'{i}_truth'],color='black',lw=1.8,label='True interval means')
    ax.plot(x,extra[f'{i}_CPOP_default_binned'],color=colors[0],lw=1.7,label='CPOP default')
    ax.plot(x,curves[f'{i}_RIDE_template_average'],color=colors[1],lw=1.7,label='Task template + average')
    ax.set_title('Slow ramp' if m['mechanism']=='slow' else 'Multiple plateaus (template mismatch)',fontsize=11)
    ax.set_xlabel('Time from request start (min)');ax.grid(alpha=.17)
axes[0].set_ylabel('Interval-average reduction (kW)')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=9,frameon=False)
for ext in ['png','svg']:fig.savefig(OUT/f'process_examples.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)
print('Saved two PNG and SVG scientific figures from frozen outputs')
