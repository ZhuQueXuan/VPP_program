"""Additional EV input boundaries and arithmetic audits, without model selection."""
from pathlib import Path
import ast,copy,dataclasses,json,sys
import numpy as np
from verify import record,requirement,HERE,ROOT
from b1_api import analyze_event,analyze_events,estimate_event_effects,estimate_metered_effects,assess_ev_recovery,provided_reference
from b1_algorithm.resources.ev import ev_config

checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

def run():
    for field in ('max_charge_kw','dwell_seconds','onset_fraction','observation_pre_min','template_ramp_max_min'):
        for value in (True,'7.2',float('nan'),float('inf')):
            try:ev_config({field:value})
            except ValueError:check('reject invalid '+field+repr(value),True)
            else:raise AssertionError((field,value))
    for settings in ({'unknown':1},{'dwell_seconds':0},{'target_fraction':.05},False,{'observation_post_min':60}):
        try:ev_config(settings)
        except ValueError:check('reject invalid settings '+repr(settings),True)
        else:raise AssertionError(settings)
    valid=record(index=7000)
    for resource in ('AC','ESS','V2G',False):
        bad=copy.deepcopy(valid);bad['task']['resource_type']=resource
        check('other resource explicitly rejected '+str(resource),analyze_event(**bad)['status']=='invalid_input')
    for label,key,value in (('boolean q','request_kw',True),('string q','request_kw','1.5'),
                            ('above domain q','request_kw',23.),('zero q','request_kw',0.)):
        bad=copy.deepcopy(valid);bad['task'][key]=value
        result=analyze_event(**bad)
        check(label,result['status'] in ('invalid_input','unavailable') and result['outcome'] is None)
    for label,field in (('power boolean','power_kw'),('power string','power_kw'),('power nan','power_kw')):
        bad=copy.deepcopy(valid);bad[field]=list(bad[field]);bad[field][0]={'power boolean':True,'power string':'4.32','power nan':float('nan')}[label]
        check(label,analyze_event(**bad)['status']=='invalid_input')
    bad=copy.deepcopy(valid);bad['ev_config']={'observation_pre_min':False}
    ordered=analyze_events([valid,bad,valid])
    check('invalid profile does not poison other events',[r['status'] for r in ordered]==['ok','unavailable','ok'])
    base=analyze_event(**valid)
    renamed=copy.deepcopy(base);renamed['task']['task_id']='renamed';renamed['task']['user_id']='renamed-user'
    rejected=estimate_event_effects([base,renamed],[[0],[1]],[0,1])
    check('renamed same physical event rejected before effect fitting',rejected['status']=='invalid_input' and 'physical meter window' in rejected['reasons'][0]['detail'])
    renamed_record=copy.deepcopy(valid);renamed_record['task']['task_id']='renamed';renamed_record['task']['user_id']='renamed-user'
    check('metered wrapper same physical event rejected',estimate_metered_effects([valid,renamed_record],[[0],[1]],[0,1])['status']=='invalid_input')
    # Deficit and energy satisfaction are independent of response curve fitting.
    rec=record(index=7001,post=30,rebound=True);req=requirement(rec)
    for label,field,value in (('negative need','remaining_ac_kwh',-1.),('bool need','remaining_ac_kwh',True),
                              ('future state','state_as_of_min',rec['task']['start_min']),('availability before state','available_at_min',rec['starts_min'][0]-1.)):
        changed=copy.deepcopy(req);changed[field]=value
        check(label,assess_ev_recovery(rec['task'],rec['starts_min'],rec['ends_min'],rec['power_kw'],changed,config=rec['ev_config'])['status']=='invalid_input')
    # If the true requirement cannot fit declared maximum, keep the record and diagnose.
    enormous=copy.deepcopy(req);enormous['remaining_ac_kwh']=100.
    result=assess_ev_recovery(rec['task'],rec['starts_min'],rec['ends_min'],rec['power_kw'],enormous,config=rec['ev_config'])
    check('impossible declared need retained',result['status']=='unmet' and result['requirement_exceeds_declared_max_energy'])
    signed=rec['power_kw'].copy();signed[0]=-1.;signed[1]=9.
    result=assess_ev_recovery(rec['task'],rec['starts_min'],rec['ends_min'],signed,req,config=rec['ev_config'])
    energy=sum(float(p)*float(b-a)/60 for p,a,b in zip(signed,rec['starts_min'],rec['ends_min']))
    check('signed and above-max observations retained in energy accounting',abs(result['delivered_ac_kwh']-energy)<1e-10 and result['negative_meter_bins']==1 and result['above_declared_max_bins']==1)
    # Reference unavailable cannot destroy separately observable energy accounting.
    rec['ev_requirement']=req;rec['reference']={'reference_status':'unavailable','reason':'no legal history'}
    result=analyze_event(**rec)
    check('unknown reference and known energy satisfaction remain distinct',result['status']=='unavailable' and result['outcome'] is None and result['ev_service_recovery']['status']=='met')
    # All interval energies from the saved 54-case matrix are checked by a separate formula.
    events=json.loads((HERE/'matrix_events.json').read_text(encoding='utf-8'))
    for i,event in enumerate(events):
        q=event['task']['request_kw'];W=event['task']['end_min']-event['task']['start_min']
        check('matrix raw energy identity '+str(i),abs(event['process']['features']['raw_observed']['request_net_kwh']-.5*q*W/60)<1e-9)
        check('matrix no clipping '+str(i),event['outcome']['process_fit_used_in_energy'] is False)
    for path in (ROOT/'B1算法').rglob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    check('all current Python sources parse',True)
    result=dict(passed=True,n_checks=len(checks),checks=checks,scope='input boundaries and raw energy arithmetic; no performance claim')
    (HERE/'boundary_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))

if __name__=='__main__':run()
