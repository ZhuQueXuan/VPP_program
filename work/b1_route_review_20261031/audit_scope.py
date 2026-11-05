"""Read-only provenance snapshot; writes only beside this review script."""
from pathlib import Path
import hashlib, json, sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SCOPES = ['B1算法', '01_项目依据', 'task',
 'work/b1_research_point1_final_plan_20261030',
 'work/b1_literature_baseline_20261029',
 'work/b1_failure_diagnosis_20261030',
 'work/b1_template_repair_20261030',
 'work/b1_finish_ev_20261030',
 'work/b1_effect_detection_diagnosis_20261031',
 'work/b1_reliability_20261031']

def snapshot():
    paths = [ROOT/'AGENTS.md']
    for scope in SCOPES:
        paths.extend(p for p in (ROOT/scope).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    result = {}
    for p in sorted(set(paths)):
        h = hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                h.update(chunk)
        result[p.relative_to(ROOT).as_posix()] = h.hexdigest()
    return result

if __name__ == '__main__':
    mode = sys.argv[1]
    actual = snapshot()
    if mode == 'before':
        (OUT/'protected_before.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'files':len(actual),'mode':mode}))
    elif mode == 'after':
        before = json.loads((OUT/'protected_before.json').read_text(encoding='utf-8'))
        receipt = dict(schema='b1.route-review.protection.v1', files_before=len(before), files_after=len(actual),
            changed=[k for k in before if k in actual and before[k]!=actual[k]],
            missing=sorted(set(before)-set(actual)), added=sorted(set(actual)-set(before)),
            limitation='Hashes cover listed source/evidence/original-document directories, not all project data. No data writes or algorithm fitting are performed by this review.')
        receipt['unchanged'] = not any(receipt[k] for k in ('changed','missing','added'))
        (OUT/'protection_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(receipt,ensure_ascii=False))
