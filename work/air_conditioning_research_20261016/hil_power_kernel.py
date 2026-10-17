"""Same-record AC electric-power reconstruction; not capacity or forecast."""
import math

def reconstruct_power(cooling_capacity_kW,outdoor_temperature_C,parameters):
    if not all(math.isfinite(x) for x in (cooling_capacity_kW,outdoor_temperature_C)):
        raise ValueError('Finite source-calculated thermal kW and measured outdoor C required.')
    q=cooling_capacity_kW;t=outdoor_temperature_C
    b=parameters['B_COP'];m=parameters['M_TEMP'];ranges=parameters['training_ranges']
    fixed=b[0]+b[1]*q;corrected=m[0]+m[1]*q+m[2]*q*(t-35.)
    return {'B_COP_W':fixed,'M_TEMP_W':corrected,
      'outside_training_input_range':not(ranges['Q_kW'][0]<=q<=ranges['Q_kW'][1] and ranges['Tout_C'][0]<=t<=ranges['Tout_C'][1]),
      'negative_temperature_corrected_estimate':corrected<0}
