"""All repeated held-out scores, no selected favorable repetition."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent

def main():
    ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    methods=['C0_current','C1_history_summary','C2_history_shape','C3_history_PCA'];labels=['Current conditions','+ History summary','+ History shape','+ History PCA6']
    scenes=['stable_history','uninformative_history','behavior_shift'];colors=['#92969e','#5fabb3','#d4a250','#276b9e']
    fig,axs=plt.subplots(1,2,figsize=(11,4.8),constrained_layout=True)
    xx=np.arange(3)
    for mi,method in enumerate(methods):
        vals=[next(v['pooled_rmse']*100 for v in ev['summary'] if v['scenario']==scene and v['split']=='test' and v['group']=='all' and v['method']==method) for scene in scenes]
        axs[0].bar(xx+(mi-1.5)*.19,vals,.18,label=labels[mi],color=colors[mi])
    axs[0].set_xticks(xx,['Stable history','No history signal','Behavior shift']);axs[0].set_ylabel('Future observed delivery RMSE (pp)');axs[0].set_title('All held-out users, later calls (20 repetitions)');axs[0].grid(axis='y',alpha=.15)
    for mi,method in enumerate(methods):
        vals=[next(v['pooled_rmse']*100 for v in ev['summary'] if v['scenario']=='behavior_shift' and v['split']=='test' and v['group']=='event_'+str(j) and v['method']==method) for j in (9,10,11)]
        axs[1].plot([9,10,11],vals,'o-',color=colors[mi],label=labels[mi])
    axs[1].set_xticks([9,10,11]);axs[1].set_xlabel('Held-out target event after change');axs[1].set_ylabel('RMSE (pp)');axs[1].set_title('Frozen model; newly completed histories allowed');axs[1].grid(alpha=.15)
    handles,names=axs[0].get_legend_handles_labels();fig.legend(handles,names,loc='outside lower center',ncol=2,fontsize=9)
    fig.suptitle('Does historical time-series representation help the next response?\nSame fixed quadratic Ridge predictor; three past curves only, no current outcome',fontsize=12)
    fig.savefig(BASE/'history_prediction.png',dpi=175);plt.close(fig)
    a=[v for v in ev['paired'] if v['split']=='test' and v['group']=='all' and v['candidate']=='C3_history_PCA' and v['baseline'] in ['C1_history_summary','C2_history_shape']]
    fig,axs=plt.subplots(1,3,figsize=(11,3.7),constrained_layout=True)
    for scene,ax in zip(scenes,axs):
        for baseline,color,label in [('C1_history_summary','#6b9f88','PCA - summary'),('C2_history_shape','#b18340','PCA - shape')]:
            v=next(v for v in a if v['scenario']==scene and v['baseline']==baseline)
            ax.plot(np.arange(1,21),10000*np.array(v['differences']),'o-',color=color,ms=3,lw=.8,label=label)
        ax.axhline(0,color='#444',lw=1);ax.set_title(scene.replace('_',' '));ax.set_xlabel('Independent repetition');ax.set_ylabel('Paired MSE difference (pp squared)');ax.grid(alpha=.15)
    handles,names=axs[0].get_legend_handles_labels();fig.legend(handles,names,loc='outside lower center',ncol=2)
    fig.suptitle('PCA increment against strong history baselines: below zero is better')
    fig.savefig(BASE/'paired_increments.png',dpi=175);plt.close(fig)

if __name__=='__main__':main()
