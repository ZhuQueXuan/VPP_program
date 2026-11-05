"""Source relocation regression; writes only into this work directory."""
from pathlib import Path
import argparse, json, sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['before', 'after'])
args = parser.parse_args()
source = ROOT if args.phase == 'before' else ROOT / 'B1算法'
sys.path.insert(0, str(source))
from b1_api import analyze_event, provided_reference, ReferenceWindow, load_reference_model, predict_reference
import b1_api, b1_algorithm

task = dict(task_id='relocation', user_id='u1', meter_id='m1', start_min=1000.,
            end_min=1030., notice_min=985., request_kw=1.5, task_pre_treatment=True)
s = np.arange(985., 1045.); e = s + 1.
b = np.full(60, 3.)
rng = np.random.default_rng(30102026)
p = b - np.where((s >= 1000.) & (s < 1030.), .45, 0.) + rng.normal(0., .05, 60)
ref = provided_reference(task, s, e, b, available_at_min=985.)
event = analyze_event(task, s, e, p, ref, .05)
assert event['status'] == 'ok', event
assert event['process']['method'] in ('CPOP', 'template', 'RIDE_template'), event['process']['method']
fixture_dir = ROOT / 'work/b1_formal_v1_20261029/reference'
window = ReferenceWindow(**json.loads((fixture_dir / 'query_fixture.json').read_text(encoding='utf-8')))
prediction = predict_reference(load_reference_model(fixture_dir / 'artifact'), window)
assert prediction.reference_status == 'available', prediction.reasons

def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if k not in ('seconds', 'elapsed_seconds', 'artifact_dir')}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value

numeric = dict(event=stable(event), reference_prediction=prediction.reference_kw.tolist(), model_id=prediction.model_id)
out = HERE / args.phase
out.mkdir(exist_ok=True)
(out / 'numerical_result.json').write_text(json.dumps(numeric, ensure_ascii=False, indent=2), encoding='utf-8')
if args.phase == 'after':
    baseline = json.loads((HERE / 'before/numerical_result.json').read_text(encoding='utf-8'))
    assert numeric == baseline, 'Relocation changed numerical results or status'
    assert Path(b1_api.__file__).resolve().is_relative_to(source)
    assert Path(b1_algorithm.__file__).resolve().is_relative_to(source)
    # Reuse the 31 existing integration checks without editing their frozen script/results.
    original = ROOT / 'work/b1_formal_v1_20261029/verify_pipeline.py'
    code = original.read_text(encoding='utf-8').replace(
        "OUT=Path(__file__).resolve().parent", 'OUT=' + repr(str(out)))
    code = code.replace('OUT=' + repr(str(out)), 'OUT=Path(' + repr(str(out)) + ')')
    exec(compile(code, str(original), 'exec'), {'__file__': str(original), '__name__': '__migration_checks__'})
    assert not (source / 'work').exists(), 'Runtime artifacts leaked into source folder'
receipt = dict(passed=True, phase=args.phase, imported_api=b1_api.__file__,
               imported_package=b1_algorithm.__file__, native_method=event['process']['method'],
               eta=event['outcome']['value'], reference_intervals=len(prediction.reference_kw),
               unchanged_numerical_results=args.phase == 'after',
               scope='path relocation and execution regression only; no new performance claims')
(out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
