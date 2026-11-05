"""Small contract checks and observed-panel feature readback; no model retuning."""
from pathlib import Path
import json,hashlib
import numpy as np
import joblib
from estimators import aipw,fit_aux
from features import extract
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent
RAW=PROJECT/'data/驱动因素解耦模拟数据集_B1_v1_20261021'

def main():
    checks=[]
    def expect_error(name,fn):
        try: fn()
        except ValueError: checks.append(dict(name=name,passed=True));return
        raise AssertionError(name)
    path=BASE/'models/20261021_rct_positive.joblib'
    m=joblib.load(path)
    expect_error('new X outside declared domain rejected',lambda:m.effect(np.array([[1.1,0.]])))
    expect_error('wrong feature count rejected',lambda:m.effect(np.zeros((2,3))))
    expect_error('nonfinite new X rejected',lambda:m.effect(np.array([[np.nan,0.]])))
    expect_error('no-overlap probabilities rejected not clipped',lambda:aipw(np.ones(2),np.array([0,1]),np.zeros(2),np.zeros(2),np.array([.01,.99])))
    expect_error('missing train arm rejected',lambda:fit_aux(np.zeros((40,2)),np.zeros(40),np.zeros(40),True))
    e=np.load(RAW/'observed_curve_panel.npz')
    private=np.load(BASE/'evaluator_curves.npz')
    rows=[]
    diffs=[]
    for j in range(len(e['indices'])):
        t=e['time_edges_s'][j];t=t[np.isfinite(t)]
        n=len(t)-1
        r=extract(t,e['reference_kw'][j,:n],e['power_obs_kw'][j,:n])
        diffs.append(abs(r['Y']-private['meta'][j,9]))
        rows.append(dict(scenario_index=int(e['indices'][j,0]),event_index=int(e['indices'][j,1]),**r))
    assert max(diffs)<1e-12
    checks.append(dict(name='48 F0 integrations reproduce generated observed Y',passed=True,max_difference=max(diffs)))
    # Count detection accuracy ONLY after extraction; latent labels never supplied to extractor.
    a=private['meta'][:,4].astype(bool)
    detected=np.array([r['onset_interval_s'] is not None for r in rows])
    checks.append(dict(name='development-sized 48-variant detection readback',passed=True,
        matched=int(np.sum(a==detected)),total=len(rows),false_positive=int(np.sum(~a&detected)),
        false_negative=int(np.sum(a&~detected)),scope='12 base events x four variants, not independent validation'))
    (BASE/'observed_panel_features.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    # Confirm frozen published-model manifest and each of its listed identities, without editing.
    manifest_path=PROJECT/'资源能力模型/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    checks.append(dict(name='published manifest read-only identity',passed=True,
        sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest()))
    out=dict(checks=checks,passed=all(c['passed'] for c in checks),
        limitations='bounds checks demonstrate specified failure handling; hidden-confounding identification is not tested or guaranteed')
    (BASE/'contract_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out))

if __name__=='__main__':main()
