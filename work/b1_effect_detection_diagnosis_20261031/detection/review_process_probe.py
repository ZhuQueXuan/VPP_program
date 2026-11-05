"""Read-only arithmetic/identity review of root's fixed512-variant oracle probe."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE.parent
OLD=ROOT/"work/b1_finish_ev_20261030/final_chain"


def read(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks={"saved_subset_identity":0,"oracle_output_identity":0,"oracle_raw_duration":0,"oracle_raw_eta":0,
            "sigma_and_task_match_protocol":0,"oracle_rebound_bound":0,"observed_vs_clean_bound_same":0}
    maximum={"raw_eta_difference":0.,"rebound_bound_difference":0.}
    bound_change=[];used={PARENT/"run_process_probe.py",PARENT/"protocol.json",PARENT/"process/summary.json"}
    indices=[u*5+j for u in range(16) for j in (3,4)]
    local=[u*2+j for u in range(16) for j in (0,1)]
    for seed in range(7240200,7240208):
        for scenario in ("positive","zero"):
            fp=ROOT/f"data/B1_finish_chain_v1_20261030/{seed}_{scenario}_facts.json"
            tp=OLD/f"evaluator/{seed}_{scenario}_truth.json"
            ip=OLD/f"factor_inputs/{seed}_{scenario}.json"
            used.update([fp,tp,ip])
            facts=read(fp);truth=read(tp)
            assert [read(ip)["target_indices"][i] for i in local]==indices
            prev_bounds=None
            for condition in ("true_reference_observed_power","true_reference_noiseless_power"):
                for method in ("ride_revised","cpop"):
                    event_path=PARENT/f"process/events/{seed}_{scenario}_{condition}_{method}.json"
                    saved_path=OLD/f"events/{seed}_{scenario}_{method}.json"
                    used.update([event_path,saved_path]);outputs=read(event_path)["events"];saved=read(saved_path)
                    assert len(outputs)==32
                    these=[]
                    for k,(old_index,saved_index) in enumerate(zip(indices,local)):
                        f=facts[old_index];t=truth[old_index];p=outputs[k];e=saved[saved_index]
                        assert e["task"]["task_id"]==f["task"]["task_id"]==t["task_id"]==p["task_id"]
                        checks["saved_subset_identity"]+=1;checks["oracle_output_identity"]+=1
                        assert f["noise_sigma_kw"]==.05 and t["W_min"]==30. and t["q_kw"]==1.5
                        assert f["task"]["notice_min"]==f["task"]["start_min"]-15
                        checks["sigma_and_task_match_protocol"]+=1
                        b=np.asarray(t["true_reference_kw"],float)
                        power=np.asarray(f["power_kw"] if condition=="true_reference_observed_power" else t["noiseless_power_kw"],float)
                        raw=b-power;s=np.asarray(t["relative_starts_min"],float);use=(s>=0)&(s<30.)
                        duration=int((raw[use]>=.15).sum())*60
                        assert duration==p["features"]["raw_observed"]["cumulative_response_seconds"]
                        checks["oracle_raw_duration"]+=1
                        diff=abs(float(raw[use].sum()/45.)-p["eta_raw"])
                        assert diff<1e-12
                        checks["oracle_raw_eta"]+=1;maximum["raw_eta_difference"]=max(maximum["raw_eta_difference"],diff)
                        if method=="ride_revised":
                            expected=(7.2-float(b.max()))/1.5
                            actual=p["selection_evidence"]["rebound_max_ratio"]
                            d=abs(expected-actual);assert d<1e-12
                            maximum["rebound_bound_difference"]=max(maximum["rebound_bound_difference"],d)
                            checks["oracle_rebound_bound"]+=1;these.append(actual)
                            if condition=="true_reference_observed_power":
                                bound_change.append(actual-e["process"]["selection_evidence"]["rebound_max_ratio"])
                    if method=="ride_revised":
                        if condition=="true_reference_observed_power":prev_bounds=these
                        else:
                            assert prev_bounds==these
                            checks["observed_vs_clean_bound_same"]+=len(these)
    changes=np.asarray(bound_change)
    report=dict(schema="b1.oracle-probe.independent-read-only-review.v1",checks=checks,max_absolute_differences=maximum,
        subset_variants=512,no_refitting=True,task_index_and_condition_construction_passed=True,
        sigma_unchanged_observed_and_noiseless=.05,
        no_truth_parameter_initialization_passed="Manual source review: only explicit true-reference / noiseless-power diagnostic arrays supplied; observed_starts derives starts from supplied signal.",
        reference_dependent_bound=dict(changed_variants=int((changes!=0).sum()),total=512,
            true_minus_predicted_ratio_mean=float(changes.mean()),min=float(changes.min()),max=float(changes.max()),
            interpretation="declared_headroom policy is fixed, but its numeric upper bound follows supplied reference; oracle contrast includes this reference-derived rule. Do not allocate cause percentages."),
        reviewed_files_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(used)},
        script_sha256=sha(Path(__file__)))
    with (HERE/"process_probe_review.json").open("x",encoding="utf-8") as f:
        json.dump(report,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!="reviewed_files_sha256"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
