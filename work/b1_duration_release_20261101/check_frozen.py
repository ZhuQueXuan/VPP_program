"""Independent run-length accounting and staged inference replay; no fitting."""
from common import *
from itertools import groupby
from b1_algorithm.resources.ev import EVAnalysisConfig

def main():
    stage_module=load_module(HERE/'staging/_duration_fusion.py','staged_duration')
    checked=0;replayed=0
    for stage in ['validation','stress','test']:
        if not (HERE/stage/'metrics.json').exists():continue
        curves={r['task_id']:r for r in read(stage+'/curves.json')}
        rows={(r['task_id'],r['method']):r for r in read(stage+'/metrics.json')}
        for panel in ['minute','10s']:
            truth={r['task_id']:r for r in read(stage+'/'+panel+'/truth.json')}
            cases=read(stage+'/'+panel+'/facts.json')
            for index,c in enumerate(cases):
                s=np.array(c['starts_s']);e=np.array(c['ends_s']);step=float(e[0]-s[0]);use=(s>=0)&(s<1800)
                t=np.array(truth[c['task_id']]['true_reduction_kw'])[use]>=.15
                def durations(mask):
                    lengths=[sum(1 for _ in group)*step for flag,group in groupby(mask.tolist()) if flag]
                    longest=max(lengths,default=0.)
                    return float(mask.sum()*step),longest if longest>=30.-1e-8 else 0.
                tc,tl=durations(t)
                cp=np.array(curves[c['task_id']]['results']['cpop']['prediction'])
                fusion=np.array(curves[c['task_id']]['results']['duration_fusion']['prediction'])
                assert bool(np.any(cp[use]>=.15))==bool(np.any(fusion[use]>=.15))
                assert np.array_equal(fusion[cp<=.1],cp[cp<=.1])
                indices=np.flatnonzero(use);offset=0
                for flag,group in groupby((cp[use]>=.15).tolist()):
                    n=sum(1 for _ in group)
                    if flag and n*step<=60.+1e-8:
                        take=indices[offset:offset+n];assert np.array_equal(cp[take],fusion[take])
                    offset+=n
                eta=float(np.dot((np.array(c['reference_kw'])-np.array(c['power_kw']))[use],(e-s)[use])/2700.)
                for method,result in curves[c['task_id']]['results'].items():
                    r=rows[c['task_id'],method];mask=np.array(result['prediction'])[use]>=.15
                    pc,pl=durations(mask)
                    assert abs(r['cumulative_error_seconds']-abs(pc-tc))<1e-7
                    assert abs(r['longest_error_seconds']-abs(pl-tl))<1e-7
                    assert r['whole_miss']==bool(t.any() and not mask.any())
                    assert r['null_false_positive']==bool(not t.any() and mask.any())
                    assert abs(r['eta_raw']-eta)<1e-12
                    checked+=5
                if index<4:
                    y=np.array(c['reference_kw'])-np.array(c['power_kw']);before=y.copy()
                    data=dict(y=y,starts=s/60,delta=step/60,sigma=c['sigma'],W=30.,q=1.5,profile=EVAnalysisConfig())
                    fitted=stage_module.fit_duration_fusion(data,cp)
                    assert np.max(abs(fitted['prediction']-fusion))<1e-12
                    assert np.array_equal(y,before);replayed+=1
    for path,expected in read('selection_freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    out=dict(independent_metric_assertions=checked,staged_inference_replays=replayed,all_passed=True,
             original_source_freeze_verified=True,field_accuracy_claim=False)
    write('independent_checks.json',out);print(json.dumps(out))
if __name__=='__main__':main()
