"""Curate verified artifacts; this assembly script stays in work/, not final code."""
from pathlib import Path
import csv
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(__file__).resolve().parent
TARGET=ROOT/'resource_research_results/lithium_ion_storage'
AUTHOR=SOURCE/'downloads/blyth_ecm_20261015/author'

def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:
        f.write(source.read_bytes())
    return {'source':str(source.relative_to(ROOT)), 'target':str(target.relative_to(ROOT)),
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}

def main():
    copied=[]
    pairs=[(SOURCE/'baseline_runs/BL_M5BAT_20261013_01/parameters.json',TARGET/'parameters/conversion_m5bat.json'),
           (SOURCE/'apr2023_response_baseline_runs/BL_APR_RESPONSE_20261013_01/parameters.json',TARGET/'parameters/log_power_lmo1.json'),
           (SOURCE/'downloads/blyth_ecm_20261015/25C_MLP001_params.csv',TARGET/'parameters/voltage_25c_params.csv'),
           (SOURCE/'downloads/blyth_ecm_20261015/25C_MLP001_ocv.csv',TARGET/'parameters/voltage_25c_ocv.csv'),
           (AUTHOR/'research/scripts/model.py',TARGET/'code/third_party/thevenin_model.py'),
           (AUTHOR/'LICENSE',TARGET/'code/third_party/LICENSE')]
    for source,target in pairs:
        copied.append(copy_file(source,target))
    conversion=json.loads((SOURCE/'baseline_runs/BL_M5BAT_20261013_01/metrics.json').read_text(encoding='utf-8'))
    with (SOURCE/'apr2023_response_baseline_runs/BL_APR_RESPONSE_20261013_01/summary_metrics.csv').open(newline='',encoding='utf-8') as f:
        power=[x for x in csv.DictReader(f) if x['partition']=='evaluation']
    voltage=json.loads((SOURCE/'downloads/blyth_ecm_20261015/BL_BLYTH_VOLTAGE_20261015_01/metrics.json').read_text())
    summary={'version':'1.0.0','date':'2026-10-15','resource':'lithium_ion_storage',
             'scope':'Separately validated components from different sources; not one end-to-end storage capability model',
             'conversion':{'object':'M5BAT four LMO units, steady-state AC->DC',
                           'fit_windows':1133,'evaluation':conversion['by_trial']['test_2'],
                           'source_run':'BL_M5BAT_20261013_01'},
             'log_forecast':{'object':'M5BAT LMO1 April2023, assumed simultaneous log availability',
                             'evaluation_days':6,'evaluation':power,
                             'preferred_comparator':'B_SET, not B1 blend',
                             'source_run':'BL_APR_RESPONSE_20261013_01'},
             'conditional_voltage':{'object':'Author MLP001 laboratory cell, given SOC0=1,Q=2.132Ah,25C discharge',
                                     'evaluation_points':79058,'evaluation':voltage,
                                     'author_commit':'b60bf6ea91aa89bc2504be9589246c12d77c1fc3',
                                     'source_run':'BL_BLYTH_VOLTAGE_20261015_01',
                                     'limitation':'Extracted public 25C parameters; not full paper exact reproduction; worst endpoint retained'},
             'not_released_as_capability':['unknown SOC estimation','usable capacity estimation',
                                           'true command response latency','VPP deliverable capacity',
                                           'posthoc phase-feature forecast without independent confirmation'],
             'capacity_candidate_status':'Generic capacity proxy not passed; old 2019 unavailable prediction and separate ~88% error candidate retained in research records'}
    dest=TARGET/'results/validation_summary.json';dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8') as f:
        json.dump(summary,f,indent=2,ensure_ascii=False)
        f.write('\n')
    out=SOURCE/'downloads/blyth_ecm_20261015/final_package_assembly.json'
    with out.open('x',encoding='utf-8') as f:
        json.dump({'copied':copied,'note':'assembly log is process-only'},f,indent=2,ensure_ascii=False)
    print('Curated 6 source artifacts and 1 final summary; raw data and process scripts excluded')

if __name__=='__main__':
    main()
