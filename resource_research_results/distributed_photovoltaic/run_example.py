"""Constructed input examples, not observed performance or additional validation."""
from pathlib import Path
import json,sys

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from dc_power import ModuleParameters,reconstruct_module_dc

def main():
    data=json.loads((BASE/'parameters/iea_supsi_mono_si.json').read_text(encoding='utf-8'))
    params=ModuleParameters(**data['model_parameters'])
    cases=json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))
    print('Constructed examples; module DC reconstruction, not future forecast or AC reserve.')
    for case in cases:
        result=reconstruct_module_dc(case['poa_W_m2'],case['back_temperature_C'],params)
        print(json.dumps({'example':case['name'],**result},ensure_ascii=False))

if __name__=='__main__':main()
