"""Freeze the first reconstruction protocol before fitting or computing errors."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = json.loads((BASE/'runs/PVDAQ_SOURCE_QA_02/source_manifest.json').read_text())
    sources = []
    for name, meta in manifest.items():
        path = ROOT / name
        assert sha(path) == meta['sha256'], name
        if path.suffix == '.csv' and 'system_1239_' in path.name:
            sources.append({'path': path.relative_to(ROOT).as_posix(), **meta})
    assert len(sources) == 30
    receipt = json.loads((BASE/'downloads/PVDAQ_MODEL_SOURCES_01/receipt.json').read_text())
    evidence = []
    for entry in receipt['files']:
        path = BASE/'downloads/PVDAQ_MODEL_SOURCES_01'/entry['name']
        assert entry['status'] == 'downloaded' and sha(path) == entry['sha256']
        evidence.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'url': entry['url']})
    protocol = {
        'id': 'PVDAQ_RECONSTRUCTION_V1', 'decision': 'D051',
        'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Retrospective same-published-label AC power reconstruction, system 1239 June 2019',
        'not_validated': ['future prediction', 'maximum available power', 'control response', 'independent site transfer', '103 accuracy'],
        'prior_exposure': 'Whole-month source quality/ranges and development day seen; no model errors computed before this freeze. Chronological retrospective holdout, not blind independent confirmation.',
        'sources': sorted(sources, key=lambda x:x['path']), 'parameter_evidence': evidence,
        'fields': {'time':'measured_on', 'power_W':'ac_power_metered_kw__3015', 'poa_W_m2':'poa_irradiance__3018', 'module_C':'module_temp_f__3019'},
        'time': {'timezone':'America/New_York', 'start':'2019-06-01 00:00:00', 'end_exclusive':'2019-07-01 00:00:00', 'step_minutes':15,
                 'alignment':'Exact published labels only; no shifts, rounding, interpolation, or averaging window inference. Actual interval start/center/end unknown.'},
        'split': {'fit_end_exclusive':'2019-06-21 00:00:00', 'fit_days':20, 'evaluation_days':10, 'selection':'No hyperparameter/model selection on holdout; all three candidates reported.'},
        'admission': 'Exact quarter label; all three core fields finite; G>=0; 1+gamma*(Tmodule-25)>0. All raw rows and missing labels retained in audit. Negative target power retained. Same mask for all methods.',
        'parameters': {'pdc0_W':20160.0, 'module_W':224.0, 'modules':90, 'gamma_per_C':-0.00485, 'reference_C':25.0,
                       'temperature_proxy':'Tcell approximately Tmodule (DeltaT=0); sensor location and mounting gradient unverified. No claim of measured cell temperature.',
                       'irradiance_proxy':'Measured total POA approximates effective irradiance; no independent spectral/IAM/soiling correction.',
                       'ac_boundary':'No verified AC clipping limit; no inverter clipping imposed. Fit scale is empirical combined AC gain, not identified inverter efficiency or degradation.'},
        'models': {
            'B_G':'x=Pdc0*G/1000; P=k*x. k=sum(x*y)/sum(x*x) on admitted fit rows, through origin, one parameter.',
            'M_T':'z=Pdc0*G/1000*(1+gamma*(Tmodule-25)); P=k*z. Same one-parameter fit, manufacturer gamma fixed.',
            'B_GT':'x=Pdc0*G/1000; w=x*(Tmodule-25); P=a*x+b*w; two-parameter unconstrained least squares on same fit rows. Same G,T information comparator; no physical coefficient interpretation.'},
        'failure_policy':'Nonpositive denominator/rank failure or any nonfinite admitted prediction is a failed experiment, never silently dropped. Negative predictions retained. No residual-based filtering, tuning, refitting on holdout, or replacement by nameplate.',
        'metrics': {'units':'W', 'groups':['all','G>=20 W/m2','G<20 W/m2'], 'primary':['MAE','RMSE'], 'secondary':['mean(pred-target)','nearest-rank p95 absolute error','max absolute error with timestamp','per-day MAE/RMSE','negative prediction count'],
                    'group_note':'Irradiance groups are reporting bins, not verified daylight/night or sensor quality flags.',
                    'normalisation':'MAE/RMSE divided by 20160 W DC nameplate, diagnostic only, not accuracy or verified AC rating.',
                    'energy':'Not scored: averaging window semantics unknown.',
                    'interpretation':'Positive component evidence requires M_T improves both holdout MAE and RMSE over B_G; also report B_GT without hiding superiority/failure. No absolute operational accuracy threshold inferred.'},
        'stop_rule':'One frozen comparison, independent source/fit/metric arithmetic verification and deterministic replay. No automatic tuning from these scores. Decide limited component scope and next evidence need.'
    }
    path = BASE/'reconstruction_protocol_v1.json'
    with path.open('x', encoding='utf-8') as f:
        json.dump(protocol,f,ensure_ascii=False,indent=2)
        f.write('\n')
    marker = {'protocol_sha256':sha(path), 'freeze_script_sha256':sha(Path(__file__)), 'state':'frozen_before_model_errors', 'client_date':'2026-10-15'}
    with (BASE/'reconstruction_freeze_receipt_v1.json').open('x',encoding='utf-8') as f:
        json.dump(marker,f,indent=2)
    print(json.dumps(marker))

if __name__ == '__main__': main()
