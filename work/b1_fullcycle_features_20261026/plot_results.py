"""Fixed first repetition examples and all full-case errors."""
from pathlib import Path
import json,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_fullcycle_features_v1_20261026'
def main():
    rows=json.loads((RAW/'observation_index.json').read_text(encoding='utf-8'));raw=np.load(RAW/'observations.npz')['power_obs_kw'];hidden=np.load(BASE/'hidden_native.npz')['reduction_kw'];fits=np.load(BASE/'fitted_reductions.npz')['reduction_kw']
    fig,axs=plt.subplots(2,3,figsize=(12,6.8),constrained_layout=True)
    for case,ax in zip(['no_action','step','partial','slow_ramp','early_exit','interrupted'],axs.flat):
        i=next(i for i,v in enumerate(rows) if v['rep']==0 and v['mechanism']==case and v['observation']=='full' and v['sigma_native_kw']==.15 and v['dt_s']==10)
        t=np.arange(360)*10/60
        ax.plot(t,3-raw[i,:360],lw=.5,alpha=.5,color='#a0a0a0',label='Observed reduction')
        ax.plot(t,hidden[rows[i]['latent_id']],color='#222',ls='--',lw=1.2,label='Latent interval mean')
        ax.plot(t,fits[2*i+1],color='#257aad',lw=1.3,label='F1 constant-mean fit')
        ax.axvspan(10,30,color='#b9d6b2',alpha=.18);ax.axhline(.15,color='#a7524a',ls=':',lw=.8)
        ax.set_title(case.replace('_',' '));ax.set_xlabel('Time (minutes)');ax.set_ylabel('Reduction (kW)');ax.grid(alpha=.15)
    handles,labels=axs.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=3,fontsize=8)
    fig.suptitle('Full-cycle EV feature experiment: fixed first repetition\n10s grid, native noise sigma=0.15kW; fitted steps do not identify physical phases',fontsize=12)
    fig.savefig(BASE/'fullcycle_examples.png',dpi=170);plt.close(fig)
    ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    cells=[(.05,10),(.05,30),(.15,10),(.15,30)];xx=np.arange(4)
    fig,axs=plt.subplots(1,3,figsize=(12,4.4),constrained_layout=True)
    for mi,method in enumerate(['F0_raw_rule','F1_segment_rule']):
        a=[[v for v in ev['summary'] if v['observation']=='full' and v['sigma_native_kw']==s and v['dt_s']==d and v['method']==method] for s,d in cells]
        stage=[sum(v['stage_correct_count'] for v in group) for group in a]
        false=[sum(v['false_onset_count'] for v in group) for group in a]
        duration=[sum(v['duration_s']['conditional_mae']*v['duration_s']['paired_available'] for v in group)/sum(v['duration_s']['paired_available'] for v in group) for group in a]
        for ax,yy in zip(axs,[stage,false,duration]):ax.bar(xx+(mi-.5)*.3,yy,.29,label=method,color=['#c68b4e','#277da8'][mi])
    for ax in axs:ax.set_xticks(xx,['.05 / 10s','.05 / 30s','.15 / 10s','.15 / 30s'],fontsize=8);ax.set_xlabel('Native sigma (kW) / sample interval');ax.grid(axis='y',alpha=.15)
    axs[0].set_title('Observable stage correct (of 150)');axs[1].set_title('False response in no-action case (of 25)');axs[2].set_title('Longest-threshold-run MAE (seconds)')
    handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2)
    fig.suptitle('All 25 repetitions x 6 paired mechanisms, full observation only\nMissing / short-window outcomes are reported separately',fontsize=12)
    fig.savefig(BASE/'feature_comparison.png',dpi=170);plt.close(fig)
if __name__=='__main__':main()
