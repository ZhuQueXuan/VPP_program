"""Independent whole-user bootstrap and finite-grid inversion verification.

No imports from the implementation, generator, evaluator, or prior studies.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
os.environ.setdefault('OMP_NUM_THREADS','2')
from pathlib import Path
from itertools import product
import ast
import csv
import hashlib
import json
import math
import numpy as np

BASE=Path(__file__).resolve().parent
ROOT=BASE.parent.parent
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_crossing_uncertainty_v1_20261026'
CHECKS=[];MAXIMA={}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def check(name,ok,detail=None):CHECKS.append(dict(name=name,ok=bool(ok),detail=detail))
def difference(name,a,b,tolerance=1e-10):
    a,b=np.asarray(a),np.asarray(b)
    finite=np.isfinite(a)&np.isfinite(b)
    err=float(np.max(abs(a[finite]-b[finite]))) if finite.any() else 0.
    MAXIMA[name]=max(MAXIMA.get(name,0.),err)
    check(name,np.array_equal(np.isfinite(a),np.isfinite(b)) and err<tolerance,err)

def aggregate(user,dose,x,y):
    masks=[np.ones(len(user),bool),x<0,x>=0]
    count=np.zeros((3,600,7),int);total=np.zeros((4,3,600,7))
    # Bincount indexed by user/dose is independent of main np.add.at path.
    for g,mask in enumerate(masks):
        keys=7*user[mask]+dose[mask]
        count[g]=np.bincount(keys,minlength=4200).reshape(600,7)
        for s in range(4):total[s,g]=np.bincount(keys,weights=y[s,mask],minlength=4200).reshape(600,7)
    return count,total

def sets_from_band(lo,hi,delta):
    """Enumerate endpoint witnesses for the rectangular simultaneous band."""
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        return dict(status='unavailable',candidates=[],no_cross_possible=None,unique=False,
                    possible_up=[],supported_up=[],supported_decrease=[])
    values=[]
    for k in range(1,7):values.append(sorted(set([float(lo[k]),float(hi[k])])))
    first=set();possible_up=set();always_up=set(range(1,7));always_down=set(range(1,7))
    for choice in product(*values):
        curve=[0.]+list(choice)
        reached=[k for k in range(1,7) if curve[k]>=delta]
        first.add(reached[0] if reached else -1)
        up={k for k in range(1,7) if curve[k-1]<delta<=curve[k]}
        down={k for k in range(1,7) if curve[k-1]>curve[k]}
        possible_up|=up;always_up&=up;always_down&=down
    candidates=sorted(first-{-1});nocross=-1 in first
    status='supported_not_reached' if not candidates else ('crossing_unresolved' if nocross else 'bounded_first_crossing')
    return dict(status=status,candidates=candidates,no_cross_possible=nocross,
                unique=len(candidates)==1 and not nocross,possible_up=sorted(possible_up),
                supported_up=sorted(always_up),supported_decrease=sorted(always_down))

def independent_truth(p):
    z,wt=np.polynomial.legendre.leggauss(17)
    q=np.empty((4,3,7))
    for g in range(3):
        x=z if g==0 else (z-1)/2 if g==1 else (z+1)/2
        cap=(.4+.2*(x[:,None]+1))*(.8+.2*z[None,:]**2)
        meancap=np.sum(cap*wt[:,None]*wt[None,:])/4
        check(f'truth mean capacity {g}',abs(meancap-[.6,.5,.7][g]*13/15)<1e-12)
        for s,name in enumerate(p['scenarios']):
            inc=p['scm']['increments'][name]
            if s==0:increments=np.maximum(np.asarray(p['doses'])-1.2,0)*.3/1.2
            elif s==1:increments=np.asarray(inc)
            elif s==2:increments=np.zeros(7)
            else:increments=.19*np.asarray(p['doses'])/2.4
            q[s,g]=meancap*.975*increments
    return q

def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8-sig'))
    raw=load(RAW/'observations.npz');bands=load(BASE/'bands.npz')
    check('observed-only raw keys',set(raw)=={'user','x','w','dose','A','Y'})
    check('frozen raw shapes',raw['user'].shape==(8400,) and all(raw[k].shape==(100,8400) for k in ('x','w','dose'))
          and all(raw[k].shape==(100,4,8400) for k in ('A','Y')))
    check('valid finite public observations',all(np.isfinite(raw[k]).all() for k in raw)
          and np.isin(raw['A'],[0,1]).all() and np.isin(raw['dose'],np.arange(7)).all()
          and (abs(raw['x'])<=1).all() and (abs(raw['w'])<=1).all())
    users,counts=np.unique(raw['user'],return_counts=True)
    check('600 user clusters each preserve all 14 events',np.array_equal(users,np.arange(600)) and (counts==14).all())
    receipt=json.loads((BASE/'inference_receipt.json').read_text())
    check('raw and bands identity before evaluation',receipt['observations_sha256']==sha(RAW/'observations.npz')
          and receipt['bands_sha256']==sha(BASE/'bands.npz'))
    own={k:[] for k in ('mean','gain','lower','upper','q','available','bad_draws','counts','maxima')}
    for r in range(100):
        user=raw['user'];di=raw['dose'][r];x=raw['x'][r];y=raw['Y'][r]
        count,total=aggregate(user,di,x,y)
        original=count.sum(axis=1);mu=total.sum(axis=2)/original[None,:,:];gain=mu-mu[:,:,:1]
        rng=np.random.default_rng(p['seed_start']+r+p['bootstrap_seed_offset'])
        weights=rng.multinomial(600,np.repeat(1/600,600),size=999)
        check(f'{r}: exact whole-user resampling weight identity',
              sha_weights(weights)==receipt['bootstrap_weight_sha256'][r] and (weights.sum(axis=1)==600).all())
        den=np.empty((999,3,7));maxima=np.empty((999,4,3))
        for g in range(3):
            den[:,g]=weights@count[g]
            for s in range(4):
                numerator=weights@total[s,g]
                means=numerator/np.where(den[:,g]>0,den[:,g],1)
                changes=means-means[:,:1]
                maxima[:,s,g]=np.max(abs(changes[:,1:]-gain[s,g,1:]),axis=1)
        bad=np.sum(np.any(den==0,axis=2),axis=0)
        available=(original.min(axis=1)>=50)&(bad==0)
        order=math.ceil((999-1)*.95)
        q=np.sort(maxima,axis=0)[order]
        q[:,~available]=np.nan
        lo=gain-q[:,:,None];hi=gain+q[:,:,None]
        lo[:,:,0]=hi[:,:,0]=0.
        lo[:,~available]=np.nan;hi[:,~available]=np.nan
        current=dict(mean=mu,gain=gain,lower=lo,upper=hi,q=q,available=np.broadcast_to(available,(4,3)),
                     bad_draws=bad,counts=original,maxima=maxima)
        for k,v in current.items():
            own[k].append(v)
            if k in ('available','bad_draws','counts'):check(f'{r}: exact independent {k}',np.array_equal(v,bands[k][r]))
            else:difference('independent bootstrap '+k,v,bands[k][r])
        # Three explicit duplicate-user draws independently confirm sufficient
        # statistics preserve event groups, doses and all scenario outcomes.
        for b in (0,498,998):
            event_weight=weights[b,user]
            masks=[np.ones(8400,bool),x<0,x>=0]
            for g,mask in enumerate(masks):
                for k in (0,3,6):
                    selected=mask&(di==k)
                    for s in (0,1,3):
                        explicit=math.fsum(float(a)*float(v) for a,v in zip(event_weight[selected],y[s,selected]))/math.fsum(event_weight[selected])
                        from_aggregates=float(weights[b]@total[s,g,:,k]/(weights[b]@count[g,:,k]))
                        difference('explicit whole-user event-weighted means',explicit,from_aggregates,1e-12)
        if (r+1)%20==0:print('independent bootstrap',r+1,flush=True)
    own={k:np.asarray(v) for k,v in own.items()}
    truth=independent_truth(p)
    verify_evaluation(p,bands,truth)
    verify_panel(raw)
    verify_sources()
    report=dict(status='passed' if all(z['ok'] for z in CHECKS) else 'failed',
        checks_passed=sum(z['ok'] for z in CHECKS),checks_failed=sum(not z['ok'] for z in CHECKS),maxima=MAXIMA,
        checks=CHECKS,identity='independent_simulation_and_numerical_verification_only',
        verifier_sha256=sha(Path(__file__)),bands_sha256=sha(BASE/'bands.npz'),observations_sha256=sha(RAW/'observations.npz'))
    (BASE/'independent_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','checks_passed','checks_failed','maxima')}))
    return 0 if report['status']=='passed' else 1

def sha_weights(weights):return hashlib.sha256(weights.astype('<i8').tobytes()).hexdigest()

def verify_evaluation(p,bands,truth):
    from scipy.stats import beta
    ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    difference('independent population truth',truth,ev['truth_gains'],1e-12)
    with (BASE/'crossings.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (BASE/'coverage.csv').open(encoding='utf-8-sig',newline='') as f:covrows=list(csv.DictReader(f))
    check('all 7200 crossing and 1200 coverage records retained',len(rows)==7200 and len(covrows)==1200)
    bykey={(int(v['seed']),v['scenario'],v['group'],float(v['delta']),v['method']):v for v in rows}
    covkey={(int(v['seed']),v['scenario'],v['group']):v for v in covrows}
    ownrows=[];owncov=[]
    def cellcheck(actual,expected,label):
        for key,value in expected.items():
            a=actual[key]
            if value is None:a=None if a=='' else ast.literal_eval(a)
            elif isinstance(value,(list,bool)):a=ast.literal_eval(a)
            elif isinstance(value,int):a=int(a)
            elif isinstance(value,float):
                difference(label+' '+key,float(a),value,1e-10);continue
            check(label+' '+key,a==value)
    for r in range(100):
        seed=p['seed_start']+r
        for s,scene in enumerate(p['scenarios']):
            for g,group in enumerate(p['groups']):
                gain=bands['gain'][r,s,g];lo=bands['lower'][r,s,g];hi=bands['upper'][r,s,g]
                valid=bool(bands['available'][r,s,g]);t=truth[s,g]
                covered=bool(valid and all(lo[k]<=t[k]<=hi[k] for k in range(7)))
                cv=dict(seed=seed,scenario=scene,group=group,available=valid,covered=covered,
                    q=float(bands['q'][r,s,g]),minimum_original_count=int(bands['counts'][r,g].min()),bad_draws=int(bands['bad_draws'][r,g]))
                owncov.append(cv);cellcheck(covkey[seed,scene,group],cv,'coverage')
                for delta in p['deltas']:
                    hits=[k for k in range(1,7) if t[k]>=delta];first=hits[0] if hits else -1
                    edges=[k for k in range(1,7) if t[k-1]<delta<=t[k]]
                    for method in ('strict_D109','naive_first','user_cluster_band'):
                        if method=='user_cluster_band':
                            inv=sets_from_band(lo,hi,delta)
                            cs=inv['candidates'];nc=inv['no_cross_possible'];st=inv['status'];unique=inv['unique']
                            reached=st!='unavailable' and not nc;notreached=st=='supported_not_reached'
                            included=st!='unavailable' and (first in cs if first!=-1 else nc)
                            down=inv['supported_decrease'];up=inv['supported_up']
                            allup=valid and set(edges)<=set(inv['possible_up'])
                            bandcovered=covered
                        else:
                            observed=[k for k in range(1,7) if gain[k]>=delta]
                            idx=observed[0] if observed else -1
                            st='not_reached' if not observed else 'bracket'
                            if method=='strict_D109' and observed and any(gain[k]-gain[k-1]<-1e-10 for k in range(1,7)):st='ambiguous_nonmonotone'
                            cs=[idx] if st=='bracket' else [];nc=st=='not_reached';unique=st=='bracket'
                            reached=unique;notreached=nc
                            included=(unique and idx==first) or (nc and first==-1)
                            down=[];up=[];allup=False;bandcovered=None
                        v=dict(seed=seed,scenario=scene,group=group,delta=delta,method=method,status=st,
                            first_candidates=cs,no_cross_possible=nc,unique=unique,true_first=first,true_up_edges=edges,
                            truth_in_set=bool(included),definite_reached=bool(reached),definite_not_reached=bool(notreached),
                            wrong_definite_reached=bool(reached and first==-1),wrong_definite_not_reached=bool(notreached and first!=-1),
                            supported_decrease=down,true_decline=bool(any(t[k]<t[k-1]-1e-12 for k in range(1,7))),
                            supported_up=up,all_true_up_possible=bool(allup),band_covered=bandcovered,candidate_count=len(cs),
                            candidate_hull_width=(max(cs)-min(cs)+1)*.4 if cs else 0.)
                        ownrows.append(v);cellcheck(bykey[seed,scene,group,delta,method],v,'crossing')
    for a in ev['summary']:
        rr=[v for v in ownrows if all(v[k]==a[k] for k in ('scenario','group','delta','method'))]
        cc=[v for v in owncov if v['scenario']==a['scenario'] and v['group']==a['group']]
        check('summary exact all100 denominator',len(rr)==a['denominator']==100)
        countfields={
            'unique_count':sum(v['unique'] for v in rr),
            'unresolved_count':sum(v['status']=='crossing_unresolved' for v in rr),
            'bounded_multiple_count':sum(v['status']=='bounded_first_crossing' and not v['unique'] for v in rr),
            'supported_not_reached_count':sum(v['definite_not_reached'] for v in rr),
            'ambiguous_count':sum(v['status']=='ambiguous_nonmonotone' for v in rr),
            'unavailable_count':sum(v['status']=='unavailable' for v in rr),
            'supported_decline_count':sum(bool(v['supported_decrease']) for v in rr),
            'all_true_up_possible_count':sum(v['all_true_up_possible'] for v in rr),
            'three_supported_up_count':sum(len(v['supported_up'])==3 for v in rr)}
        for key,value in countfields.items():check('summary '+key,a[key]==value)
        for key in ('true_first','true_up_edges'):check('summary '+key,a[key]==rr[0][key])
        difference('summary mean candidate count',a['mean_candidate_count'],np.mean([v['candidate_count'] for v in rr]))
        difference('summary mean candidate hull width',a['mean_candidate_hull_width'],np.mean([v['candidate_hull_width'] for v in rr]))
        rates={'set_or_point_coverage':sum(v['truth_in_set'] for v in rr),
               'wrong_definite_reached':sum(v['wrong_definite_reached'] for v in rr),
               'wrong_definite_not_reached':sum(v['wrong_definite_not_reached'] for v in rr)}
        if a['method']=='user_cluster_band':rates['band_coverage']=sum(v['covered'] for v in cc)
        else:check('point comparator not labeled confidence band',a['band_coverage'] is None)
        for key,k in rates.items():
            v=a[key];check('summary binomial count '+key,v['count']==k and v['denominator']==100)
            difference('summary rate '+key,v['rate'],k/100)
            ci=[0. if k==0 else beta.ppf(.025,k,101-k),1. if k==100 else beta.ppf(.975,k+1,100-k)]
            difference('independent beta MC interval '+key,v['mc95_exact'],ci,1e-10)
    with (BASE/'verification_recomputed_crossings.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(ownrows[0]));w.writeheader();w.writerows(ownrows)

def verify_panel(raw):
    panel=load(RAW/'request_panel.npz');hidden=load(BASE/'panel_evaluator.npz')
    check('public panel no hidden action labels',set(panel)=={'power_obs_kw','time_edges_s','indices','reference_kw'})
    check('84 observed request panels',panel['power_obs_kw'].shape==(84,120)
          and np.array_equal(panel['time_edges_s'],np.arange(600,1801,10)))
    for i,(s,j,a,c,delay,y) in enumerate(hidden['meta']):
        s,j=int(s),int(j)
        integral=math.fsum((3-float(v))*10 for v in panel['power_obs_kw'][i])/1800
        difference('public observed request integral',integral,raw['Y'][0,s,j],1e-12)
        difference('evaluator panel recorded Y',integral,y,1e-12)
        check(f'panel {i} metadata observation identity',a==raw['A'][0,s,j]
              and np.array_equal(panel['indices'][i],[s,j]) and delay in range(0,61,10))
    x,w=raw['x'],raw['w'];cap=(.4+.2*(x+1))*(.8+.2*w*w)
    margin=(.5+.75*(x+1))*(1800+1800*(x+1))-1.5*cap*1200
    check('840000 base conditions request bounds and analytic recovery',
          (3-1.5*cap>=0).all() and (margin>=0).all(),float(margin.min()))

def verify_sources():
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    for name,digest in frozen['source'].items():check('frozen source '+name,sha(BASE/name)==digest)
    for section in ('protected_d109','live_models'):
        for name,digest in frozen[section].items():check('unchanged '+section+' '+name,sha(ROOT/name)==digest)
    tree=ast.parse((BASE/'run.py').read_text(encoding='utf-8-sig'))
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    text=ast.unparse(main)
    check('observed aggregate reads only user,dose,x,Y',"obs['user']" in text and "obs['dose']" in text
          and "obs['x']" in text and "obs['Y']" in text and 'evaluation_truth' not in text)
    infer=(BASE/'inference.py').read_text(encoding='utf-8-sig')
    imports=[ast.unparse(n) for n in ast.walk(ast.parse(infer)) if isinstance(n,(ast.Import,ast.ImportFrom))]
    check('inference imports no simulator/evaluator',not any('generate' in n or 'evaluate' in n for n in imports))

if __name__=='__main__':raise SystemExit(main())
