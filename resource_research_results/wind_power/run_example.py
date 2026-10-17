"""Run constructed inputs or one user-supplied wind value; no training."""
from pathlib import Path
import argparse,json,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from wind_curve import evaluate
ap=argparse.ArgumentParser(description='Contemporaneous mixed-operation curve, not forecast or available capacity.')
ap.add_argument('--unit',type=int);ap.add_argument('--wind-mps',type=float);a=ap.parse_args()
parameters=json.loads((BASE/'parameters/kelmarsh_mixed_curve_v1.json').read_text(encoding='utf-8'))
if (a.unit is None)!=(a.wind_mps is None):ap.error('provide both --unit and --wind-mps')
cases=([{'unit':a.unit,'wind_mps':a.wind_mps}] if a.unit is not None else json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))['cases'])
print('Conditional same-row wind/power estimate; original six units only. No control or capacity guarantee.')
for c in cases:print(json.dumps({**c,**evaluate(parameters,c['unit'],c['wind_mps'])},ensure_ascii=False,allow_nan=False))
