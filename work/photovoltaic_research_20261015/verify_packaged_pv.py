"""Replay the retained final kernel against all frozen finite predictions."""
from pathlib import Path
import csv,hashlib,json,math,subprocess,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PACKAGE=ROOT/'resource_research_results/distributed_photovoltaic'
sys.path.insert(0,str(PACKAGE/'code'))
from dc_power import ModuleParameters,reconstruct_module_dc
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    data=json.loads((PACKAGE/'parameters/iea_supsi_mono_si.json').read_text(encoding='utf-8'))
    params=ModuleParameters(**data['model_parameters']);run=BASE/'runs/BL_IEA_COMPONENT_DC_01'
    dest=run/'package_verification.json';assert not dest.exists()
    maximum={'B_G':0.0,'M_T0':0.0,'M_T3':0.0};n=0
    with (run/'predictions_all_finite.csv').open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            g=float(r['Gpoa']);t=float(r['Tbom'])
            a=reconstruct_module_dc(g,t,params);b=reconstruct_module_dc(g,t,params,3.0)
            values={'B_G':a['irradiance_only_W'],'M_T0':a['temperature_corrected_W'],'M_T3':b['temperature_corrected_W']}
            for key,v in values.items():maximum[key]=max(maximum[key],abs(v-float(r[key])))
            assert a['outside_lab_GT_matrix_range']==(r['outside_lab_GT_range']=='True')
            n+=1
    assert n==34763 and max(maximum.values())<1e-9
    invalid_cases=[(-1,25,0),(float('nan'),25,0),(1000,float('inf'),0),(1000,300,0),(1000,25,-1)]
    for g,t,d in invalid_cases:
        try:reconstruct_module_dc(g,t,params,d)
        except ValueError:pass
        else:raise AssertionError('Invalid input did not fail')
    example=subprocess.run([sys.executable,'-X','utf8','-B',str(PACKAGE/'run_example.py')],cwd=ROOT/'work',capture_output=True,text=True,encoding='utf-8',check=True)
    assert len(example.stdout.splitlines())==4
    files=[f for f in PACKAGE.rglob('*') if f.is_file()]
    forbidden=[f for f in files if f.suffix in ('.pdf','.xlsx','.parquet') or 'downloads' in f.parts or '__pycache__' in f.parts]
    assert not forbidden
    result={'status':'passed','rows_replayed':n,'max_difference_W':maximum,'invalid_inputs_rejected':len(invalid_cases),
            'example_run_from_other_cwd':True,'example_stdout':example.stdout,'python':sys.version.split()[0],
            'protocol_sha256':sha(BASE/'iea_component_protocol_v1.json'),'package_files':{f.relative_to(PACKAGE).as_posix():sha(f) for f in files},
            'scientific_scope':'Packaging parity only, not another independent accuracy validation.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    release={k:v for k,v in result.items() if k not in ('example_stdout','package_files')}
    release['verified_files']=result['package_files']
    (PACKAGE/'results/release_validation.json').write_text(json.dumps(release,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in release.items() if k!='verified_files'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
