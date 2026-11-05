from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;rows=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))
for r in rows:
    if r['case'] not in [2,5,10,18,30,32,33,34,54,62,63]:continue
    points=[]
    for t,i,p,l in zip(r['relative_seconds'],r['current_a'],r['power_kw'],r['pilot_a']):
        if -12<=t<=16 or (r['case']==54 and 114<=t<=132) or (r['case']==62 and 99<=t<=119):points.append([t,i,p,l])
    print(json.dumps(dict(case=r['case'],n=len(r['relative_seconds']),rows=points)),flush=True)
