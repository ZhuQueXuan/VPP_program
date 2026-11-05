"""Final local artifact identity/link checks; no scientific re-fitting."""
from pathlib import Path
import hashlib,json,re
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent

def main():
    frozen=json.loads((BASE/'source_freeze_before_evaluation.json').read_text())
    identities={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()==sha for name,sha in frozen.items()}
    docs=[BASE/name for name in ('README.md','独立评估与实施裁决.md','实施协议.md','首轮研究结果与后续路线.md')]
    docs.append(PROJECT/'data/驱动因素解耦模拟数据集_B1_v1_20261021/README.md')
    links=[]
    for doc in docs:
        for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('http:','https:','#')):continue
            p=(doc.parent/target.split('#')[0]).resolve()
            links.append(dict(document=str(doc.relative_to(PROJECT)),target=target,exists=p.exists()))
    manifest=PROJECT/'资源能力模型/manifest.json'
    m=json.loads(manifest.read_text(encoding='utf-8'))
    same=all(hashlib.sha256((manifest.parent/name).read_bytes()).hexdigest()==entry['sha256'] for name,entry in m['files'].items())
    out=dict(frozen_scientific_identities=identities,local_links=links,published_files_same=same,
             global_draft_still_in_work=(PROJECT/'work/four_algorithm_plan_review_20261021/课题一四算法内容与输入输出规划_待审稿.md').exists(),
             independent_status=json.loads((BASE/'independent_verification.json').read_text(encoding='utf-8'))['status'])
    out['passed']=all(identities.values()) and all(x['exists'] for x in links) and same and out['global_draft_still_in_work'] and out['independent_status']=='passed'
    (BASE/'final_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=out['passed'],local_links=len(links),scientific_files=len(identities),published_same=same)))
    assert out['passed']

if __name__=='__main__':main()
