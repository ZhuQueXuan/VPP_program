from pathlib import Path
import importlib.util,json
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('retained_state_v2',HERE/'state_v2/adapter.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);B=A.B;P=A.P
parent=B.read(HERE/'model.json');state=B.read(HERE/'state_v2/model.json')
out={}
for role,rows,curves in [('seen_validation',B.load('validation'),B.read(B.HERE/'validation/native_curves.json')),('additional_development',B.read(HERE/'confirmation/inputs.json'),B.read(HERE/'confirmation/native_curves.json'))]:
    out[role]={}
    for name in ['without_recovery_calibration','without_qualified_rescue']:
        pred=[];cfg=dict(parent,rescue_threshold=0.) if name=='without_qualified_rescue' else parent
        for row in rows:
            cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[])
            estimate=P.infer(row,cp,parent) if name=='without_recovery_calibration' else A.infer(row,cp,cfg,state)
            base=B.predictions([row],curves,3)[0];base['methods']['candidate']=estimate;pred.append(base)
        out[role][name]=B.score(rows,pred)['candidate']
with (HERE/'component_checks.json').open('x',encoding='utf-8') as f:json.dump(B.native(out),f,ensure_ascii=False,indent=2)
print(json.dumps(out),flush=True)
