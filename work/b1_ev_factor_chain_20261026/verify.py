"""Independent curve, graph path, discrete-score and effect-reference checks.

Does not import the study generator, feature, graph, estimator or evaluator.
"""
from pathlib import Path
from itertools import combinations,product
import json,csv,math,hashlib
import numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_ev_factor_chain_v1_20261026'
NAMES=['X','W','D','A','S'];CHECKS=[];ERRORS={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(n,v):CHECKS.append(dict(name=n,passed=bool(v)))
def close(n,a,b,tol=1e-10):
    a,b=np.asarray(a),np.asarray(b);valid=np.isfinite(a)&np.isfinite(b);err=float(np.max(abs(a[valid]-b[valid]))) if valid.any() else 0.
    ERRORS[n]=max(ERRORS.get(n,0),err);check(n,a.shape==b.shape and np.array_equal(np.isfinite(a),np.isfinite(b)) and err<tol)
def sub(v):
    for k in range(len(v)+1):yield from combinations(v,k)

def valid_adjustments(edges):
    """Independent active-path enumeration after removing outgoing D edges."""
    original=set(map(tuple,edges));desc={n:{n} for n in NAMES}
    for _ in range(5):
        for a,b in original:desc[a]|=desc[b]
    allowed=[v for v in ['X','W'] if v not in desc['D']]
    back={(a,b) for a,b in original if a!='D'};adj={v:set() for v in NAMES}
    for a,b in back:adj[a].add(b);adj[b].add(a)
    paths=[]
    def walk(path):
        if path[-1]=='S':paths.append(path);return
        for v in adj[path[-1]]:
            if v not in path:walk(path+[v])
    walk(['D']);valid=[]
    # Descendants for collider activation must be in the backdoor graph.
    bd={n:{n} for n in NAMES}
    for _ in range(5):
        for a,b in back:bd[a]|=bd[b]
    for z in sub(allowed):
        blocked=True
        for path in paths:
            active=True
            for a,m,b in zip(path,path[1:],path[2:]):
                collider=(a,m) in back and (b,m) in back
                if (collider and not (bd[m]&set(z))) or (not collider and m in z):active=False;break
            if active:blocked=False;break
        if blocked:valid.append(list(z))
    return valid

def local_score(data,node,parents,minimum=20):
    ll=0.;mincount=len(data)
    for state in product((0,1),repeat=len(parents)):
        selected=np.ones(len(data),bool)
        for name,val in zip(parents,state):selected&=data[:,NAMES.index(name)]==val
        n=int(selected.sum());mincount=min(mincount,n)
        if n<minimum:return None,mincount
        one=int(data[selected,node].sum());zero=n-one
        if one:ll+=one*math.log(one/n)
        if zero:ll+=zero*math.log(zero/n)
    return -2*ll+(2**len(parents))*math.log(len(data)),mincount

def independent_truth(p):
    # Enumerate representable powers around the exact public reduction rule.
    vals=np.array([np.float32(2.85)],np.float32)
    lower=np.nextafter(vals[0],np.float32(-np.inf));upper=np.nextafter(vals[0],np.float32(np.inf))
    candidates=sorted([float(lower),float(vals[0]),float(upper)])
    floor=max(v for v in candidates if 3-v>=.15)
    ceiling=float(np.nextafter(np.float32(floor),np.float32(np.inf)))
    boundary=(floor+ceiling)/2
    q0=.5*math.erfc((3-boundary)/(.05*math.sqrt(2)))
    q1=.5*math.erfc((1.5-boundary)/(.05*math.sqrt(2)))
    check('represented Gaussian active probability one',q1==1.)
    def tail(n,k):
        if k<=0:return 1.
        if k>n:return 0.
        return math.fsum(math.comb(n,j)*q0**j*(1-q0)**(n-j) for j in range(k,n+1))
    null=tail(120,60);truth=np.zeros((4,2,2,2));levels=np.zeros((2,2,2));means=np.zeros((2,2))
    for x,w in product((0,1),repeat=2):
        durations=[];sprob=[]
        for jitter in range(-30,31):
            horizon=2700+600*x-300*w+10*jitter
            for delay in range(0,61,10):
                length=min(1200-delay,horizon-1800);durations.append(length)
                active=length//10;sprob.append(tail(120-active,60-active))
        means[x,w]=math.fsum(durations)/len(durations)
        levels[x,w]=[means[x,w]*(q1-q0),math.fsum(sprob)/len(sprob)-null]
        for s,beta in enumerate(p['acceptance_dose_coefficients']):
            p1=1/(1+math.exp(.2-beta+.8*w));p0=1/(1+math.exp(.2+.8*w))
            truth[s,x,w]=(p1-p0)*levels[x,w]
    return truth,dict(q0=q0,q1=q1,stored_threshold_boundary_kw=boundary,physical_duration_mean_s=means,accepted_minus_refused_outcome_means=levels)

def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    with np.load(RAW/'observations.npz') as z:obs={k:z[k] for k in z.files}
    with np.load(BASE/'observed_features.npz') as z:feats={k:z[k] for k in z.files}
    hidden=np.load(BASE/'hidden_evaluator.npz');pred=np.load(BASE/'predictions.npz')
    graphs=json.loads((BASE/'graphs.json').read_text(encoding='utf-8'));models=json.loads((BASE/'models.json').read_text(encoding='utf-8'))
    rec=json.loads((BASE/'fit_receipt.json').read_text(encoding='utf-8'))
    check('frozen sizes',obs['power_obs_kw'].shape==(20,4,2000,360) and pred['test'].shape==(20,4,3,400,2,2))
    check('raw without hidden duration',set(obs)=={'power_obs_kw','reference_kw','X','W','D','A','declared_deadline_s','user_split'})
    for file,key,folder in [('observations.npz','raw_sha256',RAW),('observed_features.npz','features_sha256',BASE),('predictions.npz','predictions_sha256',BASE),('graphs.json','graphs_sha256',BASE),('models.json','models_sha256',BASE)]:check('persisted '+file,sha(folder/file)==rec[key])
    true,meta=independent_truth(p);ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    close('independent observable effect truth',ev['truth'],true,1e-11)
    for k,v in meta.items():close('independent reference '+k,ev['truth_metadata'][k],v,1e-11)
    reference=np.zeros_like(feats['cumulative_s']);continuous=np.zeros_like(reference)
    for r in range(20):
        split=obs['user_split'][r];check('1200/400/400 unique users',list(np.bincount(split,minlength=3))==[1200,400,400])
        tr=np.flatnonzero(split==0);ixs={name:np.flatnonzero(split==code) for name,code in [('validation',1),('test',2)]}
        for name,ix in ixs.items():check('held-out index partition '+name,np.array_equal(ix,pred[name+'_indices'][r]) and not set(ix)&set(tr))
        ref=obs['reference_kw'][r].astype(float);t=obs['declared_deadline_s'][r];x=obs['X'][r];w=obs['W'][r]
        check('declared connection reference',np.array_equal(ref,3*(np.arange(360)[None,:]*10<t[:,None])))
        for s,scene in enumerate(p['scenarios']):
            reduction=ref-obs['power_obs_kw'][r,s].astype(float);req=reduction[:,60:180];mask=req>=.15
            cumulative=np.sum(mask,axis=1)*10
            # Independent longest runs from change boundaries, no sequential _run.
            long=[]
            for flags in mask:
                changes=np.diff(np.r_[False,flags,False].astype(int));lengths=np.flatnonzero(changes==-1)-np.flatnonzero(changes==1)
                longest=int(max(lengths,default=0));long.append(10*longest if longest>=3 else 0)
            long=np.array(long);reference[r,s]=cumulative;continuous[r,s]=long
            close('public cumulative feature',feats['cumulative_s'][r,s],cumulative)
            close('continuous duration separate',feats['longest_s'][r,s],long)
            close('public long indicator',feats['S'][r,s],(cumulative>=600).astype(int))
            close('raw signed energy',feats['net_kwh'][r,s],np.sum(req,axis=1)/360)
            close('raw signed fixed Y',feats['Y'][r,s],np.sum(req,axis=1)/180)
            close('raw cumulative debt',feats['debt_end_kwh'][r,s],np.sum(reduction[:,60:],axis=1)/360)
            # Independent physical conditions; hidden quantities only evaluator.
            tau=obs['A'][r,s]*np.minimum(1200-hidden['delay_s'][r],t-1800)
            close('physical duration from declared headroom',hidden['duration_s'][r,s],tau)
            check('repayment before declared departure',np.all(tau+1800<=t))
            latent=ref.copy();times=np.arange(360)*10
            latent-=1.5*((times[None,:]>=600+hidden['delay_s'][r,:,None])&(times[None,:]<600+hidden['delay_s'][r,:,None]+tau[:,None]))
            latent+=1.5*((times[None,:]>=1800)&(times[None,:]<1800+tau[:,None]))
            check('complete physical energy/power',np.max(abs(np.sum(latent-ref,axis=1)*10))<1e-10 and latent.min()>=0 and latent.max()<=4.5)
            gg=graphs[r][s];valid=valid_adjustments(gg['assumed_edges'])
            check('assumed backdoor active-path oracle',valid==gg['identification']['valid_sets'])
            check('selected safe pre-treatment set',gg['identification']['selected']==([] if scene.startswith('randomized') else ['X','W']))
            learned=gg['learned'];validl=valid_adjustments(learned['edges'])
            check('learned suggestions active-path oracle',validl==learned['suggested_adjustment']['valid_sets'])
            data=np.column_stack([x[tr],w[tr],obs['D'][r,s,tr],obs['A'][r,s,tr],(cumulative[tr]>=600).astype(int)])
            own_edges=[]
            for node,record in enumerate(learned['local_scores']):
                candidates=[]
                for candidate in record['candidates']:
                    score,mincount=local_score(data,node,candidate['parents'])
                    check('BIC parent support',candidate['available']==(score is not None))
                    # Main records full minimum even for unavailable; independent
                    # evaluator may short-circuit, so compare only available cells.
                    if score is not None:
                        close('direct conditional BIC',candidate['bic'],score,1e-8)
                        check('parent count minimum',candidate['minimum_parent_count']==mincount)
                        candidates.append((score,candidate['parents']))
                best=min(candidates,key=lambda v:(v[0],len(v[1]),v[1]))
                check('selected minimum BIC',record['selected']['parents']==best[1])
                own_edges.extend((a,NAMES[node]) for a in best[1])
            check('all learned edges independently reproduced',own_edges==list(map(tuple,learned['edges'])))
            outcomes=np.column_stack([cumulative,(cumulative>=600).astype(int)])
            for mi,model in enumerate(models[r][s]):
                columns=model['columns'];minimum=5 if mi==2 else 20
                shape=(2,2**len(columns));count=np.zeros(shape,int);table=np.zeros(shape+(2,));fields={'X':x,'W':w,'A':obs['A'][r,s]};d=obs['D'][r,s]
                for arm in (0,1):
                    for key in range(shape[1]):
                        match=(d[tr]==arm)
                        for j,c in enumerate(columns):match &= fields[c][tr]==((key>>j)&1)
                        ix=tr[match];count[arm,key]=len(ix)
                        if len(ix):table[arm,key]=[math.fsum(outcomes[ix,o])/len(ix) for o in range(2)]
                available=bool(count.min()>=minimum)
                check('training support gate independently',available==model['available'] and np.array_equal(count,model['counts']))
                if available:close('training cell means',model['table'],table)
                for name,ix in ixs.items():
                    own=np.full((len(ix),2,2),np.nan)
                    if available:
                        keys=sum(fields[c][ix]*(2**j) for j,c in enumerate(columns)) if columns else np.zeros(len(ix),int)
                        own=table[:,keys,:].transpose(1,0,2)
                    close('training-only '+name+' effect predictions',pred[name][r,s,mi],own)
            if s==0:
                close('randomized safe equals unadjusted',pred['test'][r,s,0],pred['test'][r,s,1])
        if (r+1)%5==0:print('independent feature/graph/fit',r+1,flush=True)
    verify_scores(p,obs,pred,true,graphs,reference,continuous,hidden,ev)
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    for name,h in frozen['source'].items():check('scientific source '+name,sha(BASE/name)==h)
    for name,h in frozen['protected'].items():check('protected prior/model '+name,sha(ROOT/name)==h)
    for name in ['features.py','graph.py','estimators.py']:
        source=(BASE/name).read_text(encoding='utf-8');check('no simulator or hidden input '+name,all(x not in source for x in ('import generate','import evaluate','hidden_evaluator','acceptance_dose_coefficients')))
    report=dict(status='passed' if all(v['passed'] for v in CHECKS) else 'failed',checks_passed=sum(v['passed'] for v in CHECKS),checks_failed=sum(not v['passed'] for v in CHECKS),maximum_errors=ERRORS,failures=[v for v in CHECKS if not v['passed']],verifier_sha256=sha(Path(__file__)),scope='independent calculation/contract checks; not independent research sample count or real EV validation')
    (BASE/'independent_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return 0 if report['status']=='passed' else 1

def verify_scores(p,obs,pred,truth,graphs,reference,continuous,hidden,ev):
    with (BASE/'metrics.csv').open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f))
    rows=[]
    for r in range(20):
        for s,scene in enumerate(p['scenarios']):
            for split in ('validation','test'):
                ix=pred[split+'_indices'][r];x=obs['X'][r,ix];w=obs['W'][r,ix];base=truth[s,x,w]
                for group,mask in [('all',np.ones(len(ix),bool)),('X0',x==0),('X1',x==1)]:
                    for mi,method in enumerate(p['methods']):
                        pp=pred[split][r,s,mi,mask];valid=bool(np.isfinite(pp).all())
                        for oi,outcome in enumerate(('cumulative_s','long600')):
                            target=math.fsum(base[mask,oi])/int(mask.sum())
                            estimate=math.fsum(pp[:,1,oi]-pp[:,0,oi])/len(pp) if valid else None
                            rows.append(dict(seed=p['seed_start']+r,scenario=scene,split=split,group=group,method=method,outcome=outcome,rows=int(mask.sum()),available=valid,true_effect=target,estimate=estimate,error=estimate-target if valid else None))
    check('2880 metric rows retained',len(actual)==len(rows)==2880)
    for a,b in zip(actual,rows):
        for key,value in b.items():
            if value is None:check('unavailable metric preserved',a[key]=='')
            elif isinstance(value,bool):check('metric availability',a[key]==str(value))
            elif isinstance(value,float):close('independent metric '+key,float(a[key]),value)
            elif isinstance(value,int):check('metric '+key,int(a[key])==value)
            else:check('metric '+key,a[key]==value)
    for a in ev['summary']:
        rr=[v for v in rows if all(v[k]==a[k] for k in ('scenario','split','group','method','outcome'))];valid=[v for v in rr if v['available']]
        check('all20 denominator and unavailable',len(rr)==a['repetitions']==20 and len(valid)==a['available_repetitions'] and len(rr)-len(valid)==a['unavailable_repetitions'])
        close('mean finite-population truth',a['mean_true_effect'],np.mean([v['true_effect'] for v in rr]))
        if valid:
            error=np.array([v['error'] for v in valid]);close('summary estimate',a['mean_estimate'],np.mean([v['estimate'] for v in valid]));close('summary bias',a['mean_bias'],error.mean());close('summary RMSE',a['rmse'],np.sqrt(np.mean(error**2)));close('summary bias MCSE',a['bias_mcse'],error.std(ddof=1)/np.sqrt(len(error)))
    # Recompute graph error records and summaries from independent learned edges
    # and declared mechanism truth; directions are time-prior constrained.
    with (BASE/'graph_metrics.csv').open(encoding='utf-8-sig',newline='') as f:gr=list(csv.DictReader(f))
    for row in gr:
        r=int(row['seed'])-p['seed_start'];s=p['scenarios'].index(row['scenario']);g=graphs[r][s];got=set(map(tuple,g['learned']['edges']))
        target={('W','A'),('X','S'),('W','S'),('A','S')}
        if p['acceptance_dose_coefficients'][s]!=0:target.add(('D','A'))
        if s>0:target|={('X','D'),('W','D')}
        tp=len(got&target)
        check('graph exact status',row['exact']==str(got==target))
        for key,value in [('true_positives',tp),('false_positives',len(got-target)),('false_negatives',len(target-got))]:check('graph '+key,int(row[key])==value)
        close('graph precision',float(row['precision']),tp/len(got) if got else 0.)
        close('graph recall',float(row['recall']),tp/len(target))
        check('adjustment agreement field',row['adjustment_matches_assumed']==str(g['learned']['suggested_adjustment']['selected']==g['identification']['selected']))
    for a in ev['graph_summary']:
        rr=[v for v in gr if v['scenario']==a['scenario']]
        check('graph summary denominator',len(rr)==a['repetitions']==20)
        check('graph exact summary',a['exact_count']==sum(v['exact']=='True' for v in rr))
        check('graph adjustment summary',a['adjustment_agreement_count']==sum(v['adjustment_matches_assumed']=='True' for v in rr))
        close('graph summary precision',a['mean_precision'],np.mean([float(v['precision']) for v in rr]));close('graph summary recall',a['mean_recall'],np.mean([float(v['recall']) for v in rr]))
    for a in ev['feature_summary']:
        r=a['seed']-p['seed_start'];s=p['scenarios'].index(a['scenario']);tau=hidden['duration_s'][r,s]
        close('feature cumulative error',a['cumulative_mae_vs_physical_s'],np.mean(abs(reference[r,s]-tau)))
        close('feature continuous error',a['longest_mae_vs_physical_s'],np.mean(abs(continuous[r,s]-tau)))
        check('feature false continuous detections',a['false_continuous_detections']==int(np.sum((tau==0)&(continuous[r,s]>0))))
        check('feature false single-bin detections',a['false_single_bin_detections']==int(np.sum((tau==0)&(reference[r,s]>0))))

if __name__=='__main__':raise SystemExit(main())
