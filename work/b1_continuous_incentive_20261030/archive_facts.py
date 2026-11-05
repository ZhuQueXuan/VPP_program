"""Retain all frozen simulation inputs without refitting or changing results."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from run import ROOT,HERE,generate

def main():
    raw=ROOT/'data/B1_continuous_incentive_v1_20261030'
    manifest={};count=0
    scenarios=['randomized_saturating','observational_saturating','randomized_zero','randomized_nonmonotone','deterministic_no_support']
    for seed in range(30103010,30103022):
        for scenario in scenarios:
            x,d,y,users,pdf,assumptions,truth=generate(seed,scenario)
            frame=pd.DataFrame(dict(user=users,X=x[:,0],offered_incentive=d,eta_observed=y))
            path=raw/f'{seed}_{scenario}.csv'
            payload=frame.to_csv(index=False).encode('utf-8')
            if path.exists():assert path.read_bytes()==payload
            else:path.write_bytes(payload)
            if seed==30103010 and scenario!='deterministic_no_support':
                original=raw/(scenario+'.csv')
                # Pandas path output uses platform line endings on Windows.
                assert original.read_text(encoding='utf-8').replace('\r\n','\n')==payload.decode().replace('\r\n','\n')
            manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();count+=len(frame)
    result=dict(files=60,factual_variants=count,repetitions=12,events_per_case=2400,
        purpose='synthetic method evaluation; not real EV observations',source='work/b1_continuous_incentive_20261030/run.py',
        refitted=False,original_study_results_changed=False,sha256=manifest)
    path=raw/'manifest.json'
    if path.exists():raise RuntimeError('completed raw archive manifest cannot be overwritten')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'}))

if __name__=='__main__':main()
