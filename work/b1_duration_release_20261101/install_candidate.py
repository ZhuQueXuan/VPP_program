"""Install only after the frozen independent adoption gate passed."""
from common import *
import shutil

def main():
    assessment=read('assessment.json');assert assessment['adopt'] and all(assessment['gates'].values())
    assert read('independent_checks.json')['all_passed']
    before={}
    for p in (ROOT/'B1算法').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            relative=p.relative_to(ROOT/'B1算法');destination=HERE/'production_before'/relative
            destination.parent.mkdir(parents=True,exist_ok=True);assert not destination.exists();shutil.copy2(p,destination)
            before[p.relative_to(ROOT).as_posix()]=sha(p)
    write('production_before.json',before)
    target=ROOT/'B1算法/b1_algorithm/process'
    for p in (HERE/'staging').rglob('*'):
        if p.is_file():
            destination=target/p.relative_to(HERE/'staging');destination.parent.mkdir(parents=True,exist_ok=True)
            assert not destination.exists();shutil.copy2(p,destination)
    write('installation_assets.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [target/'_duration_fusion.py']+list((target/'duration_models').glob('*.json'))},
                                         adopted_scope='explicit optional duration_fusion method; global default unchanged'))
    print('passed candidate assets installed; original production snapshot retained')
if __name__=='__main__':main()
