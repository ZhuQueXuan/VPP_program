"""Independent saved-score join and duplicate-trajectory audit; no model calls."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
METHODS=("ride_revised","cpop","ride_template")


def read(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open("x",encoding="utf-8") as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    frame=pd.read_csv(HERE/"event_join.csv")
    summary=read(HERE/"summary.json")
    receipt=read(HERE/"receipt.json")
    old=pd.DataFrame(read(ROOT/"work/b1_finish_ev_20261030/final_chain/process.json"))
    assert len(frame)==4096 and len(old)==12288
    assert not frame.duplicated(["seed","scenario","task_id"]).any()
    comparisons=0
    for method in METHODS:
        joined=frame.merge(old[old.method==method],on=["seed","scenario","task_id"],validate="one_to_one",suffixes=("_new","_old"))
        assert len(joined)==4096
        assert np.array_equal(joined.no_action_new,joined.no_action_old)
        assert np.array_equal(joined[method+"_duration_seconds"],joined.duration)
        assert np.array_equal(joined[method+"_detection"]*joined.no_action_new,joined.false_detection)
        comparisons+=len(joined)*3
    no=frame[frame.no_action==1]
    unique=no.drop_duplicates("task_id")
    duplicates=[]
    for task,group in no.groupby("task_id"):
        assert len(group) in (1,2)
        if len(group)==2:
            assert set(group.scenario)=={"positive","zero"}
            fields=[m+"_detection" for m in METHODS]+["reference_task_bias_mean_kw","raw_duration_seconds","raw_task_max_kw"]
            assert (group[fields].max()-group[fields].min()).abs().max()==0
            duplicates.append(task)
    pair=[]
    for i,a in enumerate(METHODS):
        for b in METHODS[i+1:]:
            aa=no[a+"_detection"].astype(bool);bb=no[b+"_detection"].astype(bool)
            pair.append(dict(method_a=a,method_b=b,intersection=int((aa&bb).sum()),union=int((aa|bb).sum()),
                             a_only=int((aa&~bb).sum()),b_only=int((bb&~aa).sum()),jaccard=float((aa&bb).sum()/(aa|bb).sum())))
    assert pair==summary["pairwise_false_detection_overlap"]
    fit_only=no[(no.ride_revised_detection==1)&(no.raw_detection==0)]
    positive=no[no.reference_task_bias_mean_kw>=.15]
    assert len(positive)==190 and (positive[[m+"_detection" for m in METHODS]]==1).all().all()
    assert no.loc[no[[m+"_detection" for m in METHODS]].sum(axis=1)>0,"reference_task_bias_mean_kw"].gt(0).all()
    assert no.noise_only_above_threshold_bins.sum()==0
    source_identity={k:sha(ROOT/k)==v for k,v in receipt["inputs_sha256"].items()}
    assert all(source_identity.values())
    out=dict(schema="b1.false-detection.independent-join-check.v1",saved_score_numeric_comparisons=comparisons,
        saved_score_all_match=True,all_original_inputs_still_identical=len(source_identity),
        variant_no_action=1778,distinct_no_action_task_ids=len(unique),paired_no_action_duplicates=len(duplicates),
        paired_duplicate_detection_and_raw_summaries_exact=True,
        distinct_task_false_detection={m:int(unique[m+"_detection"].sum()) for m in METHODS},
        fit_only_revised_cases=fit_only[["task_id","scenario","reference_method","reference_task_bias_mean_kw",
            "raw_task_max_kw","ride_revised_max_kw","ride_revised_duration_seconds"]].to_dict("records"),
        all_method_false_detections_have_positive_task_mean_reference_bias=True,
        mean_reference_bias_at_least_threshold_no_action=190,all_three_detect_all190=True,
        shared_revised_cpop_false_detection_pre_notice_history_prior_nonnegative=int(no.loc[no.common_revised_cpop_detection==1,"pre_notice_history_prior_minus_meter_mean_kw"].ge(0).sum()),
        interpretation="1121 distinct no-action tasks still share users and blocks; this does not make1121 independent trials. Cause percentages are not identified.",
        audited_files_sha256={p.name:sha(p) for p in [HERE/"event_join.csv",HERE/"summary.json",HERE/"receipt.json",Path(__file__)]})
    write(HERE/"independent_check.json",out)
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
