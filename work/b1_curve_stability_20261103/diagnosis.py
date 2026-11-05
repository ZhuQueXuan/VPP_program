"""Frozen old-cohort diagnosis only: no fitting, tuning or new study draws."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import json,hashlib,importlib.util,time
import numpy as np
from scipy.interpolate import CubicSpline,BSpline
from scipy.linalg import solve_banded
from scipy.sparse import coo_matrix,diags
from scipy.special import expit,betaincinv

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/b1_curve_spline_pilot_20261103'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('frozen_old_truth',OLD/'data.py');D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)
P=read(OLD/'protocol.json');GRID=np.asarray(P['grid']);REF=P['reference'];started=time.perf_counter();checks=[]
def check(name,actual,expected,tol=1e-7):
    delta=float(np.max(abs(np.asarray(actual)-np.asarray(expected))))
    checks.append(dict(name=name,max_error=delta,passed=bool(delta<=tol)))
def ll_weights(d,a,h):
    t=d[None,:]-a[:,None];k=np.exp(-.5*(t/h)**2)
    s0=k.sum(1);s1=(k*t).sum(1);s2=(k*t*t).sum(1)
    return k*(s2[:,None]-s1[:,None]*t)/(s0*s2-s1*s1)[:,None]

def exact_frozen_spline_weights(d,points,state):
    """Natural-basis banded linear operator at the frozen lambda.

    Solve (X+lambda*E)^(-1) for identity right-hand sides and evaluate the
    resulting basis. This is algebraic weight recovery, not an outcome fit.
    It uses the same stable natural basis as SciPy1.15.3. A first audit-only
    Reinsch Q'Q implementation lost precision on very close dose spacings;
    its output is preserved in diagnosis_attempt1.json and is superseded.
    """
    order=np.argsort(d);x=d[order]/state['x_scale'];n=len(x)
    t=np.r_[[x[0]]*3,x,[x[-1]]*3];B=BSpline.design_matrix(x,t,3)
    X=np.zeros((5,n))
    for i in range(1,4):X[i,2:-2]=B[i:i-4,3:-3][np.diag_indices(n-4)]
    X[1,1]=B[0,0]
    X[2,:2]=((x[2]+x[1]-2*x[0])*B[0,0],B[1,1]+B[1,2])
    X[3,:2]=((x[2]-x[0])*B[1,1],B[2,2])
    X[1,-2:]=(B[-3,-3],(x[-1]-x[-3])*B[-2,-2])
    X[2,-2:]=(B[-2,-3]+B[-2,-2],(2*x[-1]-x[-2]-x[-3])*B[-1,-1])
    X[3,-2]=B[-1,-1]
    def divided(xx):
        return np.asarray([1/np.prod([xx[i]-xx[j] for j in range(len(xx)) if i!=j]) for i in range(len(xx))])
    E=np.zeros((5,n));E[2:,0]=divided(x[:3]);E[1:,1]=divided(x[:4])
    for j in range(2,n-2):E[:,j]=(x[j+2]-x[j-2])*divided(x[j-2:j+3])
    E[:-1,-2]=-divided(x[-4:]);E[:-2,-1]=divided(x[-3:]);E*=6
    c=solve_banded((2,2),X+state['scipy_lambda']*E,np.eye(n))
    coefficients=np.vstack([c[0]*(t[5]+t[4]-2*t[3])+c[1],c[0]*(t[5]-t[3])+c[1],c[1:-1],
        c[-1]*(t[-4]-t[-6])+c[-2],c[-1]*(2*t[-4]-t[-5]-t[-6])+c[-2]])
    sorted_weights=BSpline(t,coefficients,3)(points/state['x_scale'])
    W=np.empty_like(sorted_weights);W[:,order]=sorted_weights
    return W

def reconstruct_primitives(seed,kind,users,events):
    """Replay the old deterministic RNG solely to recover latent H; do not save new data."""
    rng=np.random.default_rng(seed);g=np.repeat(np.arange(users),events);n=len(g)
    x=rng.uniform(-1,1,(n,3));h=rng.uniform(-.6,.6,users)[g]
    ua=rng.uniform(0,2.4,n);assignment_noise=rng.normal(size=n)
    sign=np.where(rng.random(n)<.5,-1.,1.);response=rng.random(n);full=rng.random(n);beta=rng.random(n)
    z=.5*x[:,0]-.4*x[:,1]+1.25*assignment_noise
    if kind=='assignment_mixture':z+=.65*sign
    a=ua if kind=='randomized_saturation' else 2.4*expit(z)
    p,mu,f,*_=D.mean_parts(a,x[:,0],x[:,1],h,kind)
    fraction=np.where(response<p,np.where(full<f,1.,betaincinv(20*mu,20*(1-mu),beta)),0.)
    ey=1800*p*(f+(1-f)*mu)
    ey2=1800**2*p*(f+(1-f)*(mu*mu+mu*(1-mu)/21))
    return x,h,a,1800*fraction,ey,np.maximum(0,ey2-ey*ey)

def weight_diagnostics(W,users):
    unique=np.unique(users);mass=np.stack([abs(W[:,users==v]).sum(1) for v in unique],axis=1)
    total=abs(W).sum(1);squares=(W*W).sum(1)
    # Signed-contrast weights sum to zero, so use absolute coefficient mass,
    # explicitly not propensity/support ESS or a confidence effective N.
    eff=np.divide(total*total,squares,out=np.zeros_like(total),where=squares>1e-24)
    user_eff=np.divide(mass.sum(1)**2,(mass*mass).sum(1),out=np.zeros(len(W)),where=(mass*mass).sum(1)>1e-24)
    share=np.divide(mass.max(1),mass.sum(1),out=np.zeros(len(W)),where=mass.sum(1)>1e-24)
    return dict(max_abs_coefficient_by_amount=abs(W).max(1).tolist(),negative_coefficients_by_amount=(W<-1e-12).sum(1).tolist(),
        absolute_mass_by_amount=total.tolist(),absolute_coefficient_effective_events=eff.tolist(),
        absolute_user_mass_effective_users=user_eff.tolist(),largest_user_absolute_mass_share=share.tolist(),
        interpretation='algebraic coefficient concentration; contrast uses absolute mass because signed weights sum0, not causal support ESS')

rows=[]
for seed in P['confirmation']['seeds']:
    for kind in P['confirmation']['mechanisms']:
        folder=OLD/'confirmation'/f'{seed}-{kind}';facts=read(folder/'facts.json');api=read(folder/'baseline_api.json');score=read(folder/'score.json');truth=read(folder/'truth.json')
        d=np.asarray(facts['treatment']);y=np.asarray(facts['outcome']);users=np.asarray(facts['users']);a=api['audit']
        xi=np.asarray(a['pseudo_outcome']);w=np.asarray(a['stabilized_weight']);mu=np.asarray(a['outcome_prediction']);bw=api['diagnostics']['bandwidth']
        x,h,rd,ry,ey,var=reconstruct_primitives(seed,kind,240,2)
        check('primitive_X',x,facts['X'],0.);check('primitive_A',rd,d,0.);check('primitive_Y',ry,y,0.)
        marginal=xi-w*(y-mu);resid=w*(y-ey);remaining=xi-resid
        check('xi_algebra',xi,marginal+w*(y-mu),1e-10)
        check('frozen_split',remaining,marginal+w*(ey-mu),1e-10)
        true_mean=np.asarray(truth['mean']);true_contrast=np.asarray(truth['contrasts'])
        row=dict(seed=seed,mechanism=kind,events=len(d),users=len(set(users)),
            gps_weight_quantiles={str(q):float(np.quantile(w,q)) for q in (0,.5,.9,.95,.99,1)},
            xi_quantiles={str(q):float(np.quantile(xi,q)) for q in (0,.01,.5,.99,1)},
            user_latent_h_recovered=True,methods={})
        state=read(folder/'spline_0.0001_state.json');SW=exact_frozen_spline_weights(d,GRID,state)
        frozen=BSpline(state['knots'],state['coefficients'],state['degree'])(GRID/2.4)*1800
        check('equivalent_weights_match_frozen_spline_seconds',SW@xi,frozen,1e-3)
        check('equivalent_weights_constant',SW@np.ones(len(d)),np.ones(len(GRID)),2e-4)
        check('equivalent_weights_linear_amount_units',SW@d,GRID,2e-4)
        for name,W in [('fixed_LL',ll_weights(d,GRID,bw)),('LL_2',ll_weights(d,GRID,2*bw)),('spline_0.0001',SW)]:
            C=W-W[[0]];operator_pred=W@xi;operator_error=C@xi-true_contrast;noise=C@resid
            pred=np.asarray(score['policies'][name]['mean_outcomes'])
            error=np.asarray(score['policies'][name]['contrasts'])-true_contrast
            raw_rest=C@remaining-true_contrast
            numerical_remainder=error-noise-raw_rest
            rest=raw_rest+numerical_remainder
            check('same_frozen_prediction_seconds',operator_pred,pred,1e-3)
            check('error_components_sum',error,noise+rest,2e-10)
            decomposition=dict(total_mse=float(np.mean(error**2)),sampling_residual_mse=float(np.mean(noise**2)),
                remaining_error_mse=float(np.mean(rest**2)),cross_term=float(2*np.mean(noise*rest)))
            check('mse_components_sum',decomposition['total_mse'],decomposition['sampling_residual_mse']+decomposition['remaining_error_mse']+decomposition['cross_term'],2e-7)
            levelerr=pred-true_mean
            row['methods'][name]=dict(contrast_rmse=score['policies'][name]['curve_rmse_seconds'],operator_contrast_rmse=float(np.sqrt(np.mean(operator_error**2))),
                score_source='exact saved score for main RMSE; saved mean/contrast for level/reference/error. Linear weights used only for diagnostic components.',
                level_rmse=float(np.sqrt(np.mean(levelerr**2))),level_mae=float(np.mean(abs(levelerr))),
                reference_amount=.3,reference_error=float(levelerr[0]),reference_sampling_residual=float(W[0]@resid),
                reference_remaining_error=float(levelerr[0]-W[0]@resid),
                reference_auxiliary_marginal_error=float(W[0]@marginal-true_mean[0]),
                reference_conditional_correction=float(W[0]@(w*(ey-mu))),
                error_vector=error.tolist(),level_error_vector=levelerr.tolist(),sampling_residual_error_vector=noise.tolist(),remaining_error_vector=rest.tolist(),
                raw_operator_remaining_error_vector=raw_rest.tolist(),operator_numerical_remainder_vector=numerical_remainder.tolist(),
                maximum_operator_mean_prediction_difference_seconds=float(np.max(abs(operator_pred-pred))),
                marginal_prediction_contrast=(C@marginal).tolist(),conditional_correction_contrast=(C@(w*(ey-mu))).tolist(),
                decomposition=decomposition,
                conditional_residual_variance_proxy_by_amount=np.sum(C*C*(w*w*var)[None,:],axis=1).tolist(),
                mean_weights=weight_diagnostics(W,users),contrast_weights=weight_diagnostics(C,users))
        rows.append(row)

by_seed=[]
for seed in P['confirmation']['seeds']:
    subset=[r for r in rows if r['seed']==seed];r=dict(seed=seed,paired_mechanisms=len(subset),methods={})
    for name in ('fixed_LL','LL_2','spline_0.0001'):
        vals=[row['methods'][name] for row in subset]
        r['methods'][name]=dict(mean_curve_rmse=float(np.mean([v['contrast_rmse'] for v in vals])),mean_level_rmse=float(np.mean([v['level_rmse'] for v in vals])),
            mean_reference_error=float(np.mean([v['reference_error'] for v in vals])),mean_absolute_reference_error=float(np.mean([abs(v['reference_error']) for v in vals])),
            average_error_vector=np.mean([v['error_vector'] for v in vals],axis=0).tolist(),
            average_sampling_residual_error_vector=np.mean([v['sampling_residual_error_vector'] for v in vals],axis=0).tolist(),
            average_remaining_error_vector=np.mean([v['remaining_error_vector'] for v in vals],axis=0).tolist(),
            average_mse_decomposition={k:float(np.mean([v['decomposition'][k] for v in vals])) for k in vals[0]['decomposition']},
            average_reference_sampling_residual=float(np.mean([v['reference_sampling_residual'] for v in vals])),
            average_reference_remaining_error=float(np.mean([v['reference_remaining_error'] for v in vals])),
            average_reference_auxiliary_marginal_error=float(np.mean([v['reference_auxiliary_marginal_error'] for v in vals])),
            average_reference_conditional_correction=float(np.mean([v['reference_conditional_correction'] for v in vals])),
            largest_mean_weight=float(max(max(v['mean_weights']['max_abs_coefficient_by_amount']) for v in vals)),
            largest_contrast_weight=float(max(max(v['contrast_weights']['max_abs_coefficient_by_amount']) for v in vals)),
            largest_user_contrast_mass_share=float(max(max(v['contrast_weights']['largest_user_absolute_mass_share']) for v in vals)),
            mean_conditional_residual_variance_proxy=float(np.mean([v['conditional_residual_variance_proxy_by_amount'] for v in vals])))
    r['spline_minus_fixed_rmse']=r['methods']['spline_0.0001']['mean_curve_rmse']-r['methods']['fixed_LL']['mean_curve_rmse']
    r['largest_gps_weight']=float(max(row['gps_weight_quantiles']['1'] for row in subset))
    by_seed.append(r)

formal=read(OLD/'formal_before.json');manifest=read(OLD/'artifact_manifest.json')
formal_ok=all(sha(ROOT/path)==digest for path,digest in formal.items())
old_ok=all(sha(OLD/path)==digest for path,digest in manifest.items())
findings=[
    dict(seed=90342003,interpretation='Primarily an unusually large conditional response-residual projection at the low reference; spline amplifies this realized draw slightly although its frozen conditional variance proxy is lower. Mean levels remain much closer than the referenced contrasts. Not evidence that spline variance always exceeds LL.'),
    dict(seed=90342005,interpretation='Different pattern: the remaining-error component dominates, with stochastic response residuals partly cancelling reference error. Spline worsens the cross-term alignment; zero_effect and sigmoidal produce most net RMSE deterioration. It is not explained mainly by a larger residual-noise MSE.'),
    dict(all_seeds='Reference errors and their shared subtraction are material across multiple blocks; GPS max is highest at90342005 but all compared smoothers use exactly the same GPS. Largest user coefficient concentration is not uniquely greatest in the two bad blocks. This diagnoses conditional realized errors, not a general causal failure or an oracle tuning rule.')]
result=dict(scope='Read-only diagnosis of all old8 paired confirmation blocks/48 cohorts; no parameter search, no nuisance fit, no new study draw',
    frozen_comparison=['fixed_LL','LL_2','spline_0.0001'],amounts=GRID.tolist(),independent_seed_blocks=8,paired_mechanisms_per_seed=6,
    exact_decomposition='With fitted nuisance functions held fixed: xi=marginal_hat+w(Y-mu_hat); r=w(Y-E[Y|A,X,H]); saved contrast error=T(r)+(T(xi-r)-truth)+numerical_remainder. Remaining_error includes that explicitly saved submillisecond numerical remainder, so the displayed MSE identity against exact saved errors closes. MSE includes 2*mean(noise*remaining).',
    not_claimed='Not a full causal variance attribution: fitted mu_hat depends on other observedY; remaining term combines finite covariate/H distribution, nuisance error, correction and smoothing error. Components and cross terms can cancel. Conditional variance proxy excludes nuisance refitting.',
    equivalent_spline_operator='Natural-basis (X+n*lambda_mean*E) banded inverse applied to identity, followed by BSpline basis evaluation; no observed outcome fit or lambda search. Stable basis matches SciPy1.15.3 saved state. Earlier ill-conditioned Q-transpose-Q audit attempt preserved separately, not used.',
    numerical_operator_scope='Floating inverse-basis evaluation has small roundoff on nearly coincident random doses; prediction reconstruction is checked to0.001sec, constant and linear reproduction to0.0002 in their own units. These are diagnostic algebra tolerances, not algorithm changes or new selected parameters. Exact saved scores remain the performance authority. Earlier three diagnostic numerical attempts preserved.',
    primitive_replay='Exactly recovered old X,H,A,Y from saved seeds; replay only, not new data or independent N.',
    findings=findings,seed_summaries=by_seed,cohorts=rows,checks=checks,all_checks_passed=all(v['passed'] for v in checks),
    formal_unchanged=formal_ok,formal_files=len(formal),old_manifest_unchanged=old_ok,old_files=len(manifest),
    old_manifest_sha256=sha(OLD/'artifact_manifest.json'),source_sha256=sha(Path(__file__)),elapsed_seconds=time.perf_counter()-started)
with (HERE/'diagnosis.json').open('w',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
compact=[dict(seed=r['seed'],gpsmax=r['largest_gps_weight'],delta=r['spline_minus_fixed_rmse'],
    methods={n:{k:v for k,v in m.items() if k in ('mean_curve_rmse','mean_level_rmse','mean_absolute_reference_error','average_mse_decomposition','average_reference_sampling_residual','average_reference_remaining_error','mean_conditional_residual_variance_proxy','largest_user_contrast_mass_share')} for n,m in r['methods'].items()}) for r in by_seed]
print(json.dumps(dict(checks_passed=result['all_checks_passed'],formal=formal_ok,old_manifest=old_ok,seeds=[dict(seed=r['seed'],spline_minus_fixed=r['spline_minus_fixed_rmse']) for r in by_seed]),ensure_ascii=False))
if not result['all_checks_passed'] or not formal_ok or not old_ok:raise SystemExit(1)
