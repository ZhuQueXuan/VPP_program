"""Post-run summaries from frozen predictions, never model selection/tuning."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from collections import Counter
from simulation import potential_outcome
HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)

def main():
    if (HERE/'additional_diagnostics.json').exists():raise RuntimeError('completed diagnostics cannot be overwritten')
    seeds=read(HERE/'protocol.json')['main_seeds'];grid=np.linspace(.4,2.,9)
    rows=[];recovery=[];zero_bands=[];display={}
    for scenario in ('positive','zero'):
        plot=Counter();plot_curves={key:[] for key in ('truth','RIDE_duration','CPOP_duration','raw_duration')}
        for seed in seeds:
            truth=read(HERE/f'evaluator/{seed}_{scenario}_truth.json')
            duration=np.array([np.mean([potential_outcome(float(a),r)['cumulative_response_seconds'] for r in truth]) for a in grid]);duration-=duration[0]
            eta=np.array([np.mean([potential_outcome(float(a),r)['eta'] for r in truth]) for a in grid]);eta-=eta[0]
            plot_curves['truth'].append(duration.tolist())
            for measurement in ('RIDE_duration','CPOP_duration','raw_duration','eta_raw'):
                result=read(HERE/f'effects/{seed}_{scenario}_all_{measurement}.json');target=eta if measurement=='eta_raw' else duration
                assert result['status']=='causal'
                candidates={'Kennedy_DR':result['causal_curve'],**result['comparators']}
                for name,curve in candidates.items():rows.append(dict(seed=seed,scenario=scenario,measurement=measurement,method=name,
                    latent_target_RMSE=float(np.sqrt(np.mean((np.asarray(curve['contrasts'])-target)**2)))))
                if measurement!='eta_raw':plot_curves[measurement].append(result['causal_curve']['contrasts'])
                if scenario=='zero':
                    band=result['inference'];lower=np.array(band['lower']);upper=np.array(band['upper'])
                    zero_bands.append(dict(seed=seed,measurement=measurement,all_nine_points_include_zero=bool(np.all((lower<=0)&(upper>=0)))))
            for method in ('ride_template','cpop'):
                events=read(HERE/f'events/{seed}_{scenario}_{method}.json')
                for source in ('selected_curve','raw_observed'):
                    for feature in ('power_recovery_status','energy_recovery_status'):
                        counts=Counter(e['process']['features'][source][feature] for e in events)
                        recovery.append(dict(seed=seed,scenario=scenario,method=method,source=source,feature=feature,
                            total=len(events),counts=dict(counts)))
        display[scenario]={name:np.mean(values,axis=0).tolist() for name,values in plot_curves.items()}
    df=pd.DataFrame(rows);df.to_csv(HERE/'comparator_metrics.csv',index=False)
    summary=df.groupby(['scenario','measurement','method'])['latent_target_RMSE'].mean().reset_index().to_dict('records')
    status={}
    for row in recovery:
        key='|'.join(row[k] for k in ('scenario','method','source','feature'));status.setdefault(key,Counter()).update(row['counts'])
    band_counts={name:sum(r['all_nine_points_include_zero'] for r in zero_bands if r['measurement']==name) for name in ('RIDE_duration','CPOP_duration','raw_duration','eta_raw')}
    write(HERE/'additional_diagnostics.json',dict(comparator_block_mean_RMSE=summary,recovery_status_counts={k:dict(v) for k,v in status.items()},
        zero_effect_conditional_bands_all_nine_points_include_zero_of_eight=band_counts,
        zero_effect_band_records=zero_bands,interpretation='Only8 independent blocks and conditional bands; this is not validation of nominal95percent full-chain coverage. Recovery statuses describe estimated differences, not physical recovery.',
        no_model_refitting=True))
    write(HERE/'illustrated_curves.json',dict(incentive_values=grid.tolist(),mean_over_eight_blocks=display,
        plot_grid_only=True,actual_estimator_supports_direct_arbitrary_amount_query=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),sharex=True,sharey=True)
    styles={'truth':('Latent interval target (evaluator only)','black','--'),
        'RIDE_duration':('RIDE measurement + same DR','#d55e00','-'),
        'CPOP_duration':('CPOP measurement + same DR','#0072b2','-'),
        'raw_duration':('Raw threshold + same DR','#009e73',':')}
    for ax,scenario in zip(axes,('positive','zero')):
        for name,(label,color,style) in styles.items():ax.plot(grid,np.array(display[scenario][name])/60,label=label,color=color,linestyle=style,linewidth=1.8)
        ax.set(title='Positive-effect mechanism' if scenario=='positive' else 'Zero-effect mechanism',xlabel='Offered incentive (CNY/kWh)')
        ax.axhline(0,color='.6',linewidth=.6);ax.grid(alpha=.2)
    axes[0].set_ylabel('Mean duration contrast vs 0.4 (minutes)')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=2,frameon=False,fontsize=9)
    fig.suptitle('SIMULATED EV data: shared continuous DR, different outcome measurements')
    fig.tight_layout(rect=[0,.14,1,.94]);fig.savefig(HERE/'simulated_duration_curves.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(comparator_block_mean_RMSE=summary,zero_band_counts=band_counts),indent=2))

if __name__=='__main__':main()
