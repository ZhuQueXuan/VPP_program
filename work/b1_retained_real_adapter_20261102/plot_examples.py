"""Show one prospective gain and one prospective regression without changing fits."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
read = lambda name: json.loads((HERE/name).read_text(encoding='utf-8'))
samples = {r['case']: r for r in read('confirmation/samples.json')}
annotations = {r['case']: r for r in read('confirmation/annotations.json')}
predictions = {r['event_id']: r['methods'] for r in read('confirmation/predictions.json')}
curves = read('confirmation/native_curves.json')
fig, axes = plt.subplots(2, 2, figsize=(12, 7.3), sharex='col', constrained_layout=True)
for col, case in enumerate([129, 133]):
    s = samples[case]; ann = annotations[case]; out = predictions[s['event_id']]
    lo, hi = ann['recovery_completion_bracket']['relative_seconds']
    for row, key, title in [(0, 'power_kw', 'Recorded power (kW)'), (1, 'current_a', 'Recorded current (A)')]:
        ax = axes[row, col]
        ax.plot(s['relative_seconds'], s[key], '.-', color='#273f52', lw=1, ms=3, label='Original observations')
        if row == 0:
            ax.plot(s['relative_seconds'], curves[s['event_id']]['cpop']['prediction'], color='#8499ab', lw=1.5, label='Original CPOP fit')
        ax.axvspan(lo, hi, color='#a9dab3', alpha=.55, label='Provisional reviewed bracket')
        ax.axvline(out['cpop']['recovery_seconds'], color='#d18a24', ls='--', lw=1.4, label='Original CPOP return')
        ax.axvline(out['candidate']['recovery_seconds'], color='#8a448c', ls=':', lw=2, label='Adapted return')
        ax.set_ylabel(title); ax.grid(alpha=.18)
    axes[0, col].set_title('Case129: late return corrected (141s to66s)' if case == 129 else 'Case133: new early return (28s to21s)')
    axes[1, col].set_xlabel('Original time relative to selected pilot change (s)')
    axes[1, col].set_xlim((-10, 155) if case == 129 else (-10, 65))
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc='outside lower center', ncols=3, fontsize=9)
fig.suptitle('Frozen additional development windows: benefit and remaining error\nSingle-assistant observation references; not physical effective-duration truth', fontsize=12)
fig.savefig(HERE/'recovery_examples.png', dpi=160)
print(str(HERE/'recovery_examples.png'))
