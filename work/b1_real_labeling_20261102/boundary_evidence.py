from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
rows=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))
returns={5:52,7:16,10:7,11:8,17:67,19:166,20:138,25:67,26:11,31:8,32:13,35:63,36:8,37:56,41:8,49:67,51:110,54:122,62:107}
for r in rows:
    if r['case'] not in returns:continue
    end=returns[r['case']]
    data=[[t,i,p,l] for t,i,p,l in zip(r['relative_seconds'],r['current_a'],r['power_kw'],r['pilot_a']) if -6<=t<=5 or end-9<=t<=end+5]
    print(json.dumps({'case':r['case'],'rows':data}),flush=True)
