from common import *
import importlib.util,subprocess,sys,math
dest=ROOT/'resource_research_results/electric_water_heating';out=BASE/'runs/PACKAGE_TEMPERATURE_01';out.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('water_released',dest/'code/water_temperature.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
param=load(dest/'parameters/horizontal_150L_temperature_v1.json');assert sha(dest/'parameters/horizontal_150L_temperature_v1.json')==sha(BASE/'runs/BL_TEMPERATURE_01/parameters.json')
assert sha(dest/'code/water_temperature.py')==sha(BASE/'temperature_kernel.py')
def inputs(r):return {'temperature_C':float(r['temperature_C']),'previous_temperature_C':float(r['previous_temperature_C']),'heating_flag':float(r['heating_flag']),
 'chamber_temperature_1_C':float(r['ambient_C']),'chamber_temperature_2_C':float(r['ambient_C']),'upper_sensor_C':float(r['top_C']),'lower_sensor_C':float(r['bottom_C'])}
maximum=0.;rows=read(BASE/'runs/BL_TEMPERATURE_01/predictions.csv')
for r in rows:
    result=mod.predict(param,**inputs(r));d=abs(result['temperature_C']-float(r['M_LAYER6']));assert d<1e-8;maximum=max(maximum,d)
    assert result['outside_training_feature_range']==(r['outside_training_range']=='True')
example=load(dest/'examples/constructed_inputs.json')['cases'][0]
invalid=[{'temperature_C':-127},{'temperature_C':101},{'temperature_C':float('nan')},{'upper_sensor_C':float('inf')},{'temperature_C':True},{'lower_sensor_C':None},{'heating_flag':2}]
for bad in invalid:
    try:mod.predict(param,**{**example,**bad})
    except (ValueError,TypeError):pass
    else:raise AssertionError(bad)
try:mod.predict(param,temperature_C=30)
except TypeError:pass
else:raise AssertionError('incomplete inputs accepted')
checks=0
for v in [0.,100.]:
    c={k:v for k in ['temperature_C','previous_temperature_C','chamber_temperature_1_C','chamber_temperature_2_C','upper_sensor_C','lower_sensor_C']};c['heating_flag']=0
    result=mod.predict(param,**c);assert math.isfinite(result['temperature_C']);checks+=1
process=subprocess.run([sys.executable,'-X','utf8','-B',str(dest/'run_example.py')],cwd=BASE,capture_output=True,text=True,encoding='utf-8',check=True)
example_rows=[json.loads(s) for s in process.stdout.splitlines()];assert len(example_rows)==2
for r in example_rows:assert r['result']==mod.predict(param,**r['inputs'])
prior=[]
for name,receipt,key in [('lithium_ion_storage','release_validation.json','artifact_sha256'),('distributed_photovoltaic','release_validation_v1_2.json','verified_files'),('ev_charging','release_validation_v1_1.json','verified_files'),('air_conditioning','release_validation_v1_1.json','verified_files'),('wind_power','release_validation_v1_1.json','verified_files')]:
    folder=ROOT/'resource_research_results'/name;rr=load(folder/'results'/receipt)
    for n,h in rr[key].items():assert sha(folder/n)==h,(name,n)
    prior.append({'resource':name,'files':len(rr[key]),'status':'unchanged'})
receipt={'date':'2026-10-16','decision':'D067','version':'1.0.0','status':'passed','bounded_basic_package_complete':True,'six_checks_passed':6,
 'scope':'Only original150Lhorizontalresistivewaterheater temperature observations andconditional5published-minute localthermostat estimator. Not boiler/energycapacity/control.',
 'all_test_runtime_rows_replayed':len(rows),'maximum_runtime_replay_difference_C':maximum,'invalid_or_incomplete_cases_rejected':8,'constructed_boundary_cases':checks,
 'outside_package_cwd_constructed_example_rows':len(example_rows),'Python_example_actually_executed':True,'cmd_launcher_interactively_double_clicked':False,
 'source_sample_model_verifier_sha256':sha(BASE/'runs/VERIFY_TEMPERATURE_01/receipt.json'),'description_verifier_sha256':sha(BASE/'runs/VERIFY_CHAR_TEMPERATURE_01/receipt.json'),
 'all5previous_packages':prior,'six_bounded_packages_complete':True,'industrial_boiler_verified':False,'cross_resource_integration_started':False,'wholeP1_or103_passed':False,
 'verifier_sha256':sha(Path(__file__)),'verified_files':{str(f.relative_to(dest)).replace('\\','/'):sha(f) for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='release_validation.json'}}
dump(out/'receipt.json',receipt);dump(dest/'results/release_validation.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='verified_files'},indent=2))
