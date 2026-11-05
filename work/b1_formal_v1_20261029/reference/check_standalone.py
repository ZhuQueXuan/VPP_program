"""Load only formal code and native artifact in a fresh isolated Python process."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[2]))
from b1_algorithm.reference import ReferenceWindow,load_reference_model,predict_reference
window=ReferenceWindow(**json.loads((ROOT/'query_fixture.json').read_text(encoding='utf-8')))
model=load_reference_model(ROOT/'artifact')
out=predict_reference(model,window)
assert out.reference_status=='available',out.reasons
assert out.counterfactual_identified is False
assert not any(k=='reference_api' or k=='ride' or k.startswith('ride.') for k in sys.modules)
receipt=dict(passed=True,status=out.reference_status,n_intervals=len(out.reference_kw),
             model_id=out.model_id,legacy_or_simulator_module_imported=False,
             task_id=out.task_id,user_id=out.user_id,meter_id=out.meter_id)
(ROOT/'standalone_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
