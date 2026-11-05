"""Scientific figures from all frozen repetitions, no selected favorable seed."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent

def main():
    e=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    scenes=['randomized_positive','observed_positive','observed_zero','observed_negative']
    methods=['G0_unadjusted','G1_graph_safe','Gbad_adjust_acceptance'];labels=['Unadjusted','Pre-treatment adjustment','Invalid: adjust acceptance'];colors=['#b69561','#277ba5','#b65e64']
    fig,axs=plt.subplots(1,2,figsize=(12,4.9),constrained_layout=True);xx=np.arange(4)
    for oi,outcome in enumerate(['cumulative_s','long600']):
        ax=axs[oi];scale=1 if oi==0 else 100
        for mi,method in enumerate(methods):
            rows=[next(v for v in e['summary'] if v['scenario']==s and v['split']=='test' and v['group']=='all' and v['outcome']==outcome and v['method']==method) for s in scenes]
            vals=[v['mean_estimate']*scale if v['mean_estimate'] is not None else np.nan for v in rows]
            ax.bar(xx+(mi-1)*.23,vals,.22,color=colors[mi],label=labels[mi])
            for j,v in enumerate(rows):
                if v['available_repetitions']!=20:ax.annotate(str(v['available_repetitions'])+'/20',(xx[j]+(mi-1)*.23,vals[j]),fontsize=7)
        truth=[next(v['mean_true_effect']*scale for v in e['summary'] if v['scenario']==s and v['split']=='test' and v['group']=='all' and v['outcome']==outcome) for s in scenes]
        ax.scatter(xx,truth,marker='D',s=35,color='#222',label='Evaluator reference',zorder=5)
        ax.axhline(0,color='#555',lw=.8);ax.set_xticks(xx,['Randomized +','Observed +','Observed zero','Observed -']);ax.tick_params(axis='x',labelsize=8)
        ax.set_ylabel('Total incentive effect (seconds)' if oi==0 else 'Effect on >=600s event (percentage points)');ax.grid(axis='y',alpha=.15)
        ax.set_title('Cumulative reduction time' if oi==0 else 'Long cumulative-time indicator')
    handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=8)
    fig.suptitle('One EV chain: observed curve features -> identified total-effect estimation\nMean over 20 independent repetitions; graph-safe estimate assumes the declared causal structure',fontsize=12)
    fig.savefig(BASE/'factor_effects.png',dpi=175);plt.close(fig)
    graphs=json.loads((BASE/'graphs.json').read_text(encoding='utf-8'))
    candidates=[('X','D'),('W','D'),('X','A'),('W','A'),('D','A'),('X','S'),('W','S'),('D','S'),('A','S')]
    counts=np.array([[sum(edge in set(map(tuple,graphs[r][s]['learned']['edges'])) for r in range(20)) for edge in candidates] for s in range(4)])
    fig,ax=plt.subplots(figsize=(10,3.9),constrained_layout=True);im=ax.imshow(counts,cmap='Blues',vmin=0,vmax=20)
    for (i,j),n in np.ndenumerate(counts):ax.text(j,i,str(n),ha='center',va='center',color='white' if n>12 else '#222')
    ax.set_xticks(range(9),[a+' -> '+b for a,b in candidates]);ax.set_yticks(range(4),scenes);ax.tick_params(labelsize=9)
    fig.colorbar(im,ax=ax,label='Selected in training repetitions (of 20)')
    ax.set_title('EV binary parent screening: temporal direction prescribed, edge presence from BIC\nX slack group; W urgency; D incentive; A acceptance; S long cumulative duration',fontsize=11)
    fig.savefig(BASE/'graph_screening.png',dpi=175);plt.close(fig)

if __name__=='__main__':main()
