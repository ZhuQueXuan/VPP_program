from pathlib import Path
import json,collections,statistics,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';OUT=DATA/'annotations/batch_20261102_b'
OUT.mkdir(parents=True,exist_ok=True)
samples=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))
Y='observed_change';N='no_observable_change';U='unresolved';X='not_applicable_no_limit_edge'
# Manual decisions after viewing all pages 17--32 and the source-row evidence.
decisions={
65:(Y,X,'small_sustained_drift','上限恒定，实际电流和功率在后半窗有持续小幅下降；没有给锚点编造指令。'),
66:(N,X,'quiet_zero','电流和功率均为零。'),
67:(N,X,'steady_nonzero','稳定充电及小幅波动，未见可分辨的独立事件。'),
68:(N,X,'quiet_zero','电流和功率均为零。'),
69:(N,X,'small_fluctuations','电流基本平稳，功率有小起伏；不把坐标轴放大后每个起伏都标成响应。'),
70:(Y,Y,'weak_increase_from_single_low','锚点前一格较低，0秒回升；138秒又短暂回到低值，原单点保留，基线并非长期稳定。'),
71:(N,X,'steady_nonzero','稳定充电及小幅波动。'),
72:(N,X,'quiet_zero','电流和功率均为零。'),
73:(Y,N,'pre_anchor_change_and_slow_power_drift','约-40秒已发生变化，后续功率缓慢漂移；锚点附近没有清楚的独立跟随。'),
74:(Y,X,'stop_without_limit_edge','上限恒定，约56秒后电流、功率停到零；不是无变化负例。'),
75:(N,N,'zero_output_despite_limit_change','上限改变但电流、功率全窗均零。'),
76:(Y,U,'adjacent_edges_and_preexisting_decline','锚点前已有上限改变和电流下降，0秒进一步降低；无法给本次边沿分配可靠独立起止。'),
77:(Y,Y,'repeated_step_down_and_return','由短高水平下降，63秒再回升；前后多次上限往返保留。'),
78:(Y,U,'decaying_previous_pulse','锚点前升高后已经回落，0秒接近原水平；不能把前一脉冲的自然回落硬归为当前动作。'),
79:(Y,Y,'weak_short_dip','锚点及后一格明显降低，8秒部分恢复、12秒接近较早水平；仍是单助手观察初审。'),
80:(Y,Y,'gradual_short_dip_ambiguous_first_boundary','0秒已有小幅下降，4秒下降更清楚，9秒恢复；存在短下降，但首次变化在哪一格开始不够明确，起变标签留空。'),
81:(N,X,'quiet_zero','电流和功率均为零。'),
82:(Y,Y,'sustained_increase','锚点附近由低水平升高并持续，窗口内未恢复。'),
83:(N,N,'no_clear_anchor_following','锚点小幅增上限时电流基本不变；后面另一次很短低上限也未见同步明显下降，不能据此自动宣称故障。'),
84:(Y,Y,'increase_after_brief_lower_plateau','由短低平台回升后持续，窗口内未恢复；更早还有其他下降。'),
85:(N,X,'quiet_zero','电流和功率均为零。'),
86:(N,X,'steady_nonzero','稳定充电及小幅波动。'),
87:(Y,Y,'increase_then_new_higher_limit','锚点后升高，60秒又改为更高上限并再次升高；上限只保持60秒不等于响应60秒后恢复。'),
88:(N,N,'nonbinding_short_limit','实际电流低于变更前后上限，未见对应短下降。'),
89:(N,N,'nonbinding_large_limit_change','上限大幅下降后仍高于实际电流，附近未见明显跟随。'),
90:(N,N,'zero_output_despite_limit_change','上限大幅增加，但电流和功率均为零。'),
91:(Y,Y,'increase_after_brief_low_and_other_stop','锚点从此前一格的低值回升；后面在不变上限下另有掉到零再恢复，不能都拼成当前响应。'),
92:(N,X,'small_fluctuations','小范围起伏，未见清楚的独立事件。'),
93:(Y,U,'adjacent_decreasing_edges','0秒前一格已有另一次降上限及电流下降，后续多次继续下降；整段明显变化，但本次独立贡献不清楚。'),
94:(Y,Y,'short_decrease_with_slow_recovery','短暂下降很清楚，上限恢复后实际先快速回升再长时间缓慢回升；不直接把上限9秒当成完整响应时长。'),
95:(Y,Y,'repeated_short_large_pulses','锚点后升高，33秒先下降、36秒接近此前低水平，随后再升高；原始往返均保留。'),
96:(N,N,'nonbinding_short_limit','实际电流约10A，短暂上限降到11A时未见清楚跟随。'),
97:(N,N,'nonbinding_short_limit','实际电流约28A，短暂上限31A未见清楚跟随。'),
98:(Y,X,'zero_reported_limit_with_output_pulses','上限全为零，电流和功率有明显短暂非零记录，状态也改变；记录含义待核，不当作已知毛刺或控制成功。'),
99:(Y,Y,'short_large_increase_and_return','锚点实际升高，28秒返回原低水平，后面还有其他动作。'),
100:(Y,U,'preexisting_taper','锚点前后实际已有缓慢下降且低于上限，短暂上限变化无法单独隔离。'),
101:(Y,Y,'weak_sustained_increase','0秒两路小幅升高后持续，窗口内没有恢复。'),
102:(Y,Y,'increase_then_new_lower_limit','锚点升高，87秒另一上限使实际降到比旧基线更低的平台；不是恢复到旧基线。'),
103:(U,X,'zero_reported_limit_with_output','上限整窗零但持续有电流、功率，电压字段缺失；不作干净无响应或故障标签。'),
104:(Y,Y,'short_decrease_and_lagged_recovery','实际下降后，上限16秒返回，实际20秒才接近此前水平；保留恢复滞后。'),
105:(Y,N,'later_taper_without_anchor_following','锚点增加上限时实际没有明显改变，随后在上限仍高于实际时分级下降。'),
106:(N,N,'nonbinding_limit_change','实际电流约28.4A，上限31到32A附近未见对应变化。'),
107:(Y,U,'preexisting_taper_then_stop','锚点前已有缓慢下降，后续在恒定上限下停止；当前指令的独立作用不清楚。'),
108:(U,X,'zero_reported_limit_with_output','上限整窗零但持续有电流、功率，电压字段缺失；含义待核，不作干净负例。'),
109:(Y,U,'weak_shifts_opposite_to_limit_direction','实际有弱变化，但锚点增上限后反而缓慢变低，后续还有漂移；不能标成明确控制跟随。'),
110:(Y,Y,'weak_decrease_then_further_limits','锚点小幅下降，之后新的更低上限形成新平台；未见回到旧基线。'),
111:(N,N,'nonbinding_limit_change','实际电流约27.4A，上限变更范围均高于实际，附近未见明确跟随。'),
112:(N,X,'quiet_zero','电流和功率均为零。'),
113:(Y,Y,'weak_gradual_increase_from_brief_low','从锚点前短低值逐步回升，170秒再降到接近该低值；前水平很短，不当长稳定基线。'),
114:(Y,N,'delayed_separate_drop','锚点降上限后实际约2.6A暂时不变，约55秒以后另有大幅下降；保留迟发生的变化，未硬配给锚点。'),
115:(Y,Y,'weak_sustained_increase_then_return','锚点小幅回升，63秒回到原短低平台，后面继续往返。'),
116:(Y,U,'preexisting_rise','实际在锚点前后均逐渐升高，当前上限下降没有可隔离的对应下降。'),
117:(N,N,'small_fluctuations','电流基本稳定；约16秒的单个低点照留，但未据此确认独立动作或故障。'),
118:(Y,Y,'increase_then_taper_after_brief_low','锚点前只有几秒低水平，锚点后先升高、再在不变上限下下降；不当作一个稳定长平台。'),
119:(Y,Y,'weak_increase_with_later_power_shift','锚点实际小幅升高；后面功率还有额外下降，不能全部解释为本次动作或独立故障。'),
120:(Y,Y,'sustained_increase_below_limit','锚点升高并稳定在约16A，低于32A上限；窗口内未恢复。'),
121:(N,N,'nonbinding_limit_change','实际约15A，上限31到32A时附近未见明显变化。'),
122:(Y,U,'fluctuating_taper','电流与功率有较强起伏和渐降，当前上限仍高于实际，难以单独分离其影响。'),
123:(Y,U,'high_limit_context_and_timestamp_bursts','记录有125A上限及很密集的零/非零往返，部分仅隔数十毫秒；0秒和4.727秒也有往返。保留原点，硬件类型和各通道含义未核清，不混作已确认普通AC短响应。'),
124:(Y,Y,'ramped_increase_after_brief_low','锚点前短暂变低，锚点后逐步回到高水平，原始爬坡点保留。'),
125:(Y,Y,'very_short_decrease_lagged_recovery','低上限仅3秒，实际经历多个采样点才完全回升，15秒附近接近原水平；不能按3秒直接定时长。'),
126:(Y,Y,'increase_then_separate_stop','锚点后升高并维持，约140秒在恒定上限下停止；不把停到零当作恢复到此前8A基线。'),
127:(N,N,'nonbinding_limit_change','实际约16A，上限降到18A时未见清楚跟随；后面单个较高点保留，不自动当故障。'),
128:(Y,N,'separate_short_stop_without_anchor_following','锚点降上限时实际未跟随；约88秒在恒定上限下有短暂掉到零再恢复，完整保留但原因不明。')
}
onset={c:0. for c in [70,77,79,82,84,87,91,94,95,99,101,102,104,110,113,115,118,119,120,124,125,126]}
recovered={70:138.,77:63.,79:12.,80:9.,95:36.,99:28.,104:20.,113:170.,115:63.,125:15.}
end={82:'right_censored_by_window',84:'right_censored_by_window',87:'interrupted_by_new_limit',91:'later_unrelated_drop_no_unique_recovery',94:'slow_recovery_and_later_pulse_timing_unresolved',101:'right_censored_by_window',102:'interrupted_by_new_limit',110:'interrupted_by_new_limit',118:'taper_without_return_to_pre_anchor_level',119:'right_censored_with_later_power_shift',120:'right_censored_by_window',124:'right_censored_by_window',126:'later_stop_without_return_to_old_level'}
quality={c:['overlapping_background_or_adjacent_edge'] for c in [76,78,93,100,107,109,116,122]}
for c in [70,77,84,91,113,115,118,124]:quality.setdefault(c,[]).append('brief_or_changing_pre_anchor_level')
quality[80]=['onset_timing_unresolved_despite_visible_short_episode']
quality[94]=['slow_recovery_timing_unresolved']
quality[123]=['high_pilot_context_hardware_unverified','timestamp_bursts','not_certified_ordinary_AC_case']
other={73:'锚点前约-40秒的台阶和后续缓慢漂移。',74:'约56秒后的停充，上限不变。',83:'约74秒的很短低上限，实际未见对应明显下降。',91:'约116秒附近在恒定上限下的短暂掉零。',98:'零上限下多个实际短暂输出；含义未核。',105:'约20秒后开始的分级下降。',107:'约83秒后的停充。',114:'约55秒附近的下降。',119:'约146秒额外功率下降。',126:'约140秒后停充，上限当时未变。',128:'约88秒的短暂掉零及随后恢复。'}
plateaus={82:([-24,-4],[12,40]),87:([-24,-3],[12,40]),99:([-24,-4],[4,24]),101:([-24,-4],[12,40]),102:([-24,-4],[12,40]),104:([-24,-4],[4,12]),110:([-24,-4],[12,40]),119:([-24,-4],[12,40]),120:([-24,-4],[12,40]),126:([-24,-4],[12,40])}
def bracket(s,first):
    j=s['relative_seconds'].index(first);assert j>0
    return dict(relative_seconds=s['relative_seconds'][j-1:j+1],raw_row_indices=s['raw_row_indices'][j-1:j+1],endpoint_current_a=s['current_a'][j-1:j+1],endpoint_power_kw=s['power_kw'][j-1:j+1],endpoint_pilot_a=s['pilot_a'][j-1:j+1])
