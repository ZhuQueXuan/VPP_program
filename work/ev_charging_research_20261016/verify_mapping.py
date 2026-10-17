"""Independent pandas raw sampling, vector fit and all reported metrics."""
from mapping_common import *
import sys,zipfile,math
for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015'):
    sys.path.insert(0,str(ROOT/d))
import numpy as np
import pandas as pd
run=BASE/'runs/BL_EV_MAPPING_01';replay=BASE/'runs/BL_EV_MAPPING_02';prep=BASE/'runs/PREP_EV_MAPPING_01'
dest=run/'verification.json';assert not dest.exists()
pp=BASE/'common_command_mapping_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'common_command_mapping_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
ad=load(prep/'admission.json');assert all(sha(prep/n)==h for n,h in ad['outputs'].items())
saved=pd.read_csv(prep/'samples.csv',keep_default_na=False);split=load(prep/'trial_split.json');frames=[];clockdiff=0
with zipfile.ZipFile(ROOT/p['sources']['archive']['path']) as z:
    for meta in split:
        with z.open(meta['member']) as f:
            df=pd.read_csv(f,sep=';',skiprows=[1],usecols=['epoch','P_kocos_200','AC_Power_set_ID2','AC_Power_set_ID3','AC_Power_set_ID4'])
        t=df.epoch;delta=t.diff();newhigh=t>t.cummax().shift(1).fillna(-np.inf)
        stepok=delta.between(0,2000,inclusive='right');stepok.iloc[0]=True
        start=(~stepok)|(newhigh&~newhigh.shift(1,fill_value=True));start.iloc[0]=True
        block=t.where(start).ffill();warm=(t-block<5000)|~newhigh
        u=df[['AC_Power_set_ID2','AC_Power_set_ID3','AC_Power_set_ID4']]
        common=u.eq(u.iloc[:,0],axis=0).all(axis=1)
        mask=newhigh&stepok&~warm&common&u.iloc[:,0].ge(0)&np.isfinite(df.to_numpy()).all(axis=1)
        sr=saved[saved.member.eq(meta['member'])].reset_index(drop=True);assert len(sr)==len(df)
        assert np.array_equal(sr.status.eq('admitted'),mask)
        checks={'epoch_not_new_high':~newhigh,'epoch_step_not_continuous':~stepok,'clock_warmup':warm,'commands_not_common':~common}
        for flag,m in checks.items():assert np.array_equal(sr['flags'].str.split('|').apply(lambda x:flag in x),m);clockdiff+=len(df)
        assert np.allclose(sr.epoch_ms.astype(float),t,rtol=0,atol=0)
        assert np.allclose(sr.actual_grid_kW.astype(float),df.P_kocos_200,rtol=0,atol=1e-12)
        rr=pd.DataFrame({'member':meta['member'],'record_index':np.arange(1,len(df)+1),'group':meta['group'],'split':meta['split'],
            'mode':meta['mode'],'common_command_kW':u.iloc[:,0],'actual_grid_kW':df.P_kocos_200,'epoch_ms':t})[mask]
        frames.append(rr)
raw=pd.concat(frames,ignore_index=True);assert len(raw)==262154
for group,rr in raw.groupby('group'):
    assert rr[rr.split.eq('train')].epoch_ms.max()<rr[rr.split.eq('test')].epoch_ms.min()
cal=load(run/'calibration.json');capdiff=0.;lossdiff=0.
for group,rr in raw[raw.split.eq('train')].groupby('group'):
    x=rr.common_command_kW.to_numpy();y=rr.actual_grid_kW.to_numpy();w=(1/rr.member.map(rr.member.value_counts())).to_numpy()
    levels=np.unique(np.r_[0.,x]);cand=list(levels)
    for low,high in zip(levels[:-1],levels[1:]):
        sel=x>low
        if sel.any():cand.append(float(np.clip(np.average(y[sel],weights=w[sel]),low,high)))
    cc=np.asarray(cand);loss=np.array([np.average((np.minimum(x,c)-y)**2,weights=w) for c in cc]);idx=np.lexsort((-cc,loss))[0]
    old=cal[group];capdiff=max(capdiff,abs(float(cc[idx])-old['fitted_breakpoint_kW']));lossdiff=max(lossdiff,abs(float(loss[idx])-old['objective_experiment_equal_MSE_kW2']))
