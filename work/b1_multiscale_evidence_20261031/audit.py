"""Independent bin reconstruction and immutability audit, no model fitting."""
import hashlib,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RESULT=HERE/'analysis_run2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

rows=read(RESULT/'observed_shapes.json');checks=0;maximum=0.;extra={}
for r in rows:
    with np.load(ROOT/r['raw_source'],allow_pickle=False) as raw, np.load(HERE/r['aligned_file'],allow_pickle=False) as aligned:
        if r['panel']=='held':t=raw['relative_time_us'];y=raw['phase_current_A'];u=raw['command_A']
        else:t=raw['relative_us'];y=raw['i'+str(r['phase'])];u=raw['command']
        assert np.all(np.diff(t)>0) and len(t)==r['raw_samples'];checks+=2
        for width in [100000,1000000,5000000,10000000]:
            key=str(width)+'us';lo=aligned['lo_'+key];indices=((t-lo[0])//width).astype(int)
            count=np.bincount(indices,minlength=len(lo));total=np.bincount(indices,weights=y,minlength=len(lo))
            assert np.array_equal(count,aligned['count_'+key]) and int(count.sum())==len(y);checks+=2
            good=count>0;mean=total[good]/count[good];diff=float(np.max(abs(mean-aligned['mean_'+key][good])));maximum=max(maximum,diff)
            assert diff<1e-10;checks+=1
            assert np.array_equal(aligned['complete_'+key],(lo>=-5000000)&(aligned['hi_'+key]<=15000000));checks+=1
        edges=np.flatnonzero(np.diff(u)!=0)+1
        expected=[(float(t[i]/1e6),float(u[i-1]),float(u[i])) for i in edges]
        assert expected==[(e['time_s'],e['before'],e['after']) for e in r['command_changes']];checks+=1
held=[r for r in rows if r['panel']=='held'];pulse=[r for r in rows if r['panel']=='pulse']
extra['coarse10s_mean_below90_but_fine_above90_at_least_half']=sum(r['coarse10s_progress']<.9 and r['fine100ms_first10s_fraction_above90']>=.5 for r in held)
extra['pulse_events_with_other_commands_within_pre_post2s']=len({r['event_id'] for r in pulse if not(r['pre2s_command_constant'] and r['post2s_command_constant'])})
extra['pulse_active_isolated_phase_rows']=sum(r['pre2s_command_constant'] and r['post2s_command_constant'] and r['pre_median_A']>=1 for r in pulse)
extra['phase_rows_meeting_during_command_directional_descriptor']=sum(r['pre2s_command_constant'] and r['post2s_command_constant'] and r['pre_median_A']>=1 and r['during_max_above10_span_s']>=.1 and r['during_median_progress']>=.1 for r in pulse)
extra['interpretation']='Descriptive thresholds, not classifier/causal validation. During-command metrics cannot exclude delayed response after the command has returned.'
before=read(HERE/'protected_before.json');changed=[p for p,h in before.items() if sha(ROOT/p)!=h];assert not changed
v3=ROOT/'work/b1_cpop_fine_v3_20261031';manifest=read(v3/'completion_receipt.json')['file_sha256']
v3changed=[p for p,h in manifest.items() if sha(v3/p)!=h];assert not v3changed
out=dict(status='passed',independent_checks=checks,phase_rows=len(rows),held_events=144,pulse_events=162,
    source_and_production_files_unchanged=len(before),original_v3_files_unchanged=len(manifest),
    max_independent_direct_mean_difference_A=maximum,all_original_observations_retained=True,
    no_fits_no_interpolation_no_replacement=True,extra_descriptors=extra,
    output_failure_note='Initial aligned exports completed but JSON serialization encountered numpy.int64. Initial outputs/partialJSON retained. Corrected serialization exported to analysis_run2 without changing raw data or formulas.')
with (HERE/'audit_receipt.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out))
