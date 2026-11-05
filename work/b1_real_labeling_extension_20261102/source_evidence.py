from pathlib import Path
import json,pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
samples=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))
returns={70:138,77:63,79:12,80:9,95:33,99:28,104:20,113:170,115:63,123:4.7,125:14}
positive=[70,77,79,80,82,84,87,91,94,95,99,101,102,104,110,113,115,118,119,120,123,124,125,126]
for s in samples:
    if s['case'] not in positive:continue
    end=returns.get(s['case'])
    rows=[[t,i,p,l] for t,i,p,l in zip(s['relative_seconds'],s['current_a'],s['power_kw'],s['pilot_a']) if -10<=t<=16 or end is not None and end-7<=t<=end+6]
    print(json.dumps(dict(case=s['case'],rows=rows)),flush=True)
for s in samples:
    if s['case']!=123:continue
    print('CASE123_CONTEXT',json.dumps({k:s[k] for k in ['source_path','local','station_group','split']},ensure_ascii=False),flush=True)
    for filename in ['acn_official_Caltech_2020.json','acn_official_Office_1_2019.json','acn_official_Office_1_2020.json']:
        obj=json.loads((ROOT/'work/b1_real_training_data_20261102/source_documents'/filename).read_text(encoding='utf-8'))
        rows=obj.get('_items',[]) if isinstance(obj,dict) else obj
        match=[r for r in rows if r.get('sessionID','').replace('_','-').replace(' ','T').replace(':','-').replace('.','-')+'.csv.gz'==Path(s['source_path']).name]
        for r in match:print('OFFICIAL_MATCH',json.dumps({k:r.get(k) for k in ['sessionID','stationID','spaceID','siteID','clusterID','connectionTime','disconnectTime','kWhDelivered']}),flush=True)
