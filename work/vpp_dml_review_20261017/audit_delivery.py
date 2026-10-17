"""Independent delivery checks; does not change the colleague's source."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=HERE/'vpp_dml_framework'
sys.path.insert(0,str(SOURCE))
from vpp_dml import SimConfig, simulate, build_dataset
from vpp_dml.splitting import TimeBlockSplit

def main():
    findings={}
    archive=ROOT/'vpp_dml_framework/vpp_dml_framework.zip'
    with zipfile.ZipFile(archive) as z:
        files=[i for i in z.infolist() if not i.is_dir()]
        findings['archive']={'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
          'crc_bad_member':z.testzip(),'file_count':len(files),
          'all_extracted_bytes_equal':all((HERE/i.filename).read_bytes()==z.read(i) for i in files)}
    raw=simulate(SimConfig(n_resources=40,n_days=90,seed=2026))
    df=build_dataset(raw)
    findings['full_data']={'raw_rows':len(raw),'usable_rows':len(df),'resources':int(df.id.nunique()),
                          'hours':int(df.t.nunique()),'types':df.groupby('type').id.nunique().to_dict()}
    required='id type t day hour dow offday temp solar sys_load_fc P DE DC DA p_ref subsidy flex pass_through lam_survey green_survey fatigue_pre soc_pre tin_post burn'.split()
    try:
        build_dataset(raw[required])
        findings['readme_minimum_columns']={'builds':True}
    except Exception as e:
        findings['readme_minimum_columns']={'builds':False,'error':repr(e)}
    # Deliberately remove one time label: row shifts must not pretend it is one hour.
    dropped=raw[~((raw.id==0)&(raw.t==100))]
    feature_bad=build_dataset(dropped)
    p99=raw.loc[(raw.id==0)&(raw.t==99),'P'].iloc[0]
    at101=feature_bad.loc[(feature_bad.id==0)&(feature_bad.t==101)].iloc[0]
    findings['missing_clock_test']={'removed_time':100,'next_time':101,
        'lag1_equals_time99_two_hours_ago':bool(at101.P_lag1==p99),'raises':False}
    times=df.t.to_numpy(); outer_cut=np.quantile(times,.8)
    folds=[]
    for k,(tr,te) in enumerate(TimeBlockSplit().split(times)):
        tr_times=np.unique(times[tr]); te_times=np.unique(times[te])
        before_test=(times[te]<outer_cut)
        fold={'fold':k,'train_rows':len(tr),'test_rows':len(te),
              'outer_future_rows_in_nuisance_train':int((times[tr]>=outer_cut).sum()),
              'outer_training_rows_residualized_with_future_outcomes':int(before_test.sum()) if (times[tr]>=outer_cut).any() else 0}
        fold['training_rows_with_lag168_power_from_test_time']=int(np.isin(times[tr]-168,te_times).sum())
        folds.append(fold)
    findings['fold_audit']={'outer_cut':float(outer_cut),'folds':folds,
        'interpretation':'Interleaved cross-fitting is retrospective. Final-stage-only holdout does not isolate the complete pipeline. Lagged outcomes also cross the 24-hour buffer.'}
    # Independent recomputation of every supplied coverage-summary numeric cell.
    d=pd.read_csv(SOURCE/'results/coverage_reps.csv')
    supplied=pd.read_csv(SOURCE/'results/coverage_summary.csv').set_index('feature')
    rows=[]
    for f,g in d.groupby('feature'):
        err=g.estimate-g.truth
        sd=err.std(ddof=1); centered=err-err.mean()
        crit=t_dist.ppf(.975,g.n_groups-1)
        r={'feature':f,'mean_estimate':g.estimate.mean(),'mean_truth':g.truth.mean(),
           'mean_error':err.mean(),'sd_error':sd,'mean_se_cluster':g.se_cluster.mean(),
           'mean_se_hc0':g.se_hc0.mean(),'ratio_cluster':g.se_cluster.mean()/sd,
           'ratio_hc0':g.se_hc0.mean()/sd,'coverage_cluster':(centered.abs()<=crit*g.se_cluster).mean(),
           'coverage_hc0':(centered.abs()<=1.96*g.se_hc0).mean(),
           'coverage_truth_cluster':(err.abs()<=crit*g.se_cluster).mean(),
           'n_reps':len(g),'n_groups':g.n_groups.iloc[0]}
        rows.append(r)
    calc=pd.DataFrame(rows).set_index('feature')[supplied.columns]
    calc.to_csv(HERE/'coverage_independent.csv')
    findings['coverage_summary_recalculation']={'rows_supplied':len(d),'new_training_repetitions':0,
        'numeric_cells':int(calc.size),'allclose':bool(np.allclose(calc,supplied,atol=1e-8,rtol=1e-6)),
        'max_abs_diff':float(np.max(np.abs(calc.to_numpy()-supplied.to_numpy()))),
        'Ep_centered_coverage':float(calc.loc['phi_Ep','coverage_cluster']),
        'Ep_truth_coverage':float(calc.loc['phi_Ep','coverage_truth_cluster'])}
    receipts={}
    for resource in sorted((ROOT/'resource_research_results').iterdir()):
        if resource.is_dir():
            docs=list((resource/'results').glob('*validation*.json'))+list((resource/'results').glob('*acceptance*.json'))
            receipts[resource.name]=[str(p.relative_to(ROOT)).replace('\\','/') for p in docs]
    findings['existing_resource_receipt_paths']=receipts
    (HERE/'independent_audit.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(findings,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
