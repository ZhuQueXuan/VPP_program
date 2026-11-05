"""Summarize one frozen diagnostic panel, with no refitting or model adoption."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import t
HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def main():
    if (HERE/'summary.json').exists():raise RuntimeError('completed summary cannot be overwritten')
    receipt=read(HERE/'diagnosis_receipt.json');assert receipt['completed']
    metrics=pd.read_csv(HERE/'diagnostic_metrics.csv');rows=[];shape_rows=[];differences=[]
    for (scenario,level,method),g in metrics.groupby(['scenario','level','method']):
        r=dict(scenario=scenario,level=level,method=method,events=len(g),status_counts=g.status.value_counts().to_dict())
        for name in ('curve_rmse','duration_mae','duration_error','raw_duration_mae','post_rmse','eta_error'):r[name]=float(g[name].mean())
        for name in ('no_action','false_detection','response','miss','fallback'):r[name]=int(g[name].sum())
        response=g[g.response==1];r['responders_duration_mae']=float(response.duration_mae.mean())
        r['responders_duration_bias']=float(response.duration_error.mean())
        r['false_detection_fraction']=r['false_detection']/r['no_action'] if r['no_action'] else None
        if method=='ride_template':r['structure_counts']=g.selected_structure.value_counts().to_dict()
        rows.append(r)
    for (scenario,level,method,shape),g in metrics[metrics.response==1].groupby(['scenario','level','method','shape']):
        shape_rows.append(dict(scenario=scenario,level=level,method=method,shape=shape,responders=len(g),
            duration_mae=float(g.duration_mae.mean()),duration_bias=float(g.duration_error.mean()),curve_rmse=float(g.curve_rmse.mean())))
    for scenario,g in metrics.groupby('scenario'):
        block=g.groupby(['seed','level','method'])[['curve_rmse','duration_mae']].mean().unstack(['level','method'])
        for level in ('selected_noise','oracle_noise','oracle_clean','no_post_rebound','relaxed_rebound'):
            for name in ('curve_rmse','duration_mae'):
                values=block[(name,level,'ride_template')]-block[(name,level,'cpop')]
                half=t.ppf(.975,7)*values.std(ddof=1)/np.sqrt(8)
                differences.append(dict(scenario=scenario,level=level,metric=name,meaning='RIDE minus original CPOP',
                    independent_blocks=8,mean=float(values.mean()),MC_t95=[float(values.mean()-half),float(values.mean()+half)]))
    probes=read(HERE/'optimization_probes.json');probe_summary={}
    for nstarts in (3,12):
        records=[next(r for r in p['fits'] if r['minimum_starts']==nstarts) for p in probes]
        probe_summary[str(nstarts)]=dict(cases=len(records),mean_duration_mae=float(np.mean([abs(r['duration_error']) for r in records])),
            mean_fitted_RSS=float(np.mean([r['fitted_RSS'] for r in records])),
            m2_witness_objective_strictly_better=sum(r['bic2']>p['witness_bic2']+1e-5 for r,p in zip(records,probes)),
            structures=pd.Series([r['structure'] for r in records]).value_counts().to_dict())
    result=dict(groups=rows,responders_by_shape=shape_rows,paired_gaps=differences,optimization_probes=probe_summary,
        reference=pd.read_csv(HERE/'reference_metrics.csv').groupby('scenario')[['mae','bias']].mean().reset_index().to_dict('records'),
        positive_controls=read(HERE/'positive_controls.json'),
        no_additive_causal_error_percentage=True,production_changes=False,new_independent_test=False,model_adopted=False)
    write(HERE/'summary.json',result)
    pd.DataFrame(rows).to_csv(HERE/'summary.csv',index=False);pd.DataFrame(shape_rows).to_csv(HERE/'shapes.csv',index=False)
    print(json.dumps(dict(groups=rows,optimization_probes=probe_summary),indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    levels=['selected_noise','oracle_noise','oracle_clean','no_post_rebound','relaxed_rebound']
    labels=['Estimated ref.\n+ meter noise','True ref.\n+ meter noise','True ref.\nno meter noise','Clean input\nno post recharge','Clean input\nrelaxed recharge cap']
    figure,axes=plt.subplots(1,2,figsize=(12,4.5),sharey=True)
    for ax,scenario in zip(axes,('positive','zero')):
        for offset,method,color,label in [(-.18,'ride_template','#d55e00','Current RIDE'),(.18,'cpop','#0072b2','Original CPOP')]:
            means=[next(r['duration_mae'] for r in rows if r['scenario']==scenario and r['level']==level and r['method']==method)/60 for level in levels]
            ax.bar(np.arange(5)+offset,means,width=.36,color=color,label=label)
        ax.set_xticks(np.arange(5),labels,fontsize=8);ax.set_title('Positive-effect mechanism' if scenario=='positive' else 'Zero-effect mechanism')
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_ylabel('Mean cumulative duration error (minutes)');axes[1].legend(frameon=False)
    figure.suptitle('DIAGNOSTIC SIMULATION: same 256 events per mechanism; no model adoption')
    figure.tight_layout();figure.savefig(HERE/'diagnostic_duration.png',dpi=160);plt.close(figure)
if __name__=='__main__':main()
