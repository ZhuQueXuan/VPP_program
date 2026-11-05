"""Check the existing uncertainty band's decision tradeoff on fresh cohorts.

Fixed rule before scoring: on the same 81 amounts and with the existing
conditional sampling band, return reached if any lower bound meets 120 s,
below if all upper bounds are below it, and uncertain otherwise. Admit this
optional demo decision only if errors decrease and coverage is at least 60%.
This is a finite-grid simulation check, with no uncertainty guarantee in use.
"""
import evaluate as ev
from b1_algorithm.effects.frozen import fit_continuous_model, query_continuous_model


def main():
    results = []
    cases = [('randomized', 1.), ('observed_confounding', 1.), ('nonmonotone', 1.),
             ('zero_effect', 1.), ('observed_confounding', .25), ('observed_confounding', .4)]
    for seed in range(90414001, 90414009):
        for kind, scale in cases:
            data = ev.generate(seed, kind, ev.SPEC['users_per_cohort'], ev.SPEC['events_per_user'])
            x = ev.np.asarray(data['X'])[:, :2]
            truth = scale * ev.contrast(ev.truth_function(x, kind), ev.SEARCH)
            actual = bool(truth.max() >= ev.TARGET)
            frozen = fit_continuous_model(x, data['treatment'], ev.np.array(data['outcome']) * scale,
                data['users'], dose_domain=ev.DOMAIN, reference_dose=ev.REFERENCE, incentive_unit='元/千瓦时',
                task=ev.TASK, continuous_assignment=True, assumptions=ev.assumptions(kind),
                config=ev.cfg(seed), known_density=data['known_density'])
            q = query_continuous_model(frozen, ev.SEARCH)
            row = dict(seed=seed, mechanism=kind, scale=scale, truth_reached=actual,
                       truth_max_seconds=float(truth.max()), point=None, guarded=None)
            if q['curve'] is not None:
                estimate = max(q['curve']['contrasts'])
                low, high = max(q['inference']['lower']), max(q['inference']['upper'])
                row.update(point=estimate >= ev.TARGET, guarded=True if low >= ev.TARGET else
                           (False if high < ev.TARGET else None), point_max=estimate,
                           band_lower_max=low, band_upper_max=high)
            results.append(row)

    def summarize(key):
        valid = [r for r in results if r[key] is not None]
        return dict(decisions=len(valid), wrong=sum(r[key] != r['truth_reached'] for r in valid),
                    false_reach=sum(r[key] and not r['truth_reached'] for r in valid),
                    missed=sum(not r[key] and r['truth_reached'] for r in valid))

    point, guarded = summarize('point'), summarize('guarded')
    ev.save(ev.HERE / 'target_check.json', dict(cases=results, independent_seed_blocks=8, point=point,
        guarded=guarded, demo_admission=guarded['wrong'] < point['wrong'] and guarded['decisions'] >= .60 * len(results)))
    print(point, guarded)


if __name__ == '__main__':
    main()
