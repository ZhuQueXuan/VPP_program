"""Small actual-interface check, separate from all frozen final-panel seeds."""
import run as r


def main():
    contract=r.contract_check();p=r.read(r.PARENT/'protocol.json')['step6']
    facts,truth,meta=r.generate(7240199,n_users=64,events_per_user=5)
    records,selection=r.bind_references(facts,r.load_reference_model(r.REFERENCE))
    p=dict(p,users_per_block=64)
    indices,factors,history=r.factor_inputs(facts,records,'C0',None,p)
    targets=[records[i] for i in indices]
    runtime=r._default_runtime_config();runtime.update(artifact_dir=str(r.HERE/'micro/native'),timeout_seconds=180)
    methods={}
    for name in ('ride_revised','cpop','ride_template'):
        methods[name]=r.analyze_events(targets if name=='cpop' else targets[:2],process_method=name,process_config=runtime)
        assert all(e['status'] in ('ok','degraded') for e in methods[name])
    design=r.EVFactorStudy('B1-final-micro','元/千瓦时',covariates=r.COVARIATES,graph_edges=tuple(r.EDGES))
    baseline=r.fit_ev_factor_curve(methods['cpop'],factors,design,dose_domain=[0.,2.4],grid=p['grid'],
        reference_dose=.8,assumptions=r.ASSUMPTIONS,config=dict(seed=7240199,n_boot=199),continuous_assignment=True)
    checked=r.query_and_compare(methods['cpop'],factors,design,baseline,7240199,'micro','micro_cpop',p)
    assert checked.get('equivalence_passed') is True,checked
    r.dump(r.HERE/'micro/check_receipt.json',dict(passed=True,protocol_sha256=contract['protocol_sha256'],
        seed=7240199,main_panel_generated=False,actual_process_events={k:len(v) for k,v in methods.items()},
        factor_status=baseline['status'],frozen_query_equivalence=checked,
        history_records=len(history),all_history_available_before_target=all(h['known_at_min']<=h['target_notice_min'] for h in history),
        performance_selection_done=False))
    print('MICRO PASSED',baseline['status'],checked,flush=True)


if __name__=='__main__':main()
