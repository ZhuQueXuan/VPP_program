"""Replay stricter contracts without refitting the frozen main experiment.

The original raw files are immutable. Only known synthetic identity/calendar
metadata are reconstructed; their recipe and original file hashes are saved.
"""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json,copy,hashlib,dataclasses
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import EVFactorStudy,ReferenceWindow,load_reference_model,select_ev_reference
from b1_algorithm.factors import _inputs
from b1_algorithm.contracts import task_contract
from simulation import generate

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)

def add_known_metadata(facts):
    """Only for this explicitly timed synthetic experiment; not an API default."""
    corrected=copy.deepcopy(facts)
    for row in corrected:
        for h in row['historical_non_event']:
            start=float(h['starts_min'][0]+75.)
            h.update(user_id=row['task']['user_id'],meter_id=row['task']['meter_id'],
                reference_context=dict(clock_hour=float((start%1440.)/60.),weekday=int(start//1440.)%7,
                    calendar_available_min=start-16.,temperature_available_min=start-16.))
    return corrected

def main():
    if (HERE/'corrective_replay_receipt.json').exists():raise RuntimeError('do not overwrite a completed replay')
    protocol=read(HERE/'protocol.json');model=load_reference_model(ROOT/protocol['reference']['frozen_model'])
    source_before=read(HERE/'scientific_source_freeze.json');raws={};saved={};counts=dict(factual_events=0,strict_outcome_rows=0,reference_replays=0)
    study=EVFactorStudy('strict-replay','元/千瓦时')
    for seed in protocol['main_seeds']:
        specs=[('positive',seed,dict()),('zero',seed,dict(scenario='zero')),
               ('stress_20',seed+10000,dict(n_users=8,W=20,noise_sigma_kw=.15)),
               ('stress_37',seed+10000,dict(n_users=8,W=37,noise_sigma_kw=.15))]
        for panel,generated_seed,opts in specs:
            path=ROOT/f'data/B1_EV_mainline_v1_20261030/{seed}_{panel}_facts.json'
            raw=read(path);facts=add_known_metadata(raw);regenerated,truth,meta=generate(generated_seed,**opts)
            assert facts==regenerated,(seed,panel,'metadata-only factual replay')
            assert truth==read(HERE/f'evaluator/{seed}_{panel}_truth.json'),(seed,panel,'truth changed')
            raws[path.relative_to(ROOT).as_posix()]=sha(path);counts['factual_events']+=len(raw)
            factors=[r['factor_record'] for r in facts]
            eventsets={}
            for method in ('ride_template','cpop'):
                event_path=HERE/(f'events/{seed}_{panel}_{method}.json' if panel in ('positive','zero') else f'stress/{seed}_{panel.split("_")[1]}_{method}.json')
                saved[event_path.relative_to(ROOT).as_posix()]=sha(event_path);events=read(event_path);eventsets[method]=events
                for name,source in [('cumulative_response_seconds','selected_curve'),('longest_continuous_response_seconds','selected_curve'),
                                    ('cumulative_response_seconds','raw_observed'),('eta_raw','raw_observed')]:
                    design=dataclasses.replace(study,outcome_name=name,outcome_source=source)
                    parsed=_inputs(events,factors,design);counts['strict_outcome_rows']+=len(events)
                    assert np.array_equal(parsed['D'],[r['offered_incentive'] for r in factors])
                    assert np.array_equal(parsed['all_X'],[[r['deadline_slack'],r['demand_urgency']] for r in factors])
                    expected=[e['outcome']['value'] if name=='eta_raw' else e['process']['features'][source][name] for e in events]
                    assert np.array_equal(parsed['y'],expected)
            assert [e['outcome']['value'] for e in eventsets['ride_template']]==[e['outcome']['value'] for e in eventsets['cpop']]
            # A predeclared small numerical replay of selectors; no optimization
            # or process fitting. Main positive and zero share references.
            if panel=='zero':continue
            selections=read(HERE/f'reference/{seed}_selection.json') if panel=='positive' else None
            for i,row in enumerate(facts[:8]):
                result=select_ev_reference(model,ReferenceWindow(**row['reference_window']),row['historical_non_event'])
                if selections is not None:assert result['selection']==selections[i],(seed,i,'past selection changed')
                digest=hashlib.sha256(json.dumps(dict(task=task_contract(row['task']),starts=row['starts_min'],ends=row['ends_min'],
                    power=row['power_kw'],reference=result['reference'].reference_kw.tolist()),sort_keys=True).encode()).hexdigest()
                assert digest==eventsets['ride_template'][i]['input_digest'],(seed,panel,i,'prediction changed')
                counts['reference_replays']+=1
        print('strict replay completed',seed,flush=True)
    changed={name:dict(before=old,after=sha(ROOT/name)) for name,old in source_before.items() if sha(ROOT/name)!=old}
    assert set(changed)=={'B1算法/b1_algorithm/factors.py','B1算法/b1_algorithm/reference/ev_selection.py',
        'work/b1_ev_mainline_20261030/simulation.py'},set(changed)
    write(HERE/'historical_metadata_recipe.json',dict(scope='this synthetic dataset only',original_files=raws,
        original_files_modified=False,recipe='add_known_metadata in corrective_replay.py',
        epoch='explicit synthetic day0 minute origin; historical constant temperature/calendar known before pseudo-notice',
        identity='same user and single EV meter already used by the generator',
        differences='history user_id/meter_id and explicit reference_context only; no numerical arrays or RNG changes'))
    write(HERE/'corrective_replay_receipt.json',dict(passed=True,**counts,changed_source_identity=changed,
        original_raw_sha256=raws,original_event_sha256=saved,main_results_refit=False,
        original_truth_exactly_preserved=True,facts_exactly_equal_except_new_metadata=True,
        selected_reference_numeric_inputs_preserved=True,eta_identical_between_methods=True,
        main_run_missing_explicit_history_metadata=True,
        interpretation='Main was run with original frozen source. Stricter contracts replayed on saved events and documented synthetic metadata; this does not create real historical provenance.'))
    print(json.dumps(counts))

if __name__=='__main__':main()
