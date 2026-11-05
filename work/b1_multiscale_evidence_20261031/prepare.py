"""Freeze read-only same-event evidence audit, not a new process algorithm."""
import csv,hashlib,json,statistics
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'work/b1_command_feature_selection_20261031'
BASE=ROOT/'work/ev_charging_research_20261016'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2)

def main():
    csvpath=BASE/'runs/PREP_KIT_STEPS_01/all_phase_candidates.csv';groups=defaultdict(list)
    with csvpath.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['phase']=='L1':groups[r['charging_uuid']].append(r)
    holds=[];pulses=[];short_all=0
    for uid,rows in sorted(groups.items()):
        rows.sort(key=lambda r:int(r['edge_index']))
        for a,b in zip(rows,rows[1:]):
            duration_us=int(b['edge_time_us'])-int(a['edge_time_us']);assert duration_us>0
            holds.append(duration_us)
            if duration_us<=10000000:short_all+=1
            if 0<duration_us<=10000000 and float(b['new_command_A'])==float(a['previous_command_A']) and abs(float(a['step_A']))>=2 and min(float(a['previous_command_A']),float(a['new_command_A']))>=6:
                pulses.append(dict(event_id=a['event_id'].replace(':L1',':command_return'),recording=uid,
                    edge_index=int(a['edge_index']),return_edge_index=int(b['edge_index']),
                    source_file_row=int(a['source_file_row']),return_source_file_row=int(b['source_file_row']),
                    edge_time_us=int(a['edge_time_us']),return_time_us=int(b['edge_time_us']),duration_us=duration_us,
                    previous_command_A=float(a['previous_command_A']),new_command_A=float(a['new_command_A']),
                    direction=a['direction'],label='recorded_short_command_return_not_true_response_or_fault'))
    pulses.sort(key=lambda r:(r['recording'],r['edge_index']))
    write('protocol.json',dict(scope='Same raw observations and commands across resolutions; read-only evidence verification. No process estimation, detection model, injection or parameter selection.',
        existing_panel='All144 frozen KIT100ms events, no response-based selection. Original raw NPZ native~21ms and command preserved.',
        pulse_selection='All adjacent recorded command changes returning exactly to previous value within10s, |step|>=2A, both commands>=6A. Determined from full frozen candidate ledger, no phase/current-response selection. These are command patterns, not true-response labels.',
        time='Integer relative microseconds, half-open bins, t0 original command edge. Preserve raw row order and all raw values.',
        scales_us=[100000,1000000,5000000,10000000],window_us=[-5000000,15000000],
        means='Direct arithmetic mean of original samples; coarse equals count-weighted finer means, never unweighted mean-of-means or interpolation.',
        coverage='Partial bins explicitly retained and marked; complete comparisons require full time-window support, no inserted samples.',
        descriptors='Existing directional10/90 percent command-normalized progress, not latent net reduction. Exceedance occupancy, run length and first crossings are descriptive. No rule assigns real fault/response truth.',
        pulse_context='Retain all command edges and all3phase current/power/voltage, even inactive, incomplete or non-isolated contexts. Power/current are same logger, not independent fault truth.',
        support='Native median pre2s for pulse descriptions; pre/post2s command isolation is a descriptor, not an exclusion or causal proof.',
        examples='First event in recording/event order meeting each predefined descriptive shape: native10-to90 crossing<=100ms and100ms target run>=5s; target runs<=200ms; steady last5s progress<.9; first short-command return. No accuracy inference from examples.',
        not_authorized=['Algorithm edits','Point replacement/deletion','Gap filling','New noise injection','CPOP/LABS refit','Reports or response-analysis block']))
    write('pulse_selection.json',pulses)
    write('command_inventory.json',dict(recordings=len(groups),edges=sum(len(v) for v in groups.values()),holds=len(holds),
        duration_us_min_median_max=[min(holds),statistics.median(holds),max(holds)],holds_le10s=short_all,
        selected_short_returns=len(pulses),selected_recordings=len({p['recording'] for p in pulses}),
        selection_before_loading_current=True,source_csv_sha256=sha(csvpath)))
    sources=[OLD/'real_cases.json',OLD/'real_preparation_protocol.json',OLD/'real_prepare.py',csvpath,BASE/'kit_step_protocol_v1.json']
    cases=json.loads((OLD/'real_cases.json').read_text(encoding='utf-8'));sources += [ROOT/c['raw_trace_npz'] for c in cases]
    sources += [p for folder in ['B1算法','task','01_项目依据'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    parquet=BASE/'downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet';sources.append(parquet)
    before={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    assert before[parquet.relative_to(ROOT).as_posix()]==json.loads((BASE/'kit_step_protocol_v1.json').read_text(encoding='utf-8'))['sources']['LF']['sha256']
    write('protected_before.json',before)
    print(json.dumps(dict(command_inventory=json.loads((HERE/'command_inventory.json').read_text(encoding='utf-8')),protected=len(before))))
if __name__=='__main__':main()
