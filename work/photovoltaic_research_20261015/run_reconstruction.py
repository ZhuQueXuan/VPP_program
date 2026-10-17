"""Execute the frozen small same-label reconstruction comparison (stdlib only)."""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import csv
import hashlib
import json
import math
import platform

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
MODELS = ('B_G', 'M_T', 'B_GT')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')

def table(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None

def metrics(rows, model):
    if not rows: return {'n':0}
    errors = [r[model]-r['target_W'] for r in rows]
    absolute = sorted(abs(e) for e in errors)
    worst = max(range(len(rows)), key=lambda i:abs(errors[i]))
    return {'n':len(rows), 'mae_W':math.fsum(absolute)/len(rows),
            'rmse_W':math.sqrt(math.fsum(e*e for e in errors)/len(rows)),
            'bias_W':math.fsum(errors)/len(rows),
            'p95_abs_W':absolute[math.ceil(.95*len(rows))-1],
            'max_abs_W':absolute[-1], 'worst_time':rows[worst]['time'],
            'worst_target_W':rows[worst]['target_W'], 'worst_prediction_W':rows[worst][model],
            'negative_predictions':sum(r[model]<0 for r in rows),
            'mae_div_DC_nameplate':math.fsum(absolute)/len(rows)/20160,
            'rmse_div_DC_nameplate':math.sqrt(math.fsum(e*e for e in errors)/len(rows))/20160}

def execute(out):
    protocol_path = BASE/'reconstruction_protocol_v1.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    marker = json.loads((BASE/'reconstruction_freeze_receipt_v1.json').read_text())
    assert sha(protocol_path) == marker['protocol_sha256']
    for item in protocol['sources']+protocol['parameter_evidence']:
        assert sha(ROOT/item['path']) == item['sha256'], item['path']
    dump(out/'protocol_snapshot.json', protocol)
    start = datetime.fromisoformat(protocol['time']['start'])
    end = datetime.fromisoformat(protocol['time']['end_exclusive'])
    cutoff = datetime.fromisoformat(protocol['split']['fit_end_exclusive'])
    params = protocol['parameters']; gamma = params['gamma_per_C']; pdc0 = params['pdc0_W']
    raw, accepted, seen, standard = [], [], set(), set()
    for src in protocol['sources']:
        with (ROOT/src['path']).open(newline='',encoding='utf-8') as f:
            for line, row in enumerate(csv.DictReader(f),2):
                t = datetime.fromisoformat(row['measured_on'])
                assert row['system_id']=='1239' and start<=t<end
                assert t not in seen, t
                seen.add(t)
                y = number(row['ac_power_metered_kw__3015'])
                g = number(row['poa_irradiance__3018'])
                tm = number(row['module_temp_f__3019'])
                is_grid = t.minute%15==0 and t.second==0 and t.microsecond==0
                if is_grid: standard.add(t)
                flags = []
                if not is_grid: flags.append('off_grid')
                if None in (y,g,tm): flags.append('core_nonfinite')
                if g is not None and g<0: flags.append('negative_irradiance')
                if tm is not None and 1+gamma*(tm-25)<=0: flags.append('nonpositive_temperature_factor')
                record = {'source':src['path'], 'line':line, 'time':t.isoformat(sep=' '),
                          'split':'fit' if t<cutoff else 'evaluation',
                          'target_W':y, 'poa_W_m2':g, 'module_C':tm,
                          'status':';'.join(flags) if flags else 'admitted',
                          'negative_target':y is not None and y<0}
                raw.append(record)
                if not flags:
                    x = pdc0*g/1000
                    accepted.append({**record,'x':x, 'w':x*(tm-25), 'z':x*(1+gamma*(tm-25))})
    raw.sort(key=lambda r:r['time']); accepted.sort(key=lambda r:r['time'])
    table(out/'all_raw_rows.csv',raw)
    expected = [start+timedelta(minutes=15*i) for i in range(2880)]
    bytime = {r['time']:r for r in raw if 'off_grid' not in r['status']}
    grid = [{'time':t.isoformat(sep=' '),
             'status':bytime[t.isoformat(sep=' ')]['status'] if t.isoformat(sep=' ') in bytime else 'missing_label'} for t in expected]
    table(out/'expected_labels.csv',grid)
    fit = [r for r in accepted if r['split']=='fit']
    xx = math.fsum(r['x']**2 for r in fit); zz = math.fsum(r['z']**2 for r in fit)
    xy = math.fsum(r['x']*r['target_W'] for r in fit)
    zy = math.fsum(r['z']*r['target_W'] for r in fit)
    xw = math.fsum(r['x']*r['w'] for r in fit)
    ww = math.fsum(r['w']**2 for r in fit)
    wy = math.fsum(r['w']*r['target_W'] for r in fit)
    det = xx*ww-xw*xw
    assert xx>0 and zz>0 and det>0 and det/(xx*ww)>1e-12, 'Rank/fit failure'
    coef = {'B_G':{'k':xy/xx}, 'M_T':{'k':zy/zz,'gamma_per_C':gamma},
            'B_GT':{'a':(xy*ww-wy*xw)/det,'b':(wy*xx-xy*xw)/det},
            'fit_n':len(fit),'last_fit_time':fit[-1]['time'], 'condition_determinant_ratio':det/(xx*ww)}
    assert coef['last_fit_time']<'2019-06-21 00:00:00'
    dump(out/'coefficients.json',coef)
    predictions = []
    for r in accepted:
        predictions.append({k:v for k,v in r.items() if k not in ('x','w','z')} | {
            'B_G':coef['B_G']['k']*r['x'], 'M_T':coef['M_T']['k']*r['z'],
            'B_GT':coef['B_GT']['a']*r['x']+coef['B_GT']['b']*r['w']})
    assert all(math.isfinite(r[m]) for r in predictions for m in MODELS)
    table(out/'predictions.csv',predictions)
    results = {}
    for split in ('fit','evaluation'):
        rows = [r for r in predictions if r['split']==split]
        groups = {'all':rows,'irradiance_ge20':[r for r in rows if r['poa_W_m2']>=20],
                  'irradiance_lt20':[r for r in rows if r['poa_W_m2']<20]}
        results[split] = {g:{m:metrics(rr,m) for m in MODELS} for g,rr in groups.items()}
    dump(out/'metrics.json',results)
    daily = []
    for date in sorted({r['time'][:10] for r in predictions}):
        rows = [r for r in predictions if r['time'][:10]==date]
        for m in MODELS:
            daily.append({'date':date,'split':rows[0]['split'],'model':m,**metrics(rows,m)})
    table(out/'daily_metrics.csv',daily)
    counts = {'raw_rows':len(raw),'standard_labels':len(standard),'off_grid':len(raw)-len(standard),
              'expected_labels':2880, 'missing_labels':len(set(expected)-standard),
              'admitted_rows':len(accepted),'negative_raw_targets':sum(r['negative_target'] for r in raw),
              'negative_admitted_targets':sum(r['negative_target'] for r in accepted),
              'fit_rows':len(fit), 'evaluation_rows':len(accepted)-len(fit),
              'raw_status':{s:sum(r['status']==s for r in raw) for s in sorted({r['status'] for r in raw})}}
    dump(out/'sample_counts.json',counts)
    a=results['evaluation']['all']
    summary = {'scope':protocol['scope'], 'counts':counts,'coefficients':coef,'evaluation':results['evaluation'],
               'M_T_vs_B_G':{metric+'_reduction_fraction':1-a['M_T'][metric]/a['B_G'][metric] for metric in ('mae_W','rmse_W')},
               'positive_component_criterion':all(a['M_T'][metric]<a['B_G'][metric] for metric in ('mae_W','rmse_W')),
               'limits':protocol['not_validated'], 'implementation':'Own direct equations and closed-form least squares; no pvlib installation or full ModelChain reproduction.'}
    dump(out/'summary.json',summary)
    receipt = {'status':'completed','protocol_sha256':sha(protocol_path),'script_sha256':sha(Path(__file__)),
               'python':platform.python_version(),'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    dump(out/'receipt.json',receipt)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run-id',required=True); args=parser.parse_args()
    assert Path(args.run_id).name==args.run_id
    out=BASE/'runs'/args.run_id; out.mkdir(parents=True,exist_ok=False)
    try: execute(out)
    except Exception as e:
        dump(out/'failure.json',{'status':'failed','error':repr(e)}); raise

if __name__=='__main__': main()
