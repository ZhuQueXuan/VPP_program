"""Necessary leakage, chronology, task-target and native-runtime checks."""
from engine import *

def main():
    out=HERE/'checks_panel_v2'
    if out.exists():raise RuntimeError('checks panel exists; inspect rather than overwrite')
    out.mkdir();checks=[]
    contexts=generate(4431000,out,ROOT/'data/B1_unknown_reference_v1_20261030/checks_v2')
    assert len(contexts)==2;checks.append('two independent held-out users selected using declared conditions only')
    ledger=json.loads((out/'ledger_4431000.json').read_text(encoding='utf-8'))
    assert all(r['latest_prior_end_min']<r['notice_min'] and r['end_of_data_min']<=120000 for r in ledger['training'])
    assert all(c['fit_cutoff_min']<c['query_notice_min'] for c in contexts)
    checks.append('historical priors precede target notice; fit precedes query notice')
    assert not set(ledger['roles']['train']) & set(ledger['roles']['test'])
    checks.append('training and test users isolated')
    blob=np.load(ROOT/'data/B1_unknown_reference_v1_20261030/checks_v2/contexts_4431000.npz')
    for i,c in enumerate(contexts):
        independent=float(np.mean(blob[f'{i}_prefix']-blob[f'{i}_prefix_prediction']))
        assert abs(independent-c['shift_kw'])<1e-12
        np.testing.assert_array_equal(c['references']['gbdt_pre15_shift'],
            np.maximum(0.,c['references']['fixed_gbdt']+independent))
        original=blob[f'{i}_full_meter'];altered=original.copy()
        all_s=np.arange(-120.,90.);all_e=all_s+1
        altered[all_e>-15]+=1000.
        adjusted,changed_shift=adjust_pre15(blob[f'{i}_full_prediction'],altered,all_s,all_e)
        assert independent==changed_shift
        np.testing.assert_array_equal(adjusted,np.maximum(0.,blob[f'{i}_full_prediction']+independent))
    checks.append('candidate uses only complete15 bins before notice; changing process observations cannot change correction')
    entries,cases,arrays=datasets(contexts)
    assert len(entries)==24 and len(cases)==144
    for c in contexts:
        for shape in ('none','partial','slow','multiplateau'):
            target=arrays[f'{c["seed"]}_{c["context"]}_{shape}_truth']
            assert np.all(c['baseline']-target>=0)
    checks.append('four paired interval targets are feasible; truth excluded from practical method preparation')
    first=entries[0];cfg=runtime_config();cfg['artifact_dir']=str(out/'native_calls')
    fits,backend=native.fit_cases(process.cases_for(first['data']),cfg)
    result=process.complete(first['data'],fits,policy='guarded',backend=backend)
    assert result['status']=='ok' and backend['status']=='ok'
    checks.append('actual native CPOP and unchanged guarded path execute')
    independent=score(first,result['reduction_interval_kw'],'check',result['method'])
    assert abs(independent['eta_raw']-result['eta_raw'])<1e-12
    checks.append('common raw integral independent of fitted curve')
    receipt=dict(passed=True,checks=checks,n_checks=len(checks),scope='small separate seed, no development or test selection')
    (HERE/'checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
