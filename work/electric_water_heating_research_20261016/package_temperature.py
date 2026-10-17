from common import *
import shutil
run=BASE/'runs/BL_TEMPERATURE_01';verify=load(BASE/'runs/VERIFY_TEMPERATURE_01/receipt.json');charverify=load(BASE/'runs/VERIFY_CHAR_TEMPERATURE_01/receipt.json')
assert verify['status']==charverify['status']=='passed' and load(run/'diagnostics.json')['gate_passed']
dest=ROOT/'resource_research_results/electric_water_heating';dest.mkdir(exist_ok=False)
for n in ['code','parameters','examples','results']:(dest/n).mkdir()
shutil.copy2(BASE/'temperature_kernel.py',dest/'code/water_temperature.py')
shutil.copy2(run/'parameters.json',dest/'parameters/horizontal_150L_temperature_v1.json')
for name in ['metrics.json','diagnostics.json']:shutil.copy2(run/name,dest/'results'/name)
for name in ['observed_characteristics.json','test_temperature_curves.png','test_temperature_curves.svg']:shutil.copy2(BASE/'runs/CHAR_TEMPERATURE_01'/name,dest/'results'/name)
for name in ['temperature_protocol_v1.json','temperature_characteristic_protocol_v1.json']:shutil.copy2(BASE/name,dest/'results'/name)
examples={'purpose':'Constructed input examples, not new measured evaluation or industrial boiler data. History is five published minute labels earlier, current inputs available at minute closure.',
 'cases':[{'temperature_C':30.,'previous_temperature_C':29.8,'heating_flag':1,'chamber_temperature_1_C':20.,'chamber_temperature_2_C':20.5,'upper_sensor_C':32.,'lower_sensor_C':28.},
 {'temperature_C':60.,'previous_temperature_C':60.2,'heating_flag':0,'chamber_temperature_1_C':30.,'chamber_temperature_2_C':30.,'upper_sensor_C':63.,'lower_sensor_C':54.}]}
