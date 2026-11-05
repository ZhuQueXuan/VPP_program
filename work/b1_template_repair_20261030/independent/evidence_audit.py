"""Audit completed frozen simulation evidence without running any estimator."""
from pathlib import Path
import json,csv,hashlib,math
import numpy as np
import pandas as pd
from scipy.stats import t as student_t
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=HERE.parent
checks=0
def require(condition,message):
    global checks
    if not bool(condition):raise AssertionError(message)
    checks+=1
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def close(a,b,tol=1e-9):return math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol)

def means(times,W,s,e):
    """Independent exact areas of three lines, plateau gap, and rectangle."""
    d,ru,hold,dn,wait,rb=times[:6]
    tx=min(d+ru+hold,W);rise_end=min(d+ru,tx)
    level=min(1.,max(0.,(tx-d)/max(ru,1e-9)))
    def cumulative(t):
        if rise_end>d:
            x=np.clip(t-d,0,rise_end-d);area=.5*level*x*x/(rise_end-d)
        else:area=np.zeros_like(t)
        area+=level*np.clip(t-rise_end,0,tx-rise_end)
        if dn>0:
            x=np.clip(t-tx,0,dn);area+=level*(x-.5*x*x/dn)
        if len(times)==8:
            gs,gl=times[6:8];g0=min(rise_end+gs,tx);g1=max(g0,min(rise_end+gs+gl,tx))
            area-=level*np.clip(t-g0,0,g1-g0)
        return area
    pos=(cumulative(e)-cumulative(s))/(e-s)
    start=tx+dn+wait
    neg=np.maximum(0,np.minimum(e,start+rb)-np.maximum(s,start))/(e-s)
    return pos,neg

