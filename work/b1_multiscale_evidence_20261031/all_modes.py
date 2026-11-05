"""Exhaustive command-only extension: retain zero-command stop/start returns.

The initial inventory inherited the old >=6A operating filter. The user's data
audit is broader; enumerate every short return rather than omit stop/start.
No current response is consulted in selection; initial17 remain untouched.
"""
from prepare import *

def main():
    g=defaultdict(list)
    with (BASE/'runs/PREP_KIT_STEPS_01/all_phase_candidates.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['phase']=='L1':g[r['charging_uuid']].append(r)
    out=[]
    for uid,rr in sorted(g.items()):
        rr.sort(key=lambda r:int(r['edge_index']))
        for a,b in zip(rr,rr[1:]):
            duration_us=int(b['edge_time_us'])-int(a['edge_time_us'])
            if 0<duration_us<=10000000 and float(b['new_command_A'])==float(a['previous_command_A']) and abs(float(a['step_A']))>=2:
                out.append(dict(event_id=a['event_id'].replace(':L1',':command_return'),recording=uid,
                    edge_index=int(a['edge_index']),return_edge_index=int(b['edge_index']),
                    source_file_row=int(a['source_file_row']),return_source_file_row=int(b['source_file_row']),
                    edge_time_us=int(a['edge_time_us']),return_time_us=int(b['edge_time_us']),duration_us=duration_us,
                    previous_command_A=float(a['previous_command_A']),new_command_A=float(a['new_command_A']),direction=a['direction'],
                    mode='stop_start_command_involves_zero' if min(float(a['previous_command_A']),float(a['new_command_A']))==0 else 'both_commands_ge6',
                    label='recorded_short_command_return_not_true_response_or_fault'))
    write('pulse_selection_all_modes.json',out)
    write('protocol_addendum.json',dict(reason='Initial17 inherited >=6A historic steady-charging filter; include all zero-command returns to answer user evidence question without discarding stop/start.',
        selection='All command returns within10s, |step|>=2A; no current-response selection or new tuning.',
        all_returns=len(out),zero_command_returns=sum(r['mode']=='stop_start_command_involves_zero' for r in out),recordings=len({r['recording'] for r in out}),
        subset17_kept=True,source='Same frozen command ledger and same original Parquet; auxiliary observational scope, not a new independent validation cohort.'))
    print(json.dumps(json.loads((HERE/'protocol_addendum.json').read_text(encoding='utf-8'))))
if __name__=='__main__':main()
