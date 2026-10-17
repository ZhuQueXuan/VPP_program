"""Independent stdlib CSV/time counts plus source-dictionary clarification."""
from common import *
from collections import Counter,defaultdict
from datetime import datetime
import io,zipfile
qa=BASE/'runs/PLEIA_SOURCE_QA_01';out=BASE/'runs/PLEIA_SOURCE_VERIFY_01';out.mkdir(parents=True,exist_ok=False)
raw=BASE/'downloads/PLEIA_RAW_01/selected_raw';results={}
for table,file in [('sensor','data-sensor.csv'),('hvac','data-hvac.csv'),('meter','data-cons.csv')]:
    counts=Counter();prev={};deltas=Counter();offsets=Counter();modes=Counter();n=0
    with (raw/file).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f,delimiter=';'):
            uid=int(row['IDdevice']);t=datetime.fromisoformat(row['Date']);n+=1;counts[uid]+=1
            offsets[row['Date'][-3:]]+=1
            if uid in prev:
                dt=(t-prev[uid]).total_seconds();deltas['increase' if dt>0 else 'decrease' if dt<0 else 'duplicate']+=1
            prev[uid]=t
            if table=='hvac':modes[int(row['V5'])]+=1
    expected=load(qa/(table+'_quality.json'))
    assert n==expected['rows']
    assert counts==Counter({r['id']:r['rows'] for r in expected['per_device']})
    for k,name in [('increase','original_time_increases'),('decrease','original_time_decreases'),('duplicate','adjacent_duplicate_time')]:
        assert deltas[k]==sum(r[name] or 0 for r in expected['per_device'])
    results[table]={'rows':n,'devices':len(counts),'original_clock_deltas':dict(deltas),'raw_offset_suffix_counts':dict(offsets)}
    if table=='hvac':
        assert modes==Counter({int(r['value']):r['n'] for r in expected['enums']['mode']})
        results[table]['mode_counts']=dict(modes)
    print(table,'independent rows/clocks',n,flush=True)
notes={'date':'2026-10-16','status':'passed','source_QA_not_replaced':True,'independent_parser':'stdlib CSV and datetime.fromisoformat vs DuckDB',
 'counts_and_original_clock':results,'clarifications':[
  'Original sources are monotone reverse-chronological per device, not forward clock faults. Any modelling must explicitly reverse per-device original order and exclude duplicate-time ambiguities without fabricating observations.',
  'QA summary template mentioned unknown type0; actual raw V26 has only1/2, no observed0. Do not infer a raw0 from processed aggregates.',
  'Official bundled main notebook markdown names V5:0not established,1heating,2cooling,3dry,4fan; V6fan mode, numeric fan mapping unspecified. Main notebook source reviewed only, never executed.',
  'Raw2021-12-31 versus described12-18: notebook explicitly truncates processed series at12-18 to weather availability. Not evidence of extra manufactured raw rows.',
  'All191 sensor IDs are not automatically room thermometers. Only90 relation IDs/64 observed in data-sensor,26 absent; unmapped values must not all be called room-temperature faults.',
  'Relations-hvac actually87 rows/86unique IDs, ID335545193 assigned two rooms; exclude ambiguous membership before room models.',
  'Author preprocessing fills and resamples values, sometimes before group-wise chronological separation; no inherited prediction/data-quality admission.',
  'Weather date/time offset and availability remain unconfirmed; no weather join or physical heat-parameter interpretation admitted.'
 ],'verifier_sha256':sha(Path(__file__))}
dump(out/'verification.json',notes)
print('passed',flush=True)
