"""Fixed model identity and measured remaining-demand binding."""
import copy,json
from functools import lru_cache
from core_io import BASE,ROOT,read,sha
from contracts import failed,number,identity,stamp,VERSION
from loaders import isolated
REG=read(BASE/'registry.json');DEFAULT=REG['default']

@lru_cache(maxsize=2048)
def _forecast(serialized):
    with isolated('bridge') as old:r=old.predict_b2(json.loads(serialized),replicate=0,population=1)
    return r

def predict_single(case,model_version=DEFAULT):
    try:
        if model_version not in REG['models']:raise ValueError('unknown fixed model version; trial indices are not public inputs')
        if not isinstance(case,dict):raise ValueError('single-case declaration dictionary required')
        if any(k in case for k in ['replicate','population','model_replicate']):raise ValueError('trial indices are not public declaration fields')
        spec=REG['models'][model_version]
        if sha(ROOT/spec['artifact'])!=spec['artifact_sha256'] or sha(ROOT/spec['selection'])!=spec['selection_sha256']:raise ValueError('fixed model artifact/selection identity changed')
        r=copy.deepcopy(_forecast(json.dumps(case,sort_keys=True,allow_nan=False)))
        r.update(model_version=model_version,model_artifact_sha=sha(ROOT/spec['artifact']),legacy_interface_version=r.get('interface_version'),interface_version=VERSION,result_type='single_EV_response_forecast',committed_kw=None)
        physical=r.get('physical') or {};r['capability']=dict(physical_task_upper_kw=physical.get('qmax_kw'),task_duration_min=30,expected_event_kwh=r.get('expected_delivery_kwh'),conditional_first_reach_min=r.get('conditional_first_reach_min'),conditional_continuous90_min=r.get('conditional_expected_continuous90_min'),expected_post_charging_kw=r.get('expected_post_charging_kw'),model_service_probability=r.get('service30_v1_probability'),empirical_reliability=None,committed_kw=None,evidence='conditional synthetic task fields; unavailable fields remain null, not six invented scores')
        return r
    except (ValueError,TypeError,KeyError,OverflowError) as e:return failed(e)

def predict_remaining(declaration,state,resource_id,task_id,offer_id,known_at):
    try:
        for k,v in [('resource_id',resource_id),('task_id',task_id),('offer_id',offer_id)]:identity(v,k)
        stamp(known_at);b=number(declaration['b'],'b',.6,7);T=number(state['remaining_min'],'remaining_min',0);debt=number(state['backlog_kwh'],'backlog_kwh',0)
        # An actual positive debt remains in the demand. Never normalize it away for model eligibility.
        c=copy.deepcopy(declaration);c.update(T=T,E=b*T/60+debt)
        r=predict_single(c);r.update(resource_id=resource_id,task_id=task_id,offer_id=offer_id,known_at=known_at,actual_backlog_kwh=debt,remaining_required_ac_kwh=c['E'],input_used=c)
        if debt>1e-8:
            r.update(status='unavailable',reason='measured remaining demand contains debt outside frozen B2 E=b*T/60 family',dynamic_scenarios=[],committed_kw=None)
        return r
    except (ValueError,TypeError,KeyError,OverflowError) as e:return failed(e)
