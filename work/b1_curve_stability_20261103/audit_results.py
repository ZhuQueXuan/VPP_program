"""Independent audit of frozen nested aggregation results; no study/finalize imports."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from scipy.interpolate import BSpline,make_smoothing_spline
from scipy.special import expit
from scipy.optimize import brentq
from scipy.stats import t as student_t
from numpy.polynomial.legendre import leggauss
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=HERE.parent/'b1_curve_spline_pilot_20261103'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(HERE/'protocol.json');SEL=read(HERE/'selection_freeze.json');DEC=read(HERE/'decision.json')
GRID=np.asarray(P['grid']);MESH=np.asarray(P['mesh']);REF=P['reference'];TARGET=P['target_seconds'];started=time.perf_counter()
issues=[];counts={};errors={}
def claim(name,ok,detail=None):
    counts[name]=counts.get(name,0)+1
    if not bool(ok):issues.append(dict(check=name,detail=detail))
def close(name,a,b,tol=2e-6):
    aa=np.asarray(a,float);bb=np.asarray(b,float)
    if aa.shape!=bb.shape:claim(name,False,[list(aa.shape),list(bb.shape)]);return
    e=float(np.max(abs(aa-bb))) if aa.size else 0.;errors[name]=max(e,errors.get(name,0.))
    claim(name,np.isfinite(e) and e<=tol,e)
def key(prefix,v):return prefix+'_'+format(float(v),'.8g')
def ll(d,xi,h,a,derivative=False):
    z=d[None,:]-np.atleast_1d(a)[:,None];k=np.exp(-z*z/(2*h*h));s=[(k*z**j).sum(1) for j in range(4)]
    den=s[0]*s[2]-s[1]**2;n=s[2][:,None]-s[1][:,None]*z;W=k*n/den[:,None]
    if derivative:
        ds=[s[1]/h**2,s[2]/h**2-s[0],s[3]/h**2-2*s[1]]
        dn=ds[2][:,None]-ds[1][:,None]*z+s[1][:,None];dd=ds[0]*s[2]+s[0]*ds[2]-2*s[1]*ds[1]
        W=k*(z*n/h**2+dn)/den[:,None]-W*dd[:,None]/den[:,None]
    return W@xi
def supported(x,d,users,a,h,w,cfg):
    sd=np.maximum(x.std(0),1e-8);mean=x.mean(0);out=[]
    for v in a:
        local=abs(d-v)<=h;ww=np.exp(-.5*((d-v)/h)**2)*w
        ess=ww.sum()**2/(ww@ww);smd=np.max(abs(np.average(x,axis=0,weights=ww)-mean)/sd)
        out.append(local.sum()>=cfg['min_local_events'] and len(set(users[local]))>=cfg['min_local_users'] and ess>=cfg['min_local_ess'] and smd<=cfg['max_weighted_smd'])
    return np.asarray(out,bool)
def roots(query):
    y=query(MESH)-query([REF])[0]-TARGET;rr=[]
    if y[0]>=0:rr.append(float(MESH[0]))
    for left,right,yl,yr in zip(MESH[:-1],MESH[1:],y[:-1],y[1:]):
        if yl<0<=yr:rr.append(float(brentq(lambda a:float(query([a])[0]-query([REF])[0]-TARGET),left,right,xtol=1e-10)))
    return dict(reached=bool(rr),first_crossing=rr[0] if rr else None,upcrossings=rr)
def compare_roots(name,a,b):
    claim(name+'_classification',a['reached']==b['reached']);close(name+'_crossings',a['upcrossings'],b['upcrossings'],5e-7)
    if a['first_crossing'] is not None and b['first_crossing'] is not None:close(name+'_first',a['first_crossing'],b['first_crossing'],5e-7)

# Independent analytic truth with higher quadrature order, not the generator import.
z,w=leggauss(23);l,u,h=np.meshgrid(z,z,.6*z,indexing='ij');wl,wu,wh=np.meshgrid(w,w,w,indexing='ij')
l=l.ravel();u=u.ravel();h=h.ravel();qw=(wl*wu*wh).ravel()/8
def oracle(points,kind,derivative=False):
    out=[]
    for a in np.atleast_1d(points):
        if kind in ('randomized_saturation','observed_saturation'):
            b=2.4/(1-np.exp(-3));s=b*(1-np.exp(-a/.8));ds=b/.8*np.exp(-a/.8)
        elif kind in ('nonmonotone','noisy_nonmonotone'):s=2*np.sin(np.pi*a/2.4);ds=2*np.pi/2.4*np.cos(np.pi*a/2.4)
        elif kind=='two_peak':s=1.25+.9*np.sin(4*np.pi*a/2.4)+.35*a;ds=.9*4*np.pi/2.4*np.cos(4*np.pi*a/2.4)+.35
        elif kind=='zero_effect':s=ds=0.
        elif kind=='sigmoidal':v=expit(4*(a-1.2));s=2.4*v;ds=9.6*v*(1-v)
        elif kind=='assignment_mixture':s=1.8*np.sin(1.4*a)+.35*a;ds=2.52*np.cos(1.4*a)+.35
        else:raise ValueError(kind)
        p=expit(-1.15+.85*s*(1+.3*l)+.35*l-.45*u+.20*h);mu=expit(-.55+.65*s+.3*l-.2*u+.15*h);full=expit(-3+.5*s)
        m=full+(1-full)*mu
        if derivative:
            dp=p*(1-p)*.85*(1+.3*l)*ds;dm=mu*(1-mu)*.65*ds;df=full*(1-full)*.5*ds
            val=1800*(dp*m+p*(df*(1-mu)+(1-full)*dm))
        else:val=1800*p*m
        out.append(float(qw@val))
    return np.asarray(out)
truths={}
for kind in P['confirmation']['mechanisms']:
    m=oracle(GRID,kind);truths[kind]=dict(mean=m,contrasts=m-oracle([REF],kind)[0],derivative=oracle(GRID,kind,True),target=roots(lambda a,k=kind:oracle(a,k)))
close('high_noise_same_population_mean',truths['noisy_nonmonotone']['mean'],truths['nonmonotone']['mean'],0.)

def nested_checks(cv,x,d,y,users,kd):
    n=len(d);outer=np.asarray(cv['outer_fold_by_event']);held=cv['heldout'];seen=np.zeros(n,int);cfg=cv['configuration']
    normalized=np.asarray(['string:'+str(v) for v in users])
    claim('CV_user_outer_integrity',len(set(outer))==3 and all(len(set(outer[users==v]))==1 for v in set(users)))
    close('CV_heldout_dose',held['dose'],d,0.);claim('CV_heldout_users',held['users']==normalized.tolist())
    all_valid=np.zeros(n,bool);pred_s=np.full(n,np.nan);pred_l=np.full(n,np.nan);xiv=np.full(n,np.nan);all_fail=[]
    for f in cv['folds']:
        ti=np.asarray(f['train_indices']);vi=np.asarray(f['validation_indices']);seen[vi]+=1
        claim('CV_TV_exact_complement',set(ti)==set(np.flatnonzero(outer!=f['fold'])) and set(vi)==set(np.flatnonzero(outer==f['fold'])) and not(set(users[ti])&set(users[vi])))
        claim('CV_TV_user_receipts',f['training_users']==sorted(set(normalized[ti])) and f['validation_users']==sorted(set(normalized[vi])))
        all_fail+=f['failures']
        if 'training_crossfit' not in f or 'external' not in f:continue
        tr=f['training_crossfit'];ext=f['external'];inner=np.asarray(tr['fold_by_training_event']);txi=np.asarray(tr['pseudo_outcome']);tw=np.asarray(tr['stabilized_weight'])
        claim('CV_inner_T_only_user_integrity',len(txi)==len(ti) and len(inner)==len(ti) and len(set(inner))==3 and all(len(set(inner[users[ti]==v]))==1 for v in set(users[ti])))
        claim('CV_external_TV_receipts',ext['training_users']==sorted(set(normalized[ti])) and ext['validation_users']==sorted(set(normalized[vi])) and not ext['validation_outcomes_used_for_fit'])
        claim('CV_external_GPS_seed',ext['gps_inner_seed']==cfg['seed']+f['fold']+130)
        ew=np.asarray(ext['marginal_dose_density'])/np.asarray(ext['observed_dose_density'])
        close('CV_external_weight_formula',ext['stabilized_weight'],ew,1e-10)
        xi=np.asarray(ext['marginal_outcome_prediction'])+ew*(y[vi]-np.asarray(ext['outcome_prediction']))
        close('CV_external_pseudo_formula',ext['pseudo_outcome'],xi,1e-9);xiv[vi]=xi
        close('CV_external_global_heldout',np.asarray(held['pseudo_outcome'])[vi],xi,1e-9)
        for stored,external in [('stabilized_weight','stabilized_weight'),('outcome_prediction','outcome_prediction'),('observed_dose_density','observed_dose_density')]:
            close('CV_external_heldout_'+stored,np.asarray(held[stored])[vi],ext[external],1e-9)
        if 'validation_valid_mask' not in f:continue
        ht=1.06*np.std(d[ti])*len(set(users[ti]))**(-.2);close('CV_training_bandwidth',f['training_bandwidth'],ht,1e-12)
        within=(d[vi]>=d[ti].min())&(d[vi]<=d[ti].max());eligible=within&(d[vi]>=.3)&(d[vi]<=2.1)
        ids=np.flatnonzero(eligible);mask=np.zeros(len(vi),bool)
        mask[ids]=supported(x[ti],d[ti],users[ti],d[vi][eligible],ht,tw,cfg)&supported(x[ti],d[ti],users[ti],d[vi][eligible],2*ht,tw,cfg)
        claim('CV_valid_mask_from_X_D_GPS_only',np.array_equal(mask,np.asarray(f['validation_valid_mask'])))
        claim('CV_valid_event_user_denominators',f['valid_validation_events']==mask.sum() and f['valid_validation_users']==len(set(users[vi][mask])))
        # Reconstruct fixed training smoothers from already saved training xi only.
        order=np.argsort(d[ti],kind='stable');dt=d[ti][order]/2.4;yy=txi[order]/1800.
        unique,first,multiplicity=np.unique(dt,return_index=True,return_counts=True)
        sf=make_smoothing_spline(unique,np.add.reduceat(yy,first)/multiplicity,w=multiplicity.astype(float),lam=len(ti)*1e-4)
        ps=np.full(len(vi),np.nan);ps[within]=sf(d[vi][within]/2.4)*1800.
        pl=ll(d[ti],txi,2*ht,d[vi])
        close('CV_training_spline_predictions',np.asarray(f['validation_pred_spline'],float)[within],ps[within],2e-6)
        close('CV_training_LL_predictions',f['validation_pred_LL2'],pl,2e-6)
        pred_s[vi]=ps;pred_l[vi]=pl;all_valid[vi]=mask
    claim('CV_each_event_heldout_once',np.all(seen==1));claim('CV_global_valid_mask',np.array_equal(all_valid,held['common_valid_mask']))
    if not cv['failures']:
        claim('CV_no_unreported_fold_failure',not all_fail)
        a=pred_s[all_valid]-pred_l[all_valid];b=xiv[all_valid]-pred_l[all_valid];den=float(a@a)
        raw=float(np.clip((a@b)/den,0,1)) if den>1e-20 else 1.
        close('CV_analytic_alpha',cv['alpha'],raw,1e-9);close('CV_quadratic_denominator',cv['quadratic_denominator'],den,1e-3)
        if den>1e-20:close('CV_unconstrained_alpha',cv['alpha_unconstrained'],(a@b)/den,1e-9)
        losses={'spline':np.mean((xiv[all_valid]-pred_s[all_valid])**2),'LL2':np.mean((xiv[all_valid]-pred_l[all_valid])**2),'selected':np.mean((xiv[all_valid]-(raw*pred_s[all_valid]+(1-raw)*pred_l[all_valid]))**2)}
        for k,v in losses.items():close('CV_validation_loss_'+k,cv['validation_losses'][k],v,2e-5)
        claim('CV_selected_loss_no_worse_than_components',losses['selected']<=min(losses['spline'],losses['LL2'])+1e-6)
    else:claim('CV_failed_fold_fallback_keeps_spline',cv['status']=='fallback_retained_spline' and cv['alpha']==1.)
    claim('CV_alpha_alias',cv['raw_alpha_S']==cv['alpha'])
    return int(sum(seen))

stages={};cohorts=policies=outer_folds=heldout_events=0;stage_users={}
for stage in ('development','confirmation'):
    summary=read(HERE/stage/'summary.json');rows=summary['rows'];spec=P[stage]
    expected={(s,k) for s in spec['seeds'] for k in spec['mechanisms']};actual=[(r['seed'],r['mechanism']) for r in rows]
    claim('exact_unique_protocol_roster',len(actual)==len(expected) and len(set(actual))==len(actual) and set(actual)==expected,stage)
    claim('exact_cohort_folder_roster',{p.name for p in (HERE/stage).iterdir() if p.is_dir()}=={f'{s}-{k}' for s,k in expected})
    stage_users[stage]=set();stages[stage]=[]
    for row in rows:
        cohorts+=1;seed=row['seed'];kind=row['mechanism'];folder=HERE/stage/f'{seed}-{kind}'
        claim('score_equals_summary_row',row==read(folder/'score.json'))
        facts=read(folder/'facts.json');api=read(folder/'baseline_api.json');shared=read(folder/'final_shared_state.json');cv=read(folder/'nested_selection.json');savedtruth=read(folder/'truth.json')
        x=np.asarray(facts['X'])[:,:2];d=np.asarray(facts['treatment']);y=np.asarray(facts['outcome']);users=np.asarray(facts['users']);stage_users[stage].update(users.tolist())
        claim('event_user_denominators',len(d)==480 and len(set(users))==240 and row['events']==480 and row['users']==240)
        xi=np.asarray(api['audit']['pseudo_outcome']);w=np.asarray(api['audit']['stabilized_weight']);cfg=api['configuration'];h=api['diagnostics']['bandwidth'];fold=np.asarray(api['audit']['fold_by_event'])
        claim('full_user_folds_integrity',len(set(fold))==3 and all(len(set(fold[users==u]))==1 for u in set(users)))
        for field,val in [('X',x),('dose',d),('pseudo_outcome',xi),('stabilized_weight',w)]:close('shared_full_'+field,shared[field],val,0.)
        claim('shared_xi_digest',row['shared_pseudo_outcome_sha256']==hashlib.sha256(xi.tobytes()).hexdigest())
        claim('shared_all_users_retained',shared['users']==users.tolist())
        check_fold_events=nested_checks(cv,x,d,y,users,facts['known_density']);heldout_events+=check_fold_events;outer_folds+=len(cv['folds'])
        close('row_CV_alpha',row['raw_alpha_spline'],cv['alpha'],0.);claim('row_CV_status',row['cv_status']==cv['status'] and row['cv_failure_count']==len(cv['failures']))
        state=read(folder/'retained_spline_state.json');claim('saved_shared_spline_state',shared['retained_spline']==state)
        bs=BSpline(state['knots'],state['coefficients'],state['degree'],extrapolate=False)
        sq=lambda a:bs(np.asarray(a)/2.4)*1800.;sd=lambda a:bs(np.asarray(a)/2.4,nu=1)*750.
        order=np.argsort(d,kind='stable');sf=make_smoothing_spline(d[order]/2.4,xi[order]/1800.,lam=len(d)*1e-4)
        close('retained_S_state_uses_exact_shared_xi',sq(GRID),sf(GRID/2.4)*1800.,2e-6)
        claim('retained_S_scale_and_lambda',state['lambda_mean']==1e-4 and state['x_scale']==2.4 and state['y_scale']==1800. and state['scipy_lambda']==len(d)*1e-4)
        close('bandwidth_rule',h,1.06*np.std(d)*len(set(users))**(-.2),1e-12)
        claim('common_original_support',supported(x,d,users,GRID,h,w,cfg).all())
        common_root=supported(x,d,users,MESH,h,w,cfg).all();strong=supported(x,d,users,GRID,2*h,w,cfg).all() and 2*h<=1.2
        strong_root=supported(x,d,users,MESH,2*h,w,cfg).all();spline_root=MESH.min()>=d.min() and MESH.max()<=d.max()
        for field in ('mean','contrasts','derivative'):close('independent_23node_truth_'+field,savedtruth[field],truths[kind][field],3e-5)
        compare_roots('independent_truth_target',savedtruth['target'],truths[kind]['target'])
        alpha={'retained_S':1.,'strong_LL2':0.}
        betas=P['fixed_blend_control']['beta_grid'] if stage=='development' else [SEL['selected']['beta']]
        gammas=P['candidate']['gamma_grid'] if stage=='development' else [SEL['selected']['gamma']]
        alpha.update({key('constant',b):b for b in betas});alpha.update({key('adaptive',g):1-g*(1-cv['alpha']) for g in gammas})
        claim('exact_final_policy_roster',set(row['policies'])==set(alpha)|{'original_LL'})
        reconstructed=dict(seed=seed,mechanism=kind,policies={})
        for name,saved in row['policies'].items():
            policies+=1;claim('all_designed_policy_outputs',saved['status']=='ok',[stage,seed,kind,name])
            if name=='original_LL':query=lambda a:ll(d,xi,h,a);derivative=lambda a:ll(d,xi,h,a,True);available=common_root
            else:
                a=alpha[name];close('effective_alpha_formula',saved['alpha_spline'],a,1e-14)
                claim('blend_component_support',a==1 or strong)
                query=lambda v,a=a:a*sq(v)+(1-a)*ll(d,xi,2*h,v)
                derivative=lambda v,a=a:a*sd(v)+(1-a)*ll(d,xi,2*h,v,True)
                available=common_root and (a==0 or spline_root) and (a==1 or strong_root)
            mean=query(GRID);deriv=derivative(GRID);contrast=mean-query([REF])[0]
            close('saved_final_mean',saved['mean'],mean,2e-6);close('saved_final_contrast',saved['contrast'],contrast,2e-6);close('saved_final_derivative',saved['derivative'],deriv,2e-6)
            for metric,value in [('curve_rmse_seconds',np.sqrt(np.mean((contrast-np.asarray(savedtruth['contrasts']))**2))),('level_mae_seconds',np.mean(abs(mean-np.asarray(savedtruth['mean'])))),('reference_error',mean[0]-savedtruth['mean'][0]),('derivative_rmse',np.sqrt(np.mean((deriv-np.asarray(savedtruth['derivative']))**2)))]:close('recomputed_'+metric,saved[metric],value,2e-6)
            claim('root_support_and_output',saved['root_support']==available and (saved['target'] is not None)==available)
            rr=roots(query) if available else None
            if rr is not None:compare_roots('estimated_target',saved['target'],rr)
            inserted=np.sort(np.r_[GRID,.731]);close('query_insertion',query(GRID),query(inserted)[np.searchsorted(inserted,GRID)],1e-9);close('query_single',query([GRID[7]])[0],mean[7],1e-9)
            reconstructed['policies'][name]=dict(status='ok',curve_rmse_seconds=float(np.sqrt(np.mean((contrast-np.asarray(savedtruth['contrasts']))**2))),level_mae_seconds=float(np.mean(abs(mean-np.asarray(savedtruth['mean'])))),derivative_rmse=float(np.sqrt(np.mean((deriv-np.asarray(savedtruth['derivative']))**2))),target=rr,true_target=truths[kind]['target'])
        close('formal_API_original_curve',row['policies']['original_LL']['contrast'],api['causal_curve']['contrasts'],1e-9)
        stages[stage].append(reconstructed)
claim('dev_final_users_disjoint',not(stage_users['development']&stage_users['confirmation']))

def aggregate(rows):
    out={}
    for name in sorted({n for r in rows for n in r['policies']}):
        vals=[r['policies'][name] for r in rows if r['policies'].get(name,{}).get('status')=='ok'];targets=[v for v in vals if v['target'] is not None]
        ce=[abs(v['target']['first_crossing']-v['true_target']['first_crossing']) for v in targets if v['target']['reached'] and v['true_target']['reached']]
        out[name]=dict(outputs=len(vals),designed=len(rows),mean_curve_rmse=float(np.mean([v['curve_rmse_seconds'] for v in vals])),mean_level_mae=float(np.mean([v['level_mae_seconds'] for v in vals])),mean_derivative_rmse=float(np.mean([v['derivative_rmse'] for v in vals])),target_outputs=len(targets),target_correct=sum(v['target']['reached']==v['true_target']['reached'] for v in targets),false_reached=sum(v['target']['reached'] and not v['true_target']['reached'] for v in targets),missed_reached=sum(not v['target']['reached'] and v['true_target']['reached'] for v in targets),crossing_error=float(np.mean(ce)) if ce else None,jointly_reached=len(ce))
    return out
AGG={s:aggregate(r) for s,r in stages.items()}
for stage,agg in AGG.items():
    original=read(HERE/stage/'summary.json')['aggregate']
    for name,fields in agg.items():
        for field,val in fields.items():
            if val is None:claim('aggregate_null',original[name][field] is None)
            else:close('aggregate_'+field,original[name][field],val,3e-6)
selected={}
for prefix,values,label,smaller in [('adaptive',P['candidate']['gamma_grid'],'gamma',True),('constant',P['fixed_blend_control']['beta_grid'],'beta',False)]:
    eligible=[v for v in values if AGG['development'][key(prefix,v)]['outputs']==24]
    selected[label]=min(eligible,key=lambda v:(AGG['development'][key(prefix,v)]['mean_curve_rmse'],v if smaller else -v))
claim('development_selection',selected==SEL['selected'],selected)
candidate=key('adaptive',selected['gamma']);control=key('constant',selected['beta']);final=AGG['confirmation'];compared=['retained_S',control,candidate,'original_LL','strong_LL2']
complete=len(stages['confirmation'])==96 and all(final[n]['outputs']==96 for n in compared);comparisons={}
for ref in ('retained_S',control):
    ds=[]
    for seed in P['confirmation']['seeds']:
        rows=[r for r in stages['confirmation'] if r['seed']==seed];claim('eight_mechanisms_per_final_seed',len(rows)==8)
        ds.append(float(np.mean([r['policies'][candidate]['curve_rmse_seconds']-r['policies'][ref]['curve_rmse_seconds'] for r in rows])))
    ds=np.asarray(ds);zero=[r for r in stages['confirmation'] if r['mechanism']=='zero_effect'];zero_complete=all(r['policies'][n]['target'] is not None for r in zero for n in (ref,candidate))
    fp={n:sum(r['policies'][n]['target']['reached'] for r in zero) for n in (ref,candidate)}
    half=float(student_t.ppf(.975,11)*ds.std(ddof=1)/np.sqrt(12))
    comparisons[ref]=dict(relative_gain=1-final[candidate]['mean_curve_rmse']/final[ref]['mean_curve_rmse'],seed_wins=int(np.sum(ds<0)),paired_seed_deltas=ds.tolist(),zero_targets_complete=zero_complete,zero_false_targets=fp,paired_seed_mean_delta=float(ds.mean()),paired_seed_descriptive_t95=[float(ds.mean()-half),float(ds.mean()+half)])
    original=DEC['comparisons'][ref]
    for field in ('relative_gain','seed_wins','paired_seed_mean_delta','paired_seed_descriptive_t95'):close('decision_comparison_'+field,original[field],comparisons[ref][field],3e-6)
    close('decision_seed_deltas',[v['delta'] for v in original['paired_seed_differences']],ds,3e-6);claim('decision_zero_false_targets',original['zero_false_targets']==fp)
gates=dict(all_96_outputs=complete,gain_vs_retained_at_least_5pct=complete and comparisons['retained_S']['relative_gain']>=.05,gain_vs_tuned_constant_at_least_5pct=complete and comparisons[control]['relative_gain']>=.05,seed_wins_vs_retained_at_least9=comparisons['retained_S']['seed_wins']>=9,seed_wins_vs_tuned_constant_at_least8=comparisons[control]['seed_wins']>=8,zero_false_targets_no_increase=all(v['zero_targets_complete'] and v['zero_false_targets'][candidate]<=v['zero_false_targets'][ref] for ref,v in comparisons.items()))
claim('decision_all_gates',gates==DEC['gates']);claim('decision_status',DEC['status']==('confirmed_new_stability_candidate' if all(gates.values()) else 'new_candidate_not_adopted_keep_retained_spline'))
for name in compared:
    for field,val in final[name].items():
        if val is None:claim('decision_null',DEC['aggregate'][name][field] is None)
        else:close('decision_aggregate_'+field,DEC['aggregate'][name][field],val,3e-6)
    for kind in P['confirmation']['mechanisms']:
        rows=[r for r in stages['confirmation'] if r['mechanism']==kind];values=[r['policies'][name]['curve_rmse_seconds'] for r in rows]
        claim('decision_mechanism_denominator',len(values)==DEC['per_mechanism'][kind][name]['outputs']==12)
        close('decision_mechanism_RMSE',DEC['per_mechanism'][kind][name]['mean_curve_rmse'],np.mean(values),2e-6)
formal=read(HERE/'formal_before.json');current={str(p.relative_to(ROOT)):sha(p) for ext in ('*.py','*.json') for p in (ROOT/'B1算法').rglob(ext)}
claim('formal_exact61_inventory_and_hashes',len(current)==61 and current==formal)
old=read(HERE/'retained_before.json');claim('retained376_hashes',len(old)==376 and all(sha(OLD/name)==h for name,h in old.items()))
for path,h in SEL['files'].items():claim('selection_freeze_hash',sha(ROOT/path)==h,path)
for path,h in read(HERE/'source_freeze.json').items():claim('before_sampling_source_freeze',sha(HERE/path)==h,path)
micro=read(HERE/'audit_nested.json');claim('nested_perturbation_microaudit_matches_source',micro['status']=='passed' and micro['nested_source_sha256']==sha(HERE/'nested.py'))

# Only fixed first development and first confirmation cohort public/nested replays.
sys.path.insert(0,str(ROOT/'B1算法'));sys.path.insert(0,str(HERE))
from b1_algorithm.effects.continuous import fit_continuous_effects
from nested import select_nested_alpha
replays=[]
previous=None
if (HERE/'verification_attempt1_partial.json').exists():
    text=(HERE/'verification_attempt1_partial.json').read_text(encoding='utf-8')
    end=text.index('"cohorts_checked"')
    previous=json.loads(text[:end].rstrip(', \r\n')+'}')
    claim('first_pass_replays_already_passed',all(v['check'] in {'CV_heldout_users','CV_TV_user_receipts','CV_external_TV_receipts'} for v in previous['issues']))
for stage in ('development','confirmation'):
    seed=P[stage]['seeds'][0];kind=P[stage]['mechanisms'][0];folder=HERE/stage/f'{seed}-{kind}';facts=read(folder/'facts.json');original=read(folder/'baseline_api.json');oldcv=read(folder/'nested_selection.json')
    x=np.asarray(facts['X'])[:,:2]
    if previous is None:
        b=fit_continuous_effects(x,facts['treatment'],facts['outcome'],facts['users'],dose_domain=P['domain'],grid=GRID,reference_dose=REF,incentive_unit=original['incentive_unit'],task=original['task'],continuous_assignment=True,assumptions=original['declared_assumptions'],known_density=facts['known_density'],config=original['configuration'])
        claim('public_replay_status',b['status']==original['status'])
        for field in original['audit']:close('public_replay_'+field,b['audit'][field],original['audit'][field],1e-8)
        cv=select_nested_alpha(x,facts['treatment'],facts['outcome'],facts['users'],config=original['configuration'],known_density=facts['known_density'])
        claim('nested_replay_exact_saved_dictionary',cv==oldcv,[stage,seed,kind])
    replays.append(dict(stage=stage,seed=seed,mechanism=kind,new_independent_sample=False,full_API_replay=True,nested_replay=True))

result=dict(passed=not issues,issues=issues,cohorts_checked=cohorts,development_roster=24,confirmation_roster=96,final_policy_curves_checked=policies,nested_outer_folds_checked=outer_folds,heldout_events_checked=heldout_events,total_claims=sum(counts.values()),check_counts=counts,maximum_errors=errors,independent_selected=selected,independent_aggregate=final,independent_comparisons=comparisons,independent_gates=gates,formal61_unchanged=True,retained376_unchanged=True,authorized_replays=replays,replays_are_not_new_samples=True,new_study_samples=False,all_cohort_nuisance_refits=False,
    no_gain_verified='All saved methods and nested weights reproduce. Candidate failure is an empirical result of this prespecified CV objective and test family, not evidence of implementation mismatch.',
    explicit_original_LL_context=dict(original_LL=final['original_LL']['mean_curve_rmse'],retained_S=final['retained_S']['mean_curve_rmse'],two_peak_original_LL=DEC['per_mechanism']['two_peak']['original_LL']['mean_curve_rmse'],two_peak_retained_S=DEC['per_mechanism']['two_peak']['retained_S']['mean_curve_rmse'],interpretation='Do not hide originalLL outperforming retained spline on the new overall challenge. No post-test switch or retuning authorized by this audit.'),
    verifier_correction='First pass completed all computations/replays, but receipt comparisons needed documented string: user-ID normalization and output needed Python int conversion. Its partial output is preserved; only these verifier issues corrected, with no changed study data, score, parameter or additional nuisance replay.' if previous is not None else None,
    objective_scope='Nested CV targets observed-dose common-support pseudo-outcome LEVEL risk; development/confirmation primary is uniform-grid REFERENCE CONTRAST risk. Two distinct objectives, both implemented as declared.',
    diagnosis_scope='Older frozen error decomposition is not full causal variance attribution; operator numerical remainder is explicit and old saved scores remain authority.',
    truth_check='Independent23-node analytic integration, including true sin4pi double peak; noisy_nonmonotone has unchanged mean and altered Beta concentration only.',limitations=['12 independent final seed blocks; mechanisms are paired within blocks','Related simulated family, no field compensation verification','No new uncertainty or downstream algorithms certified'],elapsed_seconds=time.perf_counter()-started,auditor_source_sha256=sha(Path(__file__)))
encoded=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
with (HERE/'verification.json').open('w',encoding='utf-8') as f:f.write(encoded)
print(json.dumps(dict(passed=result['passed'],cohorts=cohorts,policies=policies,outer_folds=outer_folds,claims=result['total_claims'],issues=issues,seconds=result['elapsed_seconds']),ensure_ascii=False))
if issues:raise SystemExit(1)
