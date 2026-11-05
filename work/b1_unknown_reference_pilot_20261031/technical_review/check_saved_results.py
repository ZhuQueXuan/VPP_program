"""Independent read-only checks of saved TF/CP outputs. No optimizer called."""
import os,sys,json,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import numpy as np
from scipy.linalg import cho_factor,cho_solve
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process.api import prepare,_features
read_hash={};counts=Counter();maxima=defaultdict(float);groups=[]
def read(p):
    p=Path(p);raw=p.read_bytes();read_hash[p.relative_to(ROOT).as_posix()]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode('utf8'))
def record_file(p):
    p=Path(p);read_hash[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
def ck(name,condition):
    counts[name]+=1
    if not condition:raise AssertionError(name)
def near(name,a,b,tol=2e-9):
    aa=np.asarray(a,float);bb=np.asarray(b,float)
    ck(name+'_shape',aa.shape==bb.shape)
    error=float(np.max(np.abs(aa-bb))) if aa.size else 0.
    maxima[name]=max(maxima[name],error)
    ck(name,np.isfinite(aa).all() and np.isfinite(bb).all() and error<=tol)
def compare(a,b):
    if isinstance(a,dict):
        ck('feature_keys',set(a)==set(b))
        for k in a:compare(a[k],b[k])
    elif isinstance(a,(int,float)) and not isinstance(a,bool):near('all_feature_values',a,b)
    else:ck('feature_categorical',a==b)
protocol=read(HERE/'protocol.json');error=read(HERE/'development_error_model.json')
selection=read(HERE/'process_selection.json');freeze=read(HERE/'freeze.json')
for p,h in freeze['source_identity'].items():
    record_file(ROOT/p);ck('frozen_source_sha',read_hash[p]==h)
for p,h in freeze['artifact_sha256'].items():
    record_file(ROOT/p);ck('frozen_artifact_sha',read_hash[p]==h)
supp=read(HERE/'supplement_freeze.json')
for key,filename in [('script_sha256','cpop_sensitivity.py'),('protocol_sha256','supplement_protocol.json'),
                     ('calibration_sha256','sensitivity_calibration.json'),('main_freeze_sha256','freeze.json')]:
    record_file(HERE/filename);ck('supplement_sha',read_hash[(HERE/filename).relative_to(ROOT).as_posix()]==supp[key])
ck('supplement_before_test_declaration',supp['test_generated'] is False and supp['validation_seen'] is True)
Sigma=np.asarray(error['covariance']);isovar=error['scalar_variance'];scale=error['sigma_effective']
near('effective_sigma',scale,np.sqrt(isovar))
residual=np.asarray(error['residuals']);near('scalar_variance',isovar,max(.05**2,float(np.mean(residual**2))))
near('residual_mean_not_fitted_shift',error['residual_mean'],residual.mean(axis=0))
ck('noise_not_added_again',error['meter_noise_already_included'] and not error['mean_bias_corrected'])
chol={'tf_standard':cho_factor(isovar*np.eye(60),lower=True),'tf_gls':cho_factor(Sigma,lower=True)}
cov={'tf_standard':isovar*np.eye(60),'tf_gls':Sigma}
D=np.diff(np.eye(60),n=2,axis=0)
def check_tf(y,fit,prediction,method,penalty):
    x=np.asarray(prediction);u=np.asarray(fit['dual_solution']);S=cov[method]
    ck('tf_status_success_finite',fit['status']=='ok' and fit['success'] and fit['finite'] and fit['gap_pass'] and fit['kkt_pass'])
    ck('tf_penalty_fixed',fit['penalty']==penalty)
    near('tf_primal_stationarity',x,y-S@D.T@u)
    diff=x-y
    primal=float(.5*diff@cho_solve(chol[method],diff)+penalty*np.sum(np.abs(D@x)))
    dual=float(u@(D@y)-.5*u@(D@S@D.T@u));gap=primal-dual
    near('tf_primal_saved',primal,fit['primal'],1e-8)
    near('tf_dual_saved',dual,fit['dual'],1e-8)
    near('tf_gap_saved',gap,fit['raw_gap'],1e-8)
    ck('tf_gap_independent',abs(gap)<=fit['gap_tolerance'])
    ck('tf_dual_bounds',np.max(np.abs(u))<=penalty+1e-10)
    gradient=D@S@D.T@u-D@y
    btol=min(.25*penalty,1e-9*max(1.,penalty))
    gradient[u>=penalty-btol]=np.maximum(gradient[u>=penalty-btol],0)
    gradient[u<=-penalty+btol]=np.minimum(gradient[u<=-penalty+btol],0)
    ck('tf_kkt_independent',np.max(np.abs(gradient))<=fit['kkt_tolerance'])
    maxima['primal_dual_gap_abs']=max(maxima['primal_dual_gap_abs'],abs(gap))
    counts['tf_fits_checked']+=1
for p in sorted((HERE/'development_solver').glob('*.json')):
    method,lam=p.stem.rsplit('_',1);fits=read(p)
    ck('development_fit_count',len(fits)==len(residual))
    for y,fit in zip(residual,fits):check_tf(y,fit,fit['prediction'],method,float(lam))

def facts(phase,seed,variant):return read(ROOT/'data/B1_unknown_reference_pilot_v1_20261031'/phase/f'{seed}_{variant}_facts.json')
stages=[]
for phase in ('calibration','validation','test'):
    design=protocol['stages'][phase]
    for seed in design.get('seeds',[design.get('seed')]):
        reference=read(HERE/'references'/('calibration.json' if phase=='calibration' else f'{phase}_{seed}.json'))
        for variant in design['variants']:
            fs=facts(phase,seed,variant)
            references=reference['prediction'];ck('reference_task_ids',reference['task_ids']==[f['task']['task_id'] for f in fs])
            outs={m:read(HERE/'calibration_outputs'/f'{m}.json' if phase=='calibration' else HERE/'outputs'/phase/f'{seed}_{variant}_{m}.json') for m in ('tf_standard','tf_gls','cpop')}
            meters=read(HERE/'sensitivity_calibration_outputs.json' if phase=='calibration' else HERE/'sensitivity_outputs'/phase/f'{seed}_{variant}.json')
            outs['cpop_meter_sigma']=meters
            for method,rows in outs.items():
                ck('output_count',len(rows)==len(fs))
                for f,ref,row in zip(fs,references,rows):
                    ck('output_identity',row['task_id']==f['task']['task_id'] and row['user_id']==f['task']['user_id'] and row['status']=='ok')
                    origin=f['task']['start_min'];s=np.asarray(f['starts_min'])-origin;e=np.asarray(f['ends_min'])-origin
                    y=np.asarray(ref)-np.asarray(f['power_kw']);x=np.asarray(row['prediction']);req=(s>=0)&(s<30)
                    near('raw_eta_recomputed',row['eta_raw'],np.sum(y[req]*(e-s)[req])/45)
                    near('raw_eta_invariant',row['eta_raw'],outs['cpop'][rows.index(row)]['eta_raw'])
                    duration=float(np.sum(x[req]>=.15)*60)
                    near('cumulative_from_curve',duration,row['features']['cumulative_response_seconds'])
                    runs=[];run=0
                    for yes in x[req]>=.15:
                        run=run+1 if yes else 0;runs.append(run)
                    near('longest_from_curve',max(runs)*60,row['features']['longest_continuous_response_seconds'])
                    near('mean_from_curve',np.mean(x[req]),row['features']['mean_reduction_kw'])
                    near('peak_from_curve',np.max(x[req]),row['features']['peak_reduction_kw'])
                    expected_scan=float(max(np.max(np.convolve(x[req],np.ones(k),mode='valid'))/np.sqrt(k) for k in (1,3,5,10,15,30)))
                    near('scan_from_curve',expected_scan,row['scan_score'])
                    task=dict(f['task']);task.update(start_min=0.,end_min=30.,notice_min=-15.)
                    dat=prepare(s,e,f['power_kw'],ref,task,.05 if method=='cpop_meter_sigma' else scale,
                        dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom'))
                    ff=_features(dat,x)['selected_curve'];ff.update(mean_reduction_kw=float(np.mean(x[req])),peak_reduction_kw=float(np.max(x[req])))
                    compare(ff,row['features'])
                    if method.startswith('tf_'):check_tf(y,row['solver'],row['prediction'],method,selection['chosen'][method]['penalty'])
                    counts['output_rows_checked']+=1
            if phase=='test':
                truth=read(HERE/'evaluator'/phase/f'{seed}_{variant}_truth.json')
                for method,rows in outs.items():
                    group=dict(seed=seed,variant=variant,method=method,n=len(rows),no_action=0,false_positive=0,positive=0,miss=0,abs_error_sum=0.)
                    for row,t in zip(rows,truth):
                        ck('truth_identity',row['task_id']==t['task_id'])
                        noaction=not t['physical_action'];positive=t['threshold_positive'];duration=row['features']['cumulative_response_seconds']
                        group['no_action']+=noaction;group['positive']+=positive;group['false_positive']+=noaction and duration>0
                        group['miss']+=positive and duration==0;group['abs_error_sum']+=abs(duration-t['cumulative_response_seconds'])
                    groups.append(group)
            # Native CPOP both sigma settings: input x/y/train are identical,
            # beta and all other algorithm settings come from frozen R source.
            mainname='calibration_cpop' if phase=='calibration' else f'{phase}_{seed}_{variant}_cpop'
            sensitivityname='calibration' if phase=='calibration' else f'{phase}_{seed}_{variant}'
            native=read(HERE/'native_outputs'/f'{mainname}.json')
            native_meter=read(HERE/'sensitivity_native_outputs'/f'{sensitivityname}.json')
            art=[]
            for originals,sigma in ((native,scale),(native_meter,.05)):
                ck('native_all_original_CPOP',all(o['status']=='ok' and o['process']['method']=='CPOP' for o in originals))
                for o in originals:near('native_sigma_ratio',o['process']['selection_evidence']['request_to_declared_meter_sigma_ratio'],1.5/sigma)
                paths={o['process']['backend']['artifact_dir'] for o in originals};ck('one_native_batch',len(paths)==1)
                inp=Path(next(iter(paths)))/'input.csv';record_file(inp)
                with inp.open(encoding='utf8',newline='') as stream:raw=list(csv.DictReader(stream))
                ck('native_csv_sigma',all(float(a['sigma'])==sigma for a in raw))
                art.append(raw)
            ck('native_same_inputs_except_sigma',len(art[0])==len(art[1]) and all({k:v for k,v in a.items() if k!='sigma'}=={k:v for k,v in b.items() if k!='sigma'} for a,b in zip(*art)))
            counts['native_paired_batches']+=1

rsource=ROOT/'B1算法/b1_algorithm/process/cpop_batch.R';record_file(rsource)
rtext=rsource.read_text(encoding='utf8')
ck('native_configuration_fixed',"beta=2*log(nrow(tr))" in rtext and "sd=tr$sigma[1]" in rtext and "minseglen=0,prune.approx=FALSE" in rtext)
merged=[]
for variant in ('strong','weak','null'):
    for method in ('tf_standard','tf_gls','cpop','cpop_meter_sigma'):
        subset=[g for g in groups if g['variant']==variant and g['method']==method]
        out=dict(variant=variant,method=method)
        for key in ('n','no_action','false_positive','positive','miss','abs_error_sum'):out[key]=sum(g[key] for g in subset)
        out['duration_mae']=out['abs_error_sum']/out['n'];merged.append(out)
for p,h in read_hash.items():ck('read_input_sha_unchanged',hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h)
receipt=dict(status='passed',scope='Read-only saved-output numerical audit; no optimizer/refit, new facts or parameter changes.',
    counts=dict(counts),max_absolute_errors=dict(maxima),test_metrics=merged,input_sha256=read_hash,
    limitations=['Feature serialization re-extracted with unchanged production extractor; duration/longest/mean/peak/scan also independently recomputed.',
      'Full covariance and standard paths differ in lambda and covariance scaling/centering; not a pure covariance-shape ablation.',
      'Supplementary meter-sigma configuration was designed after validation seen, frozen before same test; not independent extra test.',
      'H=I; no interval-average or sub-bin identification gain tested.'])
destination=Path(__file__).with_name('technical_result_receipt.json')
destination.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
print(json.dumps(dict(status=receipt['status'],counts=dict(counts),max_absolute_errors=dict(maxima),test_metrics=merged),ensure_ascii=False))
