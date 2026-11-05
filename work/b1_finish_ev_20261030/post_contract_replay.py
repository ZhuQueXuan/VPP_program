"""Replay saved valid artifacts after validation-only contract correction."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,sys,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];W=Path(__file__).parent;sys.path.insert(0,str(R/'B1算法'))
from b1_algorithm.effects.frozen import load_continuous_model,query_continuous_model,find_incentive_threshold
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=0;artifacts=0;thresholds=0
def check(a,b,label):
    global checks
    assert a==b,label
    checks+=1
for folder in ('step4','final_chain'):
    F=W/folder
    for path in sorted((F/'models').glob('*.json')):
        model=load_continuous_model(path)
        saved=read(F/(path.stem+'_query.json')) if folder=='step4' else dict(query=read(F/'queries'/path.name),threshold=read(F/'thresholds'/path.name) if (F/'thresholds'/path.name).exists() else None)
        old=saved['query'];grid=[p['dose'] for p in old['diagnostics']['by_dose']][1:]
        # Query grid lives in curve for supported cases. For unsupported, use
        # the original nine requested doses from the unchanged protocol.
        if old['curve'] is not None:grid=old['curve']['incentive_values']
        else:grid=[.4,.6,.8,1.,1.2,1.4,1.6,1.8,2.]
        new=query_continuous_model(model,grid)
        check(new['status'],old['status'],path.name+' status')
        if new['curve'] is not None:
            for name in ('mean_outcomes','contrasts','incentive_values'):
                check(new['curve'][name],old['curve'][name],path.name+' '+name)
            check(new['sensitivity'],old['sensitivity'],path.name+' sensitivity')
            check(new['inference'],old['inference'],path.name+' band')
        if saved['threshold'] is not None:
            newt=find_incentive_threshold(model,target_contrast=120.,search_domain=[.4,2.],mesh_step=.04)
            check(newt,saved['threshold'],path.name+' threshold')
            thresholds+=1
        artifacts+=1
receipt=dict(valid_artifacts=artifacts,threshold_replays=thresholds,exact_checks=checks,
    old_scientific_outputs_overwritten=False,old_frozen_sources_preserved=True,
    old_final_source_sha256=sha(W/'final_chain/source_freeze.json'),
    corrected_frozen_module_sha256=sha(R/'B1算法/b1_algorithm/effects/frozen.py'),
    correction='strict known-density bool and malformed/finite JSON validation only; no estimator or solver change')
with (W/'post_contract_replay_receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
print(receipt)
