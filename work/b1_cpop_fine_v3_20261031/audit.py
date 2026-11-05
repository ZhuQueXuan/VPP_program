"""Independent saved-output and information-contract audit, no refits."""
from common import *

def independent_features(y,s,stop,tau,dwell):
    delta=float(s[1]-s[0]);active=(s>=-1e-8)&(s<stop-1e-8)&(y>=tau)
    edges=np.diff(np.r_[False,active,False].astype(int));lengths=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
    longest=float(max(lengths,default=0)*delta)
    return dict(cumulative_seconds=float(np.count_nonzero(active)*delta),longest_seconds=longest if longest>=dwell-1e-8 else 0.,threshold_positive=bool(active.any()))

def main():
    freeze=read('validation_freeze.json');checks=0
    for p,h in freeze['source_sha256'].items():assert sha(ROOT/p)==h,p;checks+=1
    before=read('protected_before.json');after=snapshot();assert before==after;checks+=len(before)
    findings=[]
    for stage in ['development','validation','test']:
        facts=read(f'facts/{stage}.json');ev={r['task_id']:r for r in read(f'evaluator/{stage}.json')};curves=read(f'outputs/{stage}_curves.json');metrics={(r['task_id'],r['method']):r for r in read(f'outputs/{stage}_metrics.json')}
        seen=set();flag_tp=flag_fp=spike_total=0
        for c,r in zip(facts,curves):
            tid=c['task_id'];assert tid==r['task_id'] and tid not in seen;seen.add(tid)
            s=np.array(c['starts_s']);clean=np.array(ev[tid]['true_reduction_kw']);raw=np.array(c['reference_kw'])-np.array(c['power_kw']);use=(s>=0)&(s<1800)
            assert len(s)==360 and np.all(np.diff(s)==10) and np.isfinite(raw).all();checks+=3
            tf=independent_features(clean,s,1800,.15,30.);eta=float(np.sum(raw[use])/270.)
            for m,fit in r['results'].items():
                saved=metrics[tid,m];assert saved['status']==fit['status'];checks+=1
                assert abs(saved['raw_eta']-eta)<1e-12;checks+=1
                if fit['status']!='ok':continue
                y=np.array(fit['prediction']);assert len(y)==360 and np.isfinite(y).all();checks+=1
                f=independent_features(y,s,1800,.15,30.)
                assert f==saved['features'] and tf==saved['true_features'];checks+=2
                ce=abs(f['cumulative_seconds']-tf['cumulative_seconds']);le=abs(f['longest_seconds']-tf['longest_seconds'])
                assert ce==saved['cumulative_error_seconds'] and le==saved['longest_error_seconds'] and .5*(ce+le)==saved['primary_seconds'];checks+=3
                assert saved['whole_miss']==(tf['threshold_positive'] and not f['threshold_positive']);checks+=1
                assert saved['null_false_positive']==(not tf['threshold_positive'] and f['threshold_positive']);checks+=1
                assert saved['fp_bins']==int(np.sum((y[use]>=.15)&(clean[use]<.15)));checks+=1
                assert saved['fn_bins']==int(np.sum((y[use]<.15)&(clean[use]>=.15)));checks+=1
                if stage=='test' and m==freeze['method']:
                    flags=set(fit['fine_evidence']['flagged_indices']);inj=set(ev[tid]['injected_indices']);flag_tp+=len(flags&inj);flag_fp+=len(flags-inj);spike_total+=len(inj)
                    for i in flags:
                        assert 2<=i<len(s)-2 and i not in fit['fine_evidence']['protected_indices'];checks+=2
        findings.append(dict(stage=stage,inputs=len(facts),base_tasks=len({c['base_task_id'] for c in facts}),method_rows=len(metrics),
            test_flagged_injected_bins=flag_tp,test_flagged_noninjected_bins=flag_fp,test_injected_bins=spike_total))
    ids=[]
    for stage in ['development','validation','test']:ids.append({r['base_task_id'] for r in read(f'facts/{stage}.json')})
    assert not(ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2]);checks+=3
    rr=read('real_inputs.json');saved=read('real_curves.json');metrics={(r['event_id'],r['condition'],r['method']):r for r in read('real_metrics.json')}
    for c,r in zip(rr,saved):
        assert c['event_id']==r['event_id'] and c['condition']==r['condition'];checks+=1
        for m,fit in r['results'].items():
            d=metrics[c['event_id'],c['condition'],m];assert d['status']==fit['status'];checks+=1
            if fit['status']=='ok':
                f=independent_features(np.array(fit['prediction']),np.array(c['starts_s']),15.,.9,.1)
                assert all(abs(float(f[k])-float(d['features'][k]))<1e-8 for k in f);checks+=3
    write('audit_receipt.json',dict(status='passed',checks=checks,findings=findings,
        original_scientific_files_unchanged=len(before),frozen_source_unchanged=True,
        all_records_retained=True,truth_used_only_in_evaluator=True,
        limitations='Audit counts are implementation checks, not independent observations or statistical evidence of benefit. Flagged non-injected points can be genuine responses/gaps or ordinary noise.'))
    print(json.dumps(read('audit_receipt.json')),flush=True)
if __name__=='__main__':main()
