"""Versioned jump/ramp experiment helpers; previous records are read-only."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,csv,time,hashlib,subprocess,importlib.util
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PREVIOUS=ROOT/'work/b1_command_feature_selection_20261031'
V1=ROOT/'work/b1_cpop_improvement_20261031'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.process.api import prepare,_features
from b1_algorithm.api import _default_runtime_config
def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [native(x) for x in v]
    return v
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def runtime(directory):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/directory);c['timeout_seconds']=180
    return c
def load_module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def call_r(script,args,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False);tmp=out/'tmp';tmp.mkdir()
    env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),TMPDIR=str(tmp))
    command=[runtime('unused')['rscript_path'],'--vanilla',str(HERE/script)]+list(map(str,args))
    start=time.perf_counter();p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
         encoding='utf-8',errors='replace',env=env,timeout=180,check=False)
    (out/'stdout.log').write_text(p.stdout,encoding='utf-8');(out/'stderr.log').write_text(p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'R process failed {directory}: '+p.stderr[-600:])
    return {'command':command,'wall_seconds':time.perf_counter()-start,'directory':str(out)}
def labs_batch(arrays,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False);source=PREVIOUS/'vendor/LABS/LABS_functions.R'
    receipt=json.loads((PREVIOUS/'vendor/LABS/download_receipt.json').read_text(encoding='utf-8'))
    assert sha(source)==receipt['downloads']['LABS_functions.R']['sha256']
    with (out/'input.csv').open('x',encoding='utf-8',newline='') as h:
        w=csv.writer(h);w.writerow(['case_id','index','y'])
        for i,y in enumerate(arrays):w.writerows((i,j+1,float(v)) for j,v in enumerate(y))
    meta=call_r('labs_batch.R',[source,out/'input.csv',out/'output.csv'],directory+'/run')
    result={}
    with (out/'output.csv').open(encoding='utf-8-sig',newline='') as h:
        for r in csv.DictReader(h):
            i=int(r['case_id']);d=result.setdefault(i,{'status':r['status'],'prediction':[],
                   'seconds':float(r['seconds']),'knots':int(r['knots']),'error':r['error']})
            if r['status']=='ok':d['prediction'].append(float(r['fitted']))
    assert set(result)==set(range(len(arrays)))
    return result,meta
def protected_snapshot():
    scopes=['B1算法','01_项目依据','task','resource_research_results/ev_charging',
       'work/b1_unknown_reference_pilot_20261031','data/B1_unknown_reference_pilot_v1_20261031',
       'work/b1_command_feature_selection_20261031','work/b1_cpop_route_20261031',
       'work/b1_cpop_improvement_20261031','work/b1_cpop_diagnosis_20261031']
    paths=[ROOT/'AGENTS.md']
    for scope in scopes:paths.extend(p for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
if __name__=='__main__':
    if sys.argv[1]=='before':
        d=protected_snapshot();write('protected_before.json',d);print('protected',len(d))
    else:
        a=read('protected_before.json');b=protected_snapshot()
        d={'changed':[p for p in a if p in b and a[p]!=b[p]],'missing':sorted(set(a)-set(b)),
           'added':sorted(set(b)-set(a)),'files':len(a)}
        d['scientific_unchanged']=not d['missing'] and not d['added'] and not any(p!='AGENTS.md' for p in d['changed'])
        write('protection_receipt.json',d);assert d['scientific_unchanged'];print(json.dumps(d))
