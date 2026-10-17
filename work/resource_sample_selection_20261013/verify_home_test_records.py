"""Independent stdlib raw-record reconstruction for the frozen test diagnostic."""
from pathlib import Path
import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import statistics

ROOT = Path(__file__).resolve().parent
pa = argparse.ArgumentParser()
pa.add_argument('--audit-run', required=True)
pa.add_argument('--verification-id', required=True)
a = pa.parse_args()
if not a.audit_run.isidentifier() or not a.verification_id.isidentifier():
    raise ValueError('simple IDs required')
folder = ROOT/'downloads/rwth_home_test_record_diagnostic_20261014'/a.audit_run
out = folder.parent/(a.verification_id+'.json')
if out.exists():
    raise FileExistsError(out)
read = lambda p: json.loads(p.read_text('utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
p = read(ROOT/'home_test_record_diagnostic_protocol_v1.json')
r, s = read(folder/'receipt.json'), read(folder/'summary.json')
assert r['protocol_sha256'] == sha(ROOT/'home_test_record_diagnostic_protocol_v1.json')
source = ROOT/p['source']['path']
assert sha(source) == p['source']['sha256']
for name, h in r['artifacts'].items():
    assert sha(folder/name) == h, name
start, end, test = map(dt.datetime.fromisoformat, [p['window_start_inclusive'],p['window_end_exclusive'],p['test_start_native']])
with source.open(newline='', encoding='utf-8') as handle:
    raw = [(t,row) for row in csv.DictReader(handle)
           if start <= (t:=dt.datetime.strptime(row['Time'],'%d-%b-%Y %H:%M:%S')) < end]
cols = ['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']
data = []
bid = -1
for j,(t,row) in enumerate(raw):
    if j == 0 or (t-raw[j-1][0]).total_seconds() != 1:
        bid += 1
    values = {c:float(row[c]) for c in cols}
    flag = int(row['Interpolated'])
    valid = all(map(math.isfinite,values.values())) and flag in [0,1]
    state = 'invalid' if not valid else 'rest' if abs(values['I_in_A']) <= .15 else 'charge' if values['I_in_A'] > .15 else 'discharge'
    data.append({'time':t,'raw':row,**values,'flag':flag,'valid':valid,'block_id':bid,'state':state})
maximum_difference = 0.
def compare(x,y):
    global maximum_difference
    if isinstance(x,dict):
        assert set(x) == set(y),(set(x),set(y))
        for k in x: compare(x[k],y[k])
    elif isinstance(x,list):
        assert len(x) == len(y)
        for a1,b1 in zip(x,y): compare(a1,b1)
    elif isinstance(x,(int,float)) and not isinstance(x,bool):
        assert y is not None
        difference = abs(x-y)
        maximum_difference = max(maximum_difference,difference)
        assert difference <= 1e-9,(x,y)
    else:
        assert x == y,(x,y)

with (folder/'raw_window_and_derived.csv').open(newline='',encoding='utf-8') as h:
    derived = list(csv.DictReader(h))
assert len(derived) == len(data) == s['observed_rows']
for row, got in zip(data,derived):
    for c in p['fields']:
        if c == 'Time': assert row['raw'][c] == got[c]
        else: compare(float(row['raw'][c]),float(got[c]))
    assert got['native_time'] == str(row['time'])
    assert (got['record_valid'] == 'True') == row['valid']
    assert int(got['block_id']) == row['block_id'] and got['state'] == row['state']
    compare(row['V_in_V']*row['I_in_A'],float(got['UI_reconstructed_W']))
    compare(row['P_in_W']-row['V_in_V']*row['I_in_A'],float(got['P_minus_UI_W']))

blocks, gaps = [], []
cursor = start
for bid, group in itertools.groupby(data,key=lambda r:r['block_id']):
    rows = list(group); first=rows[0]['time']; last=rows[-1]['time']+dt.timedelta(seconds=1)
    if first > cursor:
        gaps.append({'start':str(cursor),'end_exclusive':str(first),'missing_seconds':int((first-cursor).total_seconds())})
    blocks.append({'block_id':bid,'start':str(first),'end_exclusive':str(last),'rows':len(rows),
                   'interpolated_rows':sum(r['flag']==1 for r in rows),'contains_test_start':first<=test<last})
    cursor=last
if cursor<end: gaps.append({'start':str(cursor),'end_exclusive':str(end),'missing_seconds':int((end-cursor).total_seconds())})
compare(blocks,s['blocks']);compare(gaps,s['gaps'])
assert len(data)+sum(r['missing_seconds'] for r in gaps)==s['expected_seconds']==86400
assert sum(r['time']==test for r in data)==s['test_start_row_count']==1
start_rows=[]
for row in data:
    if row['time']==test:
        start_rows.append({c:row['raw'][c] if c=='Time' else int(row['raw'][c]) if c=='Interpolated' else float(row['raw'][c]) for c in p['fields']})
compare(start_rows,s['test_start_rows'])
with (folder/'test_start_context.csv').open(newline='',encoding='utf-8') as handle:
    got_context=list(csv.DictReader(handle))
expected_context=[r for r in data if test-dt.timedelta(seconds=5)<=r['time']<=test+dt.timedelta(seconds=5)]
assert len(got_context)==len(expected_context)
for row,got in zip(expected_context,got_context):
    for col in p['fields']:
        if col=='Time':assert row['raw'][col]==got[col]
        else:compare(float(row['raw'][col]),float(got[col]))

def changes(rows,col,measured):
    chunks=[];current=[]
    for r in rows:
        if not r['valid'] or (measured and r['flag']!=0):
            if current:chunks.append(current);current=[]
            continue
        if current and (r['time']-current[-1]['time']).total_seconds()!=1:
            chunks.append(current);current=[]
        current.append(r)
    if current:chunks.append(current)
    intervals=[];changed=held=0
    for chunk in chunks:
        changes_at=[b['time'] for a1,b in zip(chunk,chunk[1:]) if a1[col]!=b[col]]
        changed+=len(changes_at);held+=len(chunk)-1-len(changes_at)
        intervals.extend((b-a1).total_seconds() for a1,b in zip(changes_at,changes_at[1:]))
    return {'changed_adjacent_rows':changed,'held_adjacent_rows':held,
            'median_seconds_between_changes':statistics.median(intervals) if intervals else None,
            'change_interval_counts_seconds':{str(k):v for k,v in sorted(collections.Counter(intervals).items())}}

for key,rows in [('whole_window',data),('before_test_index',[r for r in data if r['time']<test]),('at_or_after_test_index',[r for r in data if r['time']>=test])]:
    sc=s['scopes'][key]
    assert len(rows)==sc['rows'] and sum(r['flag']==1 for r in rows)==sc['interpolated_rows']
    assert sum(not r['valid'] for r in rows)==sc['invalid_rows']
    for measured,qkey in [(False,'all_valid_records'),(True,'noninterpolated_valid_records')]:
        q=[r for r in rows if r['valid'] and (not measured or r['flag']==0)]
        z=[r for r in q if r['I_in_A']==0 and r['P_in_W']!=0]
        differences=[abs(r['P_in_W']-r['V_in_V']*r['I_in_A']) for r in q]
        independent={'rows':len(q),'zero_I_nonzero_P_rows':len(z),
                     'max_abs_P_when_I_zero_W':max((abs(r['P_in_W']) for r in z),default=None),
                     'P_minus_UI_mean_abs_W':math.fsum(differences)/len(q) if q else None,
                     'P_minus_UI_max_abs_W':max(differences,default=None),
                     'ranges':{c:[min(r[c] for r in q),max(r[c] for r in q)] for c in cols} if q else {},
                     'channel_changes':{c:changes(rows,c,measured) for c in ['V_in_V','I_in_A','P_in_W']}}
        compare(independent,sc[qkey])

run_rows=[]
for rid,((bid,state,flag),group) in enumerate(itertools.groupby(enumerate(data),key=lambda pair:(pair[1]['block_id'],pair[1]['state'],pair[1]['flag'])),1):
    pairs=list(group);j=pairs[0][0];rows=[r for _,r in pairs]
    onset=j>0 and data[j-1]['block_id']==bid and data[j-1]['flag']==flag and data[j-1]['valid'] and rows[0]['valid']
    run_rows.append({'run_id':rid,'block_id':bid,'state':state,'interpolated':flag,'start':str(rows[0]['time']),
                     'end_exclusive':str(rows[-1]['time']+dt.timedelta(seconds=1)),'rows':len(rows),'state_onset_observed':bool(onset),
                     'U_first_V':rows[0]['V_in_V'],'U_last_V':rows[-1]['V_in_V'],'I_min_A':min(r['I_in_A'] for r in rows),'I_max_A':max(r['I_in_A'] for r in rows)})
with (folder/'current_state_runs.csv').open(newline='',encoding='utf-8') as h:got=list(csv.DictReader(h))
assert len(got)==len(run_rows)==s['current_state_runs']
for row,g in zip(run_rows,got):
    typed={k:(g[k]=='True' if isinstance(v,bool) else int(g[k]) if isinstance(v,int) else float(g[k]) if isinstance(v,float) else g[k]) for k,v in row.items()}
    compare(row,typed)
result={'status':'passed','audit_run':a.audit_run,'verification_id':a.verification_id,'raw_rows_checked':len(data),
        'current_state_runs_checked':len(run_rows),'scopes_checked':3,'quality_scopes_each':2,
        'max_numeric_difference':maximum_difference,'numeric_tolerance':1e-9,'protocol_sha256':r['protocol_sha256'],
        'audit_code_sha256':r['code_sha256'],'verification_code_sha256':sha(Path(__file__)),
        'scope':'every raw/derived field, native blocks/gaps, all scope channel residuals and change distributions, all state runs; independent raw CSV; no capacity inference'}
out.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