def summary(s,span):
    ix=[i for i,t in enumerate(s['relative_seconds']) if span[0]<=t<=span[1]]
    assert len(ix)>=3
    return dict(manually_reviewed_range_seconds=span,raw_row_indices=[s['raw_row_indices'][i] for i in ix],n=len(ix),recorded_current_median_a=statistics.median(s['current_a'][i] for i in ix),recorded_power_median_kw=statistics.median(s['power_kw'][i] for i in ix))
ann=[];tasks=[]
for s in samples:
    c=s['case'];w,a,pattern,note=decisions[c];q=list(quality.get(c,[]))
    voltage=[v for v in s['voltage_v'] if v is not None]
    if not voltage:q.append('voltage_channel_missing')
    if all(v==0 for v in s['pilot_a']) and any(v is not None and v>.1 for v in s['power_kw']):q.append('zero_reported_limit_with_positive_output')
    if max([0]+[v for v in s['pilot_a'] if v is not None])>80:q.append('reported_limit_above_80A')
    gaps=[b-a for a,b in zip(s['relative_seconds'][:-1],s['relative_seconds'][1:])]
    if max(gaps or [240])>15:q.append('local_record_gap_over_15s')
    r={k:s[k] for k in ['case','event_id','source_path','source_sha256','local','split','user_group','station_group','raw_row_index','anchor_timestamp','stratum','pilot_delta_a','limit_hold_seconds']}
    r.update(window_observation_label=w,anchor_following_label=a,pattern=pattern,notes_zh=note,quality_flags=sorted(set(q)),other_observed_changes_zh=other.get(c),onset_bracket=bracket(s,onset[c]) if c in onset else None,recovery_completion_bracket=bracket(s,recovered[c]) if c in recovered else None,end_status='observed_recovery' if c in recovered else end.get(c,'not_assigned'),effective_duration_seconds=None,clean_power_kw=None,fault_label=None,causal_response_success=None,gold_physical_truth=False,review_source='single_assistant_visual_raw_review',independent_review_status='pending',approved_for_production_training=False,hardware_type='unverified',source_context=dict(voltage_values_present=len(voltage),recorded_voltage_median_v=statistics.median(voltage) if voltage else None,charging_states=sorted({v for v in s['charging_state'] if v}),local_points=len(s['relative_seconds']),max_local_gap_seconds=max(gaps or [240])),review_page=f'work/b1_real_labeling_extension_20261102/review_pages/page_{(c-1)//4+1:02d}.png')
    if c in plateaus:
        before,after=[summary(s,x) for x in plateaus[c]]
        r['recorded_level_descriptors']=dict(before=before,after=after,recorded_power_change_kw=after['recorded_power_median_kw']-before['recorded_power_median_kw'],not_clean_or_counterfactual_power=True)
    if c==80:r['onset_timing_status']='unresolved_between_small_initial_change_and_clearer_next_sample'
    ann.append(r)
    tasks.append(dict(id=c,data=dict(case_id=f'ACN-review-{c:03d}',source_context='Original source states: '+','.join(sorted({v for v in s['charging_state'] if v})),ts={k:s[k] for k in ['current_a','power_kw','pilot_a','voltage_v','cumulative_energy_kwh']}|dict(time=s['relative_seconds']))))