def main():
    target=HERE/'evidence_review.json'
    if target.exists():raise RuntimeError('preserve previous independent evidence review')
    receipt=read(WORK/'test/receipt.json')
    require(receipt['completed'],'test must be complete before evidence is read')
    assessment=read(WORK/'test/assessment.json')
    protocol=read(WORK/'protocol.json');freeze=read(WORK/'final_candidate_freeze.json')
    before=read(WORK/'before_manifest.json');frozen=read(WORK/'test/source_freeze.json')
    require(freeze['source']==frozen,'test source exactly final candidate freeze')
    for name,expected in frozen.items():
        require(sha(WORK/'test/source'/name)==expected,'snapshot identity '+name)
    unchanged=['B1算法/b1_algorithm/process/_ride_identify.py','B1算法/b1_algorithm/process/_ride_fit.py',
      'B1算法/b1_algorithm/process/_ride_template.py','B1算法/b1_algorithm/process/_cpop.py',
      'B1算法/b1_algorithm/process/cpop_batch.R','B1算法/b1_algorithm/process/_policy.json']
    for name in unchanged:
        require(before['runtime'][name]==frozen[name]==sha(ROOT/name),'untouched original comparator/default '+name)
    for name,expected in before['protected'].items():require(sha(ROOT/name)==expected,'protected '+name)
    metrics=pd.read_csv(WORK/'test/metrics.csv')
    keycols=['seed','panel','scenario','method','task_id']
    require(not metrics.duplicated(keycols).any(),'one metric per method/event')
    lookup={tuple(r[c] for c in keycols):r for r in metrics.to_dict('records')}
    expected_rows=[];all_event_outputs=0;max_curve_error=0.;solver_records=0;failed_solves=0
    native_cache={};fact_variants=0;main_facts=0;stress_facts=0
    for seed in protocol['test']['seeds']:
        specs=[('main','positive',f'{seed}_positive'),('main','zero',f'{seed}_zero'),
               ('stress20','positive',f'{seed}_stress20'),('stress37','positive',f'{seed}_stress37')]
        paired_facts={}
        for panel,scenario,prefix in specs:
            facts=read(ROOT/f'data/B1_template_repair_v1_20261030/test/{prefix}_facts.json')
            truth=read(WORK/f'test/evaluator/{prefix}_truth.json')
            out={method:read(WORK/f'test/events/{prefix}_{method}.json') for method in ('ride_template','ride_revised','cpop')}
            require(all(len(v)==len(facts)==len(truth) for v in out.values()),'all methods retain every event '+prefix)
            require(len(facts)==(128 if panel=='main' else 16),'panel fact count '+prefix)
            fact_variants+=len(facts)
            if panel=='main':
                main_facts+=len(facts);paired_facts[scenario]=facts
            else:stress_facts+=len(facts)
            native_path=Path(out['cpop'][0]['process']['backend']['artifact_dir'])/'input.csv'
            native=pd.read_csv(native_path)
            require(set(native.case_id.unique())==set(np.arange(len(facts))*10),'native original CPOP all cases '+prefix)
            for i,(f,tr) in enumerate(zip(facts,truth)):
                task=f['task'];tid=task['task_id'];W=task['end_min']-task['start_min'];q=task['request_kw']
                s=np.asarray(f['starts_min'])-task['start_min'];e=np.asarray(f['ends_min'])-task['start_min']
                use=(s>=-1e-9)&(e<=W+1e-9);r=np.asarray(tr['true_reduction_kw']);p=np.asarray(f['power_kw'])
                true_dur=float(np.sum(use&(r>=.1*q))*60)
                true_eta=float(np.sum(r[use]*(e-s)[use])/(q*W))
                require(close(true_dur,tr['cumulative_response_seconds']) and close(true_eta,tr['eta']),'independent truth arithmetic '+tid)
                case=native[native.case_id==i*10]
                y=case.y.to_numpy();ref=p+y
                require(len(y)==len(s) and np.allclose(case.x.to_numpy(),(s+e)/2,rtol=0,atol=1e-8),'native case signal/grid '+tid)
                require(np.allclose(case.sigma.to_numpy(),f['noise_sigma_kw']) and (case.train==1).all(),'same declared sigma and no subset '+tid)
                source=dict(task=out['cpop'][i]['task'],starts=f['starts_min'],ends=f['ends_min'],power=f['power_kw'],reference=ref.tolist())
                # Float roundtrips do not preserve digest bytes after p+y. The
                # stored digest equality across all three methods proves their
                # common input binding; raw integral independently uses native y.
                digests=[out[m][i]['input_digest'] for m in out]
                require(len(set(digests))==1,'identical bound input digest '+tid)
                raw_eta=float(np.sum(y[use]*(e-s)[use])/(q*W))
                for method in out:
                    event=out[method][i];all_event_outputs+=1
                    require(event['task']['task_id']==tid and event['status'] in ('ok','degraded'),'retained valid identity '+tid+method)
                    proc=event['process'];curve=np.asarray(proc['reduction_interval_kw'])
                    require(curve.shape==r.shape and np.isfinite(curve).all(),'complete finite curve '+tid+method)
                    duration=float(np.sum(use&(curve>=.1*q))*60)
                    require(close(duration,proc['features']['selected_curve']['cumulative_response_seconds']),'selected duration '+tid+method)
                    require(close(raw_eta,event['outcome']['value']) and event['outcome']['process_fit_used_in_energy'] is False,'unmodified raw eta '+tid+method)
                    delta=duration-true_dur;iszero=true_dur==0
                    row=dict(seed=seed,panel=panel,scenario=scenario,method=method,task_id=tid,
                       duration_mae=abs(delta),duration_bias=delta,curve_rmse=float(np.sqrt(np.mean((curve[use]-r[use])**2))),
                       no_action=int(iszero),false_detection=int(iszero and duration>0),response=int(not iszero),miss=int(not iszero and duration==0),
                       eta_mae=abs(raw_eta-true_eta),fallback=int(event['status']=='degraded'))
                    stored=lookup[(seed,panel,scenario,method,tid)]
                    for name in ('duration_mae','duration_bias','curve_rmse','no_action','false_detection','response','miss','eta_mae','fallback'):
                        require(close(row[name],stored[name]),'recompute metric '+name+tid+method)
                    expected_rows.append(row)
                    if method=='ride_revised' and event['status']=='ok':
                        ev=proc['selection_evidence'];records=ev['solver_records'];idx=ev['selected_solver']
                        require(records[idx]['success'] and records[idx]['accepted'] and records[idx]['termination_status']>0,'selected local solver success '+tid)
                        require(all(not rr['accepted'] or rr['success'] for rr in records),'no unsuccessful solve selected '+tid)
                        solver_records+=len(records);failed_solves+=sum(not rr['accepted'] for rr in records)
                        sig=max(f['noise_sigma_kw'],.001);n=len(y)
                        accepted=[(rr['rss']/sig**2+(8 if rr['structure']==1 else 10)*math.log(n),j) for j,rr in enumerate(records) if rr['accepted']]
                        expected_idx=min(accepted,key=lambda x:(x[0],records[x[1]]['structure']))[1]
                        require(idx==expected_idx,'BIC selects accepted full family '+tid)
                        bestbic=records[idx]['rss']/sig**2+(8 if records[idx]['structure']==1 else 10)*math.log(n)
                        detected=bestbic<float(y@y)/sig**2 and ev['parameters']['positive_ratio']>=.1
                        require(ev['detected']==detected,'null amplitude detection rule '+tid)
                        a,b=means(ev['parameters']['times'],W,s,e)
                        model=q*(ev['parameters']['positive_ratio']*a-ev['parameters']['rebound_ratio']*b)
                        expected=model if detected else np.zeros(n)
                        error=float(np.max(abs(curve-expected)));max_curve_error=max(max_curve_error,error)
                        require(error<1e-8,'independent exact selected curve reconstruction '+tid)
                        expected_cap=max((7.2-float(ref.max()))/q,1e-6)
                        require(close(ev['rebound_max_ratio'],expected_cap),'frozen headroom bound '+tid)
                        require(ev['parameters']['rebound_ratio']<=expected_cap+1e-9,'fitted rebound obeys declared headroom '+tid)
                        require(ev['global_optimum_certified'] is False and ev['detection_error_calibrated'] is False,'limits explicit '+tid)
        pos,zero=paired_facts['positive'],paired_facts['zero']
        require(len(pos)==len(zero),'main mechanism pair count '+str(seed))
        for a,b in zip(pos,zero):
            require(a['task']==b['task'] and a['reference_window']==b['reference_window'] and a['historical_non_event']==b['historical_non_event'],
                    'paired exogenous/reference/history conditions '+a['task']['task_id'])
    require(fact_variants==2304 and main_facts==2048 and stress_facts==256 and all_event_outputs==6912,'all primary and stress evidence counts')
    require(len(expected_rows)==len(metrics)==6912,'no metric omitted or added')
    df=pd.DataFrame(expected_rows);main=df[df.panel=='main']
    block=main.groupby(['seed','method'])[['duration_mae','curve_rmse']].mean().unstack()
    differences=[]
    for comparator in ('cpop','ride_template'):
        for metric in ('duration_mae','curve_rmse'):
            v=block[(metric,'ride_revised')]-block[(metric,comparator)];n=len(v)
            m=float(v.mean());half=float(student_t.ppf(.975,n-1)*v.std(ddof=1)/math.sqrt(n))
            found=next(rr for rr in assessment['paired_block_differences'] if rr['comparator']==comparator and rr['metric']==metric)
            require(close(m,found['mean']) and np.allclose([m-half,m+half],found['MC_t95'],rtol=1e-9,atol=1e-9),'paired block interval '+metric+comparator)
            differences.append(dict(comparator=comparator,metric=metric,mean=m,MC_t95=[m-half,m+half],independent_blocks=n))
    pooled=main.groupby('method')[['duration_mae','curve_rmse']].mean().to_dict('index')
    for method,val in pooled.items():
        for metric,value in val.items():require(close(value,assessment['pooled_main'][method][metric]),'pooled method summary '+method+metric)
    counts=main.groupby('method')[['false_detection','no_action','miss','response']].sum()
    fpr={m:float(v.false_detection/v.no_action) for m,v in counts.iterrows()}
    miss={m:float(v['miss']/v.response) for m,v in counts.iterrows()}
    gain=1-pooled['ride_revised']['duration_mae']/pooled['cpop']['duration_mae']
    interval=next(v['MC_t95'] for v in differences if v['comparator']=='cpop' and v['metric']=='duration_mae')
    gates=dict(primary_at_least10percent=gain>=.1,paired_t95_below_zero=interval[1]<0,
      curveRMSE_within5percent=pooled['ride_revised']['curve_rmse']<=1.05*pooled['cpop']['curve_rmse'],
      empirical_false_detection_excess_at_most2pp=fpr['ride_revised']-fpr['cpop']<=.02,
      empirical_miss_excess_at_most2pp=miss['ride_revised']-miss['cpop']<=.02,all_events_retained=True)
    require(gates==assessment['CPOP_advantage_gate'] and all(gates.values())==assessment['all_CPOP_gates_pass'],'preregistered evidence gates reproduced')
    result=dict(passed=True,n_technical_assertions=checks,scope='complete saved evidence audit, no fit or change to test/source',
       independent_blocks=8,main_factual_variants=main_facts,main_base_events=1024,stress_factual_variants=stress_facts,total_method_outputs=all_event_outputs,
       pooled_main=pooled,paired_block_differences=differences,relative_primary_gain_vs_CPOP=gain,gate=gates,all_gates_pass=all(gates.values()),
       false_detection_rates=fpr,miss_rates=miss,solver_records_audited=solver_records,failed_solver_starts_retained=failed_solves,
       maximum_independent_curve_reconstruction_error=max_curve_error,
       original_comparator_and_default_files_unchanged=len(unchanged),protected_files_unchanged=len(before['protected']),
       scientific_limits=['One finite synthetic EV mechanism with fresh seeds and paired positive/zero mechanisms, not realEV evidence.',
         'Eight independent seed blocks; paired mechanism variants and methods are not independent studies.',
         'Reference error and false detections remain uncalibrated; successful termination is not global optimality.',
         'Rebound headroom cap is a model restriction, not full trajectory physical certification.',
         'Explicit caller ratio override and dropped all-failed-solve diagnostics were identified during frozen trial; subsequent contract-only changes must retain frozen artifacts and prove exact headroom-mode equivalence.'],
       frozen_test_source_sha256=sha(WORK/'test/source_freeze.json'),metrics_sha256=sha(WORK/'test/metrics.csv'))
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','n_technical_assertions','main_factual_variants','stress_factual_variants','total_method_outputs','maximum_independent_curve_reconstruction_error','all_gates_pass')},indent=2))
if __name__=='__main__':main()
