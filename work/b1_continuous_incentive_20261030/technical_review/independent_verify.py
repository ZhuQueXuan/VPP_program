"""Small independent algebra/contract checks; no research rerun or performance claim."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import sys,json,hashlib,copy
import numpy as np
from scipy.special import expit
from scipy.integrate import quad

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (fit_continuous_effects,ContinuousEffectConfig,provided_reference,
                    analyze_events,estimate_event_curve,estimate_metered_curve)
from b1_algorithm.effects.continuous import (_dr_pseudo_outcome,_marginal_logit_density,
                                            local_linear_weights)

checks=[];details={}
def check(name,condition,detail=None):
    if not bool(condition):raise AssertionError(name+': '+str(detail))
    checks.append(name)
    if detail is not None:details[name]=detail

def main():
    target=HERE/'independent_receipt.json'
    if target.exists():raise RuntimeError('receipt exists; preserve earlier check')
    # Exact X|D integration with a NONCONSTANT marginal dose density.  This is
    # separate from the parent check, whose true marginal density was constant.
    a=np.linspace(.001,.999,211);t=2*a-1
    px=np.array([.2,.3,.5])[:,None];xv=np.array([-.8,.3,1.1])[:,None]
    p=1+np.array([.2,-.4,.8])[:,None]*t
    p_bad=1+np.array([-.3,.4,-.1])[:,None]*t
    true_mu=.2+.4*np.sin(2*a)[None,:]+.17*xv*(1+a)
    bad_mu=.1+.2*a[None,:]-.05*xv
    truth=(px*true_mu).sum(0);true_marginal=(px*p).sum(0)
    x_given_a=px*p/true_marginal
    errors={}
    for mu_ok,pi_ok in ((True,True),(True,False),(False,True),(False,False)):
        m=true_mu if mu_ok else bad_mu;density=p if pi_ok else p_bad
        xi=_dr_pseudo_outcome(true_mu,m,(px*m).sum(0),density,(px*density).sum(0))
        error=float(np.max(abs((x_given_a*xi).sum(0)-truth)))
        errors[str((mu_ok,pi_ok))]=error
        check('exact_DR_nonconstant_marginal_'+str((mu_ok,pi_ok)),error<2e-14 if mu_ok or pi_ok else error>1e-3,error)
    # Independent elementary logit-normal mixture and unit transformation.
    q=np.array([.03,.31,.85,1.7,2.35]);means=np.array([-.7,.3,1.]);sd=.8;span=2.4
    def elementary(v):
        u=v/span;z=np.log(u/(1-u))
        return float(np.mean(np.exp(-.5*((z-means)/sd)**2)/(np.sqrt(2*np.pi)*sd))/(span*u*(1-u)))
    density=_marginal_logit_density(q,means,sd,0,span)
    check('marginal_GPS_matches_elementary_mixture',np.max(abs(density-np.array([elementary(v) for v in q])))<2e-14)
    mass=quad(elementary,0,span,epsabs=1e-9)[0]
    check('bounded_marginal_density_integrates_to_one',abs(mass-1)<1e-8,mass)
    check('density_yuan_cent_jacobian',np.max(abs(_marginal_logit_density(q*100,means,sd,0,span*100)*100-density))<2e-13)

    rng=np.random.default_rng(81190);n_users=180;n=n_users*3
    users=np.repeat(np.arange(n_users),3)
    x=np.column_stack([np.repeat(rng.uniform(-1,1,size=n_users),3),rng.uniform(-1,1,size=n)])
    d=span*expit(.2*x[:,0]-.1*x[:,1]+rng.normal(0,.9,n))
    y=.25+.2*np.sin(2*np.pi*d/span)+.08*x[:,0]+.03*x[:,1]+rng.normal(0,.035,n)
    assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
                     same_outcome_definition=True,conditional_exchangeability=True,randomized_assignment=False)
    task=dict(task_id='independent_EV_task',outcome_name='eta_raw',outcome_unit='ratio',
              target_population='toy_events',window_minutes=[0.,45.],q_kw=1.5,
              task_pre_treatment=True,reference_status='known',reference_uncertainty='known_reference')
    cfg=dict(n_boot=99,return_audit=True,seed=901,bandwidth=.3)
    opts=dict(dose_domain=[0,span],grid=[.65,1.05,1.65],reference_dose=1.05,
              incentive_unit='yuan/kWh',task=task,continuous_assignment=True,assumptions=assumptions,config=cfg)
    base=fit_continuous_effects(x,d,y,users,**opts)
    check('estimated_GPS_toy_supported',base['status']=='causal',base.get('reasons'))
    cent=copy.deepcopy(opts);cent.update(dose_domain=[0,240],grid=[65,105,165],reference_dose=105,
                                       incentive_unit='cent/kWh',config=cfg|{'bandwidth':30.})
    scaled=fit_continuous_effects(x,d*100,y,users,**cent)
    check('estimated_GPS_cent_supported',scaled['status']=='causal',scaled.get('reasons'))
    err=float(np.max(abs(np.array(base['causal_curve']['mean_outcomes'])-scaled['causal_curve']['mean_outcomes'])))
    check('estimated_GPS_currency_equivariance',err<1e-10,err)
    err=float(np.max(abs(np.array(base['inference']['standard_errors'])-scaled['inference']['standard_errors'])))
    check('conditional_sampling_SE_currency_equivariance',err<1e-10,err)
    audit=base['audit'];fold=np.array(audit['fold_by_event'])
    check('all_repeated_users_crossfit_together',all(np.unique(fold[users==u]).size==1 for u in np.unique(users)))
    for value in (None,False):
        unclear=opts|{'assumptions':assumptions|{'pre_treatment_X':value}}
        r=fit_continuous_effects(x,d,y,users,**unclear)
        check('unknown_or_false_X_assumption_association_'+str(value),r['status']=='association' and r['causal_curve'] is None and r['inference'] is None)
    check('no_unsmoothed_coverage_claim',base['inference']['coverage_for_unsmoothed_causal_curve_validated'] is False)
    pts=np.array([0.,.17,1.05,2.4]);h=.28
    L=local_linear_weights(d,pts,h)
    u=(d[None,:]-pts[:,None])/h;k=np.exp(-u*u/2)
    independently=[]
    for j,p0 in enumerate(pts):
        design=np.column_stack([np.ones(n),(d-p0)/h]);gram=design.T@(k[j,:,None]*design)
        independently.append(np.linalg.solve(gram,design.T*k[j])[0])
    check('local_weights_match_independent_WLS',np.max(abs(L-np.array(independently)))<2e-13)
    check('one_sided_local_weights_reproduce_constant',np.max(abs(L@np.ones(n)-1))<2e-13)
    check('one_sided_local_weights_reproduce_linear',np.max(abs(L@(1.3-.8*d)-(1.3-.8*pts)))<2e-13)
    for label,dx in [('identical',np.ones(30)),('far_absent',np.linspace(0,.1,30))]:
        try:local_linear_weights(dx,np.array([1.]),1e-3)
        except ValueError:check('local_singular_rejected_'+label,True)
        else:raise AssertionError('singular fit accepted: '+label)
    # Genuine empty neighborhood and unsupported known design, no large run.
    unif=rng.uniform(.001,span-.001,n);pdf=np.full(n,1/span)
    randomized=assumptions|{'conditional_exchangeability':None,'randomized_assignment':True}
    known_opts=opts|{'assumptions':randomized,'known_density':pdf,'grid':[.5,1.2,1.9],
                     'reference_dose':.5,'config':cfg|{'bandwidth':.15}}
    gap=np.where(unif<span/2,unif*.5,span-(span-unif)*.5)
    r=fit_continuous_effects(x,gap,y,users,**known_opts)
    check('empty_support_hole_rejected',r['status']=='unsupported' and r['causal_curve'] is None)
    r=fit_continuous_effects(x,unif,y,users,**(known_opts|{'known_density':pdf*.7}))
    check('nonuniform_known_density_rejected',r['status']=='invalid_input')
    for endpoint in (0.,span):
        atom=unif.copy();atom[0]=endpoint
        check('endpoint_atom_rejected_'+str(endpoint),fit_continuous_effects(x,atom,y,users,**known_opts)['status']=='invalid_input')
    # Public pipelines: same outcome vector, row order, and constant-reference
    # contrast cancellation.  Conservative process avoids native solver runs.
    count=240;records=[]
    for i in range(count):
        start=10000.+300*i;starts=start+np.arange(-15.,60.,15.);ends=starts+15.
        t=dict(task_id='i'+str(i),user_id='u'+str(i//3),meter_id='m'+str(i//3),
               start_min=start,end_min=start+45.,notice_min=start-15.,request_kw=1.5,task_pre_treatment=True)
        b=np.full(len(starts),3.);power=b.copy();power[(starts>=start)&(ends<=start+45.)]-=1.5*y[i]
        records.append(dict(task=t,starts_min=starts,ends_min=ends,power_kw=power,noise_sigma_kw=.04,
                            reference=provided_reference(t,starts,ends,b,available_at_min=start-15.)))
    events=analyze_events(records,process_method='conservative')
    check('public_event_outcomes_preserve_toy_values',all(e['status']=='ok' for e in events) and
          np.max(abs(np.array([e['outcome']['value'] for e in events])-y[:count]))<1e-12)
    public_opts=dict(dose_domain=[0,span],grid=[.7,1.1,1.5],reference_dose=1.1,
        incentive_unit='yuan/kWh',continuous_assignment=True,assumptions=randomized,
        known_density=pdf[:count],continuous_config=cfg|{'bandwidth':.35})
    event_curve=estimate_event_curve(events,x[:count],unif[:count],**public_opts)
    meter_curve=estimate_metered_curve(records,x[:count],unif[:count],**public_opts)
    check('both_public_curves_supported',event_curve['status']==meter_curve['status']=='causal',
          [event_curve.get('reasons'),meter_curve.get('reasons')])
    check('public_meter_event_constant_reference_contrasts_equal',np.max(abs(np.array(event_curve['causal_curve']['contrasts'])-meter_curve['causal_curve']['contrasts']))<1e-11)
    check('public_meter_absolute_level_not_net_delivery',meter_curve['metered_pipeline']['absolute_levels_are_net_delivery'] is False)
    check('public_event_no_process_fit_in_energy',event_curve['pipeline']['process_fit_used_in_energy'] is False)
    bad=copy.deepcopy(events);bad[-1]['task']['request_kw']=2.
    check('public_heterogeneous_request_rejected',estimate_event_curve(bad,x[:count],unif[:count],**public_opts)['status']=='invalid_input')
    bad=copy.deepcopy(records);bad[-1]['task']['end_min']+=15.
    check('public_heterogeneous_duration_rejected',estimate_metered_curve(bad,x[:count],unif[:count],**public_opts)['status']=='invalid_input')
    # Reusing exactly the same physical meter window must not create a new row.
    bad=copy.deepcopy(records);bad[-1]=copy.deepcopy(bad[-2]);bad[-1]['task']['task_id']='renamed'
    check('public_renamed_duplicate_meter_window_rejected',estimate_metered_curve(bad,x[:count],unif[:count],**public_opts)['status']=='invalid_input')
    sources=['B1算法/b1_algorithm/effects/continuous.py','B1算法/b1_algorithm/effects/plotting.py',
             'B1算法/b1_algorithm/api.py','B1算法/b1_algorithm/metered_effects.py']
    receipt=dict(passed=True,checks=checks,n_checks=len(checks),details=details,
        production_files_modified=False,research_experiments_rerun=False,
        scope='exact algebra and small synthetic functional checks only; no performance or real EV validation',
        reviewed_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
