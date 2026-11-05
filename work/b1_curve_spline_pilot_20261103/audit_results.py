"""Independent saved-result verification; no study/finalize imports or new cohorts."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import json,hashlib,sys,time
import numpy as np
from scipy.special import expit
from scipy.interpolate import BSpline,make_smoothing_spline
from scipy.optimize import brentq
from numpy.polynomial.legendre import leggauss

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(HERE/'protocol.json');SEL=read(HERE/'selection_freeze.json');DEC=read(HERE/'decision.json')
GRID=np.asarray(P['grid']);MESH=np.asarray(P['threshold_mesh']);REF=P['reference'];TARGET=P['target_seconds']
counts={};errors={};issues=[];started=time.perf_counter()
def claim(name,ok,detail=None):
    counts[name]=counts.get(name,0)+1
    if not bool(ok):issues.append(dict(check=name,detail=detail))
def close(name,a,b,tol=2e-6):
    aa=np.asarray(a,float);bb=np.asarray(b,float)
    if aa.shape!=bb.shape:
        claim(name,False,dict(shapes=[list(aa.shape),list(bb.shape)]));return
    e=float(np.max(abs(aa-bb))) if aa.size else 0.
    errors[name]=max(errors.get(name,0.),e);claim(name,np.isfinite(e) and e<=tol,e)
def policy(v,prefix):return prefix+'_'+format(float(v),'.8g')

# Independent physical-unit Gaussian local-moment formula and its derivative.
def ll(d,xi,h,a,derivative=False):
    t=d[None,:]-np.atleast_1d(a)[:,None];k=np.exp(-t*t/(2*h*h))
    s=[(k*t**j).sum(1) for j in range(4)]
    den=s[0]*s[2]-s[1]**2;n=s[2][:,None]-s[1][:,None]*t
    L=k*n/den[:,None]
    if derivative:
        ds=[s[1]/h**2,s[2]/h**2-s[0],s[3]/h**2-2*s[1]]
        dn=ds[2][:,None]-ds[1][:,None]*t+s[1][:,None]
        dden=ds[0]*s[2]+s[0]*ds[2]-2*s[1]*ds[1]
        L=k*(t*n/h**2+dn)/den[:,None]-L*dden[:,None]/den[:,None]
    return L@xi

def support(x,d,u,points,h,weights,cfg):
    sd=np.maximum(x.std(0),1e-8);mean=x.mean(0);failed=[]
    for a in points:
        local=abs(d-a)<=h;w=np.exp(-.5*((d-a)/h)**2)*weights
        ess=w.sum()**2/(w@w);smd=np.max(abs(np.average(x,axis=0,weights=w)-mean)/sd)
        if local.sum()<cfg['min_local_events'] or len(set(u[local]))<cfg['min_local_users'] or ess<cfg['min_local_ess'] or smd>cfg['max_weighted_smd']:
            failed.append(float(a))
    return failed

# Independent 23-node formula; no import from the study generator or truth code.
z,w=leggauss(23);l,u,h=np.meshgrid(z,z,.6*z,indexing='ij')
wl,wu,wh=np.meshgrid(w,w,w,indexing='ij')
l=l.ravel();u=u.ravel();h=h.ravel();weight=(wl*wu*wh).ravel()/8
def oracle(a,kind,derivative=False):
    out=[]
    for amount in np.atleast_1d(a):
        if kind in ('randomized_saturation','observed_saturation'):
            scale=2.4/(1-np.exp(-3));s=scale*(1-np.exp(-amount/.8));ds=scale/.8*np.exp(-amount/.8)
        elif kind=='nonmonotone':s=2*np.sin(np.pi*amount/2.4);ds=2*np.pi/2.4*np.cos(np.pi*amount/2.4)
        elif kind=='zero_effect':s=ds=0.
        elif kind=='sigmoidal':v=expit(4*(amount-1.2));s=2.4*v;ds=9.6*v*(1-v)
        elif kind=='assignment_mixture':s=1.8*np.sin(1.4*amount)+.35*amount;ds=2.52*np.cos(1.4*amount)+.35
        else:raise ValueError(kind)
        p=expit(-1.15+.85*s*(1+.3*l)+.35*l-.45*u+.20*h)
        mu=expit(-.55+.65*s+.3*l-.2*u+.15*h);full=expit(-3+.5*s)
        q=full+(1-full)*mu
        if derivative:
            dp=p*(1-p)*.85*(1+.3*l)*ds;dm=mu*(1-mu)*.65*ds;df=full*(1-full)*.5*ds
            value=1800*(dp*q+p*(df*(1-mu)+(1-full)*dm))
        else:value=1800*p*q
        out.append(float(weight@value))
    return np.asarray(out)

def roots(query):
    y=query(MESH)-float(query([REF])[0])-TARGET;roots=[]
    if y[0]>=0:roots.append(float(MESH[0]))
    for left,right,yl,yr in zip(MESH[:-1],MESH[1:],y[:-1],y[1:]):
        if yl<0<=yr:
            roots.append(float(brentq(lambda a:float(query([a])[0]-query([REF])[0]-TARGET),left,right,xtol=1e-10)))
    return dict(reached=bool(roots),first_crossing=roots[0] if roots else None,upcrossings=roots)
def rootcheck(name,a,b):
    claim(name+'_reached',a['reached']==b['reached'])
    close(name+'_roots',a['upcrossings'],b['upcrossings'],3e-7)
    if a['first_crossing'] is not None and b['first_crossing'] is not None:close(name+'_first',a['first_crossing'],b['first_crossing'],3e-7)

truth={}
for kind in P['confirmation']['mechanisms']:
    m=oracle(GRID,kind);base=oracle([REF],kind)[0]
    truth[kind]=dict(mean=m,contrasts=m-base,derivative=oracle(GRID,kind,True),target=roots(lambda a,k=kind:oracle(a,k)))

all_rows={};recomputed={};cohort_count=0;policy_count=0;spline_count=0;all_users={}
for stage in ('development','confirmation'):
    spec=P[stage];summary=read(HERE/stage/'summary.json');rows=summary['rows']
    expected={(seed,kind) for seed in spec['seeds'] for kind in spec['mechanisms']}
    actual=[(r['seed'],r['mechanism']) for r in rows]
    claim('protocol_exact_unique_roster',len(actual)==len(expected) and len(set(actual))==len(actual) and set(actual)==expected,stage)
    folders={p.name for p in (HERE/stage).iterdir() if p.is_dir()}
    claim('exact_cohort_folders',folders=={f'{s}-{k}' for s,k in expected},stage)
    all_rows[stage]=rows;recomputed[stage]=[];stage_users=set()
    for row in rows:
        seed=row['seed'];kind=row['mechanism'];folder=HERE/stage/f'{seed}-{kind}';cohort_count+=1
        claim('score_equals_summary_row',read(folder/'score.json')==row,str(folder))
        f=read(folder/'facts.json');r=read(folder/'baseline_api.json');t=read(folder/'truth.json')
        x=np.asarray(f['X'])[:,:2];d=np.asarray(f['treatment']);y=np.asarray(f['outcome']);users=np.asarray(f['users'])
        audit=r['audit'];xi=np.asarray(audit['pseudo_outcome']);sw=np.asarray(audit['stabilized_weight']);fold=np.asarray(audit['fold_by_event'])
        stage_users.update(users.tolist())
        claim('event_user_denominators',len(d)==spec['users']*spec['events_per_user'] and len(set(users))==spec['users'])
        claim('two_adjustment_source_contract','x=np.asarray(facts[\'X\'])[:,:2]' in (HERE/'study.py').read_text(encoding='utf-8'))
        claim('user_folds_do_not_cross',len(set(fold))==3 and all(len(set(fold[users==v]))==1 for v in set(users)))
        close('audit_dose_matches_facts',audit['dose'],d,0.)
        claim('shared_xi_digest',row['pseudo_outcome_sha256']==hashlib.sha256(xi.tobytes()).hexdigest())
        claim('all_zeros_and_full_retained',len(xi)==len(y) and row['events']==len(y))
        claim('pure_continuous_design',np.all((d>0)&(d<2.4)))
        claim('known_density_correct_role',(f['known_density'] is not None)==(kind=='randomized_saturation'))
        if f['known_density'] is not None:close('uniform_density',f['known_density'],np.full(len(d),1/2.4),0.)
        cfg=r['configuration'];bw=r['diagnostics']['bandwidth']
        close('production_bandwidth_rule',bw,1.06*np.std(d)*len(set(users))**(-.2),1e-12)
        claim('baseline_support_independently_passes',not support(x,d,users,GRID,bw,sw,cfg))
        common_root=not support(x,d,users,MESH,bw,sw,cfg)
        claim('saved_common_threshold_support',row['common_threshold_support']==common_root)
        for field in ('mean','contrasts','derivative'):close('high_order_truth_'+field,t[field],truth[kind][field],2e-5)
        rootcheck('high_order_truth_target',t['target'],truth[kind]['target'])
        close('formal_API_curve',r['causal_curve']['contrasts'],ll(d,xi,bw,GRID)-ll(d,xi,bw,[REF])[0],2e-7)
        newrow=dict(seed=seed,mechanism=kind,policies={})
        expected_names={'fixed_LL'}
        if stage=='development':
            expected_names|={policy(v,'LL') for v in P['tuning_control']['grid']}|{policy(v,'spline') for v in P['candidate']['lambda_mean_grid']}
        else:expected_names|={policy(SEL['selected']['ll_multiplier'],'LL'),policy(SEL['selected']['lambda_mean'],'spline')}
        claim('exact_policy_roster',set(row['policies'])==expected_names)
        for name,v in row['policies'].items():
            policy_count+=1
            if v['status']!='ok':
                issues.append(dict(check='unexpected_incomplete_policy',detail=[stage,seed,kind,name]));continue
            if name.startswith('spline_'):
                spline_count+=1;state=read(folder/(name+'_state.json'));lam=state['lambda_mean']
                fn=BSpline(state['knots'],state['coefficients'],state['degree'],extrapolate=False)
                query=lambda a,fn=fn:fn(np.asarray(a)/state['x_scale'])*state['y_scale']
                derivative=lambda a,fn=fn:fn(np.asarray(a)/state['x_scale'],nu=1)*state['y_scale']/state['x_scale']
                claim('spline_normalization_metadata',state['x_scale']==2.4 and state['y_scale']==1800. and state['events']==len(d))
                close('spline_n_lambda',state['scipy_lambda'],len(d)*lam,0.)
                # Reconstruct only the final algebraic smoother from the cached xi.
                # No nuisance fit, no new draw or newly selected policy is involved.
                order=np.argsort(d,kind='stable');unique,first,n=np.unique(d[order],return_index=True,return_counts=True)
                means=np.add.reduceat(xi[order]/1800.,first)/n
                independent=make_smoothing_spline(unique/2.4,means,w=n.astype(float),lam=len(d)*lam)
                close('spline_state_uses_exact_shared_xi',query(GRID),independent(GRID/2.4)*1800.,3e-5)
                close('spline_state_derivative_shared_xi',derivative(GRID),independent(GRID/2.4,nu=1)*750.,3e-5)
                claim('spline_no_extrapolation',GRID.min()>=d.min() and GRID.max()<=d.max())
                available=common_root and MESH.min()>=d.min() and MESH.max()<=d.max()
            else:
                mult=1. if name=='fixed_LL' else float(name[3:]);hh=bw*mult
                query=lambda a,hh=hh:ll(d,xi,hh,a)
                derivative=lambda a,hh=hh:ll(d,xi,hh,a,True)
                claim('LL_own_support',hh<=1.2 and not support(x,d,users,GRID,hh,sw,cfg))
                available=common_root and not support(x,d,users,MESH,hh,sw,cfg)
            mean=query(GRID);contrast=mean-query([REF])[0];deriv=derivative(GRID)
            close('saved_mean_recalculated',v['mean_outcomes'],mean,3e-6)
            close('saved_contrast_recalculated',v['contrasts'],contrast,3e-6)
            close('saved_derivative_recalculated',v['derivative'],deriv,3e-6)
            # Confirm saved truth scoring exactly, after independent high-order oracle verification.
            metrics=dict(curve_rmse_seconds=float(np.sqrt(np.mean((contrast-np.asarray(t['contrasts']))**2))),
                level_mae_seconds=float(np.mean(abs(mean-np.asarray(t['mean'])))),
                maximum_contrast_error_seconds=float(np.max(abs(contrast-np.asarray(t['contrasts'])))),
                derivative_rmse=float(np.sqrt(np.mean((deriv-np.asarray(t['derivative']))**2))))
            for field,value in metrics.items():close('recomputed_'+field,v[field],value,3e-6)
            target=roots(query) if available else None
            claim('threshold_output_support',(v['target'] is not None)==available)
            if target is not None:rootcheck('saved_estimated_threshold',v['target'],target)
            true_target=truth[kind]['target']
            correct=None if target is None else target['reached']==true_target['reached']
            crossing=None if target is None or not target['reached'] or not true_target['reached'] else abs(target['first_crossing']-true_target['first_crossing'])
            claim('target_correct_recalculated',v['target_correct']==correct)
            if crossing is not None:close('crossing_error_recalculated',v['crossing_error'],crossing,4e-7)
            else:claim('crossing_missing_denominator',v['crossing_error'] is None)
            # Loaded-state queries on arbitrary points require no refitting and do not depend on display grid.
            extra=.731;inserted=np.sort(np.r_[GRID,extra]);idx=np.searchsorted(inserted,GRID)
            close('all_methods_query_insertion',query(GRID),query(inserted)[idx],1e-9)
            close('all_methods_query_single',query([GRID[7]])[0],mean[7],1e-9)
            newrow['policies'][name]=dict(status='ok',**metrics,target=target,true_target=true_target,target_correct=correct,crossing_error=crossing)
        recomputed[stage].append(newrow)
    all_users[stage]=stage_users
claim('development_confirmation_users_disjoint',not (all_users['development']&all_users['confirmation']))

def aggregate(rows):
    names=sorted({k for row in rows for k in row['policies']});result={}
    for name in names:
        vals=[r['policies'][name] for r in rows if r['policies'].get(name,{}).get('status')=='ok']
        targets=[v for v in vals if v['target'] is not None];cross=[v['crossing_error'] for v in targets if v['crossing_error'] is not None]
        result[name]=dict(outputs=len(vals),designed_cohorts=len(rows),mean_curve_rmse=float(np.mean([v['curve_rmse_seconds'] for v in vals])),
            mean_level_mae=float(np.mean([v['level_mae_seconds'] for v in vals])),mean_derivative_rmse=float(np.mean([v['derivative_rmse'] for v in vals])),
            target_outputs=len(targets),target_correct=sum(v['target_correct'] for v in targets),
            false_reached=sum(v['target']['reached'] and not v['true_target']['reached'] for v in targets),
            missed_reached=sum(not v['target']['reached'] and v['true_target']['reached'] for v in targets),
            mean_crossing_error=float(np.mean(cross)) if cross else None,jointly_reached=len(cross))
    return result
AGG={stage:aggregate(rows) for stage,rows in recomputed.items()}
for stage in AGG:
    saved=read(HERE/stage/'summary.json')['aggregate']
    for name,fields in AGG[stage].items():
        for field,value in fields.items():
            if value is None:claim('aggregate_null',saved[name][field] is None)
            else:close('aggregate_'+field,saved[name][field],value,4e-6)

dev=AGG['development'];base=dev['fixed_LL']['outputs'];chosen={}
for prefix,values,target in [('spline',P['candidate']['lambda_mean_grid'],'lambda_mean'),('LL',P['tuning_control']['grid'],'ll_multiplier')]:
    eligible=[v for v in values if dev[policy(v,prefix)]['outputs']>=base]
    chosen[target]=min(eligible,key=lambda v:(dev[policy(v,prefix)]['mean_curve_rmse'],-v))
claim('development_selection_independent',chosen==SEL['selected'],chosen)
candidate=policy(chosen['lambda_mean'],'spline');refs=['fixed_LL',policy(chosen['ll_multiplier'],'LL')]
final=AGG['confirmation'];finalrows=recomputed['confirmation'];expected_final=len(P['confirmation']['seeds'])*len(P['confirmation']['mechanisms'])
complete=expected_final==48 and len(finalrows)==48 and all(final[n]['outputs']==48 for n in refs+[candidate])
comparisons={}
for ref in refs:
    gain=1-final[candidate]['mean_curve_rmse']/final[ref]['mean_curve_rmse']
    diffs=[]
    for seed in P['confirmation']['seeds']:
        block=[r for r in finalrows if r['seed']==seed];claim('six_mechanisms_each_seed',len(block)==6)
        delta=float(np.mean([r['policies'][candidate]['curve_rmse_seconds']-r['policies'][ref]['curve_rmse_seconds'] for r in block]))
        diffs.append(dict(seed=seed,candidate_minus_reference_rmse=delta))
    zero=[r for r in finalrows if r['mechanism']=='zero_effect'];zero_complete=all(r['policies'][n]['target'] is not None for r in zero for n in (ref,candidate))
    fp={n:sum(bool(r['policies'][n]['target']['reached']) for r in zero) for n in (ref,candidate)}
    comparisons[ref]=dict(relative_gain=gain,seed_differences=diffs,seed_wins=sum(v['candidate_minus_reference_rmse']<0 for v in diffs),zero_effect_target_outputs_complete=zero_complete,zero_effect_false_reached=fp)
    close('decision_gain',DEC['comparisons'][ref]['relative_gain'],gain,1e-9)
    close('decision_seed_differences',[v['candidate_minus_reference_rmse'] for v in DEC['comparisons'][ref]['seed_differences']],[v['candidate_minus_reference_rmse'] for v in diffs],3e-6)
    claim('decision_seed_wins',DEC['comparisons'][ref]['seed_wins']==comparisons[ref]['seed_wins'])
    claim('decision_zero_false_reached',DEC['comparisons'][ref]['zero_effect_false_reached']==fp)
gates=dict(all_designed_curves_output=complete,gain_at_least_5pct_vs_both=complete and all(v['relative_gain']>=.05 for v in comparisons.values()),
    at_least_6_of_8_seed_wins_vs_both=all(v['seed_wins']>=6 for v in comparisons.values()),
    zero_effect_false_target_not_increased=all(v['zero_effect_target_outputs_complete'] and v['zero_effect_false_reached'][candidate]<=v['zero_effect_false_reached'][ref] for ref,v in comparisons.items()))
claim('decision_gates_independent',gates==DEC['all_gates']);claim('decision_status_independent',DEC['status']==('confirmed_single_smoother_candidate' if all(gates.values()) else 'candidate_not_adopted'))
for name in refs+[candidate]:
    for field,value in final[name].items():close('decision_aggregate_'+field,DEC['aggregate'][name][field],value,4e-6)
    for kind in P['confirmation']['mechanisms']:
        rows=[r for r in finalrows if r['mechanism']==kind]
        close('decision_mechanism_rmse',DEC['per_mechanism'][kind][name]['rmse'],np.mean([r['policies'][name]['curve_rmse_seconds'] for r in rows]),3e-6)
        claim('decision_mechanism_denominator',DEC['per_mechanism'][kind][name]['outputs']==len(rows)==8)

formal=read(HERE/'formal_before.json');current={str(p.relative_to(ROOT)):sha(p) for ext in ('*.py','*.json') for p in (ROOT/'B1算法').rglob(ext)}
claim('formal_exact_inventory_sha',formal==current and len(current)==61)
for path,digest in SEL['files'].items():claim('selection_freeze_sha',sha(ROOT/path)==digest,path)
claim('selection_freezes_protocol_and_four_sources',all(str((HERE/name).relative_to(ROOT)) in SEL['files'] for name in ('prepare.py','smoothers.py','study.py','data.py','protocol.json')))
before=read(HERE/'development_source_amendment.json')
for name,digest in before['files'].items():claim('predevelopment_amendment_hash',sha(HERE/name)==digest,name)

# Exactly two authorized public API replays, never a new development/test draw.
# A preserved earlier audit already performed these replays; carry their evidence
# when rerunning only a corrected floating-point comparison in this verifier.
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects.continuous import fit_continuous_effects
replays=[]
previous=read(HERE/'verification_attempt1.json') if (HERE/'verification_attempt1.json').exists() else None
if previous is not None:
    claim('preserved_public_replay_evidence',not any(v['check'].startswith('two_public_replays') for v in previous['issues']) and len(previous['authorized_public_API_replays'])==2)
for stage in ('development','confirmation'):
    seed=P[stage]['seeds'][0];kind=P[stage]['mechanisms'][0];folder=HERE/stage/f'{seed}-{kind}'
    facts=read(folder/'facts.json');old=read(folder/'baseline_api.json')
    if previous is None:
        again=fit_continuous_effects(np.asarray(facts['X'])[:,:2],facts['treatment'],facts['outcome'],facts['users'],dose_domain=P['dose_domain'],grid=GRID,
            reference_dose=REF,incentive_unit=old['incentive_unit'],task=old['task'],continuous_assignment=True,assumptions=old['declared_assumptions'],known_density=facts['known_density'],config=old['configuration'])
        claim('two_public_replays_status',again['status']==old['status'])
        for field in old['audit']:close('two_public_replays_'+field,again['audit'][field],old['audit'][field],1e-8)
        close('two_public_replays_curve',again['causal_curve']['contrasts'],old['causal_curve']['contrasts'],1e-8)
    replays.append(dict(stage=stage,seed=seed,mechanism=kind,new_independent_sample=False,adjustment_columns=2))

result=dict(passed=not issues,issues=issues,cohorts_checked=cohort_count,confirmation_unique_predeclared_cohorts=48,development_unique_predeclared_cohorts=12,
    policy_curves_checked=policy_count,spline_states_checked=spline_count,check_counts=counts,total_claims=sum(counts.values()),maximum_errors=errors,
    independently_recomputed_selected=chosen,independently_recomputed_confirmation_aggregate=final,independently_recomputed_comparisons=comparisons,
    independently_recomputed_gates=gates,formal_files_sha_unchanged=len(current),selection_freeze_hashes_verified=len(SEL['files']),
    truth_validation='independent signal/logistic-chain formula, tensor 23-node quadrature vs saved15; target roots independently searched on same declared mesh',
    shared_xi_evidence='all LL from cached public API xi; every saved spline state independently reconstructed from exactly that xi and fixed lambda, then evaluated; no per-method nuisance fit',
    authorized_public_API_replays=replays,replays_count_as_new_samples=False,new_data_generated=False,new_nuisance_fits_for_main_study=False,
    query_validation='saved BSpline state and independent LL arbitrary insertion and single queries; all estimates unchanged at existing amounts',
    limitations=['Related simulated mechanisms, not field validation','Derivative and target diagnostic improvements differ from curve improvement','Targets resolved by fixed mesh; no new confidence intervals','Only8 independent confirmation seed blocks; paired mechanisms not independent repetitions'],
    verifier_correction='Initial bitwise-zero query insertion comparison flagged BLAS roundoff at most9.1e-13sec; corrected to1e-9sec and retained verification_attempt1.json. No research data, selected policies, scoring rules or decision changed. Public replay evidence carried from that first pass; no additional nuisance fit on rerun.' if previous is not None else None,
    elapsed_seconds=time.perf_counter()-started,auditor_source_sha256=sha(Path(__file__)))
with (HERE/'verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(dict(passed=result['passed'],cohorts=cohort_count,policy_curves=policy_count,spline_states=spline_count,claims=result['total_claims'],issues=issues,elapsed_seconds=result['elapsed_seconds']),ensure_ascii=False))
if issues:raise SystemExit(1)
