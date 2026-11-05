"""Read-only independent replay from saved original samples, no fitting."""
import sys,os,json,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
receipt=read(HERE/'real_preparation_receipt.json');cases=read(HERE/'real_cases.json');selection=read(HERE/'real_selection.json')
assert len(cases)==144 and all(x['status']=='ok' for x in cases)
assert len({x['case_id'] for x in cases})==144
grouped=Counter((x['recording'],x['direction']) for x in cases);assert len(grouped)==36 and set(grouped.values())=={4}
for group in selection['groups']:
    n=group['eligible'];assert group['indices']==[j*(n-1)//3 for j in range(4)]
max_current_error=0.;max_progress_error=0.;max_noise_error=0.;bin_counts=Counter();sources_checked=0
for c in cases:
    with np.load(ROOT/c['raw_trace_npz'],allow_pickle=False) as raw:
        t=raw['relative_time_us'];current=raw['phase_current_A'];command=raw['command_A']
        assert len(t)==len(current)==len(command)
        assert np.all(np.diff(t)>0) and np.max(np.diff(t))<=50000
        assert t.min()>=-5000000 and t.max()<15000000
        pre=t<0;assert np.all(command[pre]==c['previous_command_A']) and np.all(command[~pre]==c['new_command_A'])
        baseline=float(np.median(current[pre]));assert baseline==c['pre_current_A']
        index=(t+5000000)//100000
        count=np.bincount(index,minlength=200);sums=np.bincount(index,weights=current,minlength=200)
        mean=sums/count
        max_current_error=max(max_current_error,float(np.max(np.abs(mean-c['current_mean_A']))))
        assert np.array_equal(count,c['bin_counts']) and np.min(count)>=2
        progress=np.sign(c['step_A'])*(mean-baseline)/abs(c['step_A'])
        max_progress_error=max(max_progress_error,float(np.max(np.abs(progress-c['progress']))))
        diff=np.diff(np.asarray(c['progress'])[:50])
        robust=float(np.median(np.abs(diff-np.median(diff)))/(.6744897501960817*np.sqrt(2)))
        estimate=robust if robust>0 else float(np.std(diff,ddof=1)/np.sqrt(2))
        max_noise_error=max(max_noise_error,abs(max(.001,estimate)-c['noise_sigma_progress']))
        assert c['original_recorded_step_features']['event_id']==c['event_id']
        assert c['counterfactual_reference_available'] is False and c['latent_truth_available'] is False
        assert c['RIDE_formal_API_status']=='not_applicable'
        bin_counts.update(count.tolist())
assert max_current_error<1e-11 and max_progress_error<1e-11 and max_noise_error<1e-11
for p,h in receipt['source_sha256'].items():assert sha(ROOT/p)==h;sources_checked+=1
for p,h in receipt['raw_trace_sha256'].items():assert sha(ROOT/p)==h
assert sha(HERE/'real_cases.json')==receipt['cases_sha256']
result=dict(passed=True,scope='Independent saved-original-sample binning/progress/noise replay, source-hash verification only; no estimator.',
    cases=144,recordings=18,selection_groups=36,events_per_recording_direction=4,
    maximum_current_mean_difference=max_current_error,maximum_progress_difference=max_progress_error,
    maximum_pre_noise_difference=max_noise_error,sources_sha_verified=sources_checked,
    original_sample_npz_sha_verified=len(receipt['raw_trace_sha256']),observation_count_frequencies=dict(bin_counts),
    source_data_and_main_preparation_unchanged=True,independent_parquet_decoder_claim=False,python=sys.executable)
with (Path(__file__).with_name('real_preparation_independent_check.json')).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(result,ensure_ascii=False))
