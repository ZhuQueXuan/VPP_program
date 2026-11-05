"""Prepare a fixed small KIT real-record panel; no estimator or new model.

Write the exact protocol and selected IDs before reading original Parquet.
No source mutation, interpolation, counterfactual fabrication or phase pooling.
"""
import os,sys,json,csv,hashlib,math
from pathlib import Path
from collections import defaultdict,Counter
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
BASE=ROOT/'work/ev_charging_research_20261016'
SOURCE=BASE/'downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet'
CANDIDATES=BASE/'runs/PREP_KIT_STEPS_01/all_phase_candidates.csv'
SOURCE_PROTOCOL=BASE/'kit_step_protocol_v1.json'
OLD_FEATURES=ROOT/'resource_research_results/ev_charging/results/recorded_step_phase_features.csv'
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
sys.path.insert(0,str(ROOT/'work/python_packages/pyreadr'))
import numpy as np
import duckdb

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def dump_new(path,value):
    with Path(path).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

PROTOCOL=dict(schema='b1.command-record-preparation.v1',date='2026-10-31',
    purpose='Finite descriptive real command-tracking panel and future fixed input-perturbation stability; not latent truth accuracy.',
    source='KIT Zenodo17866847 v1.0.0 LF, original source order and microsecond timestamp decoding',
    selection=dict(cohort='Only old PREP status=admitted',one_phase_per_command=True,phase_priority=['L1','L2','L3'],
        per_recording_per_direction=4,directions=['up','down'],
        order='Within recording/direction ascending original edge_index, edge_time_us, event_id as tie',
        uniform_index='For n>=4, floor(j*(n-1)/3), j=0,1,2,3; n<4 retain all, no replacement.',
        selection_uses_no_response_error_or_crossing=True,preparation_failures_retained_no_replacement=True),
    aggregation=dict(window_relative_us=[-5000000,15000000],half_open_bin_width_us=100000,n_bins=200,
        method='Arithmetic mean of original observations with start<=relative_time_us<end, not a continuous-time integral.',
        no_interpolation=True,no_fill=True,minimum_observations_per_bin=2,
        maximum_adjacent_gap_us=50000,maximum_first_last_distance_to_bin_boundary_us=50000),
    units=dict(native_time='integer microseconds; source elapsed differences, not physical instrument microsecond accuracy',
        fit_time='seconds',current='A',progress='dimensionless command-step normalized observed current change'),
    progress='sign(new-old)*(current_mean_A-original_pre5s_median_A)/abs(new-old)',
    noise=dict(window='Only [-5,0) 50 aggregated pre bins',primary='MAD of pre-progress first differences /(.6744897501960817*sqrt(2))',
        if_zero='Sample SD of same differences /sqrt(2)',numerical_sigma_floor_progress=.001,
        physical_sensor_calibration_claim=False),
    counterfactual_reference_available=False,denoised_truth_available=False,
    RIDE_formal_API_status='not_applicable_seconds_current_domain',
    future_methods='Raw description and isolated seconds adapters for TFstandard/CPOP/LABS; this script runs none.',
    old_files_mutated=False)

