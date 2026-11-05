from common import *

def sources():
    all_cases=[];all_truth={};all_curves={};ledger={}
    def add(directory,cases,truth,curves):
        for c in cases:
            tid=c['task_id']
            if tid in ledger:continue
            f=dict(curves[tid]['results'])
            if 'retained' in f:f['duration_fusion']=f.pop('retained')
            all_cases.append(c);all_truth[tid]=truth[tid];all_curves[tid]=f;ledger[tid]=directory.as_posix()
    for stage in ['validation','stress','test']:
        directory=OLD/stage;curves={r['task_id']:r for r in read(directory/'curves.json')};truth={};cases=[]
        for panel in ['minute','10s']:
            cases+=read(directory/panel/'facts.json');truth.update({r['task_id']:r for r in read(directory/panel/'truth.json')})
        add(directory,cases,truth,curves)
    for name,stages in [('b1_false_unknown_20261101',['validation','test']),('b1_false_unknown_v2_20261101',['test'])]:
        for stage in stages:
            directory=ROOT/'work'/name/stage;curves={r['task_id']:r for r in read(directory/'curves.json')};truth={}
            for panel in ['minute','10s']:truth.update({r['task_id']:r for r in read(directory/f'known_{panel}/truth.json')})
            add(directory,[c for c in read(directory/'all_facts.json') if c['regime']=='known'],truth,curves)
    for name,stages in [('b1_known_weak_20261101',['train_stress']),('b1_known_functional_20261101',['test','stress_test','stress_continuous']),('b1_local_rescue_20261101',['validation','main_test','weak_test']),('b1_local_rescue_v2_20261102',['main_test','weak_test'])]:
        for stage in stages:
            directory=ROOT/'work'/name/stage;truth={}
            for panel in ['minute','10s']:
                for label in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(directory/panel/label)})
            add(directory,read(directory/'facts.json'),truth,{r['task_id']:r for r in read(directory/'curves.json')})
    return all_cases,all_truth,all_curves,ledger
