from common import *
from evaluate import dataset,score,aggregate
from assess_confirmation import paired

for p,h in read('freeze.json')['source_sha256'].items():
    if p in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py']:
        assert sha(HERE/'production_before'/p)==h,p
    else:assert sha(ROOT/p)==h,p
rows=score(dataset('stress_continuous',HERE),read('selected.json')['config'])
write('stress_continuous/metrics.json',rows)
summary={subset or 'all':{m:aggregate(rows,m,subset) for m in ['cpop','labs','retained','candidate']} for subset in [None,'weak','explicit_gap','short_n']}
checks=dict(weak_improved=summary['weak']['candidate']['primary_seconds']<summary['weak']['retained']['primary_seconds'],
    no_extra_whole_misses=summary['all']['candidate']['whole_miss']<=summary['all']['retained']['whole_miss'],
    no_extra_short_misses=summary['all']['candidate']['short_local_miss']<=summary['all']['retained']['short_local_miss'],
    false_not_increased=summary['all']['candidate']['null_false_positive']<=summary['all']['retained']['null_false_positive'])
write('continuous_assessment.json',dict(summary=summary,checks=checks,paired=paired(rows,'weak'),
    estimator_and_thresholds_not_changed=True,no_adoption_based_on_tuning_this_dataset=True))
print(json.dumps(native(dict(checks=checks,summary=summary))),flush=True)
