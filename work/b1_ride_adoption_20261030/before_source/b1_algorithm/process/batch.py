"""Ordered public batch API; one original R batch for all supported requests."""
from pathlib import Path
import json
from .api import prepare,cases_for,complete
from ._cpop import fit_cases,validate_config

def identify_process_batch(requests,config=None):
    if not isinstance(requests,(list,tuple)):raise ValueError('ordered request list required')
    try:config=validate_config(config)
    except (ValueError,TypeError) as ex:
        return [dict(status='unavailable',method=None,reason=str(ex),selection_evidence={},features=None,
                     eta_raw=None,physical_timing=None,uncertainty_status='unavailable') for _ in requests]
    policy=json.loads(Path(__file__).with_name('_policy.json').read_text(encoding='utf-8'))['default']
    prepared={};output=[None]*len(requests);cases=[]
    for i,request in enumerate(requests):
        try:
            if not isinstance(request,dict):raise ValueError('request_dict_required')
            data=prepare(request.get('starts_min'),request.get('ends_min'),request.get('power_kw'),
                         request.get('reference_kw'),request.get('task'),request.get('noise_sigma_kw'))
            prepared[i]=data
            if len(data['y'])>=40:cases.extend(cases_for(data,base=i*10,include_cv=policy=='guarded'))
        except (ValueError,TypeError,OverflowError) as ex:
            output[i]=dict(status='unavailable',method=None,reason=str(ex),selection_evidence={},features=None,
                           eta_raw=None,physical_timing=None,uncertainty_status='unavailable')
    native,backend=fit_cases(cases,config) if cases else ({},dict(status='not_needed',reason='coarse_or_unavailable_inputs_only',cases=0))
    for i,data in prepared.items():output[i]=complete(data,native,base=i*10,policy=policy,backend=backend)
    return output
