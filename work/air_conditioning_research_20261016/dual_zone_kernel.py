"""Fixed5-coefficient conditional next-label room-temperature calculation."""
import math
FEATURES=('T_prev_C','T_now_C','Tout_C','P_now_W','T_other_C')
def predict_temperature(inputs,room,parameters):
    if str(room) not in parameters['rooms']:raise ValueError('Unvalidated room identifier')
    for k in FEATURES:
        v=inputs.get(k)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Finite numeric '+k+' required')
    r=parameters['rooms'][str(room)];tn=inputs['T_now_C'];diff=tn-inputs['T_prev_C']
    x=[1.,diff,inputs['Tout_C']-tn,inputs['P_now_W']/1000.,inputs['T_other_C']-tn]
    predicted=tn+sum(c*v for c,v in zip(r['coefficients'],x))
    return {'B_P_C':tn,'B_TREND_C':tn+diff,'M_HEAT5_C':predicted,
      'outside_training_input_range':any(not r['input_ranges'][k][0]<=inputs[k]<=r['input_ranges'][k][1] for k in FEATURES),
      'scope':'Conditional next published5min label of same experimental room, not counterfactual control or verified online lead time.'}
