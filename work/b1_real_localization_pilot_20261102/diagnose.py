from common import *
registry={r['event_id']:r for r in read(VIEW/'registry.json')}
rows=load('validation');pred=read(HERE/'validation/predictions.json');diagnosis=[]
for r,p in zip(rows,pred):
    a=r['provisional_targets'];cp=p['methods']['cpop'];new=p['methods']['candidate'];case=registry[r['event_id']]['case']
    if a['recovery_completion_bracket_seconds'] is not None or a['anchor_visible_following']==0 and new['detected']:
        entry=dict(case=case,event_id=r['event_id'],target=a,methods=p['methods'])
        diagnosis.append(entry)
        print(json.dumps(dict(case=case,onset=a['onset_bracket_seconds'],recovery=a['recovery_completion_bracket_seconds'],anchor_target=a['anchor_visible_following'],cp=cp,new=new)),flush=True)
save('diagnosis.json',dict(cases=diagnosis,analysis_only_no_parameter_change=True))
