"""Exhaustive finite-dictionary checks, native nesting and data preservation."""
from common import *
from candidate import propose_edges,cache_blocks,choose_partition
from itertools import combinations
def main():
    rng=np.random.default_rng(7641000);n=17;x=np.arange(n,dtype=float);sigma=.05
    signals=[np.zeros(n),x*.05,np.where(x<8,0.,1.),np.where(x==8,1.,0.),np.where((x>=4)&(x<12),.8,0.)]
    cases=[]
    for i,signal in enumerate(signals):
        y=signal+rng.normal(0,sigma,n);command=np.where(x<5,3.,1.5)
        proposal=propose_edges(y,x,sigma,command)
        scaled=propose_edges(y*1000,x,sigma*1000,command*1000)
        assert proposal['nodes']==scaled['nodes'] and 5 in proposal['command_edges']
        cases.append({'case_id':i,'x':x,'y':y,'sigma':sigma,'proposal':proposal,'command':command})
    cache,meta=cache_blocks(cases,'native/controls_blocks')
    original=[]
    for c in cases:original.append({'case_id':c['case_id'],'starts':x-.5,'ends':x+.5,'y':c['y'],'sigma':sigma,'train':np.ones(n,bool)})
    base,bmeta=fit_cases(original,runtime('native/controls_original'));assert bmeta['status']=='ok'
    maxdiff=0.;maxgap=0.;partitions=0
    for c in cases:
        idx=c['case_id'];full=cache[idx][f'0:{n}'];maxdiff=max(maxdiff,float(np.max(np.abs(np.asarray(full['prediction'])-np.asarray(base[idx]['prediction'])))))
        assert abs(full['cost']-base[idx]['native_cost'])<1e-8
        for key,r in cache[idx].items():
            a,b=map(int,key.split(':'));pred=np.asarray(r['prediction']);observed=c['y'][a:b]
            cost=float(np.sum(((pred-observed)/sigma)**2)+2*np.log(n)*r['internal_knots'])
            maxgap=max(maxgap,abs(cost-r['cost']));assert abs(cost-r['cost'])<1e-6
        edges=c['proposal']['edges']
        for ratio in (1.,1.5,2.):
            fit=choose_partition(c['proposal'],cache[idx],sigma,n,ratio)
            minimum=float('inf')
            for length in range(len(edges)+1):
              for subset in combinations(edges,length):
                path=[0]+list(subset)+[n]
                value=sum(cache[idx][f'{a}:{b}']['cost'] for a,b in zip(path,path[1:]))+length*ratio*2*np.log(n)
                minimum=min(minimum,value);partitions+=1
            assert abs(fit['objective']-minimum)<1e-7
            assert fit['objective']<=full['cost']+1e-7
            if ratio==2.:
                assert not fit['jump_boundaries']
                assert np.max(np.abs(np.asarray(fit['prediction'])-np.asarray(base[idx]['prediction'])))<1e-8
    assert maxdiff<1e-8
    # A genuine one-point pulse survives; there is no pre-screening/weight rule.
    short=choose_partition(cases[3]['proposal'],cache[3],sigma,n,1.)
    assert short['prediction'][8]>=.15
    rejected=0
    for bad in [np.r_[np.zeros(n-1),np.nan],['1']*n]:
        try:propose_edges(bad,x,sigma,np.zeros(n))
        except ValueError:rejected+=1
    assert rejected==2
    write('controls_receipt.json',{'status':'passed','cases':len(cases),'enumerated_partition_comparisons':partitions,
       'native_full_block_max_curve_difference':maxdiff,'max_recomputed_block_cost_difference':maxgap,
       'uniform_sigma_and_values_preserved':True,'unit_scale_proposals_same':True,'single_point_response_retained':True,
       'ratio2_dominated_control_no_jumps':True,'not_a_performance_sample':True,'meta':meta,'baseline_meta':bmeta,
       'source_sha256':{p:sha(HERE/p) for p in ['candidate.py','blocks_batch.R','controls.py']}})
    print(json.dumps({'controls':'passed','cases':len(cases),'exhaustive_partitions':partitions,'max_full_curve_difference':maxdiff,'max_cost_difference':maxgap}))
if __name__=='__main__':main()
