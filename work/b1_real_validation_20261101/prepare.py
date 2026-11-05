"""Freeze real-data test selections using metadata/time coverage, not errors."""
from common import *
from collections import defaultdict

def main():
    protocol=dict(scope='Real observed ordinary AC charging external validation. No synthetic responses, injected noise, point removal, gap fill, interpolation, model training or tuning.',
        data='Dortmund publisher static AC charging profiles, actual grid-side PQA power, native~500ms aggregated by original sample count into1min means; both EVTEC200/Wirelane210 retained separately.',
        selection='All12 published ordinary AC members. First2 eligible analysis windows per member, each60min; at least180 prior minutes for2 distinct60min observed histories and one60min legal pre-notice prefix. Analysis windows nonoverlapping. Select by original timestamps/finite coverage before fitting, no outcome-based choice.',
        coverage='Each minute >=90 samples, >=59s time support, finite power in every sample, no backwards timestamp or gap>2s. Entire240min history/prefix/analysis block must meet coverage. Missing/bad minutes are exclusions, never repaired.',
        history='Two preceding nonoverlapping60min ordinary-charging segments from the SAME recording, both completed before current prefix; not other vehicles, not fictional independent past sessions. Real model is frozen; source history distribution differs from its simulated training.',
        forecast='Existing frozen reliable reference model, all60 observed prefix points before notice and supplied observed historical mean. Neither task/post-window actual power is available to the notice-time forecast.',
        process='Existing frozen duration_fusion and reference_tracked_duration, q1.5kW/W30min/sigma.05 declared model setting. Sigma is not a measured real instrument calibration. One-minute scale is native aggregation, not invented fine data.',
        truth='Future actual meter power in these ordinary charging profiles is valid observed-power forecasting target. Windows are pseudo-task background checks with no new regulation dispatched, NOT verified true DR response durations or real fault labels.',
        metrics='Compare observed future power prediction RMSE/MAE before/after tracking, plus positive response outputs on background windows, all raw feature estimates retained. Do NOT report real response-duration MAE or real short-response sensitivity from these data.',
        controlled_dynamic='Existing25AC dynamic files have minute/short command steps and subsecond power, but <60min total observation, so do not pad or rescale them into the current60min30min-task model.',
        models='All production/source models frozen before real test. No candidate selection from real performance, no automatic adoption from this test.')
    write('protocol.json',protocol)
    groups=defaultdict(dict)
    for r in read('dortmund_minutes_checked.json'):groups[r['recording']][r['minute']]=r
    selections=[];coverage=[]
    for uid,minutes in sorted(groups.items()):
        admitted=[];excluded=defaultdict(int)
        for analysis_start in range(180,max(minutes)+1-59):
            if admitted and analysis_start<admitted[-1]+60:continue
            block=[minutes.get(i) for i in range(analysis_start-180,analysis_start+60)]
            reason=None
            for r in block:
                if r is None:reason='missing_minute';break
                if r['finite_n']!=r['raw_n']:reason='nonfinite_power';break
                if r['raw_n']<90 or r['last_epoch_ms']-r['first_epoch_ms']<59000:reason='incomplete_minute';break
                if r['max_gap_ms']>2000:reason='gap_over2s';break
                if r['backward_steps']:reason='backward_timestamp';break
            if reason:excluded[reason]+=1;continue
            admitted.append(analysis_start)
            selections.append(dict(case_id='dortmund-'+str(len(selections)).zfill(3),member=uid,analysis_start_minute=analysis_start,task_start_minute=analysis_start+15,
                history1_minutes=[analysis_start-180,analysis_start-120],history2_minutes=[analysis_start-120,analysis_start-60],prefix_minutes=[analysis_start-60,analysis_start],analysis_minutes=[analysis_start,analysis_start+60],
                first_history_source_line=block[0]['first_source_line'],last_analysis_source_line=block[-1]['last_source_line'],raw_samples_in_all240min=sum(r['raw_n'] for r in block)))
            if len(admitted)==2:break
        coverage.append(dict(member=uid,available_minutes=len(minutes),selected_windows=len(admitted),reasons=dict(excluded),duration_sufficient=max(minutes)+1>=240))
    write('selection.json',selections);write('selection_coverage.json',coverage)
    paths=[p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT/'data/public_datasets/德国_多特蒙德_电动汽车充电实验/dataset_merged.zip',ROOT/'work/ev_charging_research_20261016/downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet',HERE/'protocol.json',HERE/'selection.json',HERE/'dortmund_minutes_checked.json']
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},original_algorithm_not_changed=True,selected_before_model_outputs=True))
    print(json.dumps(dict(ordinary_AC_files=len(groups),selected_windows=len(selections),selected_recordings=sum(x['selected_windows']>0 for x in coverage),coverage=coverage)),flush=True)
if __name__=='__main__':main()
