"""Original CRAN CPOP subprocess adapter; artifacts retained, no shell or deletion."""
from pathlib import Path
import csv,os,shutil,subprocess,tempfile
import numpy as np
from numbers import Real

def validate_config(config):
    if config is None:return {}
    if not isinstance(config,dict):raise ValueError('invalid_runtime_config:dict_required')
    extra=set(config)-{'rscript_path','r_library','artifact_dir','timeout_seconds'}
    if extra:raise ValueError('invalid_runtime_config:unknown_keys')
    for key in ('rscript_path','r_library','artifact_dir'):
        value=config.get(key)
        if value is not None and (not isinstance(value,(str,os.PathLike)) or isinstance(value,bool)):
            raise ValueError('invalid_runtime_config:path_type:'+key)
    if 'timeout_seconds' in config:
        timeout=config['timeout_seconds']
        if not isinstance(timeout,Real) or isinstance(timeout,(bool,np.bool_)) or not np.isfinite(timeout) or timeout<=0:
            raise ValueError('invalid_runtime_config:positive_timeout_required')
    return dict(config)

def fit_cases(cases,config=None):
    config=validate_config(config)
    exe=config.get('rscript_path') or os.environ.get('B1_RSCRIPT') or shutil.which('Rscript.exe') or shutil.which('Rscript')
    if not exe or not Path(exe).is_file():return {},dict(status='unavailable',reason='rscript_missing')
    root=Path(config.get('artifact_dir') or os.environ.get('B1_RUNTIME_DIR') or Path(__file__).resolve().parents[3]/'work'/'b1_runtime')
    root.mkdir(parents=True,exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix='process_',dir=root))
    input_path=directory/'input.csv';output_path=directory/'segments.csv'
    with input_path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['case_id','x','y','sigma','train'])
        for case in cases:
            x=(case['starts']+case['ends'])/2
            for xi,yi,train in zip(x,case['y'],case['train']):writer.writerow([case['case_id'],xi,yi,case['sigma'],int(train)])
    temp=directory/'tmp';temp.mkdir()
    env=os.environ.copy();env.update(TMPDIR=str(temp),TEMP=str(temp),TMP=str(temp),LANG='C',LC_ALL='C')
    command=[str(exe),'--vanilla',str(Path(__file__).with_name('cpop_batch.R')),str(input_path),str(output_path),
             str(config.get('r_library') or os.environ.get('B1_R_LIBRARY') or '')]
    try:
        run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
                           errors='replace',env=env,timeout=float(config.get('timeout_seconds',90)),check=False)
        (directory/'stdout.log').write_text(run.stdout,encoding='utf-8');(directory/'stderr.log').write_text(run.stderr,encoding='utf-8')
    except (OSError,subprocess.TimeoutExpired) as ex:
        (directory/'failure.txt').write_text(type(ex).__name__+':'+str(ex),encoding='utf-8')
        return {},dict(status='unavailable',reason='r_timeout_or_launch_failure',artifact_dir=str(directory))
    if run.returncode or not output_path.exists():return {},dict(status='unavailable',reason='r_backend_failed',artifact_dir=str(directory))
    groups={}
    with output_path.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):groups.setdefault(int(row['case_id']),[]).append(row)
    output={}
    for case in cases:
        rows=groups.get(case['case_id'],[])
        if not rows or any(row['status']!='ok' for row in rows):
            output[case['case_id']]=dict(status='unavailable',reason='native_case_failed');continue
        nonempty=[]
        for row in rows:
            if float(row['x1'])>float(row['x0']):nonempty.append(row)
        mid=(case['starts']+case['ends'])/2
        pred=np.full(len(mid),np.nan)
        for j,row in enumerate(nonempty):
            a,b=float(row['x0']),float(row['x1'])
            mask=(mid>=a-1e-9)&(mid<=b+1e-9)
            if j==0:mask|=mid<a
            if j==len(nonempty)-1:mask|=mid>b
            pred[mask]=float(row['gradient'])*mid[mask]+float(row['intercept'])
        if not np.isfinite(pred).all():output[case['case_id']]=dict(status='unavailable',reason='native_prediction_nonfinite');continue
        output[case['case_id']]=dict(status='ok',prediction=pred,native_cost=float(rows[0]['native_cost']),
            native_knots=len(rows)-1,empty_segments=len(rows)-len(nonempty),seconds=float(rows[0]['seconds']))
    return output,dict(status='ok',reason='original_cpop_completed',artifact_dir=str(directory),cases=len(cases))
