"""Independent analytic derivatives and scores from saved new-study outputs."""
from study import *
from scipy.special import expit
from numpy.polynomial.legendre import leggauss
from scipy.optimize import brentq


def oracle(amounts,kind,group=None,nodes=23):
    z,w=leggauss(nodes);l,u,h=np.meshgrid(z,z,.6*z,indexing='ij')
    w1,w2,w3=np.meshgrid(w,w,w,indexing='ij');weight=(w1*w2*w3).ravel()/8
    l=l.ravel();u=u.ravel();h=h.ravel()
    if group=='below':l=(l-1)/2
    if group=='above':l=(l+1)/2
    means=[];derivatives=[]
    for a in amounts:
        if kind=='zero_effect':s=0.;ds=0.
        elif kind=='nonmonotone':s=np.sin(np.pi*a/2.4);ds=np.pi/2.4*np.cos(np.pi*a/2.4)
        else:s=a;ds=1.
        p=expit(-1.5+1.25*s*(1+.35*l)+.5*l-.45*u+.35*h)
        mu=expit(-.6+.8*s+.3*l-.2*u+.15*h);full=expit(-3.+.7*s)
        dp=p*(1-p)*1.25*(1+.35*l)*ds;dm=mu*(1-mu)*.8*ds;df=full*(1-full)*.7*ds
        g=full+(1-full)*mu;dg=df*(1-mu)+(1-full)*dm
        means.append(float(1800*np.sum(weight*p*g)))
        derivatives.append(float(1800*np.sum(weight*(dp*g+p*dg))))
    return np.array(means),np.array(derivatives)


rows=[];max_truth=0.;max_score=0.;threshold_rows=[]
for row in json.loads((HERE/'final/summary.json').read_text(encoding='utf-8'))['rows']:
    folder=HERE/'final'/f"{row['seed']}-{row['mechanism']}"
    q=json.loads((folder/'query.json').read_text(encoding='utf-8'));t=json.loads((folder/'truth.json').read_text(encoding='utf-8'))
    means,der=oracle(GRID,row['mechanism']);actual=means-means[0]
    max_truth=max(max_truth,float(np.max(abs(means-t['mean']))),float(np.max(abs(der-t['derivative']))))
    c=np.asarray(q['mean_curve']['curve']['contrasts']);smooth=np.asarray(q['retained_smoothed_derivative']['values'])
    direct=np.asarray(q['direct_marginal_effect']['estimates'])
    metrics=dict(curve_rmse_seconds=float(np.sqrt(np.mean((c-actual)**2))),
        smoothed_derivative_rmse=float(np.sqrt(np.mean((smooth-der)**2))),
        direct_derivative_rmse=float(np.sqrt(np.mean((direct-der)**2))))
    max_score=max(max_score,*[abs(metrics[k]-row[k]) for k in metrics])
    baseline=means[0]
    def f(a):return oracle([a],row['mechanism'])[0][0]-baseline-120
    roots=[]
    for a,b in zip(GRID[:-1],GRID[1:]):
        if f(a)<0<=f(b):roots.append(float(brentq(f,a,b)))
    estimated=q['target_threshold'].get('first_point_crossing')
    tr=dict(seed=row['seed'],mechanism=row['mechanism'],true_first_crossing=roots[0] if roots else None,
        true_upward_crossings=roots,estimated_first_crossing=estimated,
        false_reached=not roots and estimated is not None,missed_reached=bool(roots) and estimated is None,
        crossing_absolute_error=None if not roots or estimated is None else abs(estimated-roots[0]))
    threshold_rows.append(tr);rows.append(dict(seed=row['seed'],mechanism=row['mechanism'],**metrics))
assert max_truth<1e-4 and max_score<1e-4,(max_truth,max_score)
freeze=json.loads((HERE/'source_freeze.json').read_text(encoding='utf-8'))['files']
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in freeze.items())
old=json.loads((HERE/'production_before.json').read_text(encoding='utf-8'))
changed=[p for p,h in old.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert set(changed)<=set(['B1算法/b1_algorithm/factors.py','B1算法/b1_api.py','B1算法/requirements.txt','B1算法/README.md']),changed
physical=json.loads((HERE/'physical/events.json').read_text(encoding='utf-8'))
ledger=json.loads((HERE/'physical/truth_ledger.json').read_text(encoding='utf-8'))
mae=float(np.mean([abs(e['process']['duration_estimates']['cumulative_response_seconds']-t['true_seconds']) for e,t in zip(physical,ledger)]))
result=dict(status='passed',independent_analytic_truth_max_difference=max_truth,independent_score_max_difference=max_score,
    independently_recomputed_curve_scores=len(rows)*3,rows=rows,target_threshold_rows=threshold_rows,
    true_target_reached=sum(r['true_first_crossing'] is not None for r in threshold_rows),
    false_target_reached=sum(r['false_reached'] for r in threshold_rows),
    missed_target_reached=sum(r['missed_reached'] for r in threshold_rows),
    threshold_mae_on_jointly_reached=float(np.mean([r['crossing_absolute_error'] for r in threshold_rows if r['crossing_absolute_error'] is not None])),
    physical_duration_mae=mae,physical_events=len(physical),
    original_formal_files_preserved=len(old)-len(changed),changed_formal_files=changed,
    first_block_code_and_weights_changed=False,frozen_source_files_checked=len(freeze))
save(HERE/'verification.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['rows','target_threshold_rows']},ensure_ascii=False))
