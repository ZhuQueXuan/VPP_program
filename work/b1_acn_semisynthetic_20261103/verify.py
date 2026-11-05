"""Recompute source links, duration labels and curve scores from saved artifacts."""
from study import HERE, ROOT, GRID, MECHANISMS, load, save, sha, np, pd


def integral(context, points):
    starts = np.asarray(context['starts'])
    ends = np.asarray(context['ends'])
    eligible = np.asarray(context['power']) >= .15
    completed = np.r_[0., np.cumsum((ends - starts) * eligible)]
    index = np.minimum(np.searchsorted(ends, points, side='right'), len(ends)-1)
    return completed[index] + (np.clip(points, starts[index], ends[index])-starts[index]) * eligible[index]


def main():
    result = load(HERE/'results.json')
    training = load(HERE/'training_contexts.json')
    validation = load(HERE/'validation_contexts.json')
    source_points = 0
    for context in training + validation:
        source = ROOT/context['source']
        assert sha(source) == context['source_sha256']
        raw = pd.read_csv(source, usecols=['Unnamed: 0','Power (kW)','Actual Pilot (A)'])
        indices = context['source_indices']
        np.testing.assert_array_equal(raw['Power (kW)'].iloc[indices], context['power'])
        np.testing.assert_array_equal(raw['Actual Pilot (A)'].iloc[indices], context['pilot'])
        origin = pd.Timestamp(context['time_origin'])
        times = (pd.to_datetime(raw['Unnamed: 0'], utc=True, format='mixed') - origin).dt.total_seconds().to_numpy()
        np.testing.assert_array_equal(times[indices], context['raw_time_seconds'])
        np.testing.assert_array_equal(times[np.asarray(indices)+1], context['raw_next_time_seconds'])
        prefix = context['history_source_indices']
        assert np.max(times[prefix]) < context['anchor']
        np.testing.assert_allclose(context['X'][:2], [raw['Power (kW)'].iloc[prefix].median(), raw['Actual Pilot (A)'].iloc[prefix].median()])
        assert context['starts'][0] == 0 and context['ends'][-1] == 1800
        np.testing.assert_array_equal(context['starts'][1:], context['ends'][:-1])
        source_points += len(indices)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.8), sharey=True)
    errors = {}
    examples = {}
    checked = 0
    for ax, mechanism in zip(axes, MECHANISMS):
        entries = [r for r in result['rows'] if r['mechanism'] == mechanism]
        actual = np.asarray(load(HERE/(mechanism+'_truth.json'))['validation_mean_seconds'])
        curves = {'baseline': [], 'spline': []}
        for entry in entries:
            name = f"{mechanism}_{entry['seed']}"
            events = load(HERE/(name+'_training_events.json'))
            for event in events:
                c = training[event['context']]
                reconstructed = integral(c, event['simulated_end']) - integral(c, event['simulated_start']) if event['simulated_participation'] else 0.
                assert abs(reconstructed - event['effective_response_seconds']) < 1e-8
                checked += 1
            baseline = load(HERE/(name+'_baseline.json'))['causal_curve']
            candidate = load(HERE/(name+'_spline_query.json'))['curve']
            for method, curve in [('baseline', baseline), ('spline', candidate)]:
                mean = np.asarray(curve['mean_outcomes'])
                errors_at_dose = mean - actual
                recomputed = np.linalg.norm(errors_at_dose-errors_at_dose[0])/np.sqrt(len(actual))
                assert abs(recomputed-entry[method]['contrast_rmse_seconds']) < 1e-9
                curves[method].append(mean)
        errors[mechanism] = {key: float(np.mean([r[key]['contrast_rmse_seconds'] for r in entries])) for key in curves}
        examples[mechanism] = {f'{GRID[i]:.2f}': float(actual[i]) for i in (0,10,20,30)}
        ax.plot(GRID, actual, color='#202124', linewidth=2.3, label='Simulated truth')
        for method, label, color in [('baseline','Local linear DR','#de8426'),('spline','Retained spline','#1670ab')]:
            ax.plot(GRID, np.mean(curves[method], axis=0), label=label, color=color)
        ax.set_title(mechanism.replace('_',' ').capitalize())
        ax.set_xlabel('Simulated compensation (CNY/kWh)')
        ax.grid(alpha=.18)
    axes[0].set_ylabel('Mean effective response duration (s)')
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle('Continuous EV compensation pilot on measured ACN backgrounds')
    fig.tight_layout()
    fig.savefig(HERE/'response_curves.png', dpi=170)
    plt.close(fig)
    means = {method: float(np.mean([r[method]['contrast_rmse_seconds'] for r in result['rows']])) for method in curves}
    save('verification.json', dict(passed=True, checked_real_contexts=len(training)+len(validation), checked_source_points=source_points,
        checked_effective_duration_labels=checked, summary_rmse_seconds=means, by_mechanism=errors, illustrative_truth_seconds=examples,
        spline_wins=sum(r['spline']['contrast_rmse_seconds']<r['baseline']['contrast_rmse_seconds'] for r in result['rows'])))
    print(means, errors, examples, checked, source_points)


if __name__ == '__main__':
    main()