assert capdiff<1e-9 and lossdiff<1e-9
pred=pd.read_csv(run/'predictions.csv');test=raw[raw.split.eq('test')].reset_index(drop=True)
assert pred[['member','record_index']].to_dict('records')==test[['member','record_index']].to_dict('records')
for key in ('common_command_kW','actual_grid_kW','epoch_ms'):assert np.allclose(pred[key],test[key],rtol=0,atol=1e-12)
c=pred['group'].map({g:r['fitted_breakpoint_kW'] for g,r in cal.items()}).to_numpy()
pdiff=float(np.max(abs(pred.M_CAP-np.minimum(pred.common_command_kW,c))));assert pdiff<1e-10
assert np.array_equal(pred.B_SET,pred.common_command_kW)
checks=0;metricdiff=0.
def check(rr,m,s):
    global checks,metricdiff
    if not len(rr):assert int(s['n'])==0;return
    e=rr[m].to_numpy()-rr.actual_grid_kW.to_numpy();ae=np.sort(abs(e));worst=rr.iloc[np.argmax(abs(e))]
    dd={'mae_kW':np.mean(ae),'rmse_kW':np.sqrt(np.mean(e*e)),'bias_kW':np.mean(e),'p95_abs_kW':ae[math.ceil(.95*len(ae))-1],
        'max_abs_kW':ae[-1],'worst_epoch_ms':worst.epoch_ms,'worst_actual_kW':worst.actual_grid_kW,'worst_prediction_kW':worst[m]}
    assert int(s['n'])==len(rr) and s['worst_member']==worst.member and int(s['worst_record_index'])==worst.record_index
    assert int(s['negative_actual_rows'])==sum(rr.actual_grid_kW<0) and int(s['negative_predictions'])==sum(rr[m]<0)
    for k,v in dd.items():metricdiff=max(metricdiff,abs(float(s[k])-float(v)));checks+=1
metrics=load(run/'metrics.json');bins={'all':pred,'AC':pred[pred['mode'].eq('AC')],'DC':pred[pred['mode'].eq('DC')],
    'command_zero':pred[pred.common_command_kW.eq(0)],'command_positive':pred[pred.common_command_kW.gt(0)]}
for group,rr in bins.items():
    for m in ('B_SET','M_CAP'):check(rr,m,metrics[group][m])
gg=pd.read_csv(run/'group_metrics.csv')
for s in gg.to_dict('records'):
    rr=pred[pred[s['group_type']].eq(s['key'])];check(rr,s['model'],s)
assert metricdiff<1e-9
summary=load(run/'summary.json');comp=load(run/'comparisons.json')
assert summary['predeclared_positive_criterion']==all(metrics[g]['M_CAP'][k]<metrics[g]['B_SET'][k] for g in ('all','AC','DC') for k in ('mae_kW','rmse_kW'))
for typ,field in (('group','groups_both_improve'),('member','trials_both_improve')):
    assert summary[field]==sum(r['mae_kW_improves'] and r['rmse_kW_improves'] for r in comp if r['group_type']==typ)
for m in ('B_SET','M_CAP'):
    for k in ('mae_kW','rmse_kW'):
        value=gg[gg.group_type.eq('member')&gg.model.eq(m)][k].mean();assert abs(value-summary['experiment_equal_mean_metrics'][m][k])<1e-10
art=load(run/'receipt.json')['outputs'];same={n:sha(run/n)==sha(replay/n)==h for n,h in art.items()};assert all(same.values())
# Preserve local original-order context, including all3 commands and un-interpreted state codes.
worst=metrics['all']['M_CAP'];member=worst['worst_member'];record=worst['worst_record_index']
with zipfile.ZipFile(ROOT/p['sources']['archive']['path']) as z:
    with z.open(member) as f:context=pd.read_csv(f,sep=';',skiprows=[1])
context.iloc[max(0,record-11):record+10].to_csv(run/'worst_original_row_context.csv',index=False)
result={'status':'passed','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
 'raw_rows_independently_checked':len(saved),'admitted_rows':len(raw),'training_rows':sum(raw.split.eq('train')),'test_rows':len(pred),
 'independent_raw_parser':'pandas vs stdlib CSV','independent_clock':'vector cumulative watermark/segment construction vs original-row state machine',
 'clock_flag_membership_checks':clockdiff,'fitting_method':'vector candidate stationary points and experiment-equal objectives, no runner/kernel import',
 'max_breakpoint_difference_kW':capdiff,'max_training_objective_difference_kW2':lossdiff,'max_prediction_difference_kW':pdiff,
 'metric_numeric_checks':checks,'max_metric_difference_kW':metricdiff,'replay_artifacts_equal':same,'verifier_sha256':sha(Path(__file__)),
 'limits':'Static same-row mapping only. State/connector enums and physical timing remain unverified; not independent new experimental truth.'}
dump(dest,result);print(json.dumps(result,ensure_ascii=False,indent=2))
