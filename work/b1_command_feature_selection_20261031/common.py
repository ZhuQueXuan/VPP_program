"""Isolated experiment utilities. Original libraries and scientific records are read-only."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,hashlib,time,csv,subprocess
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
sys.path.insert(0,str(ROOT/'work/b1_unknown_reference_pilot_20261031'))
from b1_algorithm.process.api import prepare,_features
from b1_algorithm.process._ride_fit import fit_original_ride
from b1_algorithm.process._ride_revised import fit_revised_ride
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config
from trend_filter import fit_curve

def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [native(x) for x in v]
    return v
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as stream:json.dump(native(value),stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def runtime(directory):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/directory);c['timeout_seconds']=180
    return c
def labs_batch(arrays,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False)
    source=HERE/'vendor/LABS/LABS_functions.R'
    receipt=read('vendor/LABS/download_receipt.json')
    assert sha(source)==receipt['downloads']['LABS_functions.R']['sha256']
    with (out/'input.csv').open('x',newline='',encoding='utf-8') as h:
        w=csv.writer(h);w.writerow(['case_id','index','y'])
        for i,y in enumerate(arrays):w.writerows((i,j+1,float(v)) for j,v in enumerate(y))
    tmp=out/'tmp';tmp.mkdir()
    env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),TMPDIR=str(tmp))
    cmd=[runtime('unused')['rscript_path'],'--vanilla',str(HERE/'labs_batch.R'),str(source),str(out/'input.csv'),str(out/'output.csv')]
    start=time.perf_counter()
    run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',env=env,timeout=180,check=False)
    wall=time.perf_counter()-start
    (out/'stdout.log').write_text(run.stdout,encoding='utf-8');(out/'stderr.log').write_text(run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError('LABS subprocess failed: '+run.stderr[-1200:])
    result={}
    with (out/'output.csv').open(encoding='utf-8-sig',newline='') as h:
        for r in csv.DictReader(h):
            i=int(r['case_id']);d=result.setdefault(i,{'status':r['status'],'prediction':[],'seconds':float(r['seconds']),'knots':int(r['knots']),'error':r['error']})
            if r['status']=='ok':d['prediction'].append(float(r['fitted']))
    assert set(result)==set(range(len(arrays)))
    return result,{'seconds_wall':wall,'source_sha256':sha(source),'command':cmd}

def protected_snapshot():
    scopes=['B1算法','resource_research_results/ev_charging','01_项目依据','task',
            'work/b1_unknown_reference_pilot_20261031','data/B1_unknown_reference_pilot_v1_20261031']
    paths=[ROOT/'AGENTS.md']
    for scope in scopes:paths.extend(p for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}

if __name__=='__main__':
    if sys.argv[1]=='before':
        d=protected_snapshot();write('protected_before.json',d);print(json.dumps({'protected_files':len(d)}))
    else:
        old=read('protected_before.json');new=protected_snapshot()
        d={'changed':[p for p in old if p in new and old[p]!=new[p]],'missing':sorted(set(old)-set(new)),
           'added':sorted(set(new)-set(old)),'files':len(old)}
        d['scientific_unchanged']=not (d['missing'] or d['added'] or any(p!='AGENTS.md' for p in d['changed']))
        write('protection_receipt.json',d);assert d['scientific_unchanged'];print(json.dumps(d))
