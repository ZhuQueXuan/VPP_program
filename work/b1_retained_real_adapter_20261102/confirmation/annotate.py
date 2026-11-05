from pathlib import Path
import json,hashlib,datetime,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
samples=read(HERE/'samples.json');Y='observed_change';N='no_observable_change';U='unresolved';X='not_applicable_no_limit_edge'
# Single-assistant raw visual review of pages33--40 and source_evidence rows.
# No new-window native fit or adapted-model output has been generated yet.
decisions={
129:(Y,Y,'weak_delayed_rise','0和1秒仍处低水平，3秒才清楚回升；66秒短暂回到旧电流水平，功率允许原记录中的自然小差异。'),
130:(Y,Y,'weak_drop_and_return','锚点下降，63秒先部分回升，67秒接近原水平。'),
131:(Y,U,'preexisting_rise_with_adjacent_edge','锚点前一格已经明显上升，且相邻上限先下降后升高；不能把整个爬升归为本次1A边沿。'),
132:(Y,Y,'short_step_up_and_return','锚点实际升高，27秒回到此前低水平；其余多次往返均保留。'),
133:(Y,Y,'short_drop_slow_return_and_later_stop','锚点有清楚下降，随后逐渐回升，28秒接近之前约9A水平；后面另有停到零，不能合并为当前恢复。上限与实际原本不贴合，不据此证明因果。'),
134:(Y,Y,'weak_step_down_with_single_point_return','锚点由此前短高水平下降，61秒单点回到高水平后又下降；这一格真实记录保留，不填平。'),
135:(N,X,'quiet_zero','电流和功率均零。'),
136:(N,X,'steady_nonzero','稳定充电与小波动，无清楚独立事件。'),
137:(Y,N,'late_weak_shift_without_anchor_following','短暂上限下降附近未见明确跟随；后半窗有轻微持续抬升，不硬归为锚点。'),
138:(N,X,'quiet_zero','电流和功率均零。'),
139:(Y,X,'late_change_without_limit_edge','上限恒定，末段电流和功率升高，不能作为整窗无变化负例。'),
140:(N,N,'nonbinding_short_limit','上限17到18A，实际约14.8A基本不变，功率仅小波动。'),
141:(N,X,'steady_nonzero','稳定充电与小波动。'),
142:(Y,N,'later_new_limit_causes_drop','锚点18到20A附近实际约16A不变，32秒另一条低上限才伴随明显下降，不能混作本次起变。'),
143:(N,N,'zero_output','上限变而电流和功率均零。'),
144:(Y,N,'pre_anchor_stop','锚点之前已经降到很小电流和功率，当前降上限附近无明确新变化。'),
145:(N,X,'quiet_zero','上限、电流、功率均零，不推断设备故障。'),
146:(Y,N,'later_taper','锚点附近无清楚跟随，后面实际缓慢下降，保留后续变化。'),
147:(Y,Y,'weak_rise_from_brief_low','锚点从短低水平回升，133秒电流回到之前低水平；功率与前值略有差异，仍是初步观测判读。'),
148:(N,N,'nonbinding_short_limit','实际约7.7A，上限10到9A附近未见明确跟随。'),
149:(Y,U,'pre_anchor_small_excursion','锚点前出现小幅电流/功率抬升然后返回，当前上限变化也在附近，不能可靠分离归属。'),
150:(N,X,'steady_nonzero','稳定充电与小波动。'),
151:(N,N,'nonbinding_limit_change','上限19到20A，实际约16A附近无清楚跟随。'),
152:(Y,Y,'increase_then_new_higher_limit','锚点升高后维持，后面另一较高上限继续升高，未回到此前低水平；左侧还存在其他短暂停充。'),
153:(N,X,'quiet_zero','电流和功率均零。'),
154:(Y,Y,'decrease_then_further_limits','锚点下降，后面更低上限带来更多下降，没有回到此前水平。'),
155:(Y,Y,'weak_short_dip_lagged_return','9秒上限返回时实际只部分恢复，12秒才接近此前电流和功率水平。'),
156:(Y,Y,'weak_short_rise_lagged_return','上限12秒返回而实际仍高，16秒才回到此前水平；后面另有较大下降，均保留。'),
157:(Y,Y,'sustained_large_decrease','锚点大幅下降后持续，窗口内没有恢复。'),
158:(N,N,'nonbinding_large_limit_change','实际约3.8A，上限18降到8A时附近仍未见清楚变化。'),
159:(Y,Y,'sustained_increase_below_limit','锚点明显升高，后续实际电流远低于32A上限，窗口内没有恢复。'),
160:(Y,Y,'weak_sustained_decrease','锚点先部分下降、下一格进一步下降，之后维持，窗口内没有恢复。')
}
onset={c:0. for c in [130,132,133,134,147,152,154,155,156,157,159,160]};onset[129]=3.
recover={129:66.,130:67.,132:27.,133:28.,134:61.,147:133.,155:12.,156:16.}
def bracket(s,time):
    j=s['relative_seconds'].index(time);assert j>0
    return dict(relative_seconds=s['relative_seconds'][j-1:j+1],raw_row_indices=s['raw_row_indices'][j-1:j+1],endpoint_power_kw=s['power_kw'][j-1:j+1],endpoint_current_a=s['current_a'][j-1:j+1])
ann=[];rows=[]
for s in samples:
    c=s['case'];w,a,pattern,note=decisions[c];end='observed_recovery' if c in recover else 'interrupted_by_new_limit' if c in [152,154] else 'right_censored_by_window' if c in [157,159,160] else 'not_assigned'
    r={k:s[k] for k in ['event_id','case','source_path','local','source_sha256','split','user_group','station_group','raw_row_index','anchor_timestamp','stratum']}
    r.update(window_observation_label=w,anchor_following_label=a,pattern=pattern,notes_zh=note,onset_bracket=bracket(s,onset[c]) if c in onset else None,recovery_completion_bracket=bracket(s,recover[c]) if c in recover else None,end_status=end,gold_physical_truth=False,independent_review_status='pending',review_source='single_assistant_raw_review_before_new_outputs',effective_duration_seconds=None,causal_success=None,fault_label=None)
    ann.append(r);binary={Y:1,N:0}
    targets=dict(window_visible_change=binary.get(w),window_label_status=w,anchor_visible_following=binary.get(a),anchor_label_status=a,onset_bracket_seconds=r['onset_bracket']['relative_seconds'] if r['onset_bracket'] else None,recovery_completion_bracket_seconds=r['recovery_completion_bracket']['relative_seconds'] if r['recovery_completion_bracket'] else None,recovery_status=end,effective_duration_seconds=None,fault_label=None,causal_response_success=None)
    rows.append(dict(event_id=s['event_id'],split='validation',model_input={k:s[k] for k in ['relative_seconds','current_a','pilot_a','power_kw']},provisional_targets=targets,label_source=r['review_source'],independent_review_status='pending',physical_gold=False))
write=lambda n,o:(HERE/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
write('annotations.json',ann);write('inputs.json',rows)
write('label_freeze.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_new_window_model_outputs=True,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'annotate.py',HERE/'annotations.json',HERE/'inputs.json']},provisional_single_assistant_not_physical_gold=True))
print(json.dumps(dict(windows=len(ann),anchor_labels=dict(collections.Counter(r['anchor_following_label'] for r in ann)),onsets=len(onset),recoveries=len(recover),independent_gold=0,new_window_model_outputs_exist=False)),flush=True)
