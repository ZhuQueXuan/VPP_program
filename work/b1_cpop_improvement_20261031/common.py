"""Isolated CPOP candidate experiment; no writes into previous studies."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,csv,time,hashlib,subprocess,importlib.util
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PREVIOUS=ROOT/'work/b1_command_feature_selection_20261031'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process.api import prepare,_features
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config
def native(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:native(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [native(v) for v in value]
    return value
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def runtime(directory):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/directory);c['timeout_seconds']=180
    return c
def run_r(script,args,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False);tmp=out/'tmp';tmp.mkdir()
    env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),TMPDIR=str(tmp))
    cmd=[runtime('unused')['rscript_path'],'--vanilla',str(HERE/script)]+[str(x) for x in args]
    tic=time.perf_counter()
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',env=env,timeout=180,check=False)
    (out/'stdout.log').write_text(p.stdout,encoding='utf-8');(out/'stderr.log').write_text(p.stderr,encoding='utf-8')
    return p.returncode,{'seconds_wall':time.perf_counter()-tic,'command':cmd,'artifact_dir':str(out)}
def labs_batch(arrays,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False)
    source=PREVIOUS/'vendor/LABS/LABS_functions.R'
    check=json.loads((PREVIOUS/'vendor/LABS/download_receipt.json').read_text(encoding='utf-8'))
    assert sha(source)==check['downloads']['LABS_functions.R']['sha256']
    with (out/'input.csv').open('x',newline='',encoding='utf-8') as h:
        w=csv.writer(h);w.writerow(['case_id','index','y'])
        for i,y in enumerate(arrays):w.writerows((i,j+1,float(v)) for j,v in enumerate(y))
    code,meta=run_r('labs_batch.R',[source,out/'input.csv',out/'output.csv'],directory+'/run')
    if code:raise RuntimeError('LABS subprocess failed: '+directory)
    result={}
    with (out/'output.csv').open(encoding='utf-8-sig',newline='') as h:
        for r in csv.DictReader(h):
            i=int(r['case_id']);d=result.setdefault(i,{'status':r['status'],'prediction':[],'seconds':float(r['seconds']),'knots':int(r['knots']),'error':r['error']})
            if r['status']=='ok':d['prediction'].append(float(r['fitted']))
    assert set(result)==set(range(len(arrays)))
    return result,meta
def weighted_batch(cases,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False)
    with (out/'input.csv').open('x',newline='',encoding='utf-8') as h:
        w=csv.writer(h);w.writerow(['case_id','x','y','sigma'])
        for case in cases:
            mid=(np.asarray(case['starts'])+np.asarray(case['ends']))/2
            w.writerows((case['case_id'],float(x),float(y),float(s)) for x,y,s in zip(mid,case['y'],case['sigma_vector']))
    lib=runtime('unused')['r_library']
    code,meta=run_r('weighted_cpop_batch.R',[out/'input.csv',out/'segments.csv',lib],directory+'/run')
    if code:raise RuntimeError('Weighted CPOP subprocess failed: '+directory)
    groups={}
    with (out/'segments.csv').open(encoding='utf-8-sig',newline='') as h:
        for r in csv.DictReader(h):groups.setdefault(int(r['case_id']),[]).append(r)
    result={}
    for case in cases:
        rows=groups.get(case['case_id'],[])
        if not rows or any(r['status']!='ok' for r in rows):
            result[case['case_id']]={'status':'unavailable','reason':rows[0].get('error') if rows else 'native_case_missing'};continue
        segments=[r for r in rows if float(r['x1'])>float(r['x0'])]
        mid=(np.asarray(case['starts'])+np.asarray(case['ends']))/2;pred=np.full(len(mid),np.nan)
        for j,r in enumerate(segments):
            a,b=float(r['x0']),float(r['x1']);mask=(mid>=a-1e-9)&(mid<=b+1e-9)
            if j==0:mask|=mid<a
            if j==len(segments)-1:mask|=mid>b
            pred[mask]=float(r['gradient'])*mid[mask]+float(r['intercept'])
        if not np.isfinite(pred).all():
            result[case['case_id']]={'status':'unavailable','reason':'nonfinite_curve'};continue
        result[case['case_id']]={'status':'ok','prediction':pred,'seconds':float(rows[0]['seconds']),
                    'native_cost':float(rows[0]['native_cost']),'knots':len(rows)-1}
    return result,meta
def protected_snapshot():
    scopes=['B1算法','01_项目依据','task','resource_research_results/ev_charging',
       'work/b1_unknown_reference_pilot_20261031','data/B1_unknown_reference_pilot_v1_20261031',
       'work/b1_command_feature_selection_20261031','work/b1_cpop_route_20261031']
    paths=[ROOT/'AGENTS.md']
    for s in scopes:paths.extend(p for p in (ROOT/s).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
if __name__=='__main__':
    if sys.argv[1]=='before':
        x=protected_snapshot();write('protected_before.json',x);print('protected',len(x))
    else:
        a=read('protected_before.json');b=protected_snapshot()
        r={'changed':[p for p in a if p in b and a[p]!=b[p]],'missing':sorted(set(a)-set(b)),
           'added':sorted(set(b)-set(a)),'files':len(a)}
        r['scientific_unchanged']=not r['missing'] and not r['added'] and not any(p!='AGENTS.md' for p in r['changed'])
        write('protection_receipt.json',r);assert r['scientific_unchanged'];print(json.dumps(r))
