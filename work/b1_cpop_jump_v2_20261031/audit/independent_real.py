"""Saved-only real auxiliary audit of finite partitions and descriptors."""
import sys,json,csv,hashlib,importlib.util
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
HELPER=HERE/'audit/independent_synthetic.py'
spec=importlib.util.spec_from_file_location('_independent_v2_partition_audit',HELPER)
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
hashes={};checks=Counter();maximum=0.;dp_maximum=0.
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(name):
    p=Path(name);p=p if p.is_absolute() else HERE/p
    hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(p.read_text(encoding='utf-8'))
def check(v,label):
    assert v,label
    checks[label]+=1
def close(a,b,label,tol=1e-8):
    global maximum
    if a is None or b is None:check(a is None and b is None,label);return
    x=np.asarray(a,float);y=np.asarray(b,float);check(x.shape==y.shape,label+' shape')
    gap=float(np.max(np.abs(x-y))) if x.size else 0.;maximum=max(maximum,gap)
    check(np.isfinite(x).all() and np.isfinite(y).all() and gap<=tol*max(1.,float(np.max(np.abs(y))) if y.size else 1.),label)
def desc(c,pred):
    s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);y=np.asarray(pred);use=(s>=0)&(e<=15.0000001)
    yes=y[use]>=.9;run=best=0
    for v in yes:run=run+1 if v else 0;best=max(best,run)
    def first(level):
        ix=np.flatnonzero((s>=0)&(s<=10.000000001)&(y>=level))
        return float(s[ix[0]]) if len(ix) else None
    return {'t10_seconds':first(.1),'t90_seconds':first(.9),'target_duration_seconds':float(yes.sum()*.1),
       'longest_target_seconds':float(best*.1),'steady_error_progress':float(np.median(y[s>=10])-1),
       'peak_progress':float(y[use].max()),'tracking_rmse_progress':float(np.sqrt(np.mean((y[use]-1)**2)))}
