"""Full final-code replay, rejected invalid inputs and directory-independent example."""
from common import *
import importlib.util,math,copy,subprocess,sys
pkg=ROOT/'resource_research_results/air_conditioning';rp=pkg/'results/release_validation_v1_0.json';assert not rp.exists()
spec=importlib.util.spec_from_file_location('released_room_temperature',pkg/'code/room_temperature.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
run=BASE/'runs/BL_DUAL_ZONE_01';v=load(run/'verification.json');assert v['status']=='passed' and v['predeclared_relative_success']
parameters=m.load_parameters();assert parameters==load(run/'calibration.json')['parameters']
maxdiff=0.;checked=0
for r in read(run/'predictions.csv'):
    inputs={k:float(r[k]) for k in m.FEATURES};actual=m.predict_temperature(inputs,int(r['zone']))
    for k,source in [('persistence_C','B_P'),('trend_C','B_TREND'),('predicted_next_label_C','M_HEAT5')]:
        delta=abs(actual[k]-float(r[source]));maxdiff=max(maxdiff,delta);assert delta<2e-9;checked+=1
    assert actual['outside_training_input_range']==(r['outside_training_input_range']=='True');checked+=1
    assert not actual['online_lead_time_verified'] and not actual['dispatch_capacity_verified']
e=load(pkg/'examples/constructed_inputs.json')['examples'][0];base=e['inputs'];invalid=[]
for title,values,room,params in [
 ('missing field',{k:v for k,v in base.items() if k!='T_other_C'},1,None),
 ('boolean power',{**base,'P_now_W':True},1,None),
 ('nan',{**base,'T_now_C':float('nan')},1,None),
 ('infinity',{**base,'P_now_W':float('inf')},1,None),
 ('text',{**base,'Tout_C':'29'},1,None),
 ('unvalidated room',base,3,None),
 ('truncated coefficients',base,1,{'rooms':{'1':{'coefficients':[1,2]}}})]:
    try:m.predict_temperature(values,room,params)
    except ValueError:invalid.append(title)
    else:raise AssertionError(title+' must be rejected')
assert len(invalid)==7
outside=m.predict_temperature({**base,'Tout_C':100.},1);assert outside['outside_training_input_range']
example=subprocess.run([sys.executable,'-X','utf8','-B',str(pkg/'run_example.py')],cwd=ROOT/'work',capture_output=True,text=True,encoding='utf-8',check=True)
assert '构造输入示例' in example.stdout and 'predicted_next_label_C' in example.stdout
out=BASE/'runs/PACKAGED_DUAL_ZONE_01';out.mkdir(exist_ok=False);(out/'example_stdout.txt').write_text(example.stdout,encoding='utf-8')
result={'status':'passed','decision':'D062','version':'1.0.0','full_test_rows_replayed':2288,'numeric_and_flag_checks':checked,'max_prediction_difference_C':maxdiff,'invalid_input_cases_rejected':invalid,'out_of_training_range_flag_checked':True,'directory_independent_constructed_example_executed':True,'desktop_double_click_UI_tested':False,'runtime_needs_only_Python_standard_library':True,'no_raw_or_process_files_copied':True,'resource_basic_package_acceptance':'not_yet_declared','online_or_capacity_or_P1_103_acceptance':False,'scientific_protocol_sha256':sha(BASE/'dual_zone_protocol_v1.json'),'independent_verification_sha256':sha(run/'verification.json'),'verified_files':{str(p.relative_to(pkg)).replace('\\','/'):sha(p) for p in sorted(pkg.rglob('*')) if p.is_file()},'verifier_sha256':sha(Path(__file__))}
dump(rp,result);dump(out/'receipt.json',{'status':'passed','final_release_receipt_sha256':sha(rp),'example_stdout_sha256':sha(out/'example_stdout.txt')})
print(json.dumps({k:v for k,v in result.items() if k!='verified_files'},ensure_ascii=False,indent=2))
