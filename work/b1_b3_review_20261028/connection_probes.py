"""Review-only function queries in isolated processes; no fitting or old-output writes."""
import json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent

def child(code):
    p=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stderr)
    return json.loads(p.stdout)

results={}
results['b3_duplicate_announced_calls']=child(r'''
import sys,json,numpy as np
sys.path.insert(0,'work/b3_feedback_20261028')
from safe_api import evaluate
c=dict(evidence_mode='hypothetical_ac_declared',b=[3.,3.],initial_kwh=4.,pv_forecast_kw=[4.]*36,grid_headroom_kw=1.,ev_headroom_kw=1.5,agents=[dict(permission=True,accepted=True) for _ in range(4)])
calls=[dict(start=0,end=6,q_kw=2.,admitted=True),dict(start=0,end=6,q_kw=2.,admitted=True)]
r=evaluate(c,announced_calls=calls,mode='envelope')
p=np.array(r['plan']['paths_kw']);delivery=(sum(c['b'])-.6*np.array(c['pv_forecast_kw']))-p.sum(axis=0)
fresh=evaluate(c,announced_calls=[calls[0]],new_call=calls[1],mode='envelope')
print(json.dumps(dict(existing_calls=calls,result_status=r['status'],service_min_kw=float(min(delivery[:6])),combined_requested_kw=4.,new_call_overlap_status=fresh['status'],new_call_reason=fresh.get('reason'))))
''')

results['native_output_not_native_input']=child(r'''
import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,'work/b3_feedback_20261028')
from safe_api import evaluate
b2=json.loads(Path('work/b2_completion_20261027/example_output.json').read_text(encoding='utf-8'))['output']
r=evaluate(b2)
print(json.dumps(dict(b2_output_keys=list(b2),b3_status=r['status'],reason=r.get('reason'))))
''')

results['b1_feature_shape']=child(r'''
import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,'work/b1_ev_factor_chain_20261026')
from features import extract
b2=json.loads(Path('work/b2_completion_20261027/example_output.json').read_text(encoding='utf-8'))
p=np.array([b2['output']['expected_event_charging_kw']]);ref=np.full(p.shape,b2['input']['b'])
try:r=extract(ref,p);result=dict(status='accepted')
except Exception as e:result=dict(status='rejected',exception=type(e).__name__,reason=str(e),shape=list(p.shape))
print(json.dumps(result))
''')

results['template_energy_vs_service_semantics']=child(r'''
import sys,json,numpy as np
sys.path.insert(0,'work/b2_completion_20261027')
from generate import templates
x=templates()[1]*1.5
coarse=x.reshape(6,5).mean(axis=1)
print(json.dumps(dict(template=1,description='two minute delay, then full28min',q_kw=1.5,b2_service30_v1=True,
    b2_strict_full30=False,fine_energy_kwh=float(x.sum()/60),coarse_energy_kwh=float(coarse.sum()/12),coarse_reduction_kw=coarse.tolist(),
    b3_strict_constant_q_each5min=bool(min(coarse)>=1.5-1e-9))))
''')

results['common_subdomain_physical_consistency']=child(r'''
import sys,json,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('ev_core',Path('资源能力模型/03_电动汽车充电设施/code/capability_model.py'))
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
sys.path.insert(0,'work/b3_coordination_20261028')
from physics import central
c=dict(evidence_mode='declared_hypothetical_ac',id='review_only_common_EV',evs=[dict(baseline_kw=3.,permission=True,accepted=True),dict(baseline_kw=1.,permission=False,accepted=False)],
    battery=dict(initial_kwh=4.,permission=False,accepted=False),pv=dict(reserve=0.,permission=False,accepted=False),fixed_kw=[5.]*24,
    available_pv_kw=[0.]*24,grid_lower_kw=[0.]*24,grid_upper_kw=[100.]*24,ev_cap_kw=[100.]*24)
r=central(c)
boundary=ev.evaluate(dict(evidence_mode='declared_scenario',station_limit_kw=7.2,vehicles=[dict(id='EV',arrival_min=0,departure_min=120,remaining_ac_kwh=6.,max_kw=7.2)],event=dict(start_min=0,end_min=30,cap_kw=0.)))
print(json.dumps(dict(analytic_qmax_kw=min(3.,(7.2-3)*1.5/.5),b3_qmax_kw=r['q_kw'],old_ev_core_at_q3=boundary['status'],
    note='constructed common physical subdomain only; no B2 learned output consumed, actual acceptance explicitly declared, not from probability')))
''')

results['b2_180min_domain']=child(r'''
import sys,json
from pathlib import Path
sys.path.insert(0,'work/b2_completion_20261027')
from api import evaluate
c=json.loads(Path('work/b2_completion_20261027/example_output.json').read_text(encoding='utf-8'))['input']
c.update(b=3.,T=180.,E=9.,q=1.5,permission=True)
r=evaluate(c)
print(json.dumps(dict(status=r['status'],reason=r.get('reason'),physical=r.get('physical'),committed_kw=r.get('committed_kw'))))
''')

with (OUT/'connection_probe_results.json').open('x',encoding='utf-8') as f:json.dump(results,f,ensure_ascii=False,indent=2)
print(json.dumps(results,ensure_ascii=False,indent=2))
