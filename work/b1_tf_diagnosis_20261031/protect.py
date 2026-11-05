"""Snapshot old artifacts; writes only to this new diagnosis directory."""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SCOPES=['B1算法','01_项目依据','task','work/b1_unknown_reference_pilot_20261031',
        'data/B1_unknown_reference_pilot_v1_20261031']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    paths=[ROOT/'AGENTS.md',ROOT/'work/b1_reliability_20261031/study/generator.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py']
    for scope in SCOPES:paths.extend(p for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
if __name__=='__main__':
    current=snapshot()
    if sys.argv[1]=='before':
        (HERE/'protected_before.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'files':len(current)}))
    else:
        before=json.loads((HERE/'protected_before.json').read_text(encoding='utf-8'))
        changed=[p for p in before if p in current and before[p]!=current[p]]
        result=dict(files_before=len(before),files_after=len(current),changed=changed,
            missing=sorted(set(before)-set(current)),added=sorted(set(current)-set(before)),
            allowed_document_update=[p for p in changed if p=='AGENTS.md'],
            scientific_unchanged=not any(p!='AGENTS.md' for p in changed) and set(before)==set(current),
            scopes=SCOPES)
        (HERE/'protection_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
