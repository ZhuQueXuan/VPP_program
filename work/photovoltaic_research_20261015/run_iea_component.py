"""Frozen lab-parameter component validation; no outdoor fitting or tuning."""
from pathlib import Path
from datetime import datetime
import argparse,csv,hashlib,json,math,platform

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
MODELS=('B_G','M_T0','M_T3')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def num(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None
def scores(rows,m,p0):
    if not rows:return {'n':0}
    err=[r[m]-r['Pm'] for r in rows];ae=sorted(abs(e) for e in err)
    worst=max(range(len(rows)),key=lambda i:abs(err[i]));mae=math.fsum(ae)/len(ae)
    rmse=math.sqrt(math.fsum(e*e for e in err)/len(err))
    return {'n':len(rows),'mae_W':mae,'rmse_W':rmse,'bias_W':math.fsum(err)/len(err),
            'p95_abs_W':ae[math.ceil(.95*len(ae))-1],'max_abs_W':ae[-1],
            'worst_time':rows[worst]['time'],'worst_target_W':rows[worst]['Pm'],
            'worst_prediction_W':rows[worst][m],'mae_div_lab_P0':mae/p0,'rmse_div_lab_P0':rmse/p0}
def execute(out):
    path=BASE/'iea_component_protocol_v1.json';p=json.loads(path.read_text(encoding='utf-8'))
    frozen=json.loads((BASE/'iea_component_freeze_receipt_v1.json').read_text())
    assert sha(path)==frozen['protocol_sha256']
    for item in p['sources']:assert sha(ROOT/item['path'])==item['sha256']
    dump(out/'protocol_snapshot.json',p)
    p0=p['lab_parameters']['p0_W'];gamma=p['lab_parameters']['gamma_per_C']
    allrows=[];pred=[];seen=set()
    for src in sorted((s for s in p['sources'] if s['path'].endswith('.csv')),key=lambda s:Path(s['path']).name):
        with (ROOT/src['path']).open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f,delimiter=';',skipinitialspace=True))
        for line,r in enumerate(rows,2):
            t=datetime.strptime(r['Date']+' '+r['Time'],'%d.%m.%Y %H:%M:%S')
            assert t not in seen and t.strftime('%Y_%m')==Path(src['path']).stem;seen.add(t)
            vals={k:num(r[k]) for k in ('Pm','Voc','Isc','Tbom','Gpoa')}
            finite=all(v is not None for v in vals.values());flags=[]
            if not finite:flags.append('core_nonfinite')
            exact=t.minute%5==0 and t.second==0
            if not exact:flags.append('off_grid')
            if vals['Gpoa'] is not None and vals['Gpoa']<0:flags.append('negative_G')
            iv_bad=finite and (vals['Pm']<0 or vals['Voc']<=0 or vals['Isc']<=0 or vals['Pm']>vals['Voc']*vals['Isc']+0.001)
            if iv_bad:flags.append('iv_inconsistent')
            record={'source':src['path'],'line':line,'time':t.isoformat(sep=' '),'month':t.strftime('%Y-%m'),
                    **vals,'status':';'.join(flags) if flags else 'admitted','iv_inconsistent':iv_bad}
            allrows.append(record)
            if finite and exact and vals['Gpoa']>=0:
                g=vals['Gpoa'];tm=vals['Tbom'];x=p0*g/1000
                factors=(1+gamma*(tm-25),1+gamma*(tm+3*g/1000-25))
                assert min(factors)>0,'Nonpositive model temperature factor'
                row=record|{'main_cohort':not iv_bad,'outside_lab_GT_range':g<100 or g>1100 or tm<15 or tm>75,
                            'B_G':x,'M_T0':x*factors[0],'M_T3':x*factors[1]}
                assert all(math.isfinite(row[m]) for m in MODELS)
                pred.append(row)
    allrows.sort(key=lambda r:r['time']);pred.sort(key=lambda r:r['time'])
    table(out/'all_raw_rows.csv',allrows);table(out/'predictions_all_finite.csv',pred)
    cohorts={'main':[r for r in pred if r['main_cohort']],'all_finite_reference_sensitivity':pred}
    results={};monthly=[]
    for name,rr in cohorts.items():
        groups={'all':rr,'G_ge200':[r for r in rr if r['Gpoa']>=200], 'G_lt200':[r for r in rr if r['Gpoa']<200]}
        results[name]={group:{m:scores(rows,m,p0) for m in MODELS} for group,rows in groups.items()}
        for month in sorted({r['month'] for r in rr}):
            subset=[r for r in rr if r['month']==month]
            for m in MODELS:monthly.append({'cohort':name,'month':month,'model':m,**scores(subset,m,p0)})
    dump(out/'metrics.json',results);table(out/'monthly_metrics.csv',monthly)
    a=results['main']['all'];mg=results['main']['G_ge200'];counts={
        'raw_rows':len(allrows),'finite_prediction_rows':len(pred),'main_rows':len(cohorts['main']),
        'raw_status':{s:sum(r['status']==s for r in allrows) for s in sorted({r['status'] for r in allrows})},
        'outside_lab_GT_range_main':sum(r['outside_lab_GT_range'] for r in cohorts['main']),
        'observed_dates':len({r['time'][:10] for r in allrows}),'fitted_outdoor_parameters':0}
    monthlywins=[]
    for month in sorted({r['month'] for r in cohorts['main']}):
        d={r['model']:r for r in monthly if r['cohort']=='main' and r['month']==month}
        monthlywins.append({'month':month,'n':d['B_G']['n'],'mae_improves':d['M_T0']['mae_W']<d['B_G']['mae_W'],
                            'rmse_improves':d['M_T0']['rmse_W']<d['B_G']['rmse_W']})
    summary={'scope':p['object'],'counts':counts,'main_all':a,'main_G_ge200':mg,
             'M_T0_vs_B_G_reduction':{key:1-a['M_T0'][key]/a['B_G'][key] for key in ('mae_W','rmse_W')},
             'positive_component_criterion':all(a['M_T0'][key]<a['B_G'][key] for key in ('mae_W','rmse_W')),
             'monthly_primary_improvement':monthlywins,'not_validated':p['not_validated'],
             'sensitivity_is_not_model_selection':'M_T3 and IV-flagged sensitivity retained, never substituted for primary result.'}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','python':platform.python_version(),'protocol_sha256':sha(path),
                           'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
if __name__=='__main__':main()