dump(dest/'examples/constructed_inputs.json',examples)
protocol=load(BASE/'temperature_protocol_v1.json');metadata=load(BASE/'downloads/SOURCE_01/dataset.json')
dump(dest/'source_manifest.json',{'dataset':{'title':metadata['name'],'doi':'10.17632/ddmv4w434g.1','url':'https://data.mendeley.com/datasets/ddmv4w434g/1',
 'authors':['P.D. van Schalkwyk','J.A.A. Engelbrecht','M.J. Booysen'],'version':1,'license':'CC-BY-4.0','license_url':'https://creativecommons.org/licenses/by/4.0/',
 'changes':'Derived minute-anchor features,6statisticalcoefficients,aggregate comparisons and plots. Original raw data not redistributed here. No endorsement implied.',
 'source_metadata_sha256':sha(BASE/'downloads/SOURCE_01/dataset.json'),'files':protocol['files']},
 'papers':[{'doi':'10.1016/j.dib.2024.110082','fulltext_url':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10838709/fullTextXML','local_xml_sha256':sha(BASE/'downloads/DICTIONARY_01/data_paper.xml'),'role':'Original apparatus/measurement/sensor/energy-unit context. Full XML actually read,not original state-space reproduction.'},
 {'url':'https://arxiv.org/html/2312.04102v1','role':'One-node thermal balance,node coupling andOLS method family,original primaryHTMLread viaweb;differentverticaltwoelementRheem apparatus. Our6coefficient label estimator is not exactMPCorpaper-reported savings reproduction.'},
 {'doi':'10.1016/j.applthermaleng.2024.122851','role':'Crossref/primaryabstract verified only; complete methods not obtained,not claimed reproduced.'}],
 'dictionary_sha256':sha(BASE/'downloads/DICTIONARY_01/Dataset descriptions.xlsx'),
 'sensor_diagram_sha256':sha(BASE/'downloads/DICTIONARY_01/Sensor referencesV2.png'),
 'protocol_sha256':sha(BASE/'temperature_protocol_v1.json')})
review={'decision':'D067','version':'1.0.0','status':'bounded_pass','date':'2026-10-16',
 'scope':'Original150Lhorizontalresistive water tank,source-minute temperature/stratification observations andconditional5published-minute localthermostat temperature label estimator. No industrialboiler/capacity/control claim.',
 'criteria':[
 {'id':1,'passed':True,'evidence':'One150L/3kWKwikotSuperline. Sevenoriginalexperimentfiles, measuredlocalNTCtemperature target andcurrent/pastpublishedinputs defined. Minuteclosureavailability andlabelhorizon explicitly conditional.'},
 {'id':2,'passed':True,'evidence':'Original localthermostat/sensor map,all3testfilecurves and7fileprofile summaries,thermalbalance/nodecoupling/OLS basis,6statisticalcoefficients andtrainingranges,sourceclock/energy limitations disclosed.'},
 {'id':3,'passed':True,'evidence':'OfficialpublisherSHA256+size match all downloaded listedfiles;130438sourceJSONrows/16751minuteanchors checked. Native localtemperature valid reference for this limitedoutput.0energycolumns not used for physicalpower/efficiency truth.'},
 {'id':4,'passed':True,'evidence':'Frozen M_LAYER6 MAE+RMSE belowBOTHpersistence/trend pooled,all3heldoutfiles andcurrentheatingflag1. No changes aftertest.'},
 {'id':5,'passed':True,'evidence':'All3files,all7331testpoints,quietflag0MAEandRMSEdeterioration,316featureoutsidepoints and2.295133Cworst retained. Datedfileoverlapsgrouped,testnotchronological/independentphysicalevents. No targeterrorfilter/state route.'},
 {'id':6,'passed':True,'evidence':'Independentvectorclock/anchor/completecases/explicitSVD/allpredictions/96metrics and5scientificexactrerun passed. Independentdescription/plot-targetalignment passed;finalruntime/fullreplay checked in release receipt. Source/decoder independence limits stated.'}],
 'checks_passed':6,'bounded_basic_package_complete':True,'not_validated':protocol['not_verified'],
 'all_six_resource_packages_have_bounded_scopes':True,'cross_resource_integration_authorized':False,'wholeP1_or103passed':False}
dump(dest/'results/basic_research_acceptance.json',review)
dump(dest/'results/evidence_summary.json',{'decision':'D067','version':'1.0.0','source_rows':130438,'minute_candidates':16751,'admitted':16636,
 'training_rows':9305,'test_rows':7331,'training_files':4,'heldout_files':3,'clock_window_exclusions':100,'temperature_exclusions':15,
 'six_coefficients_are_statistical':True,'bounded_basic_package_complete':True,'independent_model_verification':verify,'independent_description_verification':charverify,
 'quiet_group_worse_than_persistence_both_metrics':True,'feature_outside_points':316,'energy_columns_in_all3heldout_are_zero':True,'source_experiment_independence_not_proven':True,
 'new_fit_for_description':0,'independent_new_physical_test':False})
(dest/'run_example.py').write_text('''from pathlib import Path
import sys,json,argparse
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from water_temperature import predict
ap=argparse.ArgumentParser(description='Original150L tank conditional5clock-label-minute temperature estimator,notcontrol or capacity.')
ap.add_argument('--input',help='JSONobject with current/past input fields; omitted uses constructed examples')
a=ap.parse_args();parameters=json.loads((BASE/'parameters/horizontal_150L_temperature_v1.json').read_text(encoding='utf-8'))
cases=([json.loads(Path(a.input).read_text(encoding='utf-8'))] if a.input else json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))['cases'])
for case in cases:print(json.dumps({'inputs':case,'result':predict(parameters,**case)},ensure_ascii=False,allow_nan=False))
''',encoding='utf-8')
(dest/'运行示例.cmd').write_text('@echo off\r\nchcp 65001 >nul\r\nset "WATER_PYTHON=%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe"\r\nif exist "%WATER_PYTHON%" (\r\n  "%WATER_PYTHON%" -B "%~dp0run_example.py"\r\n) else (\r\n  py -3 -B "%~dp0run_example.py"\r\n)\r\npause\r\n',encoding='utf-8',newline='')
print(str(dest))
