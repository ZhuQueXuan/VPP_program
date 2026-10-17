"""Audit selected source and fixed diagnostic window; no capacity estimation model."""
from pathlib import Path
import json, hashlib
from collections import Counter
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'downloads'/'rwth_home_capacity_20261014'
SOURCE=DEST/'2017_06_System_ID_01.csv'
RECEIPT=DEST/'selected_month_quality_01.json'
WINDOW=DEST/'system01_first_test_diagnostic_window.csv'
if RECEIPT.exists() or WINDOW.exists():
    raise FileExistsError('quality outputs already exist; no overwrite')
acquired=json.loads((DEST/'selected_member_acquisition_01.json').read_text('utf-8'))
if acquired['status']!='member_acquired_crc_verified':
    raise ValueError('selected member did not pass acquisition CRC')
actual_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
if actual_hash!=acquired['csv_sha256']:
    raise ValueError('raw source changed after acquisition')
fields=['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']
count=0; parts=[]; missing=Counter(); flags=Counter(); intervals=Counter(); finite=Counter()
ranges={f:[float('inf'),float('-inf')] for f in fields}
first=previous=None; columns=None
for chunk in pd.read_csv(SOURCE,chunksize=250000):
    if columns is None:
        columns=list(chunk.columns)
        if columns!=['Time']+fields+['Interpolated']:
            raise ValueError(f'unexpected columns {columns}')
    timestamp=pd.to_datetime(chunk['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
    if first is None: first=timestamp.iloc[0]
    delta=timestamp.diff().dt.total_seconds().dropna()
    intervals.update(float(v) for v in delta)
    if previous is not None: intervals.update([float((timestamp.iloc[0]-previous).total_seconds())])
    previous=timestamp.iloc[-1]
    count+=len(chunk)
    missing.update({k:int(v) for k,v in chunk.isna().sum().items()})
    flags.update(str(v) for v in chunk['Interpolated'])
    for f in fields:
        values=chunk[f].to_numpy(dtype=float)
        finite[f]+=int((~np.isfinite(values)).sum())
        good=values[np.isfinite(values)]
        if len(good): ranges[f][0]=min(ranges[f][0],float(good.min())); ranges[f][1]=max(ranges[f][1],float(good.max()))
    selected=(timestamp>=pd.Timestamp('2017-06-14 12:00:00'))&(timestamp<pd.Timestamp('2017-06-15 12:00:00'))
    parts.append(chunk.loc[selected].copy())
window=pd.concat(parts,ignore_index=True)
wt=pd.to_datetime(window['Time'],format='%d-%b-%Y %H:%M:%S')
window.to_csv(WINDOW,index=False)
test_start=pd.Timestamp('2017-06-14 14:23:39')
at_start=window.loc[wt.eq(test_start)]
if len(at_start)!=1:
    raise ValueError('published test start is not one native CSV row')
numeric=window[fields].to_numpy(dtype=float)
mask=np.isfinite(numeric).all(axis=1)
consistency=window['P_in_W']-window['I_in_A']*window['V_in_V']
# Minute means are diagnostic views only, including original missing/interpolation flags.
minute=window.copy(); minute.index=wt
minute=minute[fields+['Interpolated']].resample('1min').mean()
minute_path=DEST/'system01_first_test_minute_diagnostic.csv'
if minute_path.exists(): raise FileExistsError(minute_path)
minute.to_csv(minute_path)
result={'raw_file':SOURCE.name,'source_sha256':actual_hash,'columns':columns,'rows':count,'start':str(first),'end':str(previous),
        'adjacent_intervals_seconds':dict(intervals),'missing_cells':dict(missing),'nonfinite_numeric':dict(finite),'interpolated_counts':dict(flags),'ranges':ranges,
        'scope':'published source is filtered/interpolated; native 1s rows do not prove fresh raw observations',
        'timezone':'not asserted; native CSV strings and Excel test serial joined within source',
        'diagnostic_window':{'start':'2017-06-14 12:00:00','end_exclusive':'2017-06-15 12:00:00','rows':len(window),
                             'duplicates':int(wt.duplicated().sum()),'missing_cells':{k:int(v) for k,v in window.isna().sum().items()},
                             'interpolated_counts':{str(k):int(v) for k,v in window['Interpolated'].value_counts(dropna=False).items()},
                             'complete_finite_rows':int(mask.sum()),'test_start_row':at_start.to_dict('records'),
                             'P_minus_UI_abs_max_W':float(consistency.abs().max()),'P_minus_UI_abs_mean_W':float(consistency.abs().mean())},
        'published_test_reference':json.loads((DEST/'published_test_reference_check_01.json').read_text('utf-8'))['selected_system_01'][0],
        'no_model_fit':True,'test_end_and_portal_SOC':'not present in CSV; no target-matched endpoint search performed',
        'window_sha256':hashlib.sha256(WINDOW.read_bytes()).hexdigest(),'minute_diagnostic_sha256':hashlib.sha256(minute_path.read_bytes()).hexdigest()}
RECEIPT.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
print(json.dumps(result,ensure_ascii=False))
