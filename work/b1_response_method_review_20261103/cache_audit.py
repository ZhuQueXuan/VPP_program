"""Behavioral reproduction of shared model cache risk, not a method performance test.

Source audited: KColangelo/Double-ML-Continuous-Treatment,
Supplement/estimation.py, ordinary DDMLCT.naive(), active lines107-111.
This independent small example demonstrates the Python mutable-object issue;
it does not import or run the authors' entire estimator or use research data.
"""
from pathlib import Path
import copy,json
import numpy as np
from sklearn.linear_model import Ridge

folder=Path(__file__).resolve().parent
x=np.zeros((2,1));first=np.full(2,10.);second=np.zeros(2)
shared=copy.deepcopy(Ridge());cache=[]
cache.append(shared.fit(x,first));initial=cache[0].predict(x).tolist()
cache.append(shared.fit(x,second));later=cache[0].predict(x).tolist()
independent=[copy.deepcopy(Ridge()).fit(x,y) for y in [first,second]]
assert cache[0] is cache[1] and initial==[10.,10.] and later==[0.,0.]
assert independent[0].predict(x).tolist()==[10.,10.]
result=dict(status='confirmed_mutable_cache_aliasing',source_url='https://raw.githubusercontent.com/KColangelo/Double-ML-Continuous-Treatment/master/Supplement/estimation.py',audited_path='ordinary_DDMLCT.naive',scope='source inspection plus minimal behavioral analogue, not full repository execution',shared_instance=cache[0] is cache[1],first_query_fold0=initial,later_query_fold0=later,independent_fold0=independent[0].predict(x).tolist(),necessary_baseline_reproduction_fix_not_innovation=True,main_experiment_run=False,user_data_used=False)
path=folder/'cache_audit.json'
if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==result
else:path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
