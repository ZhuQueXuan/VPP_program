from pathlib import Path
import importlib,importlib.util,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[2];PACKAGE=PROJECT/'b1_algorithm/process'
spec=importlib.util.spec_from_file_location('b1_formal_batch_checks',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
batch=importlib.import_module(spec.name+'.batch').identify_process_batch
task=dict(task_id='t',user_id='u',meter_id='m',start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.)
def request(dt):
 s=np.arange(-15,45,dt);b=np.full(len(s),3.);r=np.where((s>=3)&(s<30),1.,0.)
 return dict(starts_min=s,ends_min=s+dt,power_kw=b-r,reference_kw=b,task=task,noise_sigma_kw=.05)
config=dict(rscript_path=str(PROJECT/'work/b1_mainline_20261029/runtime/R-4.6.1/app/bin/Rscript.exe'),r_library=str(PROJECT/'work/b1_mainline_20261029/runtime/r_library'),artifact_dir=str(ROOT/'checks_batch_runtime'),timeout_seconds=90)
requests=[request(15),dict(request(1),task=dict(task,user_id='')),request(1)]
out=batch(requests,config)
assert [v['status'] for v in out]==['ok','unavailable','ok']
assert out[0]['method']=='raw_coarse' and out[2]['backend']['cases']==6
assert out[2]['physical_timing'] is None
json.dumps(out,allow_nan=False)
bad=batch(requests,dict(config,timeout_seconds=True))
assert all(v['status']=='unavailable' and v['reason'].startswith('invalid_runtime_config') for v in bad)
receipt=dict(passed=True,ordered_statuses=[v['status'] for v in out],single_R_batch_cases=out[2]['backend']['cases'],
             formal_method=out[2]['method'],invalid_config_rejected=True,json_native=True)
(ROOT/'batch_checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))
