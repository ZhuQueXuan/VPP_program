"""Read once-frozen phase metrics and apply the preregistered evidence rule."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import t
HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def main(phase):
    directory=HERE/phase;target=directory/'assessment.json'
    if target.exists():raise RuntimeError('do not overwrite completed assessment')
    metrics=pd.read_csv(directory/'metrics.csv');timing=pd.read_csv(directory/'timing.csv');groups=[]
    for (panel,scenario,method),g in metrics.groupby(['panel','scenario','method']):
        row=dict(panel=panel,scenario=scenario,method=method,events=len(g),status_counts=g.status.value_counts().to_dict())
        for name in ('duration_mae','duration_bias','curve_rmse','eta_mae'):row[name]=float(g[name].mean())
        for name in ('no_action','false_detection','response','miss','fallback'):row[name]=int(g[name].sum())
        row['false_detection_rate']=row['false_detection']/row['no_action'] if row['no_action'] else None
        row['miss_rate']=row['miss']/row['response'] if row['response'] else None
        groups.append(row)
    main=metrics[metrics.panel=='main'];pooled=main.groupby('method')[['duration_mae','curve_rmse']].mean().to_dict('index')
    block=main.groupby(['seed','method'])[['duration_mae','curve_rmse']].mean().unstack();paired=[]
    for comparator in ('cpop','ride_template'):
        for name in ('duration_mae','curve_rmse'):
            values=block[(name,'ride_revised')]-block[(name,comparator)];n=len(values)
            half=float(t.ppf(.975,n-1)*values.std(ddof=1)/np.sqrt(n))
            paired.append(dict(comparator=comparator,metric=name,independent_blocks=n,mean=float(values.mean()),
                MC_t95=[float(values.mean()-half),float(values.mean()+half)],wins=int((values<0).sum()),ties=int((values==0).sum())))
    counts=main.groupby('method')[['false_detection','no_action','miss','response']].sum()
    fp={method:float(row.false_detection/row.no_action) for method,row in counts.iterrows()}
    miss={method:float(row['miss']/row.response) for method,row in counts.iterrows()}
    gain=1-pooled['ride_revised']['duration_mae']/pooled['cpop']['duration_mae']
    primary=next(row for row in paired if row['comparator']=='cpop' and row['metric']=='duration_mae')
    rules=dict(primary_at_least10percent=gain>=.1,paired_t95_below_zero=primary['MC_t95'][1]<0,
        curveRMSE_within5percent=pooled['ride_revised']['curve_rmse']<=1.05*pooled['cpop']['curve_rmse'],
        empirical_false_detection_excess_at_most2pp=fp['ride_revised']-fp['cpop']<=.02,
        empirical_miss_excess_at_most2pp=miss['ride_revised']-miss['cpop']<=.02,
        all_events_retained=bool(main.status.isin(['ok','degraded']).all()))
    shape=main.groupby(['scenario','method','shape'])[['duration_mae','curve_rmse']].mean().reset_index().to_dict('records')
    result=dict(phase=phase,groups=groups,pooled_main=pooled,paired_block_differences=paired,
        relative_primary_gain_vs_CPOP=float(gain),CPOP_advantage_gate=rules,all_CPOP_gates_pass=all(rules.values()),
        false_detection_rates=fp,miss_rates=miss,shape_groups=shape,
        summed_method_seconds=timing[timing.panel=='main'].groupby('method').seconds.sum().to_dict(),
        stage='validation or development cannot establish test advantage' if phase!='test' else 'fresh finite simulation test',
        whole_B1_complete=False,real_EV_validation=False)
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:result[k] for k in ('phase','pooled_main','relative_primary_gain_vs_CPOP','CPOP_advantage_gate','paired_block_differences')},indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase');main(parser.parse_args().phase)
