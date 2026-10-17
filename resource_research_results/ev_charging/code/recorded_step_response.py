"""Features of an observed phase-current step; not dispatch latency truth."""
import math,statistics

def analyze_recorded_step(relative_time_us,phase_current_A,pre_current_A,previous_command_A,new_command_A):
    """Analyse a complete[0,15s) record under the frozen KIT study conditions.

    PRE5s quality/constant commands and observed PRE median>=1A are upstream
    preconditions.10/90 refer to command-step magnitude, not model accuracy.
    """
    times=list(relative_time_us);values=list(phase_current_A)
    if len(times)!=len(values) or len(times)<2:raise ValueError('Equal nonempty time/current arrays required.')
    numbers=values+[pre_current_A,previous_command_A,new_command_A]
    if not all(math.isfinite(v) for v in numbers):raise ValueError('Finite currents and commands required.')
    if any(not math.isfinite(t) or int(t)!=t or t<0 for t in times):raise ValueError('Relative integer microseconds required.')
    if times[0]>50000 or times[-1]<14950000 or times[-1]>=15000000:raise ValueError('Complete[0,15s) window required.')
    if any(not 0<b-a<=50000 for a,b in zip(times,times[1:])):raise ValueError('No sorting, filling or gaps>50ms allowed.')
    if pre_current_A<1 or min(previous_command_A,new_command_A)<6 or abs(new_command_A-previous_command_A)<2:
        raise ValueError('Outside the frozen preceding-load/command-step study conditions.')
    delta=new_command_A-previous_command_A;sign=1 if delta>0 else -1;magnitude=abs(delta)
    progress=[sign*(v-pre_current_A)/magnitude for v in values]
    def crossing(level):
        start=None
        for i,(t,value) in enumerate(zip(times,progress)):
            if t>10100000:break
            if value<level:start=None;continue
            if start is None:start=i
            if times[start]>10000000:return None
            if t-times[start]>=100000:
                return {'sample_s':times[start]/1e6,'interval_lower_s':times[start-1]/1e6 if start else 0.,
                        'interval_upper_s':times[start]/1e6,'confirmed_s':t/1e6}
        return None
    c10=crossing(.1);c90=crossing(.9)
    tail=[v for t,v in zip(times,values) if 10000000<=t<15000000]
    if not tail:raise ValueError('Missing final5-second observation window.')
    steady=statistics.median(tail)
    result={'t10_observed':c10 is not None,'t90_observed':c90 is not None,
            'transition_10_to90_s':c90['sample_s']-c10['sample_s'] if c10 and c90 else None,
            'steady_current_A':steady,'steady_error_from_new_command_A':steady-new_command_A,
            'steady_abs_error_A':abs(steady-new_command_A),'post_current_min_A':min(values),'post_current_max_A':max(values),
            'directional_overshoot_A':max(0.,max(sign*(v-(pre_current_A+delta)) for v in values)),
            'crossing_status':'observed90pct_command_step' if c90 else 'not_observed90pct_within10s'}
    for name,c in (('t10',c10),('t90',c90)):
        for field in ('sample_s','interval_lower_s','interval_upper_s','confirmed_s'):
            result[name+'_'+field]=c[field] if c else None
    return result
