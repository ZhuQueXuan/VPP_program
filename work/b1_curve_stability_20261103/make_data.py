"""Version the retained simulation family prospectively; no data are drawn."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE.parent/'b1_curve_spline_pilot_20261103/data.py'
text=source.read_text(encoding='utf-8')
text=text.replace("'zero_effect', 'sigmoidal', 'assignment_mixture',", "'zero_effect', 'sigmoidal', 'assignment_mixture', 'noisy_nonmonotone', 'two_peak',")
text=text.replace("if kind == 'nonmonotone':", "if kind in ('nonmonotone', 'noisy_nonmonotone'):")
text=text.replace("    if kind == 'zero_effect':", "    if kind == 'two_peak':\n        return 1.25 + 0.9*np.sin(4*np.pi*a/2.4) + 0.35*a, 0.9*(4*np.pi/2.4)*np.cos(4*np.pi*a/2.4) + 0.35\n    if kind == 'zero_effect':")
text=text.replace("beta_fraction = betaincinv(20.0 * mu, 20.0 * (1.0 - mu), beta_uniform)",
    "concentration = 5.0 if kind == 'noisy_nonmonotone' else 20.0\n    beta_fraction = betaincinv(concentration * mu, concentration * (1.0 - mu), beta_uniform)")
text=text.replace("f'spline-{seed}-user", "f'stability-{seed}-user")
text=text.replace('Fresh continuous-compensation SCM for a paired final-smoother comparison.',
    'Prospective extension of the retained continuous-compensation simulation family.')
text=text.replace('All values are simulated.',
    'New confirmation includes a higher-variance positive-duration mechanism and a two-peak signal.\nAll values are simulated.')
assert "kind == 'two_peak'" in text and 'concentration = 5.0' in text
with (HERE/'data.py').open('x',encoding='utf-8') as f:f.write(text)
print('Versioned data generator; no samples generated')
