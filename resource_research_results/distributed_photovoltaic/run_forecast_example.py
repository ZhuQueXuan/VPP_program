"""Constructed example powers, not additional observations or evaluation data."""
from pathlib import Path
import json,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from clear_sky_forecast import SiteGeometry,MODEL_SETTINGS,forecast_next_labels

def main():
    p=json.loads((BASE/'parameters/pvdaq1239_smart_geometry_v1.json').read_text(encoding='utf-8'))
    assert p['fixed_model_settings']==MODEL_SETTINGS
    site=SiteGeometry(**p['site_geometry'])
    examples=json.loads((BASE/'examples/constructed_forecast_inputs.json').read_text(encoding='utf-8'))
    result=forecast_next_labels([r['current_power_W'] for r in examples],[r['origin_time'] for r in examples],site)
    print('Constructed inputs; conditional next published label, not verified online15-minute lead time.')
    print(result.to_string(index=False))

if __name__=='__main__':main()
