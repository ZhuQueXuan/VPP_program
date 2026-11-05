from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
registry={r['event_id']:r for r in read(HERE.parents[1]/'data/ACN_real_user_benchmark_v1_20261102/prepared/observed_localization_pilot_v1_20261102/registry.json')}
blocks=[('seen_validation',read(HERE.parents[1]/'data/ACN_real_user_benchmark_v1_20261102/prepared/observed_localization_pilot_v1_20261102/validation.json'),read(HERE/'state_v2/validation/predictions.json'))]
samples={r['event_id']:r for r in read(HERE/'confirmation/samples.json')};registry.update(samples)
blocks.append(('additional_development',read(HERE/'confirmation/inputs.json'),read(HERE/'confirmation/predictions.json')))
details=[]
for role,rows,pred in blocks:
    for row,p in zip(rows,pred):
        target=row['provisional_targets'];cp=p['methods']['cpop'];new=p['methods']['candidate']
        if target['recovery_completion_bracket_seconds'] is not None:
            entry=dict(role=role,case=registry[row['event_id']]['case'],event_id=row['event_id'],target=target['recovery_completion_bracket_seconds'],cpop=cp['recovery_seconds'],adapted=new['recovery_seconds'],new_state_score=new.get('recovery_state_score'),onset=target['onset_bracket_seconds'],detected_cpop=cp['detected'],detected_adapted=new['detected'])
            details.append(entry);print(json.dumps(entry),flush=True)
(HERE/'recovery_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
