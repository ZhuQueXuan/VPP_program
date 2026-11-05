from pathlib import Path
import json, numpy as np, pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
HERE.mkdir(exist_ok=True)
samples=json.loads((ROOT/'work/b1_real_labeling_20261102/samples.json').read_text(encoding='utf-8'))
rows=[]
for s in samples:
    assert s['split'] in ['training','validation']
    df=pd.read_csv(ROOT/s['local'],compression='gzip')
    vals={k:pd.to_numeric(df[k],errors='coerce').to_numpy() for k in ['Charging Current (A)','Actual Pilot (A)','Power (kW)','Voltage (V)']}
    i=vals['Charging Current (A)'];p=vals['Power (kW)'];v=vals['Voltage (V)'];l=vals['Actual Pilot (A)']
    finite=np.isfinite(i)&np.isfinite(p)&np.isfinite(v)
    resid=p[finite]-i[finite]*v[finite]/1000
    t=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True)
    row=dict(case=s['case'],split=s['split'],source_path=s['source_path'],station_group=s['station_group'],columns=list(df.columns),rows=len(df),median_gap_seconds=float(t.diff().dt.total_seconds().median()),unique_voltage=int(pd.Series(v).nunique()),voltage_finite=int(np.isfinite(v).sum()),power_iv_residual_max_kw=float(np.max(abs(resid))) if len(resid) else None,power_iv_residual_median_kw=float(np.median(abs(resid))) if len(resid) else None,pilot_zero_positive_current=int(np.sum((l==0)&(i>1))),pilot_zero_positive_power=int(np.sum((l==0)&(p>.1))))
    rows.append(row)
    if s['case'] in [5,18,30,34,62]:
        ix=s['raw_row_index'];print(json.dumps(dict(case=s['case'],station=s['station_group'],columns=list(df.columns),anchor_rows=df.iloc[max(0,ix-1):ix+2].astype(object).where(df.iloc[max(0,ix-1):ix+2].notna(),None).values.tolist(),audit=row),ensure_ascii=False),flush=True)
(HERE/'channel_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(files=len(rows),power_iv_exact_files=sum(r['power_iv_residual_max_kw'] is not None and r['power_iv_residual_max_kw']<1e-9 for r in rows),constant_voltage_files=sum(r['unique_voltage']==1 for r in rows),zero_limit_positive_power_files=sum(r['pilot_zero_positive_power']>0 for r in rows))),flush=True)
