"""Correct label matching in frozen assessment without changing any result."""
from pathlib import Path
import json
import hashlib
HERE=Path(__file__).resolve().parent
PATHS=('old_cpop','old_ride_revised','new_cpop','new_ride_revised')


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    if not (HERE/'test/receipt.json').is_file():raise RuntimeError('wait for complete phase 1')
    phases={}
    sources={}
    for phase in ('validation','test'):
        receipt=read(HERE/phase/'receipt.json');timing=[]
        for b in receipt['blocks']:
            path=HERE/phase/'blocks'/f"{b['seed']}.json"
            sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            timing.extend(read(path)['timing'])
        sums={p:sum(t['seconds'] for t in timing if t.get('label','').endswith('_'+p) and t.get('seconds') is not None) for p in PATHS}
        counts={p:sum(t.get('label','').endswith('_'+p) for t in timing) for p in PATHS}
        phases[phase]=dict(process_timing_seconds_sum=sums,n_batches=counts,
            reference_timing_seconds_sum={k:sum(t['seconds'] for t in timing if t.get('phase')=='reference' and t.get('kind')==k) for k in ('old','new')},
            wall_seconds=receipt['seconds'])
    result=dict(passed=True,correction='Frozen analyze.py compares the short path with the longer phase_seed_variant_path label and reports all-zero timing. Match the path suffix instead.',
        replaces_field='assessment.json process_timing_seconds_sum only; original assessment and all scientific results retained',
        metric_or_process_rerun=False,changes_to_frozen_sources=False,
        runtime_scope='Batch elapsed time sums under four workers, not exclusive single-event latency',
        phases=phases,scientific_source_sha256=sources)
    with (HERE/'timing_corrected.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps(phases),flush=True)


if __name__=='__main__':main()
