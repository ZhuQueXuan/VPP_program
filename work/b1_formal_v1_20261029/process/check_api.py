from pathlib import Path
import importlib.util,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[2];PACKAGE=PROJECT/'b1_algorithm/process'
spec=importlib.util.spec_from_file_location('b1_formal_process_checks',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
call=module.identify_process
task=dict(task_id='t',user_id='u',meter_id='m',start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.)
s=np.arange(-15.,45.);e=s+1;b=np.full(60,3.);r=np.zeros(60);r[15:20]=.5;r[25:30]=.5;p=b-r
cfg=dict(rscript_path=str(ROOT/'nonexistent_R.exe'),artifact_dir=str(ROOT/'checks_runtime'))
checks=[]
def verify(name,condition):assert condition,name;checks.append(name)
result=call(s,e,p,b,task,.05,cfg)
verify('missing R explicitly degrades raw_F0',result['status']=='degraded' and result['method']=='raw_F0')
verify('distinct cumulative and continuous durations',result['features']['raw_observed']['cumulative_response_seconds']==600 and result['features']['raw_observed']['longest_continuous_response_seconds']==300)
verify('raw integral preserved',abs(result['eta_raw']-(5/45))<1e-12)
verify('physical timing unknown',result['physical_timing'] is None)
verify('missing sigma unavailable',call(s,e,p,b,task,None,cfg)['status']=='unavailable')
bad=p.copy();bad[5]=np.nan
verify('missing meter data unavailable',call(s,e,bad,b,task,.05,cfg)['status']=='unavailable')
verify('wrong task domain unavailable',call(s,e,p,b,dict(task,request_kw=3.),.05,cfg)['status']=='unavailable')
verify('wrong identity unavailable',call(s,e,p,b,dict(task,user_id=''),.05,cfg)['status']=='unavailable')
mixed=p.tolist();mixed[0]=True
verify('mixed bool float array rejected before coercion',call(s,e,mixed,b,task,.05,cfg)['status']=='unavailable')
verify('invalid runtime type unavailable not method fallback',call(s,e,p,b,task,.05,dict(cfg,timeout_seconds='bad'))['status']=='unavailable')
negative=p.copy();negative[15]=-.01;v=call(s,e,negative,b,task,.05,cfg)
verify('negative noisy reading accepted and counted',v['status']=='degraded' and v['selection_evidence']['negative_meter_values']==1)
verify('negative noisy reading not clipped',abs(v['eta_raw']-np.sum((b-negative)[15:45])/45)<1e-12)
coarse=np.arange(-15.,45.,15.);v=call(coarse,coarse+15,np.full(4,3.),np.full(4,3.),task,.05,cfg)
verify('coarse gate does not require R or force template',v['status']=='ok' and v['method']=='raw_coarse')
json.dumps(result,allow_nan=False);verify('JSON native finite result',True)
config=dict(rscript_path=str(PROJECT/'work/b1_mainline_20261029/runtime/R-4.6.1/app/bin/Rscript.exe'),r_library=str(PROJECT/'work/b1_mainline_20261029/runtime/r_library'),artifact_dir=str(ROOT/'checks_runtime'),timeout_seconds=90)
real=call(s,e,p,b,task,.05,config)
verify('actual original R CPOP invoked',real['status']=='ok' and real['method']=='CPOP' and real['backend']['status']=='ok')
timed=call(s,e,p,b,task,.05,dict(config,timeout_seconds=1e-9))
verify('timeout explicitly degrades',timed['status']=='degraded' and timed['method']=='raw_F0')
out=dict(passed=True,n_checks=len(checks),checks=checks,real_backend=real['backend'])
(ROOT/'checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
