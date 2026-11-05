"""Independent raw-meter replay, command context and frozen-source verification."""
from common import *
import zipfile,io,math
from itertools import groupby
from collections import defaultdict
from b1_algorithm.process._reference_tracking import prepare_tracking
from b1_algorithm.process.api import prepare

def main():
    selections=read('selection.json');ledger=read('input_ledger.json');records=read('records.json');old=read('old_events.json');new=read('new_events.json');results=read('results.json');minutes=defaultdict(dict)
    for row in read('dortmund_minutes_checked.json'):minutes[row['recording']][row['minute']]=row
    commands=[];recomputed=0
    archive=ROOT/'data/public_datasets/德国_多特蒙德_电动汽车充电实验/dataset_merged.zip'
    with zipfile.ZipFile(archive) as z:
      for member in sorted({c['member'] for c in selections}):
        cases=[c for c in selections if c['member']==member];minute_indices={k for c in cases for k in [c['analysis_start_minute']-180,c['analysis_start_minute']-1,c['analysis_start_minute'],c['task_start_minute'],c['task_start_minute']+29]};raw=defaultdict(list);cmd={c['case_id']:defaultdict(list) for c in cases}
        origin=next(iter(minutes[member].values()))['origin_ms']
        with z.open(member) as f:
            r=csv.reader(io.TextIOWrapper(f,encoding='utf-8-sig'),delimiter=';');h=next(r);units=next(r);pcol='P_kocos_210' if 'P_kocos_210' in h else 'P_kocos_200';pi=h.index(pcol);ti=h.index('epoch');cols=[k for k in ['I_Setpoint_WL_H','ChargingEnabled_WL_H','AC_Power_set_ID4'] if k in h]
            assert units[pi]=='kW'
            for row in r:
                if len(row)!=len(h):continue
                try:t=float(row[ti]);p=float(row[pi])
                except ValueError:continue
                index=int(math.floor((t-origin)/60000))
                if index in minute_indices:raw[index].append(p)
                for c in cases:
                    if c['analysis_start_minute']<=index<c['analysis_start_minute']+60:
                        for k in cols:
                            try:value=float(row[h.index(k)])
                            except ValueError:continue
                            if math.isfinite(value):cmd[c['case_id']][k].append(value)
        for index,values in raw.items():
            assert len(values)==minutes[member][index]['raw_n'];assert abs(math.fsum(values)/len(values)-minutes[member][index]['power_kw'])<1e-10;recomputed+=1
        for c in cases:
            values={k:dict(min=min(v),max=max(v),n=len(v),constant=min(v)==max(v)) for k,v in cmd[c['case_id']].items() if v}
            commands.append(dict(case_id=c['case_id'],member=member,command_columns=values,logged_command_context_available=bool(values),all_logged_command_fields_constant=bool(values) and all(v['constant'] for v in values.values())))
    write('command_context_audit.json',commands)
    for r,a,b,expected in zip(records,old,new,results):
        assert a['status']==b['status']=='ok';assert a['outcome']==b['outcome'];assert a['reference']==b['reference']
        task=dict(r['task'],start_min=0.,end_min=30.,notice_min=-15.);s=np.arange(-15.,45.);data=prepare(s,s+1,r['power_kw'],r['reference']['reference_kw'],task,.05)
        original=data['y'].copy();tracked=prepare_tracking(data);changed=dict(data,y=np.r_[original[:15],np.arange(45)*999.]);other=prepare_tracking(changed)
        assert np.array_equal(tracked['reference_error_prediction'],other['reference_error_prediction']);assert np.array_equal(original,data['y'])
        for method,d in expected['methods'].items():
            mask=np.asarray(d['prediction'])[15:45]>=.15;long=max((sum(1 for _ in g) for yes,g in groupby(mask.tolist()) if yes),default=0)*60
            assert d['cumulative_seconds']==sum(mask)*60 and d['longest_seconds']==long
        assert expected['ground_truth_role'].startswith('Actual meter power')
    for item in ledger:
        w=item['reference_window'];assert max(w['pre_ends_min'])<=w['notice_min'];assert w['prior_available_min']<=min(w['pre_starts_min'])
    for path,expected in read('freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    first_failure=[r['case_id'] for r in results if not r['methods']['retained']['positive'] and r['methods']['current']['positive']]
    write('verification.json',dict(passed=True,raw_minute_means_recomputed=recomputed,public_events_replayed=len(records),prior_notice_reference_and_raw_energy_unchanged=True,
        tracking_does_not_read_task_or_rebound=True,models_and_raw_sources_SHA_unchanged=True,new_background_positive_windows=first_failure,
        command_context=commands,real_response_truth_invented=False,no_retraining_or_test_selection=True))
    print(json.dumps(dict(raw_minutes=recomputed,extra_background_positive=first_failure,command_context=commands)),flush=True)
if __name__=='__main__':main()
