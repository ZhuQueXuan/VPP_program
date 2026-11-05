"""Isolated fine-evidence candidate; unchanged native baselines and raw accounting."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,csv,time,hashlib,subprocess,importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'work/b1_command_feature_selection_20261031'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config

def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def config(directory):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/directory);c['timeout_seconds']=180;return c
def cp_batch(cases,directory):
    chunks=[cases[i:i+24] for i in range(0,len(cases),24)];out={};meta=[]
    def run(j,chunk):return fit_cases(chunk,config(f'{directory}/chunk{j:03d}'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(run,j,c) for j,c in enumerate(chunks)]
        for f in as_completed(fs):
            a,b=f.result();assert b['status']=='ok',b;out.update(a);meta.append(b)
            if len(meta)%4==0:print(directory,len(meta),'/',len(chunks),flush=True)
    assert set(out)=={c['case_id'] for c in cases}
    return out,meta
def labs_batch(arrays,directory):
    source=OLD/'vendor/LABS/LABS_functions.R';expected=json.loads((OLD/'vendor/LABS/download_receipt.json').read_text(encoding='utf-8'))
    assert sha(source)==expected['downloads']['LABS_functions.R']['sha256']
    chunks=[list(enumerate(arrays))[i:i+24] for i in range(0,len(arrays),24)];out={};metas=[]
    def run(j,rows):
        p=HERE/directory/f'chunk{j:03d}';p.mkdir(parents=True,exist_ok=False);tmp=p/'tmp';tmp.mkdir()
        with (p/'input.csv').open('x',encoding='utf-8',newline='') as h:
            w=csv.writer(h);w.writerow(['case_id','index','y'])
            for i,y in rows:w.writerows((i,k+1,float(v)) for k,v in enumerate(y))
        c=config('unused');cmd=[c['rscript_path'],'--vanilla',str(OLD/'labs_batch.R'),str(source),str(p/'input.csv'),str(p/'output.csv')]
        env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),TMPDIR=str(tmp));tic=time.perf_counter()
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',env=env,timeout=180)
        (p/'stdout.log').write_text(r.stdout,encoding='utf-8');(p/'stderr.log').write_text(r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr[-500:]
        result={}
        with (p/'output.csv').open(encoding='utf-8-sig',newline='') as h:
            for r in csv.DictReader(h):
                i=int(r['case_id']);d=result.setdefault(i,dict(status=r['status'],prediction=[],seconds=float(r['seconds']),error=r['error']))
                if r['status']=='ok':d['prediction'].append(float(r['fitted']))
        return result,dict(directory=str(p),wall_seconds=time.perf_counter()-tic)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(run,j,rows) for j,rows in enumerate(chunks)]
        for f in as_completed(fs):
            a,b=f.result();out.update(a);metas.append(b)
            if len(metas)%4==0:print(directory,len(metas),'/',len(chunks),flush=True)
    assert set(out)==set(range(len(arrays)))
    return out,metas

def snapshot():
    scopes=['B1算法','01_项目依据','task','work/b1_command_feature_selection_20261031',
        'work/b1_cpop_improvement_20261031','work/b1_cpop_jump_v2_20261031',
        'work/b1_cpop_jump_diagnosis_20261031']
    paths=[p for scope in scopes for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
