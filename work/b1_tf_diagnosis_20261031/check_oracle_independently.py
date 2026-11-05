"""Read-only oracle arithmetic/certificate check: no estimator or R call."""
from pathlib import Path
from collections import defaultdict,Counter
import csv,json,hashlib,time
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PILOT=ROOT/'work/b1_unknown_reference_pilot_20261031'
DATA=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
hashes={};checks=Counter();maximum=defaultdict(float)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return json.loads(path.read_text(encoding='utf-8'))
def text(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return path.read_text(encoding='utf-8-sig')
def ck(name,value):
    if not bool(value):raise AssertionError(name)
    checks[name]+=1
def near(name,a,b,tol=1e-10):
    a=np.asarray(a,float);b=np.asarray(b,float)
    err=float(np.max(np.abs(a-b))) if a.size else 0.
    maximum[name]=max(maximum[name],err)
    ck(name,a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all() and err<=tol)

def run():
    tick=time.perf_counter();diag=read(HERE/'oracle_diagnosis.json')
    curves=read(HERE/'oracle_curves.json');metrics=read(HERE/'oracle_metrics.json')
    design=read(HERE/'diagnostic_design.json');freeze=read(PILOT/'freeze.json')
    error=read(PILOT/'development_error_model.json');selection=read(PILOT/'process_selection.json')
    for p,h in freeze['source_identity'].items():ck('frozen pilot source SHA unchanged',sha(ROOT/p)==h)
    for p,h in freeze['artifact_sha256'].items():ck('frozen pilot artifact SHA unchanged',sha(ROOT/p)==h)
    for p,h in diag['input_sha256'].items():ck('oracle recorded input SHA unchanged',sha(ROOT/p)==h)
    sample=[];saved={}
    for seed in (7610500,7610501,7610502,7610503):
        refs=read(PILOT/'references'/f'test_{seed}.json')
        for variant in ('strong','weak','null'):
            facts=read(DATA/'test'/f'{seed}_{variant}_facts.json')
            truth=read(PILOT/'evaluator'/'test'/f'{seed}_{variant}_truth.json')
            out={m:read(PILOT/'outputs'/'test'/f'{seed}_{variant}_{m}.json') for m in ('tf_standard','tf_gls')}
            out['cpop_meter']=read(PILOT/'sensitivity_outputs'/'test'/f'{seed}_{variant}.json')
            for i in range(16):
                f,t=facts[i],truth[i];task=t['task_id'];ck('fixed first16 task identity',f['task']['task_id']==task==refs['task_ids'][i])
                b=np.asarray(t['true_reference_kw']);r=np.asarray(t['true_reduction_kw']);noise=np.asarray(t['measurement_error_kw']);p=np.asarray(f['power_kw'])
                near('factual generation identity',p,b-r+noise,1e-12)
                ywith=b-p;ynone=r.copy();yorig=np.asarray(refs['prediction'][i])-p
                near('true-reference same-noise intervention',ywith,r-noise,1e-12)
                near('noise-removal-only intervention',ynone-ywith,noise,1e-12)
                sample.append(dict(seed=seed,variant=variant,task_id=task,truth=t,fact=f,
                    signals={'saved_reference_with_noise':yorig,'true_reference_with_noise':ywith,'true_reference_no_noise':ynone}))
                for method,v in out.items():saved[(seed,variant,task,method)]=v[i]
    ck('192 variants 64 base tasks',len(sample)==192 and len({(s['seed'],s['task_id']) for s in sample})==64)
    counts=Counter((s['seed'],s['variant']) for s in sample);ck('unselected 16 per seed scenario',set(counts.values())=={16})
    items={(s['seed'],s['variant'],s['task_id']):s for s in sample}
    conditions=('saved_reference_with_noise','true_reference_with_noise','true_reference_no_noise')
    methods=('tf_standard','tf_gls','cpop_meter')
    def key(r):return (r['seed'],r['variant'],r['task_id'],r['condition'],r['method'])
    C={key(c):c for c in curves};M={key(m):m for m in metrics}
    ck('exactly all1728 curve/metric keys',len(curves)==len(metrics)==len(C)==len(M)==1728 and set(C)==set(M))
    ck('complete method-condition factorial',set(C)=={(*k,c,m) for k in items for c in conditions for m in methods})
    covariance=np.array(error['covariance']);covariance=(covariance+covariance.T)/2
    scalar=np.eye(60)*error['scalar_variance']
    covs={'tf_gls':covariance,'tf_standard':scalar}
    inverses={m:np.linalg.inv(cov) for m,cov in covs.items()}
    D=np.zeros((58,60));j=np.arange(58);D[j,j]=1.;D[j,j+1]=-2.;D[j,j+2]=1.
    recomputed=[]
    for k,c in C.items():
        seed,variant,task,condition,method=k;s=items[(seed,variant,task)];t=s['truth'];y=s['signals'][condition]
        pred=np.array(c['prediction']);true=np.array(t['true_reduction_kw']);ck('full finite60 curves',pred.shape==(60,) and np.isfinite(pred).all())
        if condition=='saved_reference_with_noise':
            old=saved[(seed,variant,task,method)];ck('saved original curve exact',c['prediction']==old['prediction'])
            sol=old['solver'] if method!='cpop_meter' else None
        else:sol=c['solver']
        if method!='cpop_meter':
            lam=selection['chosen'][method]['penalty'];cov=covs[method];u=np.array(sol['dual_solution'])
            ck('same lambda full covariance/scalar policy',sol['penalty']==lam and sol['covariance_kind']==('full_covariance' if method=='tf_gls' else 'isotropic_variance'))
            near('stored TF primal reconstruction fixed covariance',pred,y-cov@D.T@u,1e-11)
            ck('dual bound fixed original lambda',np.max(np.abs(u))<=lam+1e-10)
            delta=pred-y
            primal=float(.5*delta@inverses[method]@delta+lam*np.sum(abs(D@pred)))
            dual=float(u@(D@y)-.5*u@(D@cov@D.T@u))
            near('stored TF primal objective',primal,sol['primal'],1e-8)
            near('stored TF dual objective',dual,sol['dual'],1e-8)
            ck('fixed objective certificate remains optimal',abs(primal-dual)<=sol['gap_tolerance'])
            grad=D@cov@D.T@u-D@y
            eps=min(.25*lam,1e-9*max(1.,lam));upper=u>=lam-eps;lower=u<=-lam+eps
            residual=grad.copy();residual[upper]=np.maximum(grad[upper],0);residual[lower]=np.minimum(grad[lower],0)
            ck('fixed objective dual KKT',max(np.max(abs(residual)),max(0.,np.max(abs(u))-lam))<=sol['kkt_tolerance'])
            ck('solver success and no raw fallback',sol['success'] is True and sol['raw_fallback'] is False and sol['observation_operator']=='identity_on_native_interval_means')
        actual=true[15:45]>=.15;fit=pred[15:45]>=.15
        fp=int(np.sum(fit&~actual));fn=int(np.sum(~fit&actual));bias=int(fit.sum()-actual.sum())*60
        expected=dict(physical_action=t['physical_action'],threshold_positive=t['threshold_positive'],weak_subtype=t.get('weak_subtype'),
            true_duration_seconds=float(actual.sum()*60),pred_duration_seconds=float(fit.sum()*60),
            duration_bias_seconds=float(bias),duration_error_seconds=float(abs(bias)),false_positive_bins=fp,false_negative_bins=fn,
            task_curve_mse=float(np.mean((pred[15:45]-true[15:45])**2)),mean_error_kw=float(np.mean(pred[15:45]-true[15:45])),
            rebound_error_kwh=float(abs(np.maximum(-pred[45:],0).sum()-np.maximum(-true[45:],0).sum())/60))
        for field,value in expected.items():
            if isinstance(value,(bool,str)) or value is None:ck('metric truth binding',M[k][field]==value)
            else:near('curve-to-metric full numeric replay',M[k][field],value,1e-12)
        ck('FP FN duration identity',bias==(fp-fn)*60)
        recomputed.append(dict(seed=seed,variant=variant,condition=condition,method=method,**expected))
    # Independently verify retained native-R input and reconstruct every clean CP curve.
    native_checked=0
    for timing in diag['timings']:
        condition=timing['condition'];directory=Path(timing['backend']['artifact_dir'])
        input_rows=list(csv.DictReader(text(directory/'input.csv').splitlines()))
        segments=list(csv.DictReader(text(directory/'segments.csv').splitlines()))
        by_input=defaultdict(list);by_seg=defaultdict(list)
        for r in input_rows:by_input[int(r['case_id'])].append(r)
        for r in segments:by_seg[int(r['case_id'])].append(r)
        ck('192 native cases complete',set(by_input)==set(by_seg)==set(range(192)))
        for i,s in enumerate(sample):
            ins=by_input[i];segs=by_seg[i];ck('exact60 native trained points sigma05',len(ins)==60 and all(float(v['sigma'])==.05 and int(v['train'])==1 for v in ins))
            near('native input intervention signal',[float(v['y']) for v in ins],s['signals'][condition],1e-12)
            x=np.arange(-14.5,45.,1.);near('unchanged native grid',[float(v['x']) for v in ins],x,0.)
            nonempty=[v for v in segs if float(v['x1'])>float(v['x0'])];pred=np.full(60,np.nan)
            for q,v in enumerate(nonempty):
                ck('native segment status',v['status']=='ok')
                a,b=float(v['x0']),float(v['x1']);mask=(x>=a-1e-9)&(x<=b+1e-9)
                if q==0:mask|=x<a
                if q==len(nonempty)-1:mask|=x>b
                pred[mask]=float(v['gradient'])*x[mask]+float(v['intercept'])
            c=C[(s['seed'],s['variant'],s['task_id'],condition,'cpop_meter')]
            near('all native CP curves from saved segments',pred,c['prediction'],1e-12)
            ck('native CP cost/knots metadata',c['solver']['native_cost']==float(segs[0]['native_cost']) and c['solver']['native_knots']==len(segs)-1)
            native_checked+=1
    rsource=text(ROOT/'B1算法/b1_algorithm/process/cpop_batch.R')
    ck('frozen original CP beta/grid/algorithm source',all(v in rsource for v in ('grid=tr$x','beta=2*log(nrow(tr))','sd=tr$sigma[1]','minseglen=0','prune.approx=FALSE')))
    grouped=defaultdict(list)
    for r in recomputed:grouped[(r['variant'],r['condition'],r['method'])].append(r)
    summary=[]
    for s in diag['summary']:
        k=(s['variant'],s['condition'],s['method']);rs=grouped[k];positive=[r for r in rs if r['threshold_positive']];noaction=[r for r in rs if not r['physical_action']]
        expect=dict(n=len(rs),duration_mae_seconds=float(np.mean([r['duration_error_seconds'] for r in rs])),
            duration_bias_seconds=float(np.mean([r['duration_bias_seconds'] for r in rs])),threshold_positive=len(positive),
            misses=sum(r['pred_duration_seconds']==0 for r in positive),no_action=len(noaction),
            false_positive_tasks=sum(r['pred_duration_seconds']>0 for r in noaction),
            fp_bins=sum(r['false_positive_bins'] for r in rs),fn_bins=sum(r['false_negative_bins'] for r in rs),
            task_curve_rmse_kw=float(np.sqrt(np.mean([r['task_curve_mse'] for r in rs]))))
        for field,value in expect.items():near('all27 summary groups replay',value,s[field],1e-12)
        summary.append(dict(variant=k[0],condition=k[1],method=k[2],**expect))
    ck('all27 groups present',len(summary)==27 and len(grouped)==27)
    for p,h in hashes.items():ck('all read inputs remain identical',sha(ROOT/p)==h)
    receipt=dict(status='passed',scope='Independent read-only oracle metrics, signal interventions, TF certificates and native CP retained artifacts; no fit or R execution',
        sample=dict(base_tasks=64,paired_variants=192,original_users=32,seed_blocks=4,selection='first16 records/first8users per old block'),
        curves_checked=1728,metrics_checked=1728,summary_groups_checked=27,TF_certificates_checked=1152,native_CP_cases_checked=native_checked,
        n_checks=sum(checks.values()),checks=dict(checks),max_abs_residual=dict(maximum),summary=summary,
        original_recorded_inputs=len(diag['input_sha256']),input_sha256=hashes,
        fixed_parameters=dict(tf_gls_lambda=selection['chosen']['tf_gls']['penalty'],tf_standard_lambda=selection['chosen']['tf_standard']['penalty'],
            scalar_variance=error['scalar_variance'],covariance_source='original frozen development_error_model.json',cp_sigma=.05,cp_beta='2log60'),
        no_estimator_called=True,no_R_called=True,no_new_selection=True,
        limits=['Oracle reference is unavailable in practice; no deployability evidence.',
            'Input-cleaning conditions keep covariance and regularization fixed, so this is a conditional intervention, not a newly optimized clean-data model.',
            'Interactions invalidate additive causal percentages of error reductions.',
            'Subset is already seen, 64 unique tasks, not192 independent tasks or new test.'],seconds=time.perf_counter()-tick)
    with (HERE/'oracle_independent_check.json').open('x',encoding='utf-8') as out:json.dump(receipt,out,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(status='passed',checks=sum(checks.values()),curves=1728,native_CP_cases=native_checked,files=len(hashes),seconds=receipt['seconds'])))

if __name__=='__main__':run()
