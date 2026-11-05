"""Read-only study scoring after outputs; no estimator selection or refitting."""
from pathlib import Path
import argparse
import csv
import json
import math
from collections import Counter
import numpy as np
from scipy.stats import t as student_t

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def dump_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2)


def mean(rows,key):
    values=[r[key] for r in rows if r.get(key) is not None]
    return float(np.mean(values)) if values else None


def evidence(r):return r.get('evidence_decision',{}).get('decision')


def describe(rows):
    n=len(rows);valid=[r for r in rows if r.get('duration') is not None]
    assessed=[r for r in rows if r.get('evidence_decision',{}).get('status')=='assessed']
    zero=[r for r in rows if r['no_action']];zero_valid=[r for r in zero if r.get('duration') is not None]
    zero_assessed=[r for r in zero if r.get('evidence_decision',{}).get('status')=='assessed']
    pos=[r for r in rows if r['threshold_positive']];pos_valid=[r for r in pos if r.get('duration') is not None]
    pos_assessed=[r for r in pos if r.get('evidence_decision',{}).get('status')=='assessed']
    rawfalse=sum(bool(r['false_positive_duration']) for r in zero_valid)
    evidencefalse=sum(evidence(r)=='evidence' for r in zero_assessed)
    evidencepos=sum(evidence(r)=='evidence' for r in pos_assessed)
    rawmiss=sum(bool(r['threshold_response_duration_miss']) for r in pos_valid)
    # Calibration uses user maxima, so also disclose any false evidence across
    # that user's full two-event null block, separately for each scenario.
    userzero={}
    for r in zero:userzero.setdefault(r['user_id'],[]).append(r)
    fullnull={u:r for u,r in userzero.items() if len(r)==2}
    fullassessed={u:r for u,r in fullnull.items() if all(x.get('evidence_decision',{}).get('status')=='assessed' for x in r)}
    anyfalse=sum(any(evidence(x)=='evidence' for x in r) for r in fullassessed.values())
    return dict(n_events=n,n_users=len({r['user_id'] for r in rows}),statuses=dict(Counter(r['status'] for r in rows)),
        n_valid_duration=len(valid),n_assessed_evidence=len(assessed),
        n_no_action=len(zero),n_no_action_valid_duration=len(zero_valid),n_no_action_assessed_evidence=len(zero_assessed),
        raw_false_positive_duration_count=rawfalse,
        raw_false_positive_duration_rate=rawfalse/len(zero_valid) if zero_valid else None,
        calibrated_false_evidence_count=evidencefalse,
        calibrated_false_evidence_rate=evidencefalse/len(zero_assessed) if zero_assessed else None,
        full_null_user_blocks=len(fullnull),full_null_assessed_user_blocks=len(fullassessed),
        calibrated_user_any_false_evidence_count=anyfalse,
        calibrated_user_any_false_evidence_rate=anyfalse/len(fullassessed) if fullassessed else None,
        n_threshold_positive=len(pos),n_threshold_positive_valid_duration=len(pos_valid),n_threshold_positive_assessed_evidence=len(pos_assessed),
        raw_positive_duration_miss_count=rawmiss,
        raw_positive_duration_miss_rate=rawmiss/len(pos_valid) if pos_valid else None,
        calibrated_response_evidence_count=evidencepos,
        calibrated_response_inconclusive_count=sum(evidence(r)=='inconclusive' for r in pos_assessed),
        calibrated_response_unavailable_count=len(pos)-len(pos_assessed),
        calibrated_response_not_evidence_rate=(len(pos)-evidencepos)/len(pos) if pos else None,
        physical_subthreshold_count=sum(bool(r['physical_subthreshold']) for r in rows),
        duration_mae_seconds=mean(valid,'duration_mae'),duration_bias_seconds=mean(valid,'duration_bias'),
        curve_rmse_kw=mean(valid,'curve_rmse_kw'),raw_eta_mae=mean(valid,'eta_mae'),
        reference_bias_kw=mean(rows,'reference_bias_kw'),reference_rmse_kw=mean(rows,'reference_rmse_kw'),
        reference_max_positive_error_kw=mean(rows,'reference_max_positive_error_kw'),
        reference_fraction_above_physical_threshold=mean(rows,'reference_fraction_above_physical_threshold'),
        fallback_count=sum(bool(r.get('fallback')) for r in rows),
        denominators='Each rate lists its available/evidence-assessed denominator; unavailable rows retained and counted separately. Noaction means no physical response, threshold-positive means interval truth exceeds .1q at least once.')


