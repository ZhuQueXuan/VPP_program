"""Independent read-only verification of root diagnostic summaries and identities."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;DIAG=HERE.parent;ROOT=DIAG.parents[1];OLD=ROOT/'work/b1_ev_mainline_20261030'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _ride_template as template

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    target=HERE/'result_review_receipt.json'
    if target.exists():raise RuntimeError('completed independent review cannot be overwritten')
    checks=[]
    def check(name,condition):
        if not bool(condition):raise AssertionError(name)
        checks.append(name)
    summary=read(DIAG/'summary.json');metrics=pd.read_csv(DIAG/'diagnostic_metrics.csv')
    check('expected5120metricrows',len(metrics)==5120)
    for r in summary['groups']:
        g=metrics[(metrics.scenario==r['scenario'])&(metrics.level==r['level'])&(metrics.method==r['method'])]
        check('|'.join([r['scenario'],r['level'],r['method']]),len(g)==r['events']==256 and
            np.isclose(g.duration_mae.mean(),r['duration_mae'],rtol=0,atol=1e-10) and
            np.isclose(g.curve_rmse.mean(),r['curve_rmse'],rtol=0,atol=1e-10) and
            int(g.false_detection.sum())==r['false_detection'] and int(g.no_action.sum())==r['no_action'])
    freeze=read(DIAG/'source_freeze.json')
    check('all_frozen_runtime_and_protocol_sources_unchanged',all(sha(ROOT/k)==v for k,v in freeze.items()))
    old_manifest=read(OLD/'final_manifest.json')
    check('all75protected_resource_and_compatibility_files_unchanged',all(sha(ROOT/k)==v for k,v in old_manifest['protected_files'].items()))
    check('old_study_frozen_evidence_unchanged',all(sha(ROOT/k)==v for k,v in old_manifest['evidence'].items()))
    check('old_raw_factual_files_unchanged',all(sha(ROOT/k)==v for k,v in read(OLD/'corrective_replay_receipt.json')['original_raw_sha256'].items()))
    probes=read(DIAG/'optimization_probes.json');check('15probe_cases',len(probes)==15)
    bounds_failed=0
    for p in probes:
        truth=next(r for r in read(OLD/f'evaluator/{p["seed"]}_positive_truth.json') if r['task_id']==p['task_id'])
        theta=np.array(p['witness_theta']);s=np.array(truth['relative_starts_min']);r=np.array(truth['true_reduction_kw'])
        witness=truth['q_kw']*template.interval_average(theta,truth['W_min'],s,s+1)
        check('feasible_witness_'+p['task_id'],np.max(abs(witness-r))<1e-10 and
            np.isclose(np.sum(witness[(s>=0)&(s<30)]>=.15)*60,truth['cumulative_response_seconds']))
        check('witness_bic_'+p['task_id'],np.isclose(p['witness_bic2'],9*np.log(len(r)),rtol=0,atol=1e-10))
    for n in (3,12):
        rows=[next(r for r in p['fits'] if r['minimum_starts']==n) for p in probes]
        count=sum(r['bic2']>p['witness_bic2']+1e-5 for r,p in zip(rows,probes))
        check('probe_summary_'+str(n),count==summary['optimization_probes'][str(n)]['m2_witness_objective_strictly_better'])
    controls=read(DIAG/'positive_controls.json');check('16control_method_rows',len(controls)==16)
    delayed=[r for r in controls if r['control']=='M2_end_gap_delayed_rebound' and r['noisy'] is False]
    check('clean_delayed_positive_control_fails_current_ride',next(r['duration_mae'] for r in delayed if r['method']=='ride_template')==600)
    check('clean_delayed_positive_control_CPOP_exact_duration',next(r['duration_mae'] for r in delayed if r['method']=='cpop')==0)
    check('no_candidate_or_source_replacement',summary['production_changes'] is False and summary['model_adopted'] is False)
    receipt=dict(passed=True,n_checks=len(checks),checks=checks,
        interpretation='Summary and witness evidence support a major posterior-phase/local-search failure in this fixed implementation; not proof every residual error is numerical or that a candidate improves original CPOP.',
        data_role='previously seen synthetic diagnostic data',production_modified=False,main_fits_run_by_this_auditor=0)
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(passed=True,n_checks=len(checks))))
if __name__=='__main__':main()
