"""Hash existing sources/evidence without editing them; output is survey-local."""
from pathlib import Path
import hashlib, json, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCOPES=['B1算法','01_项目依据','task','work/b1_revision_assessment_20261029',
        'work/b1_route_review_20261031','work/b1_research_point1_final_plan_20261030']
def snapshot():
    paths=[ROOT/'AGENTS.md']
    for scope in SCOPES:
        paths.extend(p for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}

if __name__=='__main__':
    mode=sys.argv[1]
    current=snapshot()
    if mode=='before':
        (HERE/'protected_before.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'files':len(current)}))
    else:
        before=json.loads((HERE/'protected_before.json').read_text(encoding='utf-8'))
        result=dict(files_before=len(before),files_after=len(current),
            changed=[p for p in before if p in current and before[p]!=current[p]],
            missing=sorted(set(before)-set(current)),added=sorted(set(current)-set(before)),
            scope=SCOPES,limitations='Does not hash all data or all frozen experiments. This survey reads no raw experimental data and runs no models.')
        result['unchanged']=not any(result[k] for k in ['changed','missing','added'])
        (HERE/'protection_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
