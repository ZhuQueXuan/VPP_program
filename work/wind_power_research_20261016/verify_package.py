"""Replay the actual final stdlib module; save a bounded release receipt."""
from common import *
import argparse,importlib.util,math,subprocess,sys
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
dest=ROOT/'resource_research_results/wind_power'
spec=importlib.util.spec_from_file_location('released_wind',dest/'code/wind_curve.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
param=load(dest/'parameters/kelmarsh_mixed_curve_v1.json')
assert sha(dest/'parameters/kelmarsh_mixed_curve_v1.json')==sha(BASE/'runs/BL_CURVE_01/parameters.json')
assert sha(dest/'code/wind_curve.py')==sha(BASE/'curve_kernel.py')
assert load(BASE/'runs/VERIFY_CURVE_01/receipt.json')['status']=='passed'
maxerr=0.;n=0
for r in read(BASE/'runs/BL_CURVE_01/predictions.csv'):
    y=mod.evaluate(param,int(r['unit']),float(r['wind_mps']))
    delta=abs(y['power_kW']-float(r['M_CURVE']));assert delta<=1e-9
    for k in ['outside_training_wind','outside_knot_centres','rare_or_unseen_bin']:assert y[k]==(r[k]=='True')
    assert y['training_bin_count']==int(r['training_bin_count']);n+=1;maxerr=max(maxerr,delta)
invalid=[(0,8),(7,8),(True,8),(1,-1),(1,float('nan')),(1,float('inf')),(1,True),(1,None),(1,'bad')]
for unit,v in invalid:
    try:mod.evaluate(param,unit,v)
    except (ValueError,TypeError,OverflowError):pass
    else:raise AssertionError((unit,v))
boundary=0
for unit in range(1,7):
    p=param['units'][str(unit)];xs=p['knot_wind_mps'];ys=p['knot_power_kW']
    for x,y in zip(xs,ys):assert mod.evaluate(param,unit,x)['power_kW']==y;boundary+=1
    low=mod.evaluate(param,unit,0);high=mod.evaluate(param,unit,p['training_wind_max_mps']+1)
    assert low['power_kW']==ys[0] and low['outside_training_wind']
    assert high['power_kW']==ys[-1] and high['outside_training_wind'];boundary+=2
    middle=(xs[0]+xs[1])/2
    assert abs(mod.evaluate(param,unit,middle)['power_kW']-(ys[0]+ys[1])/2)<1e-10;boundary+=1
example=[]
for args in [[],['--unit','1','--wind-mps','8']]:
    r=subprocess.run([sys.executable,'-X','utf8','-B',str(dest/'run_example.py'),*args],cwd=BASE,capture_output=True,text=True,encoding='utf-8',check=True)
    records=[json.loads(s) for s in r.stdout.splitlines()[1:]];assert len(records)==(6 if not args else 1)
    for row in records:assert row['power_kW']==mod.evaluate(param,row['unit'],row['wind_mps'])['power_kW']
    example.append({'arguments':args,'rows':len(records),'exit_code':r.returncode})
original=[]
for name,receipt,field in [('lithium_ion_storage','release_validation.json','artifact_sha256'),('distributed_photovoltaic','release_validation_v1_2.json','verified_files'),('ev_charging','release_validation_v1_1.json','verified_files'),('air_conditioning','release_validation_v1_1.json','verified_files')]:
    d=ROOT/'resource_research_results'/name;rr=load(d/'results'/receipt);files=rr[field]
    for f,h in files.items():assert sha(d/f)==h,(name,f)
    original.append({'resource':name,'files':len(files),'status':'unchanged'})
value={'date':'2026-10-16','decision':'D065','version':'1.0.0','status':'passed',
 'scope':'First bounded SAME-ROW mixed-operation statistical curve only. Wind resource basic package not yet accepted.',
 'resource_basic_package_complete':False,'test_rows_replayed':n,'maximum_replay_difference_kW':maxerr,
 'invalid_cases_rejected':len(invalid),'constructed_boundary_checks':boundary,'examples_outside_package_cwd':example,
 'cmd_launcher_interactively_double_clicked':False,'python_entry_points_actually_executed':True,
 'independent_source_and_algebra_receipt_sha256':sha(BASE/'runs/VERIFY_CURVE_01/receipt.json'),
 'verifier_sha256':sha(Path(__file__)),'prior_four_packages':original,
 'verified_files':{str(f.relative_to(dest)).replace('\\','/'):sha(f) for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='release_validation.json'}}
dump(out/'receipt.json',value);dump(dest/'results/release_validation.json',value)
print(json.dumps({k:v for k,v in value.items() if k!='verified_files'},indent=2))
