"""Independent frozen-result and no-fitting delivery checks."""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/"b1_ev_single_demo_20261104"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    checks=0
    def ck(ok,label):
        nonlocal checks
        if not ok:
            raise AssertionError(label)
        checks+=1
    diag=read(HERE/"diagnosis.json")
    plan=read(HERE/"experiment_plan.json")
    saved=read(OLD/"confirmation.json")
    freeze=read(OLD/"selection.json")
    preflight=read(HERE/"preflight.json")
    for mapping in (freeze["source_sha256"],diag["input_sha256"],preflight["source_sha256"]):
        for path,sha in mapping.items():
            ck(digest(ROOT/path)==sha,path)
    ck(preflight["new_model_fits"]==0 and preflight["passed"],"no fits")
    ck(preflight["research_development_or_confirmation_data_generated"] is False,"no research generation")
    ck(not (HERE/"development").exists() and not (HERE/"confirmation").exists(),"no new research artifacts")
    ck(not (HERE/"development_receipt.json").exists(),"training not performed")
    with (HERE/"cohort_diagnosis.csv").open(encoding="utf-8-sig",newline="") as fp:
        rows=list(csv.DictReader(fp))
    ck(len(rows)==24,"24 cohorts")
    for old,new in zip(saved["cohorts"],rows):
        ck(str(old["seed"])==new["seed"] and old["mechanism"]==new["mechanism"],"row keys")
        for label,name in (("dr","incumbent"),("or","10.0")):
            predicted=old["scores"][name]["curves"]
            truth=old["truth"]
            own_errors=[a-b for a,b in zip(predicted[0],truth[0])]
            own=math.sqrt(sum(v*v for v in own_errors)/len(own_errors))
            group_errors=[(h-l)-(th-tl) for l,h,tl,th in zip(predicted[1],predicted[2],truth[1],truth[2])]
            group=math.sqrt(sum(v*v for v in group_errors)/len(group_errors))
            ck(abs(own-float(new[label+"_contrast_rmse_s"]))<1e-9,"own recomputation")
            ck(abs(group-float(new[label+"_group_difference_rmse_s"]))<1e-9,"group recomputation")
    block_deltas=[]
    for seed in plan["development"]["seeds"]:
        ck(seed not in {r["seed"] for r in saved["cohorts"]},"new development seeds")
    oldseeds=sorted({int(r["seed"]) for r in rows})
    for seed in oldseeds:
        rs=[r for r in rows if int(r["seed"])==seed]
        ck(len(rs)==4,"4 paired mechanisms")
        block_deltas.append(mean(float(r["contrast_delta_s"]) for r in rs))
    ck(sum(v<0 for v in block_deltas)==2,"2/6")
    ck(sum(mean(float(r["group_difference_delta_s"]) for r in rows if int(r["seed"])==seed)<0
           for seed in oldseeds)==5,"5/6 groups")
    without_first=[r for r in rows if int(r["seed"])!=oldseeds[0]]
    ck(mean(float(r["or_contrast_rmse_s"]) for r in without_first)>
       mean(float(r["dr_contrast_rmse_s"]) for r in without_first),"leave first reverses")
    ck(diag["level_identifiability"]["absolute_level_saved"] is False,"level boundary")
    ck(plan["candidate_count"]==1 and plan["status"]=="awaiting_root_review_0_new_fits","one proposal")
    ck(len(plan["confirmation"]["seeds"])==20 and plan["confirmation"]["cohorts"]==120,"new confirmation")
    ck(plan["execution"]["no_point5"],"no point5")
    ck(len(set(plan["development"]["seeds"]+plan["confirmation"]["seeds"]))==26,"seed split")
    ck(not list(HERE.rglob("*.cmd")),"no CMD")
    for link in re.findall(r"\]\(([^)]+)\)",(HERE/"README.md").read_text(encoding="utf-8")):
        if not link.startswith("https://") and link!="verification.json":
            ck((HERE/link).is_file(),link)
    artifacts={p.relative_to(HERE).as_posix():digest(p) for p in sorted(HERE.rglob("*"))
               if p.is_file() and p.name!="verification.json" and "__pycache__" not in p.parts}
    output=dict(date="2026-11-05",passed=True,checks=checks,new_fits=0,
        old_cohorts=24,old_independent_seed_blocks=6,new_research_cohorts_generated=0,
        candidate_count=1,training_authorized_or_performed=False,real_effect_estimated=False,
        old_confirmation_role="consumed_diagnostic_only",source_hashes_checked=
        len(freeze["source_sha256"])+len(diag["input_sha256"])+len(preflight["source_sha256"]),
        artifacts_sha256=artifacts,
        limitation="Saved-result audit, static review, syntax and no-fit arithmetic only; candidate training not tested.")
    (HERE/"verification.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{checks} checks passed; zero fits; 24 old cohorts / 6 independent blocks.")


if __name__=="__main__":
    main()
