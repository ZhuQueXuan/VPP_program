"""Replay a frozen development case; no fit, new selection, or test access."""
from pathlib import Path
import argparse, importlib.util, json

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('retained_real_replay', HERE/'state_v2/adapter.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
B = A.B


def replay(case):
    registry = B.read(B.VIEW/'registry.json') + B.read(HERE/'confirmation/samples.json')
    matches = [r for r in registry if r['case'] == case]
    if len(matches) != 1:
        raise ValueError('Case must be one of the retained development cases 1 through160.')
    record = matches[0]
    if case >= 129:
        rows = B.read(HERE/'confirmation/inputs.json')
        curves = B.read(HERE/'confirmation/native_curves.json')
    else:
        rows = B.load(record['split'])
        curves = B.read(B.HERE/record['split']/'native_curves.json')
    row = next(r for r in rows if r['event_id'] == record['event_id'])
    observation = dict(event_id=row['event_id'], model_input=row['model_input'])
    pair = curves.get(row['event_id'], {})
    a = B.arrays(observation)
    parent = B.read(HERE/'model.json')
    state = B.read(HERE/'state_v2/model.json')
    return dict(case=case, role=record['split'], source=record['local'],
                cpop=B.estimate(a, pair.get('cpop', {}).get('prediction', [])),
                labs=B.estimate(a, pair.get('labs', {}).get('prediction', [])),
                adapted=A.infer(observation, pair.get('cpop', {}).get('prediction', []), parent, state))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=int, default=129)
    args = parser.parse_args()
    print(json.dumps(B.native(replay(args.case)), ensure_ascii=False, indent=2, allow_nan=False))
