"""Generate fresh versioned facts; simulation truth is sealed separately."""
from pilot_common import HERE,ROOT,FACTS,read,write_new,sha,load_module,facts_path,truth_path

GENPATH=ROOT/'work/b1_reliability_20261031/study/generator.py'
GEN=load_module(GENPATH,'unchanged_reliability_generator_for_new_pilot')

def generate(phase):
    design=read(HERE/'protocol.json')['stages'][phase]
    seeds=design.get('seeds',[design.get('seed')]);rows=[]
    for seed in seeds:
        users=design.get('users',design.get('users_per_block'))
        out=GEN.generate_reliability(seed,users,events_per_user=2,variants=tuple(design['variants']),clock_shift_min=design['shift_min'])
        for variant,(facts,truth,metadata) in out.items():
            fp=facts_path(phase,seed,variant);tp=truth_path(phase,seed,variant)
            mp=FACTS/phase/f'{seed}_{variant}_metadata.json'
            write_new(fp,facts);write_new(tp,truth)
            write_new(mp,dict(metadata,pilot_protocol_sha256=sha(HERE/'protocol.json'),origin='Fresh seed reuse of unchanged independent simulator, not old experimental samples'))
            rows.append(dict(seed=seed,variant=variant,n=len(facts),users=len({f['task']['user_id'] for f in facts}),
                facts=fp.relative_to(ROOT).as_posix(),truth=tp.relative_to(ROOT).as_posix(),
                first_notice=min(f['task']['notice_min'] for f in facts),
                last_label=max(f['availability']['power_records_available_at_min'] for f in facts),
                sha256={p.relative_to(ROOT).as_posix():sha(p) for p in (fp,tp,mp)}))
    write_new(HERE/'data_receipts'/f'{phase}.json',dict(phase=phase,rows=rows))
    return rows

def prepare():
    phases=['train','reference_validation','process_development','calibration']
    receipts={p:generate(p) for p in phases}
    allusers=[]
    for p in phases:
        row=receipts[p][0];facts=read(ROOT/row['facts'])
        group={f['task']['user_id'] for f in facts}
        assert all(not group&other for other in allusers);allusers.append(group)
        assert all(max(f['reference_window']['pre_ends_min'])<=f['task']['notice_min'] for f in facts)
        assert all(f['non_event'] is True and f['task_dispatched'] is False for f in facts)
    assert all(receipts[a][0]['last_label']<receipts[b][0]['first_notice'] for a,b in zip(phases,phases[1:]))
    write_new(HERE/'prepare_receipt.json',dict(phases=phases,users_disjoint=True,time_ordered=True,generator_sha256=sha(GENPATH)))
    return receipts

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','validation','test'])
    args=parser.parse_args()
    if args.phase=='prepare':prepare()
    else:generate(args.phase)
