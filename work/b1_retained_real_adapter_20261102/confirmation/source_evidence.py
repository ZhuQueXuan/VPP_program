from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;rows=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))
ranges={129:(60,72),130:(59,76),132:(23,35),133:(0,40),134:(57,73),147:(125,145),155:(7,19),156:(7,22)}
for r in rows:
    if r['case'] not in ranges:continue
    lo,hi=ranges[r['case']]
    pts=[[t,i,p,l] for t,i,p,l in zip(r['relative_seconds'],r['current_a'],r['power_kw'],r['pilot_a']) if -9<=t<=12 or lo<=t<=hi]
    print(json.dumps(dict(case=r['case'],rows=pts)),flush=True)
