"""Independent saved-output/real-sample audit; never calls an estimator."""
import sys,os,json,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import numpy as np
HERE=Path(__file__).resolve().parents[2];ROOT=HERE.parents[1];OUT=Path(__file__).resolve().parent
input_hash={};checks=Counter();maximum=defaultdict(float)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()
def track(p):input_hash[Path(p).relative_to(ROOT).as_posix()]=sha(p)
def read(p):track(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(k,x):
    checks[k]+=1
    if not x:raise AssertionError(k)
def near(k,a,b,tol=1e-9):
    if a is None or b is None:ck(k,a is b);return
    a=np.asarray(a,float);b=np.asarray(b,float);ck(k+'_shape',a.shape==b.shape)
    error=float(np.max(np.abs(a-b))) if a.size else 0.
    maximum[k]=max(maximum[k],error);ck(k,np.isfinite(a).all() and np.isfinite(b).all() and error<=tol)

cases=read(HERE/'real_cases.json');prep=read(HERE/'real_preparation_receipt.json')
sel=read(HERE/'real_selection.json');proto=read(HERE/'real_comparison_protocol.json')
receipt=read(HERE/'real_comparison_receipt.json');saved=read(HERE/'real_outputs.json')
metrics=read(HERE/'real_metrics.json');summary=read(HERE/'real_summary.json');inputs=read(HERE/'real_perturbed_inputs.json')
for name,h in receipt['original_inputs_sha256'].items():track(HERE/name);ck('original_prepared_input_sha',sha(HERE/name)==h)
for name,h in receipt['source_sha256'].items():track(HERE/name);ck('comparison_source_sha',sha(HERE/name)==h)
for name,h in prep['source_sha256'].items():track(ROOT/name);ck('original_source_sha',sha(ROOT/name)==h)
ck('original_cases_sha',sha(HERE/'real_cases.json')==prep['cases_sha256'])
ck('all_selected_retained',len(cases)==len(sel['selected'])==144 and {c['event_id'] for c in cases}=={c['event_id'] for c in sel['selected']})
ck('all_cases_available',all(c['status']=='ok' for c in cases))
ck('recording_direction_denominators',len({c['recording'] for c in cases})==18 and set(Counter((c['recording'],c['direction']) for c in cases).values())=={4})
for g in sel['groups']:ck('uniform_selection',g['indices']==[j*(g['eligible']-1)//3 for j in range(4)])
for c in cases:
    ck('seconds_progress_units',c['time_unit']=='seconds' and c['signal_unit']=='dimensionless_command_normalized_current')
    ck('no_fake_reference',c['counterfactual_reference_available'] is False and c['latent_truth_available'] is False and c['RIDE_formal_API_status']=='not_applicable')
    p=ROOT/c['raw_trace_npz'];track(p);ck('raw_npz_sha',sha(p)==prep['raw_trace_sha256'][c['raw_trace_npz']])
    with np.load(p,allow_pickle=False) as raw:
        t=raw['relative_time_us'];I=raw['phase_current_A'];u=raw['command_A'];before=t<0
        ck('raw_time_gap',np.all(np.diff(t)>0) and np.max(np.diff(t))<=50000 and t.min()>=-5000000 and t.max()<15000000)
        near('pre_original_median',np.median(I[before]),c['pre_current_A'])
        ck('raw_command_direction',np.all(u[before]==c['previous_command_A']) and np.all(u[~before]==c['new_command_A']))
        ix=(t+5000000)//100000;counts=np.bincount(ix,minlength=200);means=np.bincount(ix,weights=I,minlength=200)/counts
        near('independent_bin_means',means,c['current_mean_A']);near('bin_counts',counts,c['bin_counts'],0)
        prog=np.sign(c['step_A'])*(means-c['pre_current_A'])/abs(c['step_A'])
        near('independent_progress',prog,c['progress'])
        diff=np.diff(np.asarray(c['progress'])[:50]);rob=float(np.median(np.abs(diff-np.median(diff)))/(.6744897501960817*np.sqrt(2)))
        estimate=rob if rob>0 else float(np.std(diff,ddof=1)/np.sqrt(2))
        near('pre_noise_sigma',max(.001,estimate),c['noise_sigma_progress'])
    near('starts_seconds',c['starts_s'],np.arange(-50,150)/10,1e-12)
    near('ends_seconds',c['ends_s'],np.arange(-49,151)/10,1e-12)

bycase={c['event_id']:c for c in cases};rng=np.random.default_rng(7621300)
expected_inputs=[]
for c in cases:
    y=np.asarray(c['progress']);z=rng.normal(0,.03,len(y));spike=z.copy()
    index=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False)
    spike[index]+=rng.choice([-1.,1.],2)*.30
    for condition,arr in [('original_observation',y),('added_gaussian',y+z),('added_gaussian_and_spikes',y+spike)]:
        expected_inputs.append((c,condition,arr,index))
ck('input_output_counts',len(inputs)==len(saved)==432 and len(metrics)==1728)

def features(c,x):
    # Independently derive interval counts and first qualifying grid starts.
    values=np.asarray(x,float);s=np.asarray(c['starts_s']);post=np.flatnonzero(s>=0)
    indices90=post[values[post]>=.9]
    runs=[];run=0
    for i in post:
        run=run+1 if values[i]>=.9 else 0;runs.append(run)
    def start(level):
        indices=[i for i in post if s[i]<=10+1e-9 and values[i]>=level]
        return float(s[indices[0]]) if indices else None
    return dict(t10_seconds=start(.1),t90_seconds=start(.9),target_duration_seconds=float(len(indices90)/10),
      longest_target_seconds=float(max(runs)/10),steady_error_progress=float(np.median(values[s>=10])-1),
      peak_progress=float(max(values[post])),tracking_rmse_progress=float(np.sqrt(sum((values[post]-1)**2)/len(post))))

metricmap={(m['event_id'],m['condition'],m['method']):m for m in metrics}
recomputed=[];features_by_method={};D=np.diff(np.eye(200),n=2,axis=0);rejections=[];solver_records=[]
for j,(c,condition,y,index) in enumerate(expected_inputs):
    inp=inputs[j];out=saved[j]
    ck('input_identity',inp['event_id']==c['event_id']==out['event_id'] and inp['condition']==condition==out['condition'])
    near('perturbation_exact_replay',inp['y'],y,0)
    sigma=c['noise_sigma_progress'] if condition=='original_observation' else float(np.hypot(c['noise_sigma_progress'],.03))
    near('condition_noise_sigma',inp['sigma'],sigma,0)
    ck('two_post_spike_indices',inp['added_spike_indices']==(index.tolist() if condition=='added_gaussian_and_spikes' else []))
    basefeatures=features(c,c['progress'])
    for method,result in out['results'].items():
        row=metricmap[(c['event_id'],condition,method)];ck('all_metric_identity',row['recording']==c['recording'] and row['direction']==c['direction'] and row['status']==result['status'])
        new=dict(event_id=c['event_id'],recording=c['recording'],condition=condition,method=method,status=result['status'],seconds=result.get('seconds',0))
        if method=='tf_standard':
            u=np.asarray(result['dual_solution']);x=y-sigma**2*D.T@u
            P=float(.5*np.sum((x-y)**2)/(sigma**2)+4*np.sum(np.abs(D@x)))
            dual=float(u@(D@y)-.5*sigma**2*np.sum((D.T@u)**2));gap=P-dual
            near('TF_primal_recomputed',P,result['primal'],2e-8);near('TF_dual_recomputed',dual,result['dual'],2e-8)
            near('TF_gap_recomputed',gap,result['raw_gap'],2e-8)
            near('TF_scalar_covariance_condition',result['covariance_condition_number'],1.)
            ck('TF_all_numerically_finite',result['success'] and result['finite'] and np.isfinite(x).all())
            grad=sigma**2*D@D.T@u-D@y;btol=4e-9
            grad[u>=4-btol]=np.maximum(grad[u>=4-btol],0);grad[u<=-4+btol]=np.minimum(grad[u<=-4+btol],0)
            near('TF_KKT_recomputed',np.max(np.abs(grad)),result['kkt_residual'],1e-9)
            cert=dict(event_id=c['event_id'],condition=condition,sigma=sigma,status=result['status'],reason=result['reason'],
                raw_gap=result['raw_gap'],gap_tolerance=result['gap_tolerance'],gap_ratio=result['raw_gap']/result['gap_tolerance'],
                kkt=result['kkt_residual'],kkt_tolerance=result['kkt_tolerance'],success=result['success'],finite=result['finite'],
                solver_status=result['solver_status'],solver_message=result['solver_message'])
            solver_records.append(cert)
            if result['status']!='ok':
                ck('TF_rejections_not_replaced',result['prediction'] is None and 'features' not in row and 'reason' in row)
                ck('TF_rejection_math_gate',not result['gap_pass'] and result['raw_gap']>result['gap_tolerance'])
                rejections.append(cert)
            else:
                near('TF_accepted_prediction_reconstructed',x,result['prediction'])
                ck('TF_accepted_math_gate',result['gap_pass'] and result['kkt_pass'])
        if result['status']=='ok':
            f=features(c,result['prediction']);features_by_method[(c['event_id'],condition,method)]=f
            ck('feature_keys',set(f)==set(row['features'])==set(basefeatures)==set(row['original_observation_features']))
            for k in f:
                near('all_feature_recomputation',f[k],row['features'][k]);near('original_observation_reference_features',basefeatures[k],row['original_observation_features'][k])
            new.update(features=f)
            for k in ('t10_seconds','t90_seconds'):
                disagreement=(f[k] is None)!=(basefeatures[k] is None)
                absolute=abs(f[k]-basefeatures[k]) if f[k] is not None and basefeatures[k] is not None else None
                ck('crossing_status_disagreement',row[k+'_status_disagreement']==disagreement)
                near('conditional_crossing_difference',absolute,row[k+'_absolute_difference'])
                new[k+'_status_disagreement']=disagreement;new[k+'_absolute_difference']=absolute
            for k in ('target_duration_seconds','longest_target_seconds','steady_error_progress','peak_progress','tracking_rmse_progress'):
                diff=abs(f[k]-basefeatures[k]);near('feature_difference_to_observation',diff,row[k+'_absolute_difference']);new[k+'_absolute_difference']=diff
            rms=float(np.sqrt(np.mean((np.asarray(result['prediction'])-np.asarray(c['progress']))**2)))
            near('curve_difference_to_observation',rms,row['curve_difference_rms_progress']);new['curve_difference_rms_progress']=rms
        recomputed.append(new)

summary_map={(x['condition'],x['method']):x for x in summary};re_summary=[]
for condition in proto['conditions']:
    for method in proto['methods']:
        rr=[r for r in recomputed if r['condition']==condition and r['method']==method];valid=[r for r in rr if r['status']=='ok']
        old=summary_map[(condition,method)];ck('full_summary_denominator',len(rr)==old['n']==144 and len(valid)==old['available'])
        out=dict(condition=condition,method=method,n=144,available=len(valid),unavailable=144-len(valid),
          conditional_available_fraction=len(valid)/144)
        for k in ('target_duration_seconds_absolute_difference','longest_target_seconds_absolute_difference','steady_error_progress_absolute_difference','curve_difference_rms_progress','seconds'):
            mean=float(np.mean([r[k] for r in valid]));near('summary_means_recomputed',mean,old[k]);out[k]=mean
        for k in ('t10_seconds','t90_seconds'):
            disagreement=sum(r[k+'_status_disagreement'] for r in valid);ck('summary_status_counts',disagreement==old[k+'_status_disagreement'])
            values=[r[k+'_absolute_difference'] for r in valid if r[k+'_absolute_difference'] is not None]
            mean=float(np.mean(values)) if values else None;near('summary_conditional_time_means',mean,old[k+'_absolute_difference'])
            ck('summary_conditional_time_denominator',len(values)==old[k+'_paired_present_n'])
            out[k+'_status_disagreement']=disagreement;out[k+'_paired_present_n']=len(values);out[k+'_absolute_difference']=mean
        re_summary.append(out)

# Additional read-only paired descriptions: same method before/after added
# Gaussian, and same Gaussian/sigma before/after exactly two post-window spikes.
paired=[]
for a,b,label in [('original_observation','added_gaussian','method_original_to_Gaussian'),
                  ('added_gaussian','added_gaussian_and_spikes','same_Gaussian_sigma_spike_conditional_effect')]:
    for method in proto['methods']:
        values=[];missing=[]
        for c in cases:
            fa=features_by_method.get((c['event_id'],a,method));fb=features_by_method.get((c['event_id'],b,method))
            if fa is None or fb is None:missing.append(c['event_id']);continue
            values.append(dict(event_id=c['event_id'],longest_change=abs(fb['longest_target_seconds']-fa['longest_target_seconds']),
                duration_change=abs(fb['target_duration_seconds']-fa['target_duration_seconds']),
                t90_status_change=(fa['t90_seconds'] is None)!=(fb['t90_seconds'] is None),
                t90_change=abs(fb['t90_seconds']-fa['t90_seconds']) if fa['t90_seconds'] is not None and fb['t90_seconds'] is not None else None))
        paired.append(dict(comparison=label,method=method,total_records=144,paired_available=len(values),unavailable_pairs=len(missing),
            missing_event_ids=missing,longest_target_absolute_change_seconds=float(np.mean([r['longest_change'] for r in values])),
            target_duration_absolute_change_seconds=float(np.mean([r['duration_change'] for r in values])),
            t90_status_changes=sum(r['t90_status_change'] for r in values),
            t90_present_pairs=sum(r['t90_change'] is not None for r in values),
            t90_absolute_change_conditional_seconds=float(np.mean([r['t90_change'] for r in values if r['t90_change'] is not None]))))

# Confirm real native CPOP saw actual seconds and exactly the shared y/sigma.
backend=receipt['CP_backend'];path=Path(backend['artifact_dir'])/'input.csv';track(path)
with path.open(encoding='utf8',newline='') as f:cp_rows=list(csv.DictReader(f))
ck('native_CP_200bins_each',len(cp_rows)==432*200)
for j,inp in enumerate(inputs):
    c=bycase[inp['event_id']];x=(np.asarray(c['starts_s'])+np.asarray(c['ends_s']))/2
    rr=cp_rows[j*200:(j+1)*200]
    ck('native_CP_ids_train',all(int(r['case_id'])==j and int(r['train'])==1 for r in rr))
    near('native_CP_seconds_x',[float(r['x']) for r in rr],x,0)
    near('native_CP_shared_y',[float(r['y']) for r in rr],inp['y'],0)
    near('native_CP_shared_sigma',[float(r['sigma']) for r in rr],np.full(200,inp['sigma']),0)
labs_input=HERE/'labs/real/input.csv';track(labs_input)
with labs_input.open(encoding='utf8',newline='') as f:ls=list(csv.DictReader(f))
ck('LABS_input_count',len(ls)==432*200)
for j,inp in enumerate(inputs):
    rr=ls[j*200:(j+1)*200];ck('LABS_index_mapping',all(int(r['case_id'])==j and int(r['index'])==k+1 for k,r in enumerate(rr)))
    near('LABS_shared_y',[float(r['y']) for r in rr],inp['y'],0)

rej_summary=dict(n=len(rejections),conditions=dict(Counter(r['condition'] for r in rejections)),
    reasons=dict(Counter(r['reason'] for r in rejections)),all_success_finite=all(r['success'] and r['finite'] for r in rejections),
    solver_status=dict(Counter(str(r['solver_status']) for r in rejections)),
    raw_gap_range=[min(r['raw_gap'] for r in rejections),max(r['raw_gap'] for r in rejections)],
    gap_tolerance_range=[min(r['gap_tolerance'] for r in rejections),max(r['gap_tolerance'] for r in rejections)],
    sigma_range=[min(r['sigma'] for r in rejections),max(r['sigma'] for r in rejections)],
    at_pre_noise_floor=sum(r['sigma']==.001 for r in rejections),
    kkt_failed=sum(r['kkt']>r['kkt_tolerance'] for r in rejections),
    finite_reconstructed_curves_not_used_as_accepted_results=True,
    interpretation='Implementation certificate/termination limitation in transferred200-bin low-noise regime, not proof that the convex TF model lacks a finite mathematical solution.')
for p,h in input_hash.items():ck('all_read_inputs_unchanged',sha(ROOT/p)==h)
result=dict(status='passed',scope='Read-only real-sample, saved-certificates, feature-metric-summary audit, no estimator call.',
    checks=dict(checks),maximum_absolute_difference=dict(maximum),cases=144,recordings=18,perturbed_inputs=432,metric_rows=1728,
    recreated_summary=re_summary,TF_rejections=rej_summary,TF_rejection_details=rejections,
    same_method_paired_feature_changes=paired,input_sha256=input_hash,
    unavailable_records_not_removed_from_full_denominator=True,latent_truth_or_field_accuracy_claim=False,
    reference='original100ms observed-bin descriptors; original~50Hzfeatures remain separate descriptive records',
    important_limits=['Current summary differences mix original denoising shift and perturbation sensitivity; same-method paired changes supplied separately.',
      'Original TF115/144 means are conditional, not all144 superiority evidence.',
      'Artificial two-spike robustness is scenario-specific, not physical-truth accuracy.',
      'TF rejected curves reconstructed only to verify existing certificates, never reinstated in ranking.'])
with (OUT/'real_audit.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(dict(status='passed',checks=dict(checks),maximum_absolute_difference=dict(maximum),TF_rejections=rej_summary,paired=paired),ensure_ascii=False))
