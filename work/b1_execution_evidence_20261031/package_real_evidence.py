"""Group duplicate status columns into device episodes; preserve raw context."""
from common import *
import io,zipfile

def main():
    faults=read(HERE/'device_reported_fault_runs.json');groups={}
    files={r['member']:r for r in read(HERE/'dortmund_files.json')}
    for r in faults:groups.setdefault((r['member'],r['start_data_index'],r['end_data_index']),[]).append(r)
    examples=[]
    with zipfile.ZipFile(ARCHIVE) as z:
      for j,((member,start,end),records) in enumerate(sorted(groups.items())):
        with z.open(member) as stream:
            reader=csv.reader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''),delimiter=';');h=next(reader);units=next(reader);idx={k:i for i,k in enumerate(h)}
            keys=[k for k in ['epoch','P_kocos_200','Output_Power_ID2','Output_Current_ID2','Output_Voltage_ID2','AC_Power_set_ID2','STATE_ID2','ChargeState_ID2','SoC_ID2'] if k in idx]
            arr={k:[] for k in keys}
            for r in reader:
                if r:
                    for k in keys:arr[k].append(num(r[idx[k]]))
        arr={k:np.asarray(v,float) for k,v in arr.items()};t=arr['epoch'];use=(t>=t[start]-30000)&(t<=t[end]+30000);ids=np.flatnonzero(use)
        out=HERE/'reported_device_faults';out.mkdir(exist_ok=True);path=out/f'fault{j:02d}.npz'
        with path.open('xb') as f:np.savez_compressed(f,original_data_indices=ids,**{k:v[ids] for k,v in arr.items()})
        mode=files[member]['mode'];status_start=records[0]['start_epoch_ms'];status_end=records[0]['end_epoch_ms']
        examples.append(dict(sample_id=f'reported-device-fault-{j:02d}',member=member,mode=mode,port='CCS_ID2',
            evidence_tier='device-reported_fault_and_error_end_verified_dictionary_not_sensor_spike_truth',
            status_codes={r['column']:r['code'] for r in records},first_report_epoch_ms=status_start,last_report_epoch_ms=status_end,
            first_report_data_index=start,last_report_data_index=end,observed_status_span_s=(status_end-status_start)/1000,
            right_censored_at_record_end=bool(end==len(t)-1),native_preceding_report_interval_ms=float(t[start]-t[start-1]) if start else None,
            raw_window_path=path.relative_to(ROOT).as_posix(),rows=len(ids),
            acceptable_use='Reported DC device-error context only; retain as auxiliary evidence, not AC100ms false-spike labels or exact fault onset truth.',
            dictionary_url='https://zenodo.org/records/14065331/files/parameters.csv?download=1'))
    write('real_evidence_samples.json',dict(reported_device_fault_episodes=examples,
        count_distinct_device_fault_episodes=len(examples),count_status_runs=len(faults),
        ac100ms_verified_sensor_fault_samples=0,verified_short_duration_ac_response_samples=read(HERE/'dortmund_summary.json')['ac_cross_supported_short_change_windows'],
        cross_measurement_candidates_files=[r['member'] for r in files.values() if r['ac_cross_audited']],
        tier_summary=dict(A='No independently calibrated100ms action/fault truth samples established',B='2native DC device-reported error episodes, not electrical glitch truth',C='25AC two-instrument traces and KIT raw current/command for corroborative observations only'),
        no_unlabelled_events_promoted_to_ground_truth=True))
    print(json.dumps(dict(device_episodes=len(examples),status_runs=len(faults),ac100ms_spike_truth=0,short_ac_samples=0)))
if __name__=='__main__':main()
