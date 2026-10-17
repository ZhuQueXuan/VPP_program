"""Unchanged final kernel on the complete D055 admitted cross-season cohort."""
from crossseason_common import *
import argparse,importlib.metadata as md
import numpy as np
import pandas as pd
import pvlib
from run_smart_forecast import score,MODELS
sys.path.insert(0,str(ROOT/'resource_research_results/distributed_photovoltaic/code'))
from clear_sky_forecast import SiteGeometry,forecast_next_labels

def execute(out):
    p=frozen();prep=BASE/'runs/PREP_CROSSSEASON_02';ad=json.loads((prep/'admission.json').read_text())
    for n,h in ad['files'].items():assert sha(prep/n)==h
    for s in json.loads((prep/'source_manifest.json').read_text()):assert sha(ROOT/s['path'])==s['sha256']
    env=json.loads((ROOT/p['frozen_artifacts']['environment']['path']).read_text());lib=Path(pvlib.__file__).parent
    assert all(md.version(n)==v for n,v in env['versions'].items())
    assert sha(lib/'data/LinkeTurbidities.h5')==env['climatology_sha256']
    assert all(sha(lib/f)==h for f,h in env['core_module_sha256'].items())
    samples=[r for r in read(prep/'samples.csv') if r['status']=='admitted']
    cfg=json.loads((ROOT/p['frozen_artifacts']['geometry']['path']).read_text())
    forecasts=forecast_next_labels([float(r['origin_W']) for r in samples],pd.to_datetime([r['origin_utc'] for r in samples],utc=True),SiteGeometry(**cfg['site_geometry']))
    assert forecasts.target_time.dt.tz_convert('UTC').dt.strftime('%Y-%m-%d %H:%M:%S').tolist()==[r['target_utc'] for r in samples]
    b=json.loads((ROOT/p['frozen_artifacts']['ar2']['path']).read_text());pred=[]
    for r,f in zip(samples,forecasts.to_dict('records')):
        row={**r,**{k:float(r[k]) for k in ('target_W','origin_W','lag_W')},
             'B_P':float(f['persistence_W']),'M_SP':float(f['clear_sky_persistence_W']),
             'F_AR2':1000*(b['intercept_kW']+b['current_weight']*float(r['origin_W'])/1000+b['previous_weight']*float(r['lag_W'])/1000),
             'clear_current_W_m2':float(f['clear_current_W_m2']),'clear_target_W_m2':float(f['clear_target_W_m2']),
             'ratio':float(f['ratio']),'branch':f['branch']}
        pred.append(row)
    table(out/'predictions.csv',pred)
    groups={'all':pred,'origin_ge1000W':[r for r in pred if r['origin_W']>=1000],
            'origin_lt1000W':[r for r in pred if r['origin_W']<1000],
            'target_change_ge2016W':[r for r in pred if abs(r['target_W']-r['origin_W'])>=2016]}
    metrics={key:{m:score(rr,m) for m in MODELS} for key,rr in groups.items()};dump(out/'metrics.json',metrics)
    grouped=[]
    for typ,keys in (('season',list(p['period']['seasons'])),('month',p['period']['months']),('date',sorted({r['target_time'][:10] for r in pred}))):
        for key in keys:
            rr=[r for r in pred if (r['target_time'][:10] if typ=='date' else r[typ])==key]
            for m in MODELS:grouped.append({'group_type':typ,'group':key,'model':m,**score(rr,m)})
    table(out/'group_metrics.csv',grouped)
    gains=[]
    for typ,key in sorted({(r['group_type'],r['group']) for r in grouped}):
        dd={r['model']:r for r in grouped if r['group_type']==typ and r['group']==key}
        gains.append({'group_type':typ,'group':key,'n':dd['B_P']['n'],
                      **{k+'_improves':dd['M_SP']['n']>0 and dd['M_SP'][k]<dd['B_P'][k] for k in ('mae_W','rmse_W')},
                      **{k+'_skill':1-dd['M_SP'][k]/dd['B_P'][k] if dd['B_P'].get(k,0)>0 else None for k in ('mae_W','rmse_W')}})
    dump(out/'comparisons.json',gains)
    a=metrics['all'];summary={'date':'2026-10-16','protocol_sha256':sha(BASE/'crossseason_protocol_v1.json'),
        'admission_sha256':sha(prep/'admission.json'),'object':p['object'],'samples':len(pred),'expected_targets':26304,
        'coverage_fraction':len(pred)/26304,'new_fitted_power_parameters':0,'all':a,
        'M_SP_skill_vs_B_P':{k:1-a['M_SP'][k]/a['B_P'][k] for k in ('mae_W','rmse_W')},
        'crossseason_positive_criterion':all(a['M_SP'][k]<a['B_P'][k] for k in ('mae_W','rmse_W')) and all(r['mae_W_improves'] and r['rmse_W_improves'] for r in gains if r['group_type']=='season'),
        'month_both_improve':sum(r['mae_W_improves'] and r['rmse_W_improves'] for r in gains if r['group_type']=='month'),
        'daily_both_improve':sum(r['mae_W_improves'] and r['rmse_W_improves'] for r in gains if r['group_type']=='date'),
        'observed_dates':len({r['target_time'][:10] for r in pred}),
        'scaled_samples':sum(r['branch']=='scaled' for r in pred),'fallback_samples':sum(r['branch']=='persistence_fallback' for r in pred),
        'ratio_min':min(r['ratio'] for r in pred),'ratio_max':max(r['ratio'] for r in pred),
        'seasons':[r for r in grouped if r['group_type']=='season'],
        'limits':p['not_validated']+['October9-31 source absent; no claim for missing labels','DST ambiguous publication values excluded by prior protocol']}
    dump(out/'summary.json',summary)
    frozen()
    dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'crossseason_protocol_v1.json'),
        'admission_sha256':sha(prep/'admission.json'),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('seasons','limits','all')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
