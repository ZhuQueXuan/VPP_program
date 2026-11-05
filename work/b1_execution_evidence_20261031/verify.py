"""Independent evidence checks, not process-method tests or fits."""
from common import *
import zipfile,io
from decimal import Decimal

def main():
    book=read(HERE/'real_evidence_samples.json');checks=0
    with zipfile.ZipFile(ARCHIVE) as z:
      for event in book['reported_device_fault_episodes']:
        with z.open(event['member']) as f:
            rows=csv.reader(io.TextIOWrapper(f,encoding='utf-8-sig'),delimiter=';');header=next(rows);units=next(rows);data=list(rows)
        idx={k:i for i,k in enumerate(header)};start=event['first_report_data_index'];end=event['last_report_data_index']
        for key,code in event['status_codes'].items():
            assert all(Decimal(data[i][idx[key]])==Decimal(code) for i in range(start,end+1));checks+=end-start+1
            assert start==0 or Decimal(data[start-1][idx[key]])!=Decimal(code);checks+=1
        assert event['mode']=='DC' and event['port']=='CCS_ID2';checks+=2
        with np.load(ROOT/event['raw_window_path'],allow_pickle=False) as saved:
            ids=saved['original_data_indices']
            for k in saved.files:
                if k=='original_data_indices':continue
                expected=np.array([num(data[int(i)][idx[k]]) for i in ids]);assert np.array_equal(expected,saved[k],equal_nan=True);checks+=len(ids)
    pairs=read(HERE/'simulation_pairs.json');samples=read(HERE/'simulation_samples.json');maxtruthdiff=0.
    for pair in pairs:
        files={k:np.load(ROOT/v,allow_pickle=False) for k,v in pair['samples'].items()}
        a=files['actual_response'];b=files['primary_meter_fault'];c=files['common_mode_meter_fault']
        for key in ['starts_us','command_kw','primary_power_kw','primary_current_A']:
            assert np.array_equal(a[key],b[key]) and np.array_equal(a[key],c[key]);checks+=2
        assert np.all(np.diff(a['starts_us'])==100000) and len(a['starts_us'])==200;checks+=2
        assert np.array_equal(a['optional_secondary_meter_kw'],c['optional_secondary_meter_kw']);checks+=1
        assert np.max(abs(a['optional_secondary_meter_kw']-b['optional_secondary_meter_kw']))>0;checks+=1
        assert np.any(a['truth_physical_response_kw']>.15) and not np.any(b['truth_physical_response_kw']>.15);checks+=2
        maxtruthdiff=max(maxtruthdiff,float(np.max(abs(a['truth_physical_power_kw']-b['truth_physical_power_kw']))))
        for label,arr in files.items():
            assert np.isfinite(arr['primary_power_kw']).all() and np.all(arr['truth_physical_power_kw']>0) and np.all(arr['truth_physical_power_kw']<=7.2);checks+=3
            # Clean+bias+noise equal observed, same paired noise by construction.
            noise=arr['primary_power_kw']-arr['truth_physical_power_kw']-arr['truth_primary_measurement_bias_kw']
            if label=='actual_response':reference_noise=noise
            else:assert np.max(abs(noise-reference_noise))<1e-12;checks+=1
            arr.close()
    before=read(HERE/'protected_before.json');changed=[p for p,h in before.items() if sha(ROOT/p)!=h];assert not changed
    old=ROOT/'work/b1_cpop_fine_v3_20261031';manifest=read(old/'completion_receipt.json')['file_sha256'];assert all(sha(old/p)==h for p,h in manifest.items())
    result=dict(status='passed',checks=checks,device_fault_episodes_verified=len(book['reported_device_fault_episodes']),
        paired_simulation_waveforms=len(pairs),simulation_variants=len(samples),same_observations_different_truth_pairs=len(pairs),
        maximum_latent_power_difference_kw=maxtruthdiff,original_sources_and_production_files_unchanged=len(before),old_v3_files_unchanged=len(manifest),
        no_feature_algorithms_run=True,no_original_observations_modified=True,
        limitations='Checks verify records/codes/identity and constructed information examples; not fault detector accuracy, physical EV model validity or field reliability.')
    write('verification_receipt.json',result);print(json.dumps(result))
if __name__=='__main__':main()
