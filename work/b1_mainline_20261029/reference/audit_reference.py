"""Independent reread of serialized event errors and frozen source identity."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
raw=pd.read_csv(ROOT/'raw.csv')
detail=pd.read_csv(ROOT/'test_events.csv')
checks=[]
for keys,g in detail.groupby(['seed','hot','resource','method']):
    seed,hot,resource,method=keys
    r=raw[(raw.seed==seed)&(raw.hot==hot)&(raw.resource==resource)&(raw.method==method)]
    assert len(r)==1
    r=r.iloc[0]
    err=g.window_reference_error_kw.to_numpy()
    np.testing.assert_allclose(np.sqrt(np.mean(err**2)),r.rmse_kw,atol=1e-12)
    np.testing.assert_allclose(err.mean(),r.bias_kw,atol=1e-12)
    assert len(g)==int(r.n_events)
    checks.append(1)
identity=json.loads((ROOT/'data_identity.json').read_text())
assert len(identity)==40
for item in identity:
    roles=item['user_splits']
    sets=[set(v) for v in roles.values()]
    assert sum(map(len,sets))==200
    assert len(set.union(*sets))==200
manifest_path=ROOT.parents[1]/'ride_b1_v02_reproduction_20261029/source_manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
base=manifest_path.parent/'source'
for item in manifest['files']:
    assert hashlib.sha256((base/item['path']).read_bytes()).hexdigest()==item['sha256']
for condition,g in raw.query("method=='selected'").groupby(['seed','hot','resource']):
    choice=g.iloc[0].selected_candidate
    source=raw[(raw.seed==condition[0])&(raw.hot==condition[1])&(raw.resource==condition[2])&(raw.method==choice)].iloc[0]
    np.testing.assert_allclose(g.iloc[0].rmse_kw,source.rmse_kw,atol=1e-12)
    np.testing.assert_allclose(g.iloc[0].bias_kw,source.bias_kw,atol=1e-12)
receipt=dict(passed=True,independent_event_rmse_and_bias_groups=len(checks),test_event_records=len(detail),role_partitions_checked=len(identity),original_ride_files_sha_unchanged=len(manifest['files']),selected_methods_match=True)
(ROOT/'audit_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
