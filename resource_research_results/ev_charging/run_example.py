"""Constructed calls only, not newly measured charging or control results."""
from pathlib import Path
import json,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from common_command_mapping import Calibration,map_common_command
params=json.loads((BASE/'parameters/evtec_common_command_v1.json').read_text(encoding='utf-8'))
examples=json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))
for r in examples:
    calibration=Calibration(**params['groups'][r['group']]['calibration'])
    print(json.dumps({'constructed_example':r,**map_common_command(*r['commands_kW'],calibration)},ensure_ascii=False))
