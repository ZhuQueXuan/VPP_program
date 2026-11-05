"""Finalize the optional-source adoption receipt after independent verification."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name in ('checks.json','formal_checks.json','boundary_review.json','standalone_receipt.json','results/audit_receipt.json','legacy_compatibility/pipeline_verification.json'):
    assert json.loads((HERE/name).read_text(encoding='utf-8'))['passed'],name
before={Path(k).as_posix():v for k,v in json.loads((HERE/'adoption_before_manifest.json').read_text(encoding='utf-8')).items()}
changed=[]
for name,value in before.items():
    if sha(ROOT/name)!=value:changed.append(name)
assert set(changed)=={'B1算法/b1_api.py','B1算法/README.md'},changed
for name in ('b1_api.py','README.md'):
    assert sha(HERE/'adoption_before'/name)==before['B1算法/'+name]
destination=ROOT/'B1算法/b1_algorithm/metered_effects.py'
assert sha(destination)==sha(HERE/'prototype.py')
summary=json.loads((HERE/'results/receipt.json').read_text(encoding='utf-8'))
receipt=dict(adopted=True,date='2026-10-30',kind='optional metered-energy relative-effect input',
    source=str(destination),source_sha256=sha(destination),public_entry='from b1_api import estimate_metered_effects',
    source_identical_to_validated_prototype=True,old_numeric_source_unchanged=True,existing_default_changed=False,
    changed_existing_files=changed,old_facade_and_readme_preserved='adoption_before/',
    tests=dict(formal_contract_checks=23,independent_boundary_checks=14,legacy_integration_checks=31,isolated_import=True),
    study=dict(seed_blocks=20,paired_scenarios=4,event_variants=288000,method_rows=240,
        wrapper_vs_standard_AIPW_max_difference=summary['wrapper_vs_direct_AIPW_max_difference'],
        audit='results/audit_receipt.json'),
    conclusions=['Input dependence reduced: reference and process fit not needed for relative metered-energy effects',
        'No universal precision improvement; predicted-reference and metered results nearly equal in this matched synthetic experiment',
        'Original absolute-delivery and process pipeline remains; new absolute Z levels are not net delivery',
        'No real-data validation or whole-B1 completion claim'],
    research_runtime_imports=False,report_generated=False,zip_generated=False,
    upstream_process_study='../b1_unknown_reference_20261030/decision.json')
target=HERE/'adoption_receipt.json';assert not target.exists()
target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='conclusions'},ensure_ascii=False,indent=2))

