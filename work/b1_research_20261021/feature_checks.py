"""Independent arithmetic/semantic development checks, no main study data."""
from __future__ import annotations
import json
import math
from pathlib import Path
from features import extract


def run_checks():
    checks = []
    def check(case, field, actual, expected, tol=1e-10):
        if isinstance(expected, float):
            passed = actual is not None and math.isclose(actual, expected, abs_tol=tol, rel_tol=tol)
        else:
            passed = actual == expected
        checks.append({'case': case, 'field': field, 'actual': actual,
                       'expected': expected, 'passed': passed})
        if not passed:
            raise AssertionError(f'{case}.{field}: {actual!r} != {expected!r}')
    def panel(pieces=(), end=3600):
        # Independent rectangular construction; expected values below are
        # closed-form width*height, not output from a second extractor.
        t = list(range(0, end+1, 10))
        reduction = [sum(level for start, stop, level in pieces if start <= left < stop) for left in t[:-1]]
        return t, [3.0]*(len(t)-1), [3.0-v for v in reduction]
    def evaluate(name, pieces=(), end=3600):
        values = panel(pieces, end)
        answer = extract(*values)
        check(name, 'coverage', answer['request_coverage'], 1.0)
        return answer

    a=evaluate('refusal')
    check('refusal','Y',a['Y'],0.0)
    check('refusal','stage',a['stage'],'no_response')
    for field in ['onset_interval_s','onset_delay_interval_s','onset_confirmation_s','power_recovery_time_s','energy_recovery_time_s']:
        check('refusal',field,a[field],None)
    for field in ['power_recovery_status','energy_recovery_status']:
        check('refusal',field,a[field],'not_applicable')

    a=evaluate('rectangle',[(600,1800,1.5)])
    check('rectangle','Y',a['Y'],1.0)
    check('rectangle','energy',a['request_net_kwh'],0.5)
    check('rectangle','stage',a['stage'],'response')
    check('rectangle','onset bracket',a['onset_interval_s'],[600,600])
    check('rectangle','onset confirm',a['onset_confirmation_s'],630)
    check('rectangle','power recovery',a['power_recovery_time_s'],1800)
    check('rectangle','power confirm',a['power_recovery_confirmation_s'],1830)
    check('rectangle','energy status',a['energy_recovery_status'],'right_censored')
    check('rectangle','energy time',a['energy_recovery_time_s'],None)
    check('rectangle','debt',a['remaining_debt_kwh'],0.5)

    a=evaluate('delayed',[(660,1800,1.5),(1800,2940,-1.5)])
    check('delayed','Y',a['Y'],0.95)
    check('delayed','onset bracket',a['onset_interval_s'],[650,660])
    check('delayed','delay bracket',a['onset_delay_interval_s'],[50,60])
    check('delayed','onset confirm',a['onset_confirmation_s'],690)
    check('delayed','energy recovered',a['energy_recovery_time_s'],2940.0)
    check('delayed','power recovered',a['power_recovery_time_s'],2940)

    a=evaluate('partial',[(600,1800,0.75),(1800,3000,-0.75)])
    check('partial','Y',a['Y'],0.5)
    check('partial','stage',a['stage'],'partial')
    check('partial','target',a['target_interval_s'],None)
    check('partial','energy',a['request_net_kwh'],0.25)
    check('partial','rebound',a['post_rebound_kwh'],0.25)
    check('partial','remaining debt',a['remaining_debt_kwh'],0.0)

    a=evaluate('full_rebound',[(600,1800,1.5),(1800,3000,-1.5)])
    check('full_rebound','request energy',a['request_net_kwh'],0.5)
    check('full_rebound','rebound energy',a['post_rebound_kwh'],0.5)
    check('full_rebound','Y excludes rebound',a['Y'],1.0)
    check('full_rebound','power status',a['power_recovery_status'],'recovered')
    check('full_rebound','energy status',a['energy_recovery_status'],'recovered')
    check('full_rebound','energy time',a['energy_recovery_time_s'],3000.0)

    a=evaluate('short_post',[(600,1800,1.5),(1800,3000,-1.5)],2100)
    check('short_post','Y',a['Y'],1.0)
    for field in ['power_recovery_status','energy_recovery_status']:
        check('short_post',field,a[field],'right_censored')
    check('short_post','remaining debt',a['remaining_debt_kwh'],0.375)
    check('short_post','power time',a['power_recovery_time_s'],None)
    check('short_post','energy time',a['energy_recovery_time_s'],None)

    a=evaluate('no_post',[(600,1800,1.5)],1800)
    check('no_post','power status',a['power_recovery_status'],'right_censored')
    check('no_post','energy status',a['energy_recovery_status'],'right_censored')

    args=panel([(600,1800,1.5)])
    args[2][90]=None
    a=extract(*args)
    check('missing_request','Y',a['Y'],None)
    check('missing_request','stage',a['stage'],'unavailable')
    check('missing_request','coverage',a['request_coverage'],1190/1200)
    check('missing_request','energy status',a['energy_recovery_status'],'unavailable')

    args=panel([(600,1800,1.5)])
    args[2][200]=float('nan')
    a=extract(*args)
    check('missing_post','Y still computable',a['Y'],1.0)
    check('missing_post','energy status',a['energy_recovery_status'],'unavailable')
    check('missing_post','rebound',a['post_rebound_kwh'],None)

    a=evaluate('negative_Y',[(600,1800,-0.75)])
    check('negative_Y','Y',a['Y'],-0.5)
    check('negative_Y','negative energy',a['request_negative_kwh'],-0.25)
    check('negative_Y','stage',a['stage'],'no_response')
    a=evaluate('overdelivery',[(600,1800,2.25)])
    check('overdelivery','Y',a['Y'],1.5)
    check('overdelivery','energy',a['request_net_kwh'],0.75)

    a=evaluate('short_spike',[(600,620,1.5)])
    check('short_spike','Y not thresholded',a['Y'],1/60)
    check('short_spike','stage',a['stage'],'no_response')
    check('short_spike','delay',a['onset_delay_interval_s'],None)
    a=evaluate('below_threshold',[(600,1800,0.1)])
    check('below_threshold','Y preserved',a['Y'],1/15)
    check('below_threshold','stage',a['stage'],'no_response')

    # Unequal interval widths: explicit 600*1 + 600*2 kW*s =1800.
    a=extract([0,600,1200,1800,3600],[3]*4,[3,2,1,3])
    check('irregular_grid','Y by actual duration',a['Y'],1.0)
    check('irregular_grid','energy',a['request_net_kwh'],0.5)
    for label,args in [('mismatched',([0,10],[3,3],[3,3])),('unordered',([0,10,5],[3,3],[3,3]))]:
        try:
            extract(*args)
            got=False
        except ValueError:
            got=True
        check(label,'reject invalid input',got,True)
    out={'identity':'development_constructed_checks_only',
         'main_study_test_read':False, 'cases':len(set(x['case'] for x in checks)),
         'checks':len(checks),'passed':all(x['passed'] for x in checks),
         'details':checks,
         'limitations':['Threshold no_response does not identify true refusal.',
                        'Energy recovery is cumulative relative-reference debt, not an independently measured service state.',
                        'Dwell covers full intervals, confirmation is the third interval end.',
                        'These constructed arithmetic checks do not establish real EV performance.']}
    destination=Path(__file__).with_name('feature_checks.json')
    destination.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ['details','limitations']},ensure_ascii=False))
    return out

if __name__=='__main__':
    run_checks()
