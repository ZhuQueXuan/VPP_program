"""Independent pandas/numpy source parsing and least-squares verification.

Does not import the runner, reuse its fit/sample builder, or modify the protocol.
The numerical check is not an independent site/physical validation.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/teacher_storage_brief_20261014/plot_dependencies'))
import numpy as np
import pandas as pd

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-id',required=True); ap.add_argument('--replay-id',required=True)
    args=ap.parse_args(); run=BASE/'runs'/args.run_id; replay=BASE/'runs'/args.replay_id
    dest=run/'verification.json'; assert not dest.exists()
    protocol_path=BASE/'reconstruction_protocol_v1.json'
    p=json.loads(protocol_path.read_text(encoding='utf-8'))
    assert sha(protocol_path)==json.loads((BASE/'reconstruction_freeze_receipt_v1.json').read_text())['protocol_sha256']
    frames=[]
    for item in p['sources']:
        file=ROOT/item['path']; assert sha(file)==item['sha256']
        df=pd.read_csv(file)
        df['source']=item['path']; df['line']=np.arange(len(df))+2
        frames.append(df)
    df=pd.concat(frames,ignore_index=True)
    t=pd.to_datetime(df['measured_on'],format='%Y-%m-%d %H:%M:%S')
    assert not t.duplicated().any() and df['system_id'].eq(1239).all()
    df['time']=t; df=df.sort_values('time').reset_index(drop=True)
    t=df['time']; y=df[p['fields']['power_W']].to_numpy(float)
    g=df[p['fields']['poa_W_m2']].to_numpy(float); tm=df[p['fields']['module_C']].to_numpy(float)
    gamma=p['parameters']['gamma_per_C']; p0=p['parameters']['pdc0_W']
    exact=(t.dt.minute%15==0)&(t.dt.second==0)&(t.dt.microsecond==0)
    finite=np.isfinite(np.column_stack((y,g,tm))).all(axis=1)
    valid=exact.to_numpy()&finite&(g>=0)&(1+gamma*(tm-25)>0)
    expected=pd.date_range('2019-06-01','2019-07-01',inclusive='left',freq='15min')
    missing=expected.difference(t[exact])
    df['split']=np.where(t<pd.Timestamp('2019-06-21'),'fit','evaluation')
    df['expected_status']=np.where(valid,'admitted','excluded')
    audit=pd.read_csv(run/'all_raw_rows.csv')
    assert np.array_equal(audit['time'],df['measured_on'])
    assert np.array_equal(audit['status'].eq('admitted'),valid)
    assert np.array_equal(audit['split'],df['split'])
    labels=pd.read_csv(run/'expected_labels.csv')
    assert labels['time'].tolist()==expected.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert set(labels.loc[labels.status.eq('missing_label'),'time'])==set(missing.strftime('%Y-%m-%d %H:%M:%S'))
    fit=valid & (t<pd.Timestamp('2019-06-21')).to_numpy()
    x=p0*g/1000; z=x*(1+gamma*(tm-25)); w=x*(tm-25)
    kg=np.linalg.lstsq(x[fit,None],y[fit],rcond=None)[0][0]
    kt=np.linalg.lstsq(z[fit,None],y[fit],rcond=None)[0][0]
    ab=np.linalg.lstsq(np.column_stack((x[fit],w[fit])),y[fit],rcond=None)[0]
    calc={'B_G':kg*x[valid], 'M_T':kt*z[valid], 'B_GT':ab[0]*x[valid]+ab[1]*w[valid]}
    actual=pd.read_csv(run/'predictions.csv')
    assert np.array_equal(actual['time'],df.loc[valid,'measured_on'])
    assert np.allclose(actual['target_W'],y[valid],rtol=0,atol=1e-9)
    diffs={m:float(np.max(np.abs(actual[m].to_numpy()-v))) for m,v in calc.items()}
    assert max(diffs.values())<1e-7
    original=json.loads((run/'metrics.json').read_text())
    maxdiff=0.
    daytable=pd.read_csv(run/'daily_metrics.csv')
    for split in ('fit','evaluation'):
        splitmask=actual['split'].eq(split).to_numpy()
        groups={'all':np.ones(len(actual),dtype=bool), 'irradiance_ge20':g[valid]>=20, 'irradiance_lt20':g[valid]<20}
        for group,mask in groups.items():
            subset=actual[splitmask&mask].reset_index(drop=True)
            for m in calc:
                record=original[split][group][m]
                errors=subset[m].to_numpy()-subset.target_W.to_numpy(); absolute=np.sort(np.abs(errors))
                values={'mae_W':np.mean(absolute), 'rmse_W':np.sqrt(np.mean(errors**2)), 'bias_W':np.mean(errors),
                        'p95_abs_W':absolute[math.ceil(.95*len(errors))-1], 'max_abs_W':absolute[-1]}
                assert record['n']==len(errors)
                for key,v in values.items(): maxdiff=max(maxdiff,abs(record[key]-v))
                worst=int(np.argmax(np.abs(errors)))
                assert record['worst_time']==subset.iloc[worst]['time']
        for date,dd in actual[splitmask].groupby(actual[splitmask]['time'].str[:10]):
            for m in calc:
                rr=daytable[(daytable.date==date)&(daytable.model==m)].iloc[0]
                err=dd[m]-dd.target_W
                assert rr['n']==len(dd)
                maxdiff=max(maxdiff,abs(rr.mae_W-float(np.mean(abs(err)))),abs(rr.rmse_W-float(np.sqrt(np.mean(err**2)))))
    assert maxdiff<1e-7
    artifacts=json.loads((run/'receipt.json').read_text())['outputs']
    assert all(sha(run/name)==h for name,h in artifacts.items())
    replay_same={name:sha(run/name)==sha(replay/name) for name in artifacts}
    assert all(replay_same.values())
    # Post-score diagnostic only: fixed +/- one hour around the worst M_T point.
    # No source changes, re-selection of samples, or new model scores.
    worst=pd.Timestamp(original['evaluation']['all']['M_T']['worst_time'])
    context=df[(t>=worst-pd.Timedelta(hours=1))&(t<=worst+pd.Timedelta(hours=1))]
    context.to_csv(run/'worst_point_source_context.csv',index=False)
    result={'status':'passed','source_files':len(frames),'independent_parser':'pandas.read_csv vs runner stdlib csv',
            'independent_fit':'numpy.linalg.lstsq (SVD) vs runner closed-form sums',
            'numpy':np.__version__,'pandas':pd.__version__,
            'raw_rows':len(df),'admitted_rows':int(valid.sum()),'missing_labels':len(missing),
            'max_prediction_diff_W':diffs,'max_metric_diff_W':float(maxdiff),'replay_artifacts_equal':replay_same,
            'diagnostic_context_rows':len(context),'protocol_sha256':sha(protocol_path),
            'verifier_sha256':sha(Path(__file__)),
            'limits':'Checks source selection, prediction/fit arithmetic and deterministic replay; not physical sensor calibration or independent generalisation.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