def execute():
    dump_new(HERE/'real_preparation_protocol.json',PROTOCOL)
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in (SOURCE_PROTOCOL,CANDIDATES,OLD_FEATURES,BASE/'downloads/KIT_LF_SOURCE_01/charging.csv')}
    old=json.loads(SOURCE_PROTOCOL.read_text(encoding='utf8'))
    assert sha(SOURCE)==old['sources']['LF']['sha256']
    sources[SOURCE.relative_to(ROOT).as_posix()]=old['sources']['LF']['sha256']
    admitted=[r for r in read_csv(CANDIDATES) if r['status']=='admitted']
    preferred={};priority={'L1':0,'L2':1,'L3':2}
    for row in admitted:
        key=(row['charging_uuid'],int(row['edge_index']))
        if key not in preferred or priority[row['phase']]<priority[preferred[key]['phase']]:preferred[key]=row
    bygroup=defaultdict(list)
    for row in preferred.values():bygroup[(row['charging_uuid'],row['direction'])].append(row)
    selected=[];selection_groups=[]
    for (uid,direction),rows in sorted(bygroup.items()):
        rows.sort(key=lambda r:(int(r['edge_index']),int(r['edge_time_us']),r['event_id']))
        ix=list(range(len(rows))) if len(rows)<4 else [j*(len(rows)-1)//3 for j in range(4)]
        assert len(set(ix))==len(ix)
        for rank,k in enumerate(ix):selected.append(dict(rows[k],selected_rank=rank,eligible_direction_count=len(rows),selected_original_direction_index=k))
        selection_groups.append(dict(recording=uid,direction=direction,eligible=len(rows),selected=len(ix),indices=ix))
    assert len({r['event_id'] for r in selected})==len(selected)<=144
    assert len({r['charging_uuid'] for r in selected})==18
    dump_new(HERE/'real_selection.json',dict(protocol_sha256=sha(HERE/'real_preparation_protocol.json'),
        groups=selection_groups,selected=selected,selected_before_parquet_read=True))
    oldfeatures={r['event_id']:r for r in read_csv(OLD_FEATURES)}
    byrecord=defaultdict(list)
    for r in selected:byrecord[r['charging_uuid']].append(r)
    trace_dir=HERE/'real_raw_traces';trace_dir.mkdir(exist_ok=False)
    temp_dir=HERE/'real_duckdb_temp';temp_dir.mkdir(exist_ok=False)
    con=duckdb.connect()
    con.execute("SET memory_limit='512MB'");con.execute('SET threads=1')
    con.execute('SET temp_directory=?',[str(temp_dir)])
    cases=[];allcounts=Counter();binminimum=None;binmaximum=0;maxgap=0;rawsha={}
    starts_us=np.arange(-5000000,15000000,100000,dtype=np.int64)
    for uid,rows in sorted(byrecord.items()):
        d=con.execute('SELECT file_row_number, epoch_us(timestamp_ns) AS t_us, cast(i_l1_a as double) AS i1, '
            'cast(i_l2_a as double) AS i2, cast(i_l3_a as double) AS i3, setpoint_a AS u '
            'FROM read_parquet(?,file_row_number=true) WHERE charging_uuid=cast(? AS UUID) ORDER BY file_row_number',
            [str(SOURCE),uid]).fetchnumpy()
        t=np.asarray(d['t_us']);commands=np.asarray(d['u'])
        assert np.all(np.diff(t)>0)
        for r in rows:
            base=dict(case_id=r['event_id'],event_id=r['event_id'],recording=uid,charging_uuid=uid,
                car_brand=r['car_brand'],car_model=r['car_model'],date=r['date'],phase=r['phase'],direction=r['direction'],
                edge_index=int(r['edge_index']),edge_time_us=int(r['edge_time_us']),source_file_row=int(r['source_file_row']),
                previous_command_A=float(r['previous_command_A']),new_command_A=float(r['new_command_A']),step_A=float(r['step_A']),
                selected_original_direction_index=r['selected_original_direction_index'],eligible_direction_count=r['eligible_direction_count'],
                status='unavailable',reasons=[],counterfactual_reference_available=False,latent_truth_available=False,
                RIDE_formal_API_status='not_applicable',time_unit='seconds',signal_unit='dimensionless_command_normalized_current')
            try:
                i=int(r['edge_index']);left=int(r['pre_start_index']);right=int(r['post_end_index']);t0=int(r['edge_time_us'])
                assert int(t[i])==t0 and int(d['file_row_number'][i])==int(r['source_file_row'])
                assert float(commands[i-1])==base['previous_command_A'] and float(commands[i])==base['new_command_A']
                rel=np.asarray(t[left:right],dtype=np.int64)-t0
                current=np.asarray(d['i'+r['phase'][1:]][left:right],dtype=float)
                cmd=np.asarray(commands[left:right],dtype=float)
                file_rows=np.asarray(d['file_row_number'][left:right],dtype=np.int64)
                assert np.isfinite(current).all() and np.isfinite(cmd).all()
                assert rel.min()>=-5000000 and rel.max()<15000000
                gaps=np.diff(rel);assert np.all((gaps>0)&(gaps<=50000))
                pre=rel<0;post=rel>=0
                assert np.all(cmd[pre]==base['previous_command_A']) and np.all(cmd[post]==base['new_command_A'])
                premedian=float(np.median(current[pre]));assert premedian>=1
                assert abs(premedian-float(r['pre_observed_current_A']))<1e-12
                base['pre_current_A']=premedian
                rawpath=trace_dir/(uid+'_'+str(i)+'_'+r['phase']+'.npz')
                with rawpath.open('xb') as h:np.savez_compressed(h,relative_time_us=rel,phase_current_A=current,command_A=cmd,source_file_row=file_rows)
                rawsha[rawpath.relative_to(ROOT).as_posix()]=sha(rawpath)
                base['raw_trace_npz']=rawpath.relative_to(ROOT).as_posix()
                means=[];counts=[];bad=[]
                for k,start in enumerate(starts_us):
                    use=(rel>=start)&(rel<start+100000);idx=np.flatnonzero(use)
                    counts.append(int(len(idx)))
                    if len(idx)<2:bad.append(dict(bin=k,reason='fewer_than_two_original_observations'))
                    elif rel[idx[0]]-start>50000 or start+100000-rel[idx[-1]]>50000:bad.append(dict(bin=k,reason='insufficient_bin_edge_coverage'))
                    means.append(float(np.mean(current[idx])) if len(idx) else None)
                base['bin_counts']=counts;base['bin_quality_failures']=bad
                if bad:
                    base['reasons']=['bin_quality_failed_no_replacement'];cases.append(base);allcounts['unavailable']+=1;continue
                means=np.asarray(means);step=base['step_A'];progress=np.sign(step)*(means-premedian)/abs(step)
                before=progress[:50];diff=np.diff(before)
                robust=float(np.median(np.abs(diff-np.median(diff)))/(.6744897501960817*np.sqrt(2)))
                sample=float(np.std(diff,ddof=1)/np.sqrt(2))
                estimate=robust if robust>0 else sample
                method='pre_bin_first_difference_MAD' if robust>0 else 'pre_bin_first_difference_SD_zero_MAD'
                sigma=max(.001,estimate)
                base.update(status='ok',starts_s=(starts_us/1e6).tolist(),ends_s=((starts_us+100000)/1e6).tolist(),
                    current_mean_A=means.tolist(),progress=progress.tolist(),
                    pre_noise_sigma_progress=sigma,noise_sigma_progress=sigma,
                    pre_noise=dict(robust_difference_sigma=robust,sample_difference_sigma=sample,
                        method=method,n_pre_bins=50,n_differences=49,estimated_before_numerical_floor=estimate,
                        numerical_floor=.001,floor_used=estimate<.001,only_pre_window_used=True,
                        physical_sensor_calibration_claim=False),
                    original_recorded_step_features=oldfeatures.get(r['event_id']),raw_feature_reference_role='Descriptive original-sampling record features, not independent latent truth')
                binminimum=min(counts) if binminimum is None else min(binminimum,min(counts));binmaximum=max(binmaximum,max(counts))
                maxgap=max(maxgap,int(np.max(gaps)))
                allcounts['ok']+=1
            except (AssertionError,ValueError,IndexError,KeyError) as exc:
                base['reasons']=[type(exc).__name__+': '+str(exc)];allcounts['unavailable']+=1
            cases.append(base)
        print(json.dumps(dict(recording=uid,processed=len(rows),total_cases=len(cases))),flush=True)
    con.close()
    for p,h in sources.items():assert sha(ROOT/p)==h,p
    assert len(cases)==len(selected)
    dump_new(HERE/'real_cases.json',cases)
    receipt=dict(status='prepared_not_fitted',selected=len(selected),prepared=len(cases),status_counts=dict(allcounts),
        recordings=len(byrecord),direction_counts=dict(Counter(r['direction'] for r in cases)),
        phase_counts=dict(Counter(r['phase'] for r in cases)),n_bins=200,bin_seconds=.1,
        minimum_bin_observations=binminimum,maximum_bin_observations=binmaximum,max_original_gap_us=maxgap,
        protocol_sha256=sha(HERE/'real_preparation_protocol.json'),selection_sha256=sha(HERE/'real_selection.json'),
        cases_sha256=sha(HERE/'real_cases.json'),script_sha256=sha(__file__),source_sha256=sources,
        raw_trace_sha256=rawsha,source_hashes_unchanged=True,preparation_failures_replaced=False,
        no_estimator_or_new_model_run=True,no_interpolation_or_fill=True,
        timestamp_precision_claim='relative source elapsed microseconds only',counterfactual_reference_available=False,
        latent_clean_curve_accuracy_evaluable=False,RIDE_formal_domain='not_applicable',
        old_source_results_and_data_mutated=False,python=sys.executable,duckdb_version=duckdb.__version__,numpy_version=np.__version__,
        preparation_environment='Existing CPython3.12 decoder packages only; downstream estimators remain in separately frozen original environment.')
    dump_new(HERE/'real_preparation_receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('raw_trace_sha256','source_sha256')},ensure_ascii=False),flush=True)

if __name__=='__main__':execute()
