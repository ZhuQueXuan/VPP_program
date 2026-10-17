"""Create third-event tools without changing any previously executed source."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def change(s,a,b):
    assert s.count(a)==1,a[:80]
    return s.replace(a,b)
def save(name,s): (ROOT/name).open('x',encoding='utf-8',newline='\n').write(s)
s=(ROOT/'freeze_home_crossperiod_protocol.py').read_text('utf-8')
s=s.replace('rwth_home_crossperiod_20261014','rwth_home_third_test_20261014').replace('home_capacity_crossperiod_protocol_v2.json','home_capacity_crossperiod_protocol_v3.json')
s=change(s,"future=[r for r in system_tests if float(r['A'])>float(old['reference']['excel_time_value'])]", "previous=json.loads((ROOT/'home_capacity_crossperiod_protocol_v2.json').read_text('utf-8'))\nfuture=[r for r in system_tests if float(r['A'])>float(previous['reference']['excel_time_value'])]")
s=s.replace('2018-03-06 16:24:35','2019-07-01 13:55:06').replace('01/2018_02_System_ID_01.csv','01/2019_06_System_ID_01.csv').replace('01/2018_03_System_ID_01.csv','01/2019_07_System_ID_01.csv')
s=s.replace('CROSSPERIOD-v2','CROSSPERIOD-v3').replace('CROSSPERIOD-BL-v2','CROSSPERIOD-BL-v3').replace('DC-20261014-05','DC-20261014-07').replace('rwth_home_id01_test_20180306T162435','rwth_home_id01_test_20190701T135506')
s=s.replace('February and March required for fixed lookback','June history and July test diagnostics required')
s=change(s,"p['frozen_at_utc']=datetime.now(timezone.utc).isoformat()", """p['frozen_at_utc']=datetime.now(timezone.utc).isoformat()
p['design_status']='retrospective; all published ID01 reference values previously seen; new June/July 2019 raw curves not acquired or inspected at freeze time'
p['history_admission_failure_policy']={
    'requirement':'exact frozen 1002219 native consecutive seconds with finite values and valid published interpolation flags; no resampling, widening or cadence conversion',
    'if_failed':'retain target event; B_HIST_SPAN unavailable due raw_history_not_admitted; B_NOM/B_DS still evaluated for their supported outputs; no fabricated anchors or integrals',
    'quality_scope':'full-month quality diagnostics separate from frozen history eligibility; interpolation inside history retained and disqualifies affected spans per v1',
    'verification':'independently count native history rows/cadence/finite/flags from raw; verify empty unavailable proxy and original published reference'}""")
s=change(s,"p['baseline']['implementation_status']='frozen before new raw acquisition, no new scoring yet'", """p['baseline']['implementation_status']='frozen before new raw acquisition, no new scoring yet'
p['baseline']['reference']='published third chronological ID01 controlled test selected by outer reference key; numeric values used as labels only'
p['baseline']['unavailable_history']='retain event and both B_HIST_SPAN outputs with raw_history_not_admitted if original history cannot be evaluated; no nominal fill'""")
s=change(s,"p['changes']='v2 adds next chronological event, equal duration cross-month history and multi-file provenance; rest thresholds, embargo, pairing, net I/UI integration, models and tolerances identical to v1; old files unchanged'", "p['changes']='v3 advances chronologically to third test with same duration, embargo, algorithm and comparisons; clarifies metadata text and explicit unavailable output policy for raw cadence/coverage failure; old frozen versions unchanged'")
s=s.replace("'selected_by':'earliest listed ID01 test after v1, regardless of capacity value'", "'selected_by':'earliest listed ID01 test after v2, regardless of capacity value'")
s=s.replace("open('x',encoding='utf-8').write", "open('x',encoding='utf-8',newline='\\n').write")
save('freeze_home_third_test_protocol.py',s)

s=(ROOT/'acquire_audit_home_crossperiod.py').read_text('utf-8').replace('home_capacity_crossperiod_protocol_v2.json','home_capacity_crossperiod_protocol_v3.json')
# Frozen history admission is separate from full-month diagnostics.
s=change(s,"quality=[]; history_count=history_bad=history_interpolated=0; history_first=history_last=None; previous=None", "quality=[]; history_count=history_bad=history_interpolated=history_invalid_flags=history_bad_steps=0; history_first=history_last=None; previous=history_previous=None")
s=change(s,"            history_last=str(subset.iloc[-1])", """            history_last=str(subset.iloc[-1])
            st=subset.to_numpy(dtype='datetime64[s]').astype(np.int64)
            history_bad_steps+=int(np.count_nonzero(np.diff(st)!=1))
            if history_previous is not None: history_bad_steps+=int(subset.iloc[0]!=history_previous+pd.Timedelta(seconds=1))
            history_previous=subset.iloc[-1]
            history_invalid_flags+=int((~f.loc[mask,'Interpolated'].isin([0,1])).sum())""")
s=change(s,"admitted=history_count==expected and history_first==str(start) and history_last==str(cutoff-pd.Timedelta(seconds=1)) and history_bad==0 and all(q['missing_cells']==q['nonfinite_rows']==q['invalid_flags']==q['nonsecond_steps_including_month_join']==0 for q in quality)", "admitted=history_count==expected and history_first==str(start) and history_last==str(cutoff-pd.Timedelta(seconds=1)) and history_bad==history_invalid_flags==history_bad_steps==0")
s=s.replace("'failed_not_admitted','protocol_sha256':sha(pf)","'raw_history_not_admitted','protocol_sha256':sha(pf)")
s=change(s,"'history_interpolated_rows':history_interpolated,", "'history_interpolated_rows':history_interpolated,'history_nonsecond_steps':history_bad_steps,'history_invalid_flags':history_invalid_flags,")
s=change(s,"if not admitted: raise ValueError('not admitted')", "if not admitted: print('Frozen event retained: historical proxy unavailable; evaluate metadata-only baselines without resampling.',flush=True)")
save('acquire_audit_home_third_test.py',s)

for old,new in [('prepare_home_crossperiod_samples.py','prepare_home_third_test_samples.py'),('verify_home_crossperiod_samples.py','verify_home_third_test_samples.py'),('run_home_crossperiod_baselines.py','run_home_third_test_baselines.py'),('verify_home_crossperiod_baselines.py','verify_home_third_test_baselines.py')]:
    s=(ROOT/old).read_text('utf-8').replace('home_capacity_crossperiod_protocol_v2.json','home_capacity_crossperiod_protocol_v3.json')
    save(new,s)
print('Created six third-event tools, v1/v2 unchanged; unavailable-history path is frozen before raw acquisition.')
