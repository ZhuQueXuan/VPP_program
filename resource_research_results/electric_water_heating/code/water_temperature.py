"""Fixed predictor for original 150L tank, standard library only.

The caller supplies the latest observation of a completed published minute,
the comparable observation five clock labels earlier, and synchronous current
sensor readings. No true300s lead time, power/energy or control guarantee.
"""
import math


def predict(parameters, temperature_C, previous_temperature_C, heating_flag,
            chamber_temperature_1_C, chamber_temperature_2_C,
            upper_sensor_C, lower_sensor_C):
    values=[temperature_C,previous_temperature_C,chamber_temperature_1_C,
            chamber_temperature_2_C,upper_sensor_C,lower_sensor_C]
    for value in values:
        if isinstance(value,bool):raise ValueError('temperature must be a finite number in0..100C')
    try:values=[float(x) for x in values]
    except (TypeError,ValueError):raise ValueError('temperature must be numeric') from None
    if not all(math.isfinite(v) and 0<=v<=100 for v in values):
        raise ValueError('temperature outside the admitted sensor range0..100C')
    if heating_flag not in [0,1]:raise ValueError('published heating_flag must be0or1')
    t,prev,c1,c2,upper,lower=values
    x=[1.,t-prev,float(heating_flag),(c1+c2)/2-t,upper-t,lower-t]
    beta=parameters['beta']
    y=t+sum(a*b for a,b in zip(x,beta))
    outside=any(v<lo or v>hi for v,lo,hi in zip(x,parameters['feature_min'],parameters['feature_max']))
    return {'temperature_C':y,'outside_training_feature_range':outside,
            'label_horizon_minutes':5,'exact_physical_horizon_validated':False}
