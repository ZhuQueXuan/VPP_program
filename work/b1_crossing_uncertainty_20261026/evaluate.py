"""Evaluator-only population truth and repeated-sampling accuracy. No fitting."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
from scipy.stats import binomtest
from numpy.polynomial.legendre import leggauss
from inference import invert,old_strict,naive_first
BASE=Path(__file__).resolve().parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def population_truth():
    d=np.array(P['doses']);inc=np.array([.3*np.maximum(0,d-1.2)/1.2,
        [0,.05,.35,.05,.32,.02,.36],np.zeros(7),.19*d/2.4])
    scale=np.array([.6,.5,.7])*13/15*.975
    gain=inc[:,None,:]*scale[None,:,None]
    # Independent polynomial quadrature of E(c*p*.975), then subtract dose zero.
    z,wt=leggauss(12);quadrature=np.zeros((4,3,7))
    for g,(a,b) in enumerate([(-1,1),(-1,0),(0,1)]):
        x=a+(z+1)*(b-a)/2;w=z
        c=(.4+.2*(x[:,None]+1))*(.8+.2*w[None,:]**2)
        base=.12+.12*(x[:,None]+1)/2+.06*w[None,:]
        for s in range(4):
            for k in range(7):quadrature[s,g,k]=np.sum(wt[:,None]*wt[None,:]*c*(base+inc[s,k]))/4*.975
    qgain=quadrature-quadrature[:,:,:1]
    err=float(np.max(abs(qgain-gain)))
    assert err<1e-12
    return gain,err

def refs(g,delta):
    hits=np.flatnonzero(g>=delta)
    first=int(hits[0]) if len(hits) else -1
    edges=[k for k in range(1,7) if g[k-1]<delta and g[k]>=delta]
    return first,edges

def rate(k,n):
    lo,hi=binomtest(k,n).proportion_ci(confidence_level=.95,method='exact')
    return dict(count=int(k),denominator=int(n),rate=k/n,mc95_exact=[lo,hi])

def main():
    receipt=json.loads((BASE/'inference_receipt.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((BASE/'bands.npz').read_bytes()).hexdigest()==receipt['bands_sha256']
    b=np.load(BASE/'bands.npz');truth,qerr=population_truth()
    rows=[];coverage=[]
    for r in range(P['repetitions']):
        for s,scene in enumerate(P['scenarios']):
            for g,group in enumerate(P['groups']):
                gain=b['gain'][r,s,g];lo=b['lower'][r,s,g];hi=b['upper'][r,s,g];t=truth[s,g]
                av=bool(b['available'][r,s,g])
                covered=bool(av and np.all((lo<=t)&(t<=hi)))
                coverage.append(dict(seed=P['seed_start']+r,scenario=scene,group=group,available=av,covered=covered,
                    q=float(b['q'][r,s,g]),minimum_original_count=int(b['counts'][r,g].min()),bad_draws=int(b['bad_draws'][r,g])))
                for delta in P['deltas']:
                    truefirst,trueedges=refs(t,delta)
                    true_decline=bool(np.any(np.diff(t)<-1e-12))
                    for method,fn in [('strict_D109',old_strict),('naive_first',naive_first)]:
                        status,idx=fn(gain,delta)
                        correct=(status=='bracket' and idx==truefirst) or (status=='not_reached' and truefirst==-1)
                        rows.append(dict(seed=P['seed_start']+r,scenario=scene,group=group,delta=delta,method=method,
                            status=status,first_candidates=[idx] if status=='bracket' else [],no_cross_possible=status=='not_reached',
                            unique=status=='bracket',true_first=truefirst,true_up_edges=trueedges,
                            truth_in_set=bool(correct),definite_reached=status=='bracket',definite_not_reached=status=='not_reached',
                            wrong_definite_reached=bool(status=='bracket' and truefirst==-1),
                            wrong_definite_not_reached=bool(status=='not_reached' and truefirst>=1),
                            supported_decrease=[],true_decline=true_decline,supported_up=[],all_true_up_possible=False,
                            band_covered=None,candidate_count=int(status=='bracket'),candidate_hull_width=.4 if status=='bracket' else 0.))
                    inv=invert(lo,hi,delta);cs=inv['candidates'];nc=inv['no_cross_possible'];valid=inv['status']!='unavailable'
                    iset=bool(valid and (truefirst in cs if truefirst>=1 else nc))
                    definite=bool(valid and not nc)
                    not_reached=inv['status']=='supported_not_reached'
                    rows.append(dict(seed=P['seed_start']+r,scenario=scene,group=group,delta=delta,method='user_cluster_band',
                        status=inv['status'],first_candidates=cs,no_cross_possible=nc,unique=inv['unique'],true_first=truefirst,true_up_edges=trueedges,
                        truth_in_set=iset,definite_reached=definite,definite_not_reached=not_reached,
                        wrong_definite_reached=bool(definite and truefirst==-1),wrong_definite_not_reached=bool(not_reached and truefirst>=1),
                        supported_decrease=inv['supported_decrease'],true_decline=true_decline,supported_up=inv['supported_up'],
                        all_true_up_possible=bool(valid and set(trueedges)<=set(inv['possible_up'])),
                        band_covered=covered,candidate_count=len(cs),candidate_hull_width=float((max(cs)-min(cs)+1)*.4) if cs else 0.))
    for name,rr in [('crossings.csv',rows),('coverage.csv',coverage)]:
        with (BASE/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    summaries=[]
    for scene in P['scenarios']:
        for group in P['groups']:
            cov=[v for v in coverage if v['scenario']==scene and v['group']==group]
            for delta in P['deltas']:
                for method in ['strict_D109','naive_first','user_cluster_band']:
                    a=[v for v in rows if v['scenario']==scene and v['group']==group and v['delta']==delta and v['method']==method]
                    n=len(a)
                    summaries.append(dict(scenario=scene,group=group,delta=delta,method=method,
                        denominator=n,true_first=a[0]['true_first'],true_up_edges=a[0]['true_up_edges'],
                        set_or_point_coverage=rate(sum(v['truth_in_set'] for v in a),n),
                        band_coverage=rate(sum(v['covered'] for v in cov),len(cov)) if method=='user_cluster_band' else None,
                        unique_count=sum(v['unique'] for v in a),unresolved_count=sum(v['status']=='crossing_unresolved' for v in a),
                        bounded_multiple_count=sum(v['status']=='bounded_first_crossing' and not v['unique'] for v in a),
                        supported_not_reached_count=sum(v['definite_not_reached'] for v in a),
                        ambiguous_count=sum(v['status']=='ambiguous_nonmonotone' for v in a),
                        unavailable_count=sum(v['status']=='unavailable' for v in a),
                        wrong_definite_reached=rate(sum(v['wrong_definite_reached'] for v in a),n),
                        wrong_definite_not_reached=rate(sum(v['wrong_definite_not_reached'] for v in a),n),
                        mean_candidate_count=float(np.mean([v['candidate_count'] for v in a])),
                        mean_candidate_hull_width=float(np.mean([v['candidate_hull_width'] for v in a])),
                        supported_decline_count=sum(bool(v['supported_decrease']) for v in a),
                        all_true_up_possible_count=sum(v['all_true_up_possible'] for v in a),
                        three_supported_up_count=sum(len(v['supported_up'])==3 for v in a)))
    report=dict(summary=summaries,truth_gains=truth.tolist(),quadrature_max_error=qerr,
        scope='100 fresh MC repetitions, 999 whole-user bootstrap draws; approximate per-curve simultaneous bands, finite seven-node first crossing. No continuous root or real EV claims.')
    (BASE/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for v in summaries:
        if v['group']=='all' and v['delta']==.1:
            print(v['scenario'],v['method'],'covered',v['set_or_point_coverage']['count'],'unique',v['unique_count'],'unresolved',v['unresolved_count'],'wrongreached',v['wrong_definite_reached']['count'],'ambiguous',v['ambiguous_count'])

if __name__=='__main__':main()
