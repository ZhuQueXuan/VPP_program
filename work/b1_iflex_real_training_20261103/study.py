"""Train/validate once per fixed budget, lock, then score the five future dates."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
from pathlib import Path
from collections import defaultdict
import csv,json,sys,time
import numpy as np
import joblib
from models import Design,fit_model
from prepare import HERE,ROOT,DATA,save,sha

P=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
METHODS=list(P['methods']);FEATURE=HERE/'features_peak_history.csv'
TARGET='actual_peak_2h_kwh';KEY=('ID','Group','Date')

def read_rows(splits,augmented=False):
    if sha(DATA/'prepared_P_events.csv')!=P['prepared_data_sha256']:raise ValueError('Prepared data changed')
    history={}
    if augmented:
        with FEATURE.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] not in splits:continue
                k=tuple(r[n] for n in KEY);assert k not in history
                history[k]=r
    rows=[]
    with (DATA/'prepared_P_events.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] not in splits:continue
            assert P['dates_assignment'][r['Date']]==r['split']
            assert all(r[k]=='TRUE' for k in ('complete_peak','signal_matches','price_matches'))
            if augmented:
                h=history[tuple(r[n] for n in KEY)]
                assert h['split']==r['split'] and h['notice_utc']==r['notice_utc'] and h['latest_available_utc']<=r['notice_utc']
                r['mean_peak_history_kwh']=h['mean_peak_history_kwh']
            rows.append(r)
    assert len(rows)==sum(P['counts'][s] for s in splits)
    assert len({tuple(r[k] for k in KEY) for r in rows})==len(rows)
    return rows

def y_values(rows):
    y=np.asarray([float(r[TARGET]) for r in rows]);assert np.isfinite(y).all();return y

def slices(rows,keys):
    grouped=defaultdict(list)
    for i,r in enumerate(rows):grouped['|'.join(r[k] for k in keys)].append(i)
    return dict(sorted(grouped.items()))

def score(rows,y,pred):
    assert len(rows)==len(pred) and np.isfinite(pred).all()
    err=pred-y
    def rmse(v):return float(np.sqrt(np.mean(v*v)))
    def rows_for(keys):
        return {k:dict(rows=len(ids),rmse=rmse(err[ids]),mae=float(np.mean(abs(err[ids]))),
            observed_mean=float(np.mean(y[ids])),prediction_mean=float(np.mean(pred[ids])),
            signed_bias=float(np.mean(err[ids])),dates=len({rows[i]['Date'] for i in ids}))
            for k,ids in slices(rows,keys).items()}
    date=rows_for(('Date',));group=rows_for(('Date','Group'))
    return dict(events=len(rows),dates=len(date),group_days=len(group),
        date_equal_rmse=float(np.mean([r['rmse'] for r in date.values()])),pooled_rmse=rmse(err),
        mae=float(np.mean(abs(err))),group_day_mean_rmse=rmse(np.array([r['signed_bias'] for r in group.values()])),
        per_date=date,per_group_day=group,per_price=rows_for(('nominal_price_level',)),per_group=rows_for(('Group',)))

def write_predictions(path,rows,y,columns):
    fields=['ID','Group','Region','Date','split','nominal_price_level',TARGET,*columns]
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(fields)
        for i,r in enumerate(rows):w.writerow([r[n] for n in fields[:6]]+[float(y[i])]+[float(p[i]) for p in columns.values()])

def configs(method):
    return [dict(alpha=a) for a in P['ridge_alpha_grid']] if method.endswith('ridge') else P['hgb_grid']

def fit_validate(kind):
    aug=kind=='peak';tr=read_rows(['train'],aug);va=read_rows(['validation'],aug)
    y=y_values(tr);yv=y_values(va);design=Design(aug).fit(tr)
    summaries={};predictions={}
    for method in METHODS:
        x=design.transform(tr,method);xv=design.transform(va,method);trials=[]
        for i,cfg in enumerate(configs(method)):
            start=time.perf_counter();model=fit_model(method,cfg,P['hgb_fixed'],x,y)
            pred=model.predict(xv);m=score(va,yv,pred)
            name=f'{method}__cfg{i}';predictions[name]=pred
            trials.append(dict(id=name,params=cfg,score=m,elapsed_seconds=time.perf_counter()-start))
        def rank(r):
            c=r['params'];tie=(-c['alpha'],) if 'alpha' in c else (c['leaves'],-c['l2'])
            return (r['score']['date_equal_rmse'],*tie)
        best=min(trials,key=rank);summaries[method]=dict(best=best,trials=trials)
        print(kind,method,best['params'],round(best['score']['date_equal_rmse'],6),flush=True)
    write_predictions(HERE/f'{kind}_validation_predictions.csv',va,yv,predictions)
    save(HERE/f'{kind}_validation.json',dict(feature_set=kind,train_events=len(tr),validation_events=len(va),
        test_numeric_outcomes_used=False,results=summaries))

def lock_and_refit():
    vs={k:json.loads((HERE/f'{k}_validation.json').read_text(encoding='utf-8'))['results'] for k in ('base','peak')}
    def choose(kind,methods):return min(methods,key=lambda m:(vs[kind][m]['best']['score']['date_equal_rmse'],m))
    ref=choose('base',('linear_ridge','spline_ridge'))
    b=choose('base',P['price_aware']);p=choose('peak',P['price_aware'])
    bval=vs['base'][b]['best']['score']['date_equal_rmse'];pval=vs['peak'][p]['best']['score']['date_equal_rmse']
    kind='peak' if pval<=.99*bval else 'base';chosen=p if kind=='peak' else b
    keys=dict(reference='base__'+ref,best_base_price='base__'+b,best_peak_price='peak__'+p,candidate=kind+'__'+chosen,
        candidate_no_price_control=kind+'__'+('history_hgb' if chosen=='price_hgb' else 'history_ridge'))
    folder=HERE/'frozen_models';folder.mkdir(exist_ok=False)
    files=[HERE/n for n in ('protocol.json','models.py','study.py','prepare.py','features_peak_history.csv','base_validation.json','peak_validation.json')]
    files += [DATA/'prepared_P_events.csv',DATA/'real_data_protocol.json']
    for kind in ('base','peak'):
        tr=read_rows(['train','validation'],kind=='peak');y=y_values(tr);design=Design(kind=='peak').fit(tr)
        for method in METHODS:
            params=vs[kind][method]['best']['params'];x=design.transform(tr,method)
            model=fit_model(method,params,P['hgb_fixed'],x,y)
            name=kind+'__'+method;path=folder/(name+'.joblib')
            joblib.dump(dict(model=model,design=design,method=method,params=params,events=len(y)),path,compress=3)
            files.append(path)
            print('refit',name,len(y),flush=True)
    r=dict(keys=keys,validation_best_price_base=bval,validation_best_price_peak=pval,
        validation_selected_configurations={kind+'__'+m:v[m]['best']['params'] for kind,v in vs.items() for m in METHODS},
        hashes={str(f.relative_to(ROOT)):sha(f) for f in files},test_numeric_outcomes_used=False)
    save(HERE/'selection_freeze.json',r);print(json.dumps(r['keys']),flush=True)

def test_once():
    assert not (HERE/'decision.json').exists()
    f=json.loads((HERE/'selection_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT/p)==v for p,v in f['hashes'].items())
    assert all(sha(ROOT/p)==v for p,v in json.loads((HERE/'formal_before.json').read_text(encoding='utf-8')).items())
    rows={k:read_rows(['test'],k=='peak') for k in ('base','peak')}
    y=y_values(rows['base']);assert np.array_equal(y,y_values(rows['peak']))
    predictions={};scores={}
    for k in ('base','peak'):
        for m in METHODS:
            name=k+'__'+m;state=joblib.load(HERE/'frozen_models'/(name+'.joblib'))
            pred=state['model'].predict(state['design'].transform(rows[k],m))
            predictions[name]=pred;scores[name]=score(rows[k],y,pred)
    c=f['keys']['candidate'];b=f['keys']['reference'];np_control=f['keys']['candidate_no_price_control']
    gain=1-scores[c]['date_equal_rmse']/scores[b]['date_equal_rmse']
    wins=sum(scores[c]['per_date'][d]['rmse']<scores[b]['per_date'][d]['rmse'] for d in scores[b]['per_date'])
    gates=dict(five_date_coverage=scores[c]['dates']==5 and scores[c]['events']==2419,
        gain_at_least_5pct=gain>=.05,date_wins_at_least4=wins>=4)
    decision=dict(status='real_auxiliary_candidate_confirmed' if all(gates.values()) else 'real_auxiliary_gain_not_confirmed',
        selected=f['keys'],gates=gates,date_equal_rmse_gain=gain,dates_won=wins,
        no_price_comparison=dict(control=np_control,relative_gain=1-scores[c]['date_equal_rmse']/scores[np_control]['date_equal_rmse']),
        observed_test_prices=sorted(int(p) for p in scores[c]['per_price']),
        absent_test_price=5,targets='Measured peak-window energy at actually assigned P path only',
        causal_effect_or_EV_duration_validated=False,real_auxiliary_only=True,other_parts_changed=False,default_changed=False,
        test_scored_once=True,all_scores=scores)
    write_predictions(HERE/'test_predictions.csv',rows['base'],y,predictions)
    save(HERE/'decision.json',decision)
    print(json.dumps(dict(status=decision['status'],keys=f['keys'],gain=gain,dates_won=wins,
        date_equal_rmse={n:s['date_equal_rmse'] for n,s in scores.items()},
        price_ablation=decision['no_price_comparison'])),flush=True)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode in ('base','peak'):fit_validate(mode)
    elif mode=='lock':lock_and_refit()
    elif mode=='test':test_once()
    else:raise ValueError(mode)
