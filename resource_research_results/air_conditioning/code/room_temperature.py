"""Same-test-bed conditional next-label predictor; not a control/capacity model."""
from pathlib import Path
import json,math
FEATURES=('T_prev_C','T_now_C','Tout_C','P_now_W','T_other_C')
def load_parameters():
    return json.loads((Path(__file__).resolve().parents[1]/'parameters/dual_zone_temperature_v1.json').read_text(encoding='utf-8'))
def predict_temperature(inputs,room,parameters=None):
    """Five finite current/history inputs; room=1or2 of ORIGINAL test bed only.

    Current published P and temperatures assumed available at label; actual
    aggregation/publication timing is unverified. W inputs are converted to kW.
    Range flags describe training ranges, never physical/comfort guarantees.
    """
    p=load_parameters() if parameters is None else parameters
    if str(room) not in ('1','2'):raise ValueError('Only original experimental room1or2 has verified parameters')
    for k in FEATURES:
        value=inputs.get(k)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Finite numeric '+k+' required')
    r=p['rooms'][str(room)];coefficients=r['coefficients']
    if len(coefficients)!=5 or not all(isinstance(c,(int,float)) and not isinstance(c,bool) and math.isfinite(c) for c in coefficients):raise ValueError('Exactly5finite coefficients required')
    now=inputs['T_now_C'];delta=now-inputs['T_prev_C']
    x=[1.,delta,inputs['Tout_C']-now,inputs['P_now_W']/1000.,inputs['T_other_C']-now]
    prediction=now+sum(c*v for c,v in zip(coefficients,x))
    trend=now+delta
    if not math.isfinite(prediction) or not math.isfinite(trend):raise ValueError('Derived forecast overflow; inputs outside numerical limits')
    return {'persistence_C':now,'trend_C':trend,'predicted_next_label_C':prediction,
      'outside_training_input_range':any(not r['input_ranges'][k][0]<=inputs[k]<=r['input_ranges'][k][1] for k in FEATURES),
      'horizon_seconds_in_source':300,'online_lead_time_verified':False,'dispatch_capacity_verified':False}
