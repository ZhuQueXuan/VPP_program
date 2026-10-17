"""Check retained forecasting code parity and portable example; no new scores."""
from pathlib import Path
import hashlib,json,subprocess,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
DEPS=[ROOT/d for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015')]
for d in DEPS:sys.path.insert(0,str(d))
PACKAGE=ROOT/'resource_research_results/distributed_photovoltaic'
sys.path.insert(0,str(PACKAGE/'code'))
from clear_sky_forecast import SiteGeometry,MODEL_SETTINGS,forecast_next_labels
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    run=BASE/'runs/BL_SMART_FORECAST_01';dest=run/'package_verification.json';assert not dest.exists()
    p=json.loads((PACKAGE/'parameters/pvdaq1239_smart_geometry_v1.json').read_text(encoding='utf-8'))
    assert p['fixed_model_settings']==MODEL_SETTINGS;site=SiteGeometry(**p['site_geometry'])
    frozen=pd.read_csv(run/'predictions.csv')
    values=forecast_next_labels(frozen.origin_W.to_numpy(),pd.DatetimeIndex(frozen.origin_time),site)
    fields={'persistence_W':'B_P','clear_sky_persistence_W':'M_SP','clear_current_W_m2':'clear_current_W_m2','clear_target_W_m2':'clear_target_W_m2','ratio':'clear_ratio_applied'}
    diffs={k:float(np.max(np.abs(values[k].to_numpy()-frozen[v].to_numpy()))) for k,v in fields.items()}
    assert max(diffs.values())<1e-7 and len(values)==2931
    assert values.branch.tolist()==frozen.smart_branch.tolist()
    assert values.target_time.dt.tz_localize(None).dt.strftime('%Y-%m-%d %H:%M:%S').tolist()==frozen.target_time.tolist()
    bad=[([float('nan')],['2019-08-01']),([],[]),([1.,2.],['2019-08-01']),([1.],[None])]
    for powers,times in bad:
        try:forecast_next_labels(powers,times,site)
        except (ValueError,TypeError):pass
        else:raise AssertionError('Invalid input accepted')
    fallback=forecast_next_labels([-20.,30000.],['2019-08-01 00:00','2019-08-01 00:15'],site)
    assert fallback.clear_sky_persistence_W.tolist()==[-20.,30000.] and fallback.branch.eq('persistence_fallback').all()
    # Dependency bootstrap is verification-only; delivered code has no work paths.
    bootstrap='import sys,runpy;'+''.join('sys.path.insert(0,'+repr(str(d))+');' for d in DEPS)+'runpy.run_path('+repr(str(PACKAGE/'run_forecast_example.py'))+',run_name="__main__")'
    example=subprocess.run([sys.executable,'-X','utf8','-B','-c',bootstrap],cwd=ROOT/'work',capture_output=True,text=True,encoding='utf-8',check=True)
    assert 'persistence_fallback' in example.stdout and 'scaled' in example.stdout
    old=json.loads((PACKAGE/'results/release_validation.json').read_text())['verified_files']
    unchanged={n:sha(PACKAGE/n)==h for n,h in old.items() if n!='README.md'};assert all(unchanged.values())
    assert not any(x.suffix in ('.pdf','.xlsx','.parquet') or '__pycache__' in x.parts for x in PACKAGE.rglob('*') if x.is_file())
    outputs={f.relative_to(PACKAGE).as_posix():sha(f) for f in PACKAGE.rglob('*') if f.is_file()}
    result={'status':'passed','release_version':'1.1.0','rows_replayed':len(values),'maximum_difference':diffs,
            'branches_and_target_labels_match':True,'invalid_inputs_rejected':len(bad),'negative_and_large_fallback_not_clipped':True,
            'example_from_other_cwd_with_declared_dependencies':True,'old_v1_0_files_except_updated_README_unchanged':unchanged,
            'protocol_sha256':sha(BASE/'smart_forecast_protocol_v1.json'),'verified_files':outputs,
            'limit':'Engineering packaging parity, not independent scientific or online validation.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PACKAGE/'results/release_validation_v1_1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('verified_files','old_v1_0_files_except_updated_README_unchanged')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
