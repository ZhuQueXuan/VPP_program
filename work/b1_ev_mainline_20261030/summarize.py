"""Describe frozen metrics; no fitting, filtering decisions, or main reruns."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import t
HERE=Path(__file__).resolve().parent

def grouped(frame,keys,means,sums):
    rows=[]
    for values,g in frame.groupby(keys,sort=True):
        if not isinstance(values,tuple):values=(values,)
        r=dict(zip(keys,values));r['events']=len(g)
        for name in means:r[name]=float(g[name].mean())
        for name in sums:r[name]=int(g[name].sum())
        r['status_counts']=g['status'].value_counts().to_dict();rows.append(r)
    return rows

def main():
    p=pd.read_csv(HERE/'process_metrics.csv');e=pd.read_csv(HERE/'effect_metrics.csv');r=pd.read_csv(HERE/'reference_metrics.csv')
    process=grouped(p,['panel','scenario','method'],['curve_rmse','duration_absolute_error','eta_absolute_error'],['no_action','false_detection','response','miss','fallback'])
    for x in process:
        x['false_detection_fraction']=x['false_detection']/x['no_action'] if x['no_action'] else None
        x['miss_fraction']=x['miss']/x['response'] if x['response'] else None
    references=r.groupby('method')[['mae','bias']].mean().reset_index().to_dict('records')
    effect=[]
    for (scenario,group,method),g in e.groupby(['scenario','group','method']):
        success=g[g.status=='causal'];effect.append(dict(scenario=scenario,group=group,method=method,
            blocks=len(g),supported_blocks=len(success),status_counts=g.status.value_counts().to_dict(),
            supported_mean_curve_rmse=float(success.curve_rmse.mean()) if len(success) else None,
            supported_mean_max_absolute_contrast=float(success.max_absolute_contrast.mean()) if len(success) else None,
            mean_true_max_contrast=float(g.true_max_contrast.mean()),events_per_block=g.events.tolist()))
    paired=[]
    mainp=p[p.panel=='main']
    for scenario,g in mainp.groupby('scenario'):
        block=g.groupby(['seed','method'])[['curve_rmse','duration_absolute_error']].mean().unstack()
        for name in ('curve_rmse','duration_absolute_error'):
            diff=block[(name,'ride_template')]-block[(name,'cpop')]
            half=t.ppf(.975,len(diff)-1)*diff.std(ddof=1)/np.sqrt(len(diff))
            paired.append(dict(scenario=scenario,metric=name,meaning='RIDE minus CPOP',n_independent_blocks=len(diff),
                mean=float(diff.mean()),MC_t95=[float(diff.mean()-half),float(diff.mean()+half)]))
    selections={}
    for path in (HERE/'reference').glob('*_selection.json'):
        for item in json.loads(path.read_text(encoding='utf-8')):selections[item['method']]=selections.get(item['method'],0)+1
    screens=json.loads((HERE/'structure_screening.json').read_text(encoding='utf-8'))
    screen_counts={}
    for item in screens:
        if item['scenario']=='positive':
            key=','.join(item['selected_parents']);screen_counts[key]=screen_counts.get(key,0)+1
    result=dict(process=process,references=references,reference_selection=selections,effects=effect,
        paired_process_differences=paired,incentive_parent_screen_by_8_positive_blocks=screen_counts,
        independent_blocks=8,paired_scenarios_not_independent=True,
        effect_RMSE_target='common latent noiseless1min interval truth for evaluator only; fitting targets declared measured outcome',
        uncertainty_note='MC_t95 describes across-eight-block mean difference, not method coverage or real-device reliability')
    with (HERE/'results_summary.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
