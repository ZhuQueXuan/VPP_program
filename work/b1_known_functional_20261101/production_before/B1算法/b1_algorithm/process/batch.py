"""Ordered batch API; native CPOP routes share one R batch when required."""
from pathlib import Path
import json
from .api import prepare,cases_for,complete,resolve_policy,needs_native
from ._cpop import fit_cases,validate_config

def identify_process_batch(requests,config=None,*,method=None,native_unavailable_reason=None):
    if not isinstance(requests,(list,tuple)):raise ValueError('ordered request list required')
    try:config=validate_config(config)
    except (ValueError,TypeError) as ex:
        return [dict(status='unavailable',method=None,reason=str(ex),selection_evidence={},features=None,
                     eta_raw=None,physical_timing=None,uncertainty_status='unavailable') for _ in requests]
    prepared={};policies={};output=[None]*len(requests);cases=[]
    for i,request in enumerate(requests):
        try:
            if not isinstance(request,dict):raise ValueError('request_dict_required')
            data=prepare(request.get('starts_min'),request.get('ends_min'),request.get('power_kw'),
                         request.get('reference_kw'),request.get('task'),request.get('noise_sigma_kw'),request.get('ev_config'))
            prepared[i]=data
            policy=resolve_policy(len(data['y']),method,delta_min=data['delta'])
            if policy=='duration_fusion':
                from ._duration_fusion import validate_domain
                validate_domain(data)
            if policy=='reference_tracked_duration':
                from ._reference_tracking import prepare_tracking
                data=prepare_tracking(data);prepared[i]=data
            policies[i]=policy
            if needs_native(len(data['y']),policy):cases.extend(cases_for(data,base=i*10,include_cv=policy=='guarded'))
        except (ValueError,TypeError,OverflowError) as ex:
            output[i]=dict(status='unavailable',method=None,reason=str(ex),selection_evidence={},features=None,
                           eta_raw=None,physical_timing=None,uncertainty_status='unavailable')
    if cases and native_unavailable_reason is not None:
        native,backend={},dict(status='unavailable',reason=native_unavailable_reason,cases=0)
    else:
        native,backend=fit_cases(cases,config) if cases else ({},dict(status='not_needed',reason='selected_routes_do_not_require_R',cases=0))
    for i,data in prepared.items():
        if i in policies:output[i]=complete(data,native,base=i*10,policy=policies[i],backend=backend)
    return output
