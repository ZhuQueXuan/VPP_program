from common import *
freeze=read(HERE/'selection_freeze.json')
for name,value in freeze['source_sha256'].items():assert sha(HERE/name)==value,name
assert sha(VIEW/'validation.json')==freeze['input_validation_sha256']
rows=load('validation');curves=fit_native(rows,'validation');pred=predictions(rows,curves,freeze['selected_k']);stats=score(rows,pred)
save('validation/predictions.json',pred);save('validation/scores.json',stats)
cp=stats['cpop'];new=stats['candidate'];lb=stats['labs'];raw=stats['raw_only']
paired=[]
for p in pred:
    c=p['methods']['candidate'];o=p['methods']['cpop'];r=p['methods']['raw_only']
    if any(c[k]!=o[k] for k in ['detected','onset_seconds','recovery_seconds']):paired.append(dict(event_id=p['event_id'],cpop=o,candidate=c,raw_only=r))
save('validation/changed_events.json',paired)
save('assessment.json',dict(status='completed_provisional_real_validation_pilot',selected_k=freeze['selected_k'],training_safety_passed=freeze['training_safety_passed'],validation_scores=stats,validation_detection_noninferiority=new['false_positive']<=cp['false_positive'] and new['false_negative']<=cp['false_negative'],validation_joint_boundary_better=new['joint_capped_interval_mae_seconds']<cp['joint_capped_interval_mae_seconds'],candidate_matches_raw_only_on_validation=all(all(p['methods']['candidate'][k]==p['methods']['raw_only'][k] for k in ['detected','onset_seconds','recovery_seconds']) for p in pred),production_adopt=False,reason='Small provisional development labels, no physical gold or final test. No production adoption regardless of pilot score.',closed_test_values_read=False,production_changed=False))
print(json.dumps(dict(scores=stats,changed_events=len(paired),production_adopt=False)),flush=True)
