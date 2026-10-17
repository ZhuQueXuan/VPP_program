"""Constructed example, works from any current directory using standard Python."""
from pathlib import Path
import json,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'code'))
from room_temperature import predict_temperature
if __name__=='__main__':
    d=json.loads((BASE/'examples/constructed_inputs.json').read_text(encoding='utf-8'))
    print('构造输入示例；不是实测成绩。参数仅对应原试验的两个房间。')
    for example in d['examples']:
        print(json.dumps({'room':example['room'],**predict_temperature(example['inputs'],example['room'])},ensure_ascii=False,indent=2))
