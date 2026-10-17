from pathlib import Path
import sys,json,argparse
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from water_temperature import predict
ap=argparse.ArgumentParser(description='Original150L tank conditional5clock-label-minute temperature estimator,notcontrol or capacity.')
ap.add_argument('--input',help='JSONobject with current/past input fields; omitted uses constructed examples')
a=ap.parse_args();parameters=json.loads((BASE/'parameters/horizontal_150L_temperature_v1.json').read_text(encoding='utf-8'))
cases=([json.loads(Path(a.input).read_text(encoding='utf-8'))] if a.input else json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))['cases'])
for case in cases:print(json.dumps({'inputs':case,'result':predict(parameters,**case)},ensure_ascii=False,allow_nan=False))