def main():
    global dp_maximum
    protocol=read('protocol.json');receipt=read('real_receipt.json');selection=read('real_selection.json');freeze=read('validation_freeze.json')
    for path,digest in receipt['source_sha256'].items():check(sha(ROOT/path)==digest,'real source SHA unchanged')
    check(receipt['available']==receipt['outputs']==648,'all real648 outputs available')
    check(receipt['original_events']==72 and receipt['input_variants']==216,'72events216variants')
    check(receipt['known_latent_clean_truth'] is False and receipt['new_real_holdout'] is False,'real evidence limits explicit')
    old=read(ROOT/'work/b1_command_feature_selection_20261031/real_cases.json')
    check(sha(ROOT/'work/b1_command_feature_selection_20261031/real_cases.json')==selection['source_sha256'],'old144 source unchanged')
    groups=defaultdict(list)
    for c in old:groups[(c['recording'],c['direction'])].append(c)
    cases=[]
    for key,rr in sorted(groups.items()):
        rr.sort(key=lambda r:(r['edge_index'],r['event_id']));cases.extend([rr[0],rr[-1]])
    check([c['event_id'] for c in cases]==selection['selected_ids'],'first-last selection independently rebuilt')
    check(len(cases)==len({c['event_id'] for c in cases})==72 and len({c['recording'] for c in cases})==18,'72unique events18records')
    inputs=read('real_inputs.json');proposals=read('real_proposals.json');caches=read('real_block_cache.json')
    curves=read('real_curves.json');metrics=read('real_metrics.json');summary=read('real_summary.json');pairs=read('real_paired_stability.json')
    check(len(inputs)==len(caches)==len(curves)==216 and len(metrics)==648,'real all denominators')
    spec=protocol['real_auxiliary'];rng=np.random.default_rng(spec['seed']);method=freeze['selected_method'];ratio=freeze['selected_ratio']
    check(ratio==1. and method=='jump_1p0','unchanged frozen ratio1 on real')
    synthetic_facts=[];lookup={(m['event_id'],m['condition'],m['method']):m for m in metrics};recomputed=[]
    for j,c in enumerate(cases):
        y=np.asarray(c['progress']);g=rng.normal(0,.03,len(y));sp=g.copy()
        ix=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False);sp[ix]+=rng.choice([-1.,1.],2)*.30
        s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);x=(s+e)/2;command=np.where(s<0,c['previous_command_A'],c['new_command_A'])
        reference=desc(c,y)
        for k,condition in enumerate(spec['conditions']):
            i=3*j+k;item=inputs[i];cache=caches[i]['blocks'];actualproposal=proposals[str(i)]
            observed=y if k==0 else y+(g if k==1 else sp)
            sigma=c['noise_sigma_progress'] if k==0 else float(np.hypot(c['noise_sigma_progress'],.03))
            check(item['event_id']==curves[i]['event_id']==caches[i]['event_id']==c['event_id'],'real event binding')
            check(item['condition']==curves[i]['condition']==caches[i]['condition']==condition,'real condition binding')
            close(item['y'],observed,'exact fixed perturbation array',0)
            close(item['sigma'],sigma,'same original sigma or known extra-noise sigma')
            close(item['command'],command,'real recorded command identical')
            synthetic_facts.append({'starts':s,'ends':e,'reference_kw':observed,'power_kw':np.zeros(len(y)),'sigma':sigma})
            expected=h.proposal(observed,x,sigma,command)
            for key in ['nodes','edges','observational_edges','command_edges']:check(actualproposal[key]==expected[key],'real independent proposals '+key)
            for a,b in zip(actualproposal['all_boundary_scores'],expected['all_boundary_scores']):close(a['score'],b['score'],'real independent score')
            entries=h.enumerate_partitions(expected['nodes'],cache,2*np.log(len(y)));full=cache[f'0:{len(y)}'];fit=curves[i]['results'][method]
            objective=min(v+ratio*2*np.log(len(y))*n for v,n,path in entries)
            gap=abs(fit['objective']-objective);dp_maximum=max(dp_maximum,gap);close(fit['objective'],objective,'real exhaustive partition objective',2e-7)
            close(min(v+2*2*np.log(len(y))*n for v,n,path in entries),full['cost'],'real ratio2 dominated control',2e-7)
            path=[0]+fit['jump_boundaries']+[len(y)]
            close(fit['prediction'],np.concatenate([cache[f'{a}:{b}']['prediction'] for a,b in zip(path,path[1:])]),'real selected block reconstruction')
            check(fit['values_and_weights_unchanged'] and fit['zero_jump_CPOP_included'],'unchanged observations and original family inclusion')
            close(curves[i]['results']['cpop']['prediction'],full['prediction'],'real zero-jump literal original CP')
            for m in ['cpop',method,'labs']:
                result=curves[i]['results'][m];row=lookup[(c['event_id'],condition,m)]
                check(row['status']==result['status']=='ok','all648 outputs retained')
                f=desc(c,result['prediction']);r={'event_id':c['event_id'],'condition':condition,'method':m,'features':f,
                      'jump_count':len(result.get('jump_boundaries',[])),'seconds':result['seconds']}
                close(row['seconds'],r['seconds'],'real time bookkeeping');check(row['jump_count']==r['jump_count'],'real jump count')
                for key,value in f.items():close(row['features'][key],value,'independent real descriptor');close(row['original_observed_features'][key],reference[key],'real original observed reference')
                for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
                    r[key+'_difference']=abs(f[key]-reference[key]);close(row[key+'_difference'],r[key+'_difference'],'real observation-reference difference')
                for key in ['t10_seconds','t90_seconds']:
                    a,b=f[key],reference[key];r[key+'_status_difference']=(a is None)!=(b is None);r[key+'_difference']=abs(a-b) if a is not None and b is not None else None
                    check(row[key+'_status_difference']==r[key+'_status_difference'],'real missing time category');close(row[key+'_difference'],r[key+'_difference'],'real conditional time difference')
                recomputed.append(r)
    count=h.native_dictionary('real',synthetic_facts,caches)
    lin=defaultdict(list);lout=defaultdict(list)
    for r in h.table(HERE/'labs/real/input.csv'):lin[int(r['case_id'])].append(float(r['y']))
    for r in h.table(HERE/'labs/real/output.csv'):check(r['status']=='ok','real author LABS status');lout[int(r['case_id'])].append(float(r['fitted']))
    cpdirs=list((HERE/'native/real_original').glob('process_*/input.csv'));check(len(cpdirs)==1,'one original real CP native input')
    cpin=defaultdict(list)
    for r in h.table(cpdirs[0]):cpin[int(r['case_id'])].append(r)
    for i,item in enumerate(inputs):
        close(lin[i],item['y'],'LABS shared real observed y');close(lout[i],curves[i]['results']['labs']['prediction'],'real native LABS output replay')
        close([float(r['y']) for r in cpin[i]],item['y'],'original CP real observed y')
        close([float(r['sigma']) for r in cpin[i]],np.repeat(item['sigma'],200),'original CP same noise metadata')
        close([float(r['x']) for r in cpin[i]],(np.asarray(cases[i//3]['starts_s'])+np.asarray(cases[i//3]['ends_s']))/2,'original CP real seconds grid')
    for saved in summary:
        rr=[r for r in recomputed if r['method']==saved['method'] and r['condition']==saved['condition']]
        check(saved['n']==saved['available']==len(rr)==72,'real summary full72 denominator')
        for key in ['target_duration_seconds_difference','longest_target_seconds_difference','steady_error_progress_difference','jump_count','seconds']:close(saved[key],np.mean([r[key] for r in rr]),'real summary mean')
        for key in ['t10_seconds','t90_seconds']:
            values=[r[key+'_difference'] for r in rr if r[key+'_difference'] is not None]
            check(saved[key+'_paired_present_n']==len(values),'real time conditional denominator')
            check(saved[key+'_status_difference']==sum(r[key+'_status_difference'] for r in rr),'real missing status summary')
            close(saved[key+'_difference'],np.mean(values) if values else None,'real conditional time mean')
    for saved in pairs:
        q={(r['event_id'],r['condition']):r for r in recomputed if r['method']==saved['method']}
        check(saved['n']==saved['available_pairs']==72,'same-method72 pairs')
        for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
            changes=[abs(q[(c['event_id'],'gaussian')]['features'][key]-q[(c['event_id'],'gaussian_plus_spikes')]['features'][key]) for c in cases]
            close(saved[key+'_change'],np.mean(changes),'same-method real added-spike change')
        check(saved['t90_status_flips']==sum((q[(c['event_id'],'gaussian')]['features']['t90_seconds'] is None)!=(q[(c['event_id'],'gaussian_plus_spikes')]['features']['t90_seconds'] is None) for c in cases),'real paired t90 flips')
    hashes.update(h.hashes)
    for path,digest in hashes.items():check(sha(ROOT/path)==digest,'all real read inputs unchanged')
    output={'status':'passed','scope':'Read-only real observation descriptors, fixed perturbations, native blocks and finite-partition audit; no estimator or R called',
       'real_events':72,'recordings':18,'input_variants':216,'metric_rows':648,'all_available':True,
       'native_blocks_checked':count,'exhaustive_partitions_checked':h.partitions,
       'maximum_native_cost_difference':h.cost_maximum,'maximum_DP_difference':dp_maximum,'maximum_other_difference':maximum,
       'checks':dict(checks+h.checks),'n_checks':sum(checks.values())+sum(h.checks.values()),
       'same_method_paired_stability':pairs,'input_sha256':hashes,'no_fit':True,'no_parameter_selection':True,
       'limits':['72 are an explicit subset of existing144 events, not a new real holdout','Original observed100ms descriptors are not latent-clean physical truth',
          'Same-method added-spike stability cannot override failed simulated adoption gate','Current-step progress1 is not necessarily the new absolute current command',
          'Finite dictionary optimum and seconds/current normalization do not imply physical sub-bin timing or net-reduction identification']}
    with (HERE/'audit/independent_real.json').open('x',encoding='utf-8') as f:json.dump(output,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:output[k] for k in ['status','real_events','metric_rows','native_blocks_checked','exhaustive_partitions_checked','maximum_native_cost_difference','maximum_DP_difference','n_checks','same_method_paired_stability']},ensure_ascii=False))
if __name__=='__main__':main()
