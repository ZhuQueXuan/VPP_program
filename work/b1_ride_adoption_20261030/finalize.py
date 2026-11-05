from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name in ('verification.json','review_receipt.json','legacy_explicit_compatibility/pipeline_verification.json'):
    assert json.loads((HERE/name).read_text(encoding='utf-8'))['passed'],name
before={Path(k).as_posix():v for k,v in json.loads((HERE/'before_manifest.json').read_text(encoding='utf-8')).items()}
changed=[name for name,value in before.items() if sha(ROOT/name)!=value]
allowed={'B1算法/README.md','B1算法/requirements.txt','B1算法/b1_algorithm/api.py',
         'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/b1_algorithm/process/_policy.json'}
assert set(changed)==allowed,changed
for name,value in before.items():
    assert sha(HERE/'before_source'/Path(name).relative_to('B1算法'))==value,name
added=[p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in before]
assert {p.name for p in added}=={'_ride_identify.py','_ride_fit.py'}
verification=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
assert verification['maximum_curve_difference']==0.
decision=json.loads((HERE/'decision.json').read_text(encoding='utf-8'))
receipt=dict(adopted=True,date='2026-10-30',policy=decision['implementation']['policy_version'],
    default_by_meter=dict(ten_seconds='guarded CPOP',one_minute='original RIDE template',fifteen_minutes='original RIDE interval-average template, assumption-sensitive'),
    numerical_parity_cases=verification['numerical_migration_cases'],maximum_curve_difference=0.,
    route_checks=verification['n_checks'],independent_review='review_receipt.json',legacy_explicit_checks=31,
    original_template_preserved=True,reference_and_effects_numerics_unchanged=True,
    new_independent_performance_experiment=False,selection_basis='decision.json',
    reports_modified=False,zip_created=False,deletion_performed=False,
    changed_existing_files=changed,new_source_files={str(p.relative_to(ROOT)):sha(p) for p in added},
    after_source={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts})
dest=HERE/'adoption_receipt.json';assert not dest.exists()
dest.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='after_source'},ensure_ascii=False,indent=2))
