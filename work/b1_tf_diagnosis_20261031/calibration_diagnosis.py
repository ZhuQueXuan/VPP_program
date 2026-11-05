"""Saved-score calibration diagnosis. No model fitting or threshold adoption."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,hashlib,math,re
from collections import Counter,defaultdict
import numpy as np
from scipy.stats import beta,betabinom,binom,ks_2samp,spearmanr

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'work/b1_unknown_reference_pilot_20261031'
FACT=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
HASH={};CHECK=Counter()
def read(p):
    p=Path(p);HASH[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text(encoding='utf8'))
def ck(name,value):
    assert value,name;CHECK[name]+=1
def near(name,a,b):ck(name,bool(np.allclose(a,b,rtol=1e-10,atol=1e-10)))
def uid_index(uid):return int(uid.rsplit('-user-',1)[1])
def dist(a):
    a=np.asarray(a,float)
    return dict(n=len(a),mean=float(a.mean()),std=float(a.std()),min=float(a.min()),max=float(a.max()),quantiles={str(p):float(np.quantile(a,p)) for p in (.1,.25,.5,.75,.9,.95,.975,.99)})
def rawscan(x):
    x=np.asarray(x)[15:45]
    return float(max(np.max(np.convolve(x,np.ones(k),mode='valid'))/np.sqrt(k) for k in (1,3,5,10,15,30)))

protocol=read(OLD/'protocol.json');freeze=read(OLD/'freeze.json')
for path,h in freeze['source_identity'].items():ck('frozen main source unchanged',hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h)
methods=('tf_standard','tf_gls','cpop','cpop_meter_sigma')
phase_data={};event_info={};stage_fields={}
stages=('train','reference_validation','process_development','calibration','test')
for phase in stages:
    d=protocol['stages'][phase];seeds=d.get('seeds',[d.get('seed')]);events=[];users={}
    for seed in seeds:
        variant='null' if phase=='test' else 'non_event'
        fs=read(FACT/phase/f'{seed}_{variant}_facts.json')
        ts=read(OLD/'evaluator'/phase/f'{seed}_{variant}_truth.json')
        refs=None
        if phase=='calibration':refs=read(OLD/'references'/'calibration.json')['prediction']
        if phase=='test':refs=read(OLD/'references'/f'test_{seed}.json')['prediction']
        if phase=='reference_validation':refs=read(OLD/'reference_validation_predictions'/'lgbm_leaves7.json')['prediction']
        if phase=='process_development':
            err=read(OLD/'development_error_model.json')
            refs=np.asarray(err['residuals'])+np.asarray([f['power_kw'] for f in fs])
        for i,(f,t) in enumerate(zip(fs,ts)):
            w=f['reference_window'];task=f['task'];uid=task['user_id'];idx=uid_index(uid)
            ck('same fact/truth task',task['task_id']==t['task_id'])
            ck('legal information cutoff',max(w[k] for k in ('pre_available_min','prior_available_min','calendar_available_min','temperature_available_min'))<=task['notice_min'])
            ck('whole-week shift preserves calendar',w['clock_hour']==(task['start_min']%1440)/60 and w['weekday']==int(task['start_min']//1440)%7)
            row=dict(seed=seed,task_id=task['task_id'],user_id=uid,user_index=idx,event_index=int(task['task_id'].rsplit('-event-',1)[1]),weekday=w['weekday'],clock_hour=w['clock_hour'],temperature_c=w['temperature_c'],prefix_mean_kw=float(np.mean(w['pre_power_kw'])),historical_mean_kw=float(np.mean(w['prior_mean_kw'])),observed_task_mean_kw=float(np.mean(f['power_kw'][15:45])),notice_min=task['notice_min'],label_complete_min=f['availability']['power_records_available_at_min'])
            if refs is not None:
                reference=np.asarray(refs[i]);natural=np.asarray(t['true_reference_kw']);e=reference-natural;y=reference-np.asarray(f['power_kw'])
                near('non-event/no-action meter equation',f['power_kw'],natural+np.asarray(t['measurement_error_kw']))
                row.update(reference_bias_task_kw=float(e[15:45].mean()),reference_rmse_task_kw=float(np.sqrt(np.mean(e[15:45]**2))),reference_bias_full_kw=float(e.mean()),residual_bias_task_kw=float(y[15:45].mean()),raw_scan=rawscan(y),raw_task_above_bins=int(np.sum(y[15:45]>=.15)))
            events.append(row);event_info[task['task_id']]=row
            users.setdefault(uid,[]).append(row)
    ck('two tasks per stage user',all(len(v)==2 for v in users.values()))
    fields=dict(users=len(users),events=len(events),user_index_range=[min(v['user_index'] for v in events),max(v['user_index'] for v in events)],weekday_user_counts=dict(Counter(str(v[0]['weekday']) for v in users.values())),clock_user_counts=dict(Counter(str(v[0]['clock_hour']) for v in users.values())),first_notice=min(v['notice_min'] for v in events),last_label_complete=max(v['label_complete_min'] for v in events))
    for k in ('temperature_c','prefix_mean_kw','historical_mean_kw','observed_task_mean_kw','reference_bias_task_kw','reference_rmse_task_kw','raw_scan'):
        if k in events[0]:fields[k]=dist([v[k] for v in events])
    stage_fields[phase]=fields;phase_data[phase]=dict(events=events,users=users)

maincal=read(OLD/'event_calibration.json');metercal=read(OLD/'sensitivity_calibration.json')
score_tables={};results={};false_sets={}
for method in methods:
    co=read(OLD/'sensitivity_calibration_outputs.json') if method=='cpop_meter_sigma' else read(OLD/'calibration_outputs'/f'{method}.json')
    cal_event=defaultdict(list)
    for o in co:
        near('saved cal scan independently recomputed',o['scan_score'],rawscan(o['prediction']))
        cal_event[o['user_id']].append(o)
    cal_scores={u:max(x['scan_score'] for x in rows) for u,rows in cal_event.items()}
    ck('48 calibration users',len(cal_scores)==48)
    ck('stored calibration maxima unchanged',cal_scores==(metercal['maxima'] if method=='cpop_meter_sigma' else maincal[method]['user_maxima']))
    threshold=sorted(cal_scores.values())[-2]
    to=[]
    for seed in protocol['stages']['test']['seeds']:
        path=OLD/'sensitivity_outputs'/'test'/f'{seed}_null.json' if method=='cpop_meter_sigma' else OLD/'outputs'/'test'/f'{seed}_null_{method}.json'
        to.extend(read(path))
    test_event=defaultdict(list)
    for o in to:
        near('saved test scan independently recomputed',o['scan_score'],rawscan(o['prediction']))
        pv=(1+sum(v>=o['scan_score'] for v in cal_scores.values()))/49
        near('test pvalue exact',pv,o['evidence_p'])
        ck('test decision agrees with second-largest cal',bool(o['evidence_status']=='evidence')==bool(o['scan_score']>threshold))
        test_event[o['user_id']].append(o)
    test_scores={u:max(x['scan_score'] for x in rows) for u,rows in test_event.items()}
    ck('128 test user blocks',len(test_scores)==128)
    false={u for u,s in test_scores.items() if s>threshold};false_sets[method]=false
    rawfalse={u for u,es in test_event.items() if any(o['features']['cumulative_response_seconds']>0 for o in es)}
    cal_table=[];test_table=[]
    for phase,scores,ev,target in [('calibration',cal_scores,cal_event,cal_table),('test',test_scores,test_event,test_table)]:
        for uid,s in sorted(scores.items(),key=lambda x:(-x[1],x[0])):
            info=phase_data[phase]['users'][uid]
            target.append(dict(user_id=uid,user_index=uid_index(uid),seed=info[0]['seed'],score_max=s,events=[dict(task_id=o['task_id'],score=o['scan_score'],rank_p=(1+sum(v>=o['scan_score'] for v in cal_scores.values()))/49) for o in ev[uid]],above_original_threshold=s>threshold,weekday=info[0]['weekday'],clock_hour=info[0]['clock_hour'],max_reference_bias_task_kw=max(x['reference_bias_task_kw'] for x in info),max_raw_scan=max(x['raw_scan'] for x in info)))
    score_tables[method]=dict(calibration_descending=cal_table,test_descending=test_table)
    ca=np.array(list(cal_scores.values()));te=np.array(list(test_scores.values()));ks=ks_2samp(ca,te,method='exact')
    cal32=[v for u,v in cal_scores.items() if uid_index(u)<32];cal16=[v for u,v in cal_scores.items() if uid_index(u)>=32]
    matched=ks_2samp(cal32,te,method='exact')
    assoc=spearmanr([x['score_max'] for x in test_table],[x['max_reference_bias_task_kw'] for x in test_table])
    conditional=[]
    for weekday in range(7):
        crows=[x for x in cal_table if x['weekday']==weekday];trows=[x for x in test_table if x['weekday']==weekday]
        conditional.append(dict(weekday=weekday,cal_users=len(crows),test_users=len(trows),test_evidence_false_users=sum(x['above_original_threshold'] for x in trows),cal_score_mean=float(np.mean([x['score_max'] for x in crows])) if crows else None,test_score_mean=float(np.mean([x['score_max'] for x in trows])) if trows else None))
    results[method]=dict(original_threshold_second_largest=threshold,cal_score_unique=len(set(ca.tolist())),cal_score_distribution=dist(ca),test_score_distribution=dist(te),test_users=len(te),false_users=len(false),false_user_rate=len(false)/128,false_events=sum(o['evidence_status']=='evidence' for o in to),n_events=256,
        raw_duration_false_users=len(rawfalse),evidence_and_raw_false_users=len(false&rawfalse),evidence_false_without_positive_duration_users=len(false-rawfalse),raw_false_without_evidence_users=len(rawfalse-false),
        original_threshold_test_descending_rank=sum(te>threshold)+1,cal_top5=cal_table[:5],test_top5=test_table[:5],false_user_ids=sorted(false),
        descriptive_score_KS=dict(statistic=float(ks.statistic),pvalue=float(ks.pvalue),not_exchangeability_proof=True),
        calibration_index0_31_distribution=dist(cal32),calibration_index32_47_distribution=dist(cal16),
        original_second_largest_equals_index0_31_max=bool(threshold==max(cal32)),weekday_conditional_descriptors=conditional,
        matched_index_score_KS=dict(statistic=float(matched.statistic),pvalue=float(matched.pvalue),not_recalibration=True),
        score_vs_reference_positive_bias_spearman=dict(r=float(assoc.statistic),pvalue=float(assoc.pvalue),association_not_cause=True),
        ideal_beta_binomial_P_K_ge_observed=float(betabinom.sf(len(false)-1,128,2,47)),
        fixed_q005_binomial_tail_for_contrast_only=float(binom.sf(len(false)-1,128,.05)),
        fixed_q2over49_binomial_tail_for_contrast_only=float(binom.sf(len(false)-1,128,2/49)))

overlap=[]
for i,a in enumerate(methods):
    for b in methods[i+1:]:
        inter=false_sets[a]&false_sets[b];union=false_sets[a]|false_sets[b]
        overlap.append(dict(method_a=a,method_b=b,intersection=len(inter),union=len(union),jaccard=len(inter)/len(union),shared_user_ids=sorted(inter)))
common=set.intersection(*false_sets.values());anyfalse=set.union(*false_sets.values())
common_info=[]
for uid in sorted(anyfalse):
    infos=phase_data['test']['users'][uid]
    common_info.append(dict(user_id=uid,seed=infos[0]['seed'],user_index=uid_index(uid),weekday=infos[0]['weekday'],clock_hour=infos[0]['clock_hour'],methods=[m for m in methods if uid in false_sets[m]],events=infos))

# Pure label permutations of frozen per-user scores. All methods use the same
# permutations to preserve cross-method dependence. No replacement calibration
# file is written and no threshold from this diagnostic is adopted.
cal_ids=sorted(score_tables['tf_gls']['calibration_descending'],key=lambda x:x['user_id']);test_ids=sorted(score_tables['tf_gls']['test_descending'],key=lambda x:x['user_id'])
order=[v['user_id'] for v in cal_ids+test_ids]
matrix=np.empty((176,4))
for j,m in enumerate(methods):
    lookup={v['user_id']:v['score_max'] for part in score_tables[m].values() for v in part}
    matrix[:,j]=[lookup[u] for u in order]
rng=np.random.default_rng(2026103105);N=5000;counts=np.empty((N,4),int)
for i in range(N):
    perm=rng.permutation(176);c=matrix[perm[:48]];t=matrix[perm[48:]]
    th=np.partition(c,-2,axis=0)[-2]
    counts[i]=np.sum(t>th,axis=0)
perm_results={}
obs=np.array([results[m]['false_users'] for m in methods])
for j,m in enumerate(methods):
    perm_results[m]=dict(repeats=N,seed=2026103105,mean_false_users=float(counts[:,j].mean()),quantile_05_50_95=np.quantile(counts[:,j],[.05,.5,.95]).tolist(),tail_P_K_ge_observed_plus1=float((1+np.sum(counts[:,j]>=obs[j]))/(N+1)),observed_false_users=int(obs[j]))
perm_joint=float((1+np.sum(np.all(counts>=obs,axis=1)))/(N+1))

theory=dict(assumptions='Ideal continuous iid user-block scores conditional on the proper trained model; marginal rank validity needs exchangeability. Actual calendar-mixture imbalance is separately reported.',n_cal_users=48,n_test_users=128,tail_order_r=2,tail_probability_distribution='Beta(2,47)',test_count_distribution='BetaBinomial(128,2,47)',marginal_false_probability=2/49,expected_test_count=float(betabinom.mean(128,2,47)),test_count_sd=float(betabinom.std(128,2,47)),test_count_central95=betabinom.ppf([.025,.975],128,2,47).tolist(),fixed_calibration_q_quantiles={str(p):float(beta.ppf(p,2,47)) for p in (.5,.9,.95,.975)},probability_calibration_q_exceeds_005=float(beta.sf(.05,2,47)),probability_calibration_q_exceeds_010=float(beta.sf(.10,2,47)),pac_target=dict(epsilon=.05,delta=.05,meaning='With probability >=.95 over new calibration cohorts, frozen threshold population user-FPR<=.05; not conditional-on-every-calibration guarantee'))
pac=[]
for n in (48,59,64,93,96,128):
    allowed=[r for r in range(1,n+1) if binom.cdf(r-1,n,.05)<=.05]
    r=max(allowed) if allowed else 0
    marginal_r=int(math.floor(.05*(n+1)+1e-12))
    pac.append(dict(n_cal_users=n,max_finite_tail_order_for_95confidence_FPR005=r,tail_upper95_for_maximum=float(beta.ppf(.95,1,n)),standard_marginal_tail_order=marginal_r,standard_marginal_q_upper95=float(beta.ppf(.95,marginal_r,n-marginal_r+1)) if marginal_r else None,selected_PAC_q_upper95=float(beta.ppf(.95,r,n-r+1)) if r else None))
theory['minimum_n_for_maximum_threshold_PAC95_005']=next(n for n in range(1,1000) if binom.cdf(0,n,.05)<=.05)
theory['minimum_n_for_second_largest_threshold_PAC95_005']=next(n for n in range(2,1000) if binom.cdf(1,n,.05)<=.05)
theory['PAC_order_table']=pac

calwd=stage_fields['calibration']['weekday_user_counts'];tewd=stage_fields['test']['weekday_user_counts']
TV=.5*sum(abs(calwd.get(str(k),0)/48-tewd.get(str(k),0)/128) for k in range(7))
shift=dict(known_calendar_covariate_shift=True,weekday_mixture_total_variation=TV,calibration48_vs_test32_per_seed='Generator fixes task_start=200000+180*user_index+20160*event. Whole-week shifts preserve weekday. Calibration includes indices32..47, each test block excludes them.',natural_generator_calendar_effect='Natural power depends on random user/day offset, trend, relative-time sinusoid and temperature; it does not directly depend on weekday/absolute date. The learned tree nevertheless includes weekday/clock, so conditional forecast-error shifts can occur. Calendar mix imbalance alone does not prove it caused the excess.',absolute_time_shift='Stages deliberately shifted by whole weeks; no explicit calendar-time concept drift is in the generator. Do not infer seasonal drift merely from large numerical timestamps.',stage_fields=stage_fields)
for p,h in HASH.items():ck('all inputs read-only SHA unchanged',hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h)
result=dict(schema='b1.tf-calibration-diagnosis.v1',scope='Already-seen pilot saved scores and facts only; 5000 diagnostic permutations are not new fitted-model trials or new performance samples, and no alternative threshold is adopted.',methods=results,overlap=overlap,common_all_four_users=sorted(common),union_false_users=len(anyfalse),false_users_context=common_info,permutation=perm_results,permutation_all_methods_at_least_observed=perm_joint,theory=theory,shift=shift,raw_scores_rank_tables=score_tables,checks=dict(CHECK),n_checks=sum(CHECK.values()),input_sha256=HASH,analysis_notes=['Initial diagnostic serializer encountered a NumPy int64 after numerical calculations; partial output is retained as calibration_diagnosis.failed_serialization.json and native scalar conversion was added. No numerical assertions changed.','First complete diagnostic is retained as calibration_diagnosis.v1.json; this version adds raw-duration/evidence cross-tabs and known-weekday descriptors without changing original pilot decisions.'],limitations=['One fixed calibration cohort. No cause percentages can be assigned to finite calibration variance, calendar mixture and reference error from this analysis.','Unstratified permutations erase the known calendar allocation; they are descriptive exchangeability diagnostics, not proof of no distribution shift.','Test scores are already seen; no permutation threshold or PAC choice may be adopted or evaluated as a new independent test here.','No new model fit, process optimization, recalibration artifact or production change.'])
def native(v):
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
result=native(result)
out=HERE/'calibration_diagnosis.json'
with out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(native(dict(methods={m:{k:v for k,v in r.items() if k in ('original_threshold_second_largest','false_users','false_user_rate','false_events','descriptive_score_KS','matched_index_score_KS','ideal_beta_binomial_P_K_ge_observed','score_vs_reference_positive_bias_spearman')} for m,r in results.items()},overlap=[{k:v for k,v in r.items() if k!='shared_user_ids'} for r in overlap],common_all_four=len(common),union_false_users=len(anyfalse),permutation=perm_results,theory=theory,weekday_TV=TV,weekday_counts={p:stage_fields[p]['weekday_user_counts'] for p in stages},n_checks=sum(CHECK.values()),input_files=len(HASH))),ensure_ascii=False,indent=2))