def mc_interval(values):
    a=np.asarray(values,float);mean=float(a.mean())
    half=float(student_t.ppf(.975,len(a)-1)*np.std(a,ddof=1)/math.sqrt(len(a))) if len(a)>1 else None
    return dict(n_blocks=len(a),mean=mean,mc95=[mean-half,mean+half] if half is not None else None,
        interpretation='Across-seed simulation Monte Carlo t interval; not field confidence or independent event inference')


def analyze(phase):
    receipt=read(HERE/phase/'receipt.json');rows=[];times=[]
    for b in receipt['blocks']:
        block=read(HERE/phase/'blocks'/f"{b['seed']}.json")
        rows.extend(block['metric_rows']);times.extend(block['timing'])
    scenarios=sorted({r['scenario'] for r in rows});paths=sorted({r['path'] for r in rows});seeds=sorted({r['seed'] for r in rows})
    summaries=[];byblock=[];weak=[]
    for scenario in scenarios:
        for path in paths:
            subset=[r for r in rows if r['scenario']==scenario and r['path']==path]
            summaries.append(dict(scenario=scenario,path=path,**describe(subset)))
            for seed in seeds:
                byblock.append(dict(seed=seed,scenario=scenario,path=path,**describe([r for r in subset if r['seed']==seed])))
            if scenario=='weak':
                for subtype in ('brief3','brief6','sustained'):
                    for amp in (.14,.20):
                        weak.append(dict(path=path,subtype=subtype,amplitude_fraction=amp,**describe([r for r in subset if r['weak_subtype']==subtype and r['weak_amplitude_fraction']==amp])))
    differences=[]
    for scenario in scenarios:
        for a,b in (('new_cpop','old_cpop'),('new_ride_revised','old_ride_revised'),('new_ride_revised','new_cpop')):
            for metric in ('duration_mae_seconds','reference_rmse_kw','raw_false_positive_duration_rate','calibrated_false_evidence_rate','calibrated_response_not_evidence_rate'):
                delta=[]
                for seed in seeds:
                    first=next(r for r in byblock if r['scenario']==scenario and r['path']==a and r['seed']==seed)
                    second=next(r for r in byblock if r['scenario']==scenario and r['path']==b and r['seed']==seed)
                    if first.get(metric) is not None and second.get(metric) is not None:delta.append(first[metric]-second[metric])
                if delta:differences.append(dict(scenario=scenario,first=a,second=b,metric=metric,**mc_interval(delta)))
    result=dict(phase=phase,n_scored_rows=len(rows),n_independent_seed_blocks=len(seeds),
        summaries=summaries,by_block=byblock,weak_by_subtype_amplitude=weak,paired_block_differences=differences,
        process_timing_seconds_sum={path:sum(t['seconds'] for t in times if t.get('label')==path and t.get('seconds') is not None) for path in paths},
        runtime_scope='Elapsed task-batch sums under four process workers, not exclusive single-event latency',
        process_wall_seconds=receipt['seconds'],all_events_retained=True,
        calibration_caveat='Finite ranks require exchangeable user maxima, same two-event blocks; simulated observed rates do not certify field false alarm rate.',
        decision_caveat='Inconclusive is not proof of no response. Duration and raw eta remain unchanged; no events filtered for total effects.',
        source_receipt=str(HERE/phase/'receipt.json'))
    dump_new(HERE/phase/'assessment.json',result)
    with (HERE/phase/'process.csv').open('x',encoding='utf-8-sig',newline='') as f:
        fields=sorted(set().union(*(r.keys() for r in rows)) - {'evidence_decision','reasons'})
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(phase=phase,n_scored_rows=len(rows),n_blocks=len(seeds),assessment=str(HERE/phase/'assessment.json'))),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['validation','test'],required=True)
    analyze(p.parse_args().phase)