write=lambda n,o:(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
write('first_pass_annotations.json',ann);write('second_review_unlabelled_tasks.json',tasks)
write('task_registry.json',[{k:r[k] for k in ['case','event_id','source_path','source_sha256','split','user_group']} for r in ann])
config=(DATA/'annotations/batch_20261102/label_studio_config.xml').read_text(encoding='utf-8')
config=config.replace('<Header value="$case_id"/>','<Header value="$case_id"/>\n  <Text name="source_context" value="$source_context"/>')
config=config.replace('<Channel column="pilot_a"/>','<Channel column="pilot_a"/>\n    <Channel column="voltage_v"/>\n    <Channel column="cumulative_energy_kwh"/>')
(OUT/'label_studio_config.xml').write_text(config,encoding='utf-8')
(OUT/'review_rubric.json').write_text((ROOT/'work/b1_real_labeling_20261102/review_rubric.json').read_text(encoding='utf-8'),encoding='utf-8')
stats=dict(windows=len(ann),users=len({r['user_group'] for r in ann}),roles=dict(collections.Counter(r['split'] for r in ann)),strata=dict(collections.Counter(r['stratum'] for r in ann)),window_labels=dict(collections.Counter(r['window_observation_label'] for r in ann)),anchor_labels=dict(collections.Counter(r['anchor_following_label'] for r in ann)),onset_brackets=sum(r['onset_bracket'] is not None for r in ann),recovery_completion_brackets=sum(r['recovery_completion_bracket'] is not None for r in ann),independent_gold_labels=0,models_fit=0,test_values_read=False,production_changed=False)
write('batch_summary.json',stats)
old=json.loads((DATA/'annotations/batch_20261102/first_pass_annotations.json').read_text(encoding='utf-8'))
combined=dict(windows=len(old+ann),users=len({r['user_group'] for r in old+ann}),roles=dict(collections.Counter(r['split'] for r in old+ann)),window_labels=dict(collections.Counter(r['window_observation_label'] for r in old+ann)),anchor_labels=dict(collections.Counter(r['anchor_following_label'] for r in old+ann)),onset_brackets=sum(r['onset_bracket'] is not None for r in old+ann),recovery_completion_brackets=sum(r['recovery_completion_bracket'] is not None for r in old+ann),gold_physical_labels=0,independent_review_pending=True,models_fit=0,test_values_read=False)
(HERE/'combined_summary.json').write_text(json.dumps(combined,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(new=stats,combined=combined)),flush=True)
