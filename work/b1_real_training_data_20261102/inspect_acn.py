from pathlib import Path
import pandas as pd,numpy as np,json
HERE=Path(__file__).resolve().parent
manifest=[]
for fn in ['acn_early_screening_manifest.json','acn_screening_manifest.json']:
    p=HERE/fn
    if p.exists():manifest+=json.loads(p.read_text(encoding='utf-8'))
out=[];seen=set()
for r in manifest:
    if r['path'] in seen:continue
    seen.add(r['path']);df=pd.read_csv(HERE/r['local'],compression='gzip');summary=dict(path=r['path'],local=r['local'],rows=len(df),columns=list(df.columns),nonnull={k:int(v) for k,v in df.notna().sum().items()})
    if len(df):
        stamp=pd.to_datetime(df.iloc[:,0],utc=True,errors='coerce');dt=stamp.diff().dt.total_seconds();summary.update(time_parse_fail=int(stamp.isna().sum()),time_start=str(stamp.min()),time_end=str(stamp.max()),median_sample_seconds=float(dt.median()),duplicate_timestamps=int(stamp.duplicated().sum()),backward_timestamps=int((dt<0).sum()))
    for col in ['Charging Current (A)','Actual Pilot (A)','Voltage (V)','Power (kW)']:
        if col not in df:continue
        x=pd.to_numeric(df[col],errors='coerce');summary.setdefault('numeric',{})[col]=dict(nonnull=int(x.notna().sum()),unique=int(x.nunique()),min=float(x.min()) if x.notna().any() else None,max=float(x.max()) if x.notna().any() else None,changes=int((x.diff().abs()>.01).sum()))
    out.append(summary);print(json.dumps(dict(file=Path(r['path']).name,rows=len(df),columns=summary['columns'],nonnull=summary['nonnull'],sampling=summary.get('median_sample_seconds'))),flush=True)
(HERE/'acn_screening_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
