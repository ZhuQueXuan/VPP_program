from common import *
from candidates import fit_segments

def main():
    write('initial_plan.json',dict(authorization='2026-11-01 user removes method restrictions and asks persistent effective exploration beyond CPOP',
        efficiency_interpretation='Duration/short-response/null performance plus runtime; initial target>=10percent smaller primaryMAE, no added short misses/FP, faster core. No promise of universal sensor-fault identifiability.',
        first_families='Exact degree0/1 segmented-regression DP, variable segment penalty and slope complexity. No point suppression or min segment length>1.',
        reused_assets='Native locked CPOP and LABS. Reviewed ruptures BSD2 mature compiled KernelCPD/PELT and SciPy BSD filtering; constant/kernel alone does not target ramps, so first reuse existing NumPy runtime and independently implement standard small-vector sufficient-statistic DP. Not novel estimator.',
        development='All prior v2/v3 test data explicitly reclassified as seen development for this new selection only; no new generalisation claim from them. Old results unchanged.',
        final='Freeze selected method/config before fresh seed panels. If unsuccessful inspect development and try a different family, never chase frozen test. Preserve all failures. First feature block only, report deferred.',
        sources=['https://github.com/deepcharles/ruptures','https://centre-borelli.github.io/ruptures-docs/code-reference/detection/kernelcpd-reference/','https://github.com/scipy/scipy/ndimage/_filters.py']))
    rows=[]
    specs=[('minute',ROOT/'work/b1_cpop_jump_v2_20261031'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031')]
    grid=[(b,s) for b in [1.,2.,3.,4.] for s in [0.,1.,2.]]
    for panel,p in specs:
        facts=json.loads((p/'facts/test.json').read_text(encoding='utf-8'));truth={r['task_id']:r for r in json.loads((p/'evaluator/test.json').read_text(encoding='utf-8'))};old={r['task_id']:r for r in json.loads((p/'outputs/test_curves.json').read_text(encoding='utf-8'))}
        for i,c in enumerate(facts):
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.array(c['starts_s'] if panel=='10s' else c['starts'])* (1. if panel=='10s' else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[tid]['true_reduction_kw'])
            for method in ['cpop','labs']:
                fit=old[tid]['results'][method];d=measure(fit['prediction'],t,s,step);d.update(panel=panel,method=method,task_id=tid,seconds=fit['seconds']);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
            for b,sl in grid:
                tic=time.perf_counter();r=fit_segments(y,c['sigma'],b,sl);elapsed=time.perf_counter()-tic;d=measure(r['prediction'],t,s,step)
                d.update(panel=panel,method=f'poly_b{b:g}_s{sl:g}',task_id=tid,seconds=elapsed)
                d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
            if (i+1)%120==0:print(panel,i+1,'/',len(facts),flush=True)
    ss=summary(rows);write('development_metrics.json',rows);write('development_summary.json',ss)
    print(json.dumps([r for r in ss if r['panel']=='all']),flush=True)
if __name__=='__main__':main()
