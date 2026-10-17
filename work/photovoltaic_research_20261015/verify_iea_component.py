"""Independently parse original CSV and XLSX XML; verify every cohort and metric."""
from pathlib import Path
import argparse,hashlib,json,math,sys,zipfile
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/teacher_storage_brief_20261014/plot_dependencies'))
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--replay-id',required=True);a=ap.parse_args()
    run=BASE/'runs'/a.run_id;replay=BASE/'runs'/a.replay_id
    dest=run/'verification.json';assert not dest.exists()
    path=BASE/'iea_component_protocol_v1.json';p=json.loads(path.read_text(encoding='utf-8'))
    assert sha(path)==json.loads((BASE/'iea_component_freeze_receipt_v1.json').read_text())['protocol_sha256']
    frames=[]
    for src in p['sources']:
        file=ROOT/src['path'];assert sha(file)==src['sha256']
        if file.suffix=='.csv':
            df=pd.read_csv(file,sep=';',skipinitialspace=True)
            df['source']=src['path'];df['line']=np.arange(len(df))+2;frames.append(df)
    df=pd.concat(frames,ignore_index=True)
    df['time']=pd.to_datetime(df.Date+' '+df.Time,format='%d.%m.%Y %H:%M:%S')
    df=df.sort_values('time').reset_index(drop=True);assert not df.time.duplicated().any()
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(BASE/'downloads/IEA_MODULE_SOURCES_01/module_characterization.xlsx') as z:
        tree=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    vals={c.attrib['r']:c.find('s:v',ns).text for c in tree.findall('.//s:c',ns) if c.find('s:v',ns) is not None}
    p0=float(vals['C10']);gamma=float(vals['K9'])/100
    assert float(vals['A10'])==1000 and float(vals['C8'])==25
    assert p0==p['lab_parameters']['p0_W'] and gamma==p['lab_parameters']['gamma_per_C']
    core=df[['Pm','Voc','Isc','Tbom','Gpoa']].to_numpy(float)
    finite=np.isfinite(core).all(axis=1)
    exact=(df.time.dt.minute%5==0)&(df.time.dt.second==0)
    valid=finite & exact.to_numpy() & df.Gpoa.ge(0).to_numpy()
    ivbad=finite & ((df.Pm<0)|(df.Voc<=0)|(df.Isc<=0)|(df.Pm>df.Voc*df.Isc+0.001)).to_numpy()
    raw=pd.read_csv(run/'all_raw_rows.csv');pred=pd.read_csv(run/'predictions_all_finite.csv')
    assert raw.time.tolist()==df.time.dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert np.array_equal(raw.iv_inconsistent,ivbad)
    assert pred.time.tolist()==df.loc[valid,'time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert np.array_equal(pred.main_cohort,~ivbad[valid])
    for field in ('Pm','Gpoa','Tbom','Voc','Isc'):
        assert np.allclose(pred[field],df.loc[valid,field],atol=1e-9,rtol=0)
    g=df.loc[valid,'Gpoa'].to_numpy();tm=df.loc[valid,'Tbom'].to_numpy();x=p0*g/1000
    calculated={'B_G':x,'M_T0':x*(1+gamma*(tm-25)),'M_T3':x*(1+gamma*(tm+3*g/1000-25))}
    diffs={m:float(np.max(np.abs(pred[m]-v))) for m,v in calculated.items()};assert max(diffs.values())<1e-8
    allmetrics=json.loads((run/'metrics.json').read_text());monthly=pd.read_csv(run/'monthly_metrics.csv')
    maxdiff=0.;metric_checks=0
    def check(rows,m,stored):
        nonlocal maxdiff,metric_checks
        e=rows[m].to_numpy()-rows.Pm.to_numpy();a=np.sort(np.abs(e))
        numbers={'mae_W':np.mean(a),'rmse_W':np.sqrt(np.mean(e**2)),'bias_W':np.mean(e),
                 'p95_abs_W':a[math.ceil(.95*len(a))-1],'max_abs_W':a[-1],
                 'mae_div_lab_P0':np.mean(a)/p0,'rmse_div_lab_P0':np.sqrt(np.mean(e**2))/p0}
        assert int(stored['n'])==len(rows)
        for key,value in numbers.items():maxdiff=max(maxdiff,abs(float(stored[key])-float(value)));metric_checks+=1
        worst=int(np.argmax(np.abs(e)));assert stored['worst_time']==rows.iloc[worst].time
        maxdiff=max(maxdiff,abs(float(stored['worst_target_W'])-float(rows.iloc[worst].Pm)),
                    abs(float(stored['worst_prediction_W'])-float(rows.iloc[worst][m])))
    for cohort,rr in (('main',pred[pred.main_cohort]),('all_finite_reference_sensitivity',pred)):
        groups={'all':rr,'G_ge200':rr[rr.Gpoa>=200],'G_lt200':rr[rr.Gpoa<200]}
        for group,sub in groups.items():
            for m in calculated:check(sub.reset_index(drop=True),m,allmetrics[cohort][group][m])
        for month,sub in rr.groupby('month'):
            for m in calculated:
                r=monthly[(monthly.cohort==cohort)&(monthly.month==month)&(monthly.model==m)]
                assert len(r)==1;check(sub.reset_index(drop=True),m,r.iloc[0].to_dict())
    assert maxdiff<1e-8
    artifact=json.loads((run/'receipt.json').read_text())['outputs']
    same={name:sha(run/name)==sha(replay/name) for name in artifact}
    assert all(sha(run/name)==h for name,h in artifact.items()) and all(same.values())
    # Fixed post-score diagnostic, not an exclusion rule or new experiment.
    worst=pd.Timestamp(allmetrics['main']['all']['M_T0']['worst_time'])
    context=df[(df.time>=worst-pd.Timedelta(minutes=15))&(df.time<=worst+pd.Timedelta(minutes=15))]
    context.to_csv(run/'worst_point_source_context.csv',index=False)
    result={'status':'passed','independent_source_parser':'pandas CSV vs stdlib CSV',
            'independent_lab_parser':'XLSX worksheet XML vs openpyxl','source_files':len(p['sources']),
            'raw_rows':len(df),'finite_rows':int(valid.sum()),'main_rows':int((valid&~ivbad).sum()),
            'lab_P0_W':p0,'gamma_per_C':gamma,'outdoor_fitted_parameters':0,
            'prediction_max_diff_W':diffs,'metric_checks':metric_checks,'max_metric_diff_W':maxdiff,
            'replay_artifacts_equal':same,'context_rows':len(context),
            'protocol_sha256':sha(path),'verifier_sha256':sha(Path(__file__)),
            'limit':'Numeric and cohort verification only; not independent module, sensor calibration, cell temperature or site confirmation.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
