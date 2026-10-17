"""Curate only the verified fixed component; no download/fit/raw-data copying."""
from common import *
import shutil
source=BASE/'runs/BL_CURVE_01';verify=BASE/'runs/VERIFY_CURVE_01/receipt.json'
assert load(verify)['status']=='passed' and load(source/'diagnostics.json')['gate_passed']
dest=ROOT/'resource_research_results/wind_power';dest.mkdir(exist_ok=False)
for n in ['code','parameters','examples','results']:(dest/n).mkdir()
shutil.copy2(BASE/'curve_kernel.py',dest/'code/wind_curve.py')
shutil.copy2(source/'parameters.json',dest/'parameters/kelmarsh_mixed_curve_v1.json')
shutil.copy2(source/'metrics.json',dest/'results/validation_metrics.json')
shutil.copy2(source/'diagnostics.json',dest/'results/diagnostics_summary.json')
shutil.copy2(BASE/'curve_protocol_v1.json',dest/'results/frozen_protocol.json')
dump(dest/'examples/constructed_inputs.json',{'description':'Constructed demonstration inputs, not new measured evaluation data. Parameters belong only to the six original Kelmarsh units.',
 'cases':[{'unit':u,'wind_mps':8.0} for u in range(1,7)]})
dump(dest/'source_manifest.json',{'data':{'title':'Kelmarsh wind farm data','creators':['Plumley, Charlie','Takeuchi, Roberta'],
 'publisher':'Cubico / Zenodo','url':'https://zenodo.org/records/16807551','doi':'10.5281/zenodo.16807551','publication_date':'2025-08-12','license':'CC-BY-4.0','license_url':'https://creativecommons.org/licenses/by/4.0/',
 'archive_sha256':load(BASE/'curve_protocol_v1.json')['archive']['sha256'],'archive_publisher_md5':'972e5280172216a5fe76dcab19c741b0',
 'static_sha256':sha(BASE/'downloads/KELMARSH_2018_01/Kelmarsh_WT_static.csv'),
 'mapping_sha256':sha(BASE/'downloads/KELMARSH_2018_01/Kelmarsh_WT_dataSignalMapping.csv'),
 'modifications':'Derived training-bin means, statistical coefficients and evaluation aggregates from original 2018 wind/power rows; source raw records are not redistributed here.'},
 'methods':[{'url':'https://arxiv.org/html/1707.06497v2','basis':'Static nonlinear and predefined piecewise-linear power-curve benchmark family. Primary HTML read via web, local retrieval failed SSL validation; different Vestas V80 data. Our 0.5m/s training-mean knots are our prespecified design, not exact paper replication or imported thresholds.'},
 {'url':'https://doi.org/10.1002/we.70012','basis':'Kelmarsh source/SCADA/event context, primary HTML read via web. No paper neural method or outage-week filter reproduced. Local Crossref metadata only; local publisher HTML 403.'}],
 'evidence':{'protocol_sha256':sha(BASE/'curve_protocol_v1.json'),'admission_sha256':sha(BASE/'runs/PREP_CURVE_01/admission.json'),
 'independent_verification_sha256':sha(verify),'independent_verification_path':str(verify.relative_to(ROOT)).replace('\\','/')}})
dump(dest/'results/evidence_summary.json',{'version':'1.0.0','decision':'D065','date':'2026-10-16',
 'scope':'First finite component only: contemporaneous 10-minute published mean wind to active power of six studied units in mixed observed operation.',
 'resource_basic_package_complete':False,'six_criterion_resource_review_complete':False,
 'source_rows':315360,'admitted_rows':303987,'training_rows':234751,'test_rows':69236,'excluded_core_rows':11373,
 'per_unit_training_rows':{u:p['training_rows'] for u,p in load(source/'parameters.json')['units'].items()},
 'training_knots_total':280,'training_months':'2018-01 through 2018-09','held_out_months':'2018-10 through 2018-12',
 'gate_passed':True,'six_units_both_metrics_vs_both_baselines_passed':True,'three_test_months_both_metrics_vs_both_baselines_passed':True,
 'independent_verification':load(verify),'not_verified':load(BASE/'curve_protocol_v1.json')['not_verified']})
(dest/'run_example.py').write_text('''"""Run constructed inputs or one user-supplied wind value; no training."""
from pathlib import Path
import argparse,json,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from wind_curve import evaluate
ap=argparse.ArgumentParser(description='Contemporaneous mixed-operation curve, not forecast or available capacity.')
ap.add_argument('--unit',type=int);ap.add_argument('--wind-mps',type=float);a=ap.parse_args()
parameters=json.loads((BASE/'parameters/kelmarsh_mixed_curve_v1.json').read_text(encoding='utf-8'))
if (a.unit is None)!=(a.wind_mps is None):ap.error('provide both --unit and --wind-mps')
cases=([{'unit':a.unit,'wind_mps':a.wind_mps}] if a.unit is not None else json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))['cases'])
print('Conditional same-row wind/power estimate; original six units only. No control or capacity guarantee.')
for c in cases:print(json.dumps({**c,**evaluate(parameters,c['unit'],c['wind_mps'])},ensure_ascii=False,allow_nan=False))
''',encoding='utf-8')
(dest/'运行示例.cmd').write_text('@echo off\r\nchcp 65001 >nul\r\nset "WIND_PYTHON=%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe"\r\nif exist "%WIND_PYTHON%" (\r\n  "%WIND_PYTHON%" -B "%~dp0run_example.py"\r\n) else (\r\n  py -3 -B "%~dp0run_example.py"\r\n)\r\npause\r\n',encoding='utf-8',newline='')
print(str(dest))
