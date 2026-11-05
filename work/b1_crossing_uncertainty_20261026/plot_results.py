"""Standalone research figures, all repetition indices fixed before outcomes."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inference import invert
BASE=Path(__file__).resolve().parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def main():
    b=np.load(BASE/'bands.npz');ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    truth=np.array(ev['truth_gains']);d=np.array(P['doses']);fig,axs=plt.subplots(2,2,figsize=(11,7.6),constrained_layout=True)
    for s,ax in enumerate(axs.flat):
        lo=b['lower'][0,s,0];hi=b['upper'][0,s,0];g=b['gain'][0,s,0]
        ax.fill_between(d,100*lo,100*hi,color='#84bbdf',alpha=.4,label='Approx. 95% simultaneous gain band')
        ax.plot(d,100*truth[s,0],color='#222',ls='--',label='Evaluator population truth')
        ax.plot(d,100*g,'o-',color='#1866a1',label='Observed dose means')
        ax.axhline(10,color='#ac423e',lw=1.2,label='Target +10 pp')
        inv=invert(lo,hi,.1)
        for k in inv['candidates']:ax.axvspan(d[k-1],d[k],color='#dbb63c',alpha=.12)
        ax.set_title(P['scenarios'][s].replace('_',' '));ax.set_xlabel('Declared incentive (yuan/kWh)');ax.set_ylabel('Delivery gain (percentage points)')
        ax.grid(alpha=.15);ax.set_xticks(d)
        ax.text(.02,.97,'First-crossing candidates: '+(', '.join(f'[{d[k-1]:g}, {d[k]:g}]' for k in inv['candidates']) or 'none')+'\nNo crossing still possible: '+str(inv['no_cross_possible']),transform=ax.transAxes,va='top',fontsize=8)
    handles,labels=axs.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=8)
    fig.suptitle('New EV simulation: fixed first repetition, overall population\nShaded yellow = possible first grid intervals; no monotonicity imposed',fontsize=12)
    fig.savefig(BASE/'gain_bands.png',dpi=180);plt.close(fig)
    scenes=P['scenarios'];methods=['strict_D109','naive_first','user_cluster_band'];colors=['#8b8f98','#d58939','#277da8']
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    xx=np.arange(4)
    for mi,method in enumerate(methods):
        a=[next(v for v in ev['summary'] if v['scenario']==s and v['group']=='all' and v['delta']==.1 and v['method']==method) for s in scenes]
        axs[0].bar(xx+(mi-1)*.24,[v['set_or_point_coverage']['count'] for v in a],.23,label=method,color=colors[mi])
    axs[0].set_xticks(xx,[s.replace('_','\n') for s in scenes]);axs[0].set_ylim(0,110);axs[0].set_ylabel('Correct point / truth included in set (of 100)');axs[0].set_title('Set inclusion can retain several possibilities');axs[0].legend(fontsize=8)
    a=[next(v for v in ev['summary'] if v['scenario']==s and v['group']=='all' and v['delta']==.1 and v['method']=='user_cluster_band') for s in scenes]
    bottom=np.zeros(4)
    for key,label,col in [('unique_count','One supported first interval','#277da8'),('bounded_multiple_count','Several first intervals; crossing supported','#70b7ba'),('unresolved_count','Crossing / no crossing unresolved','#e5b964'),('supported_not_reached_count','Supported no crossing','#a4a6af')]:
        yy=np.array([v[key] for v in a]);axs[1].bar(xx,yy,bottom=bottom,label=label,color=col);bottom+=yy
    axs[1].set_xticks(xx,[s.replace('_','\n') for s in scenes]);axs[1].set_ylim(0,110);axs[1].set_ylabel('Repetitions (all 100 retained)');axs[1].set_title('What the uncertainty method actually returns');axs[1].legend(fontsize=7,loc='upper left')
    fig.suptitle('First reaching +10 pp: honest sets are not exact location estimates',fontsize=12)
    fig.savefig(BASE/'crossing_comparison.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
