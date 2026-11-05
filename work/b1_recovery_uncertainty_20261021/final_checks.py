"""Delivery links and immutable earlier-study / published-model identities."""
from pathlib import Path
import hashlib,json,re
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent
GRAPH=PROJECT/'work/b1_graph_learning_20261021'
OLD=PROJECT/'work/b1_research_20261021'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    checks=[]
    def check(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
    for name,value in json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8')).items():
        check('recovery scientific identity '+name,sha(BASE/name)==value)
    for name,value in json.loads((OLD/'source_freeze_before_evaluation.json').read_text(encoding='utf-8')).items():
        check('D106 scientific identity '+name,sha(OLD/name)==value)
    oldr=json.loads((OLD/'fit_receipt.json').read_text(encoding='utf-8'))
    check('D106 predictions unchanged',sha(OLD/'predictions.npz')==oldr['predictions_sha256'])
    check('D106 raw unchanged',sha(PROJECT/'data/驱动因素解耦模拟数据集_B1_v1_20261021/main_observations.npz')==oldr['raw_sha256'])
    recovery=json.loads((BASE/'independent_verification.json').read_text(encoding='utf-8'))
    graph=json.loads((GRAPH/'independent_verification.json').read_text(encoding='utf-8'))
    check('recovery independent verification',recovery['passed'] and recovery['check_count']==1006)
    check('graph independent verification',graph['status']=='passed')
    mpath=PROJECT/'资源能力模型/manifest.json'
    m=json.loads(mpath.read_text(encoding='utf-8'))
    for name,identity in m['files'].items():
        check('published '+name,sha(mpath.parent/name)==identity['sha256'])
    expected=set(m['files'])|{'manifest.json'}
    actual={str(p.relative_to(mpath.parent)).replace('\\','/') for p in mpath.parent.rglob('*') if p.is_file()}
    check('published 74 files no extras',actual==expected and len(actual)==74)
    oldpub=json.loads((OLD/'contract_checks.json').read_text(encoding='utf-8'))
    oldmanifest=next(r['sha256'] for r in oldpub['checks'] if r['name']=='published manifest read-only identity')
    check('manifest v15 identity unchanged',sha(mpath)==oldmanifest and m['version']=='ready-models-v15')
    docs=list(BASE.glob('*.md'))+list(GRAPH.glob('*.md'))
    docs += [PROJECT/'data/驱动因素解耦模拟数据集_B1_recovery_v1_20261021/README.md',
             PROJECT/'data/驱动因素解耦模拟数据集_B1_graph_v1_20261021/README.md']
    for doc in docs:
        for _,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('https:','http:','#')):continue
            check('link '+str(doc.relative_to(PROJECT))+' -> '+target,(doc.parent/target.split('#')[0]).exists())
    check('global draft remains in work',(PROJECT/'work/four_algorithm_plan_review_20261021/课题一四算法内容与输入输出规划_待审稿.md').exists())
    out=dict(passed=all(x['passed'] for x in checks),check_count=len(checks),checks=checks)
    (BASE/'final_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=out['passed'],checks=len(checks),failed=[x for x in checks if not x['passed']])))
    assert out['passed']

if __name__=='__main__':main()
