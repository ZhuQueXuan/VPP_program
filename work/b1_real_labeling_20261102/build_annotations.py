from pathlib import Path
import json, hashlib, collections, statistics, math

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
OUT=DATA/'annotations/batch_20261102'
OUT.mkdir(parents=True,exist_ok=True)
samples=json.loads((HERE/'samples.json').read_text(encoding='utf-8'))

# Manual first-pass decisions after visual inspection of all sixteen raw pages.
# W/A: whole-window / following-anchor observational labels. These are not model
# predictions or certified physical truths. Coordinates below are manually chosen
# native sample times, not selected by a numerical edge detector.
Y='observed_change';N='no_observable_change';U='unresolved';X='not_applicable_no_limit_edge'
decisions={
 1:(N,X,'quiet_zero','电流和功率均为零；上限保持不变。'),
 2:(Y,Y,'weak_decrease_with_repeated_pulses','锚点附近两路均小幅下降；后面还有往返。功率另有电流不对应的变化，不全归为本次动作。'),
 3:(Y,X,'pre_anchor_pulse','上限不变，但锚点之前电流和功率曾短暂升高后回零；不是整个窗口的无变化样本。'),
 4:(N,X,'small_fluctuations','电流轻微漂移、功率有小波动，未见可分辨的独立事件；不表示物理变化严格为零。'),
 5:(Y,Y,'short_ramp_pulse','上限先变，下一原始采样才开始升高，随后爬坡、短平台并返回。'),
 6:(Y,N,'late_separate_drop','锚点附近实际电流低于上限且无明显跟随；约末段另一次上限变化伴随大幅下降。'),
 7:(Y,Y,'repeated_short_pulses','本窗口多次短往返；锚点附近上升后回到原来水平，不能把全窗口合成一个长响应。'),
 8:(N,X,'steady_nonzero','持续非零充电，仅小幅波动。'),
 9:(N,N,'short_limit_without_visible_following','短暂上限变化期间实际电流低于上限，未见清楚的对应短脉冲。'),
10:(Y,Y,'weak_single_low_observation','锚点时电流未变，4秒处出现下降，7秒已返回；原点保留，不能仅因短而标为故障。前面另有更大脉冲。'),
11:(Y,Y,'weak_short_pulse','锚点及随后一格电流和功率降低，8秒处恢复。'),
12:(N,X,'steady_nonzero','稳定充电及小波动，没有清楚的事件边界。'),
13:(Y,U,'overlapping_taper','整窗缓慢下降，早于锚点已在变化；不能把整个下降归为这次小幅上限变化。'),
14:(Y,U,'fluctuating_taper','有缓慢下降及明显起伏，短暂上限变化没有可可靠隔离的对应片段。'),
15:(Y,Y,'weak_sustained_decrease','两路在锚点同步小幅下降并维持；窗口内未见恢复。'),
16:(N,X,'quiet_zero','电流和功率均为零。'),
17:(Y,Y,'weak_repeated_steps','锚点下降并持续，67秒附近回升；此前高水平很短，不当作长稳定基线。'),
18:(U,U,'insufficient_local_coverage','窗口实际只有三个原始点（-5、-4、0秒）；0秒虽见升高，缺少后续记录，无法可靠标完整片段。'),
19:(Y,Y,'decrease_with_later_extra_dropout','锚点附近下降，166秒附近返回；其间另有一次掉到零又恢复，不删除、不宣称设备故障。'),
20:(Y,Y,'weak_increase','锚点由较低值升高；此前低水平很短，后续仍有小幅往返。'),
21:(N,X,'quiet_zero','电流和功率均为零。'),
22:(Y,N,'late_separate_stop','锚点附近未见跟随；窗口末端有明显下降，不能把末端下降硬配给锚点。'),
23:(Y,X,'stop_without_limit_edge','上限保持不变但末段停止充电；不能因为上限没变就当负例。'),
24:(Y,U,'overlapping_taper','实际电流持续渐降，低于变更前后上限；锚点独立作用不清楚。'),
25:(Y,Y,'weak_repeated_steps','锚点小幅下降并维持，后面反复回升、回落。'),
26:(Y,Y,'short_multi_sample_dip','短暂降上限伴随数格下降，随后逐渐恢复；恢复滞后于上限返回。'),
27:(N,X,'steady_nonzero','稳定充电及小波动。'),
28:(N,N,'nonbinding_limit_change','上限增加，实际电流仍在原水平，未见清楚的附近变化。'),
29:(N,X,'quiet_zero','电流和功率均为零。'),
30:(U,X,'channel_interpretation_issue','上限和功率均零，电流却恒为约0.782A；记录含义待核，不标成干净无响应或已知故障。'),
31:(Y,Y,'weak_short_dip','锚点及后一格下降，8秒处恢复；不能抹去短低点。'),
32:(Y,Y,'large_short_dip','0秒收到低上限但电流未降，4秒大幅下降，8秒已回升、13秒接近原水平；原始单个最低点保留。'),
33:(N,X,'quiet_zero','回查原始数值，电流和功率均为零。'),
34:(Y,X,'variable_output_zero_reported_limit','上限整窗零但实际持续有电流和功率，且明显变化；上限含义不可直接解释，不能推断故障。'),
35:(Y,Y,'weak_sustained_step_then_return','锚点小幅下降，63秒上限恢复时实际尚低，67秒实际接近原水平。'),
36:(Y,Y,'weak_short_pulse','两格降低后8秒恢复。'),
37:(Y,Y,'weak_short_increase_with_single_return','升高持续至52秒，56秒出现低值，60秒再次升高；这一格回落也保留。'),
38:(N,N,'small_fluctuations','短暂上限下降未见清楚电流响应，功率有小幅起伏，不据此造故障标签。'),
39:(Y,Y,'increase_then_new_limit','锚点后升高；12秒很快换成另一上限，未回到锚点前水平，不能给完整恢复时长。'),
40:(N,X,'steady_nonzero','稳定充电及小波动。'),
41:(Y,Y,'weak_short_pulse','锚点下降、8秒接近原水平，后面另有更大变化。'),
42:(Y,N,'late_separate_drop','锚点小幅降上限时实际未跟随；后面更低上限伴随明显下降，单独保留。'),
43:(N,N,'nonbinding_limit_change','实际电流低于上限变化范围，未见附近明确变化。'),
44:(Y,Y,'increase_to_lower_than_limit_plateau','实际由低水平上升后稳定在约16A，明显低于29A上限；窗口左边另有启动变化。'),
45:(Y,Y,'sustained_increase','锚点附近升高并维持，窗口内未恢复。'),
46:(N,N,'nonbinding_limit_change','实际电流约15A，上限31到32A没有可见对应改变。'),
47:(N,X,'quiet_zero','电流和功率均为零。'),
48:(N,X,'quiet_zero','电流和功率均为零。'),
49:(Y,Y,'decrease_then_ramped_recovery','实际下降，后续上限升高时逐步恢复；使用原记录上限30到26A，不沿用图外估计数。'),
50:(Y,Y,'sustained_increase','锚点附近升高；后续上限微降仍高于实际，未出现回到旧水平的恢复。'),
51:(Y,Y,'weak_increase_from_brief_low','由短低点回升；106秒后回落再回升，基线仅短暂出现，不标长稳定基线。'),
52:(N,N,'nonbinding_limit_change','实际电流约16A，上限增加后未见清楚附近变化。'),
53:(N,N,'nonbinding_limit_change','实际电流约15.5A，上限增加后未见清楚附近变化。'),
54:(Y,Y,'weak_sustained_increase_then_return','锚点小幅升高，122秒首次接近旧水平、126秒更接近；恢复不是精确瞬时真值。'),
55:(Y,U,'overlapping_taper','实际电流远低于上限，锚点前后都在缓慢下降，无法可靠隔离该指令影响。'),
56:(Y,Y,'increase_after_short_low','从短暂低水平升高并维持；前面已有反复短动作。'),
57:(N,N,'very_low_output_without_following','电流约0.5A、功率约0.025kW，附近未见对应清楚变化；不能推断潜在响应恰为零。'),
58:(Y,U,'isolated_observed_excursions_unknown_cause','多个短暂非零记录，方向也不是上限下降对应的下降；均保留，不能宣称真实控制响应或已知毛刺。'),
59:(Y,Y,'increase_then_new_plateau','锚点后升高；后续新上限形成另一平台，没有回到原基线，不强填恢复时间。'),
60:(N,N,'nonbinding_limit_change','实际电流约3.6A，上限18降12A时未见对应变化。'),
61:(Y,Y,'ramp_then_taper','锚点后爬坡，继而在恒定上限下逐步下降；不能用一个长稳定平台描述全段。'),
62:(Y,Y,'very_weak_sustained_change','约0.1kW下降清楚可见并随上限返回而回升；有变化不等于达到旧0.15kW有效阈值。'),
63:(Y,U,'preexisting_decline_then_stop','锚点前另一上限变化时已经下降，随后停到零；不能把整段停充归因本次上限。'),
64:(N,N,'small_fluctuations','实际电流基本平稳，功率有轻微漂移；未见可隔离的锚点事件。')
}
# First visibly changed native observation for manually identifiable anchor
# transitions; the immediately preceding native sample supplies the other bound.
onset={c:0. for c in [2,7,11,15,17,19,20,25,26,31,35,36,37,39,41,44,45,49,50,51,54,56,59,61]}
onset.update({5:4.,10:4.,32:4.,62:4.})
# First observation near the former level, deliberately distinct from return
# start and from any threshold-defined effective duration.
recovered={5:51.,7:15.,10:7.,11:8.,17:67.,19:166.,20:141.,25:67.,26:11.,31:8.,32:13.,35:67.,36:8.,37:56.,41:8.,49:67.,51:110.,54:126.,62:107.}
end_status={2:'multiple_later_edges_no_unique_recovery',15:'right_censored_by_window',39:'interrupted_by_new_limit',44:'right_censored_by_window',45:'right_censored_by_window',50:'right_censored_by_window',56:'right_censored_by_window',59:'interrupted_by_new_limit',61:'taper_without_return_to_old_level'}
quality={18:['insufficient_local_coverage'],30:['current_nonzero_power_zero_reported_limit_zero'],34:['reported_limit_zero_with_sustained_output'],58:['isolated_observations_cause_unresolved']}
for c in [13,14,24,55,63]:quality[c]=['overlapping_background_change']
for c in [17,20,37,51,56,61]:quality.setdefault(c,[]).append('brief_or_changing_pre_anchor_level')
other={
 3:'锚点之前约-56至-40秒的脉冲；上限恒定。',
 6:'约154秒以后的另一次下降，不是锚点事件。',
19:'约120至128秒另有短暂掉到零又返回，原因未核。',
22:'约窗口末端180秒的停止，右截尾。',
23:'约166秒附近的停止，上限无边沿。',
34:'整窗存在变化，但零上限无法提供可靠配对依据。',
42:'约175秒附近另一上限下降及实际下降。',
58:'锚点及约45秒的短暂非零记录，原点保留、原因不明。',
63:'约-8秒开始的已有下降和4至8秒之间的停到零。'
}
plateau_ranges={5:([-12,-4],[12,40]),15:([-12,-4],[12,40]),54:([-12,-4],[12,40]),62:([-12,-4],[12,40])}

def bracket(s,first):
    t=s['relative_seconds'];j=t.index(first)
    assert j>0
    return dict(relative_seconds=[t[j-1],t[j]],raw_row_indices=[s['raw_row_indices'][j-1],s['raw_row_indices'][j]],endpoint_current_a=[s['current_a'][j-1],s['current_a'][j]],endpoint_power_kw=[s['power_kw'][j-1],s['power_kw'][j]],endpoint_pilot_a=[s['pilot_a'][j-1],s['pilot_a'][j]])

def native_summary(s,span):
    use=[i for i,t in enumerate(s['relative_seconds']) if span[0]<=t<=span[1]]
    assert len(use)>=3
    return dict(manually_reviewed_range_seconds=span,raw_row_indices=[s['raw_row_indices'][i] for i in use],n=len(use),recorded_current_median_a=statistics.median(s['current_a'][i] for i in use),recorded_power_median_kw=statistics.median(s['power_kw'][i] for i in use))

annotations=[];tasks=[]
for s in samples:
    c=s['case'];w,a,pattern,note=decisions[c]
    assert (c in onset)==(a==Y)
    record={k:s[k] for k in ['case','event_id','source_path','source_sha256','local','split','user_group','station_group','raw_row_index','anchor_timestamp','stratum','pilot_delta_a','limit_hold_seconds']}
    record.update(window_observation_label=w,anchor_following_label=a,pattern=pattern,notes_zh=note,quality_flags=quality.get(c,[]),other_observed_changes_zh=other.get(c),onset_bracket=bracket(s,onset[c]) if c in onset else None,recovery_completion_bracket=bracket(s,recovered[c]) if c in recovered else None,end_status='observed_recovery' if c in recovered else end_status.get(c,'not_assigned'),effective_duration_seconds=None,clean_power_kw=None,fault_label=None,causal_response_success=None,gold_physical_truth=False,review_source='single_assistant_visual_raw_review',independent_review_status='pending',approved_for_production_training=False,review_page=f'work/b1_real_labeling_20261102/review_pages/page_{(c-1)//4+1:02d}.png')
    if c in plateau_ranges:
        before,after=[native_summary(s,x) for x in plateau_ranges[c]]
        record['recorded_level_descriptors']=dict(before=before,after=after,recorded_power_change_kw=after['recorded_power_median_kw']-before['recorded_power_median_kw'],not_clean_or_counterfactual_power=True)
    annotations.append(record)
    # Deliberately no predictions, annotations, outcomes or manual notes in the
    # independent-review packet. The role is inherited unchanged in a separate
    # registry, and is not presented as a clue to an outcome.
    tasks.append(dict(id=c,data=dict(case_id=f'ACN-review-{c:02d}',ts=dict(time=s['relative_seconds'],current_a=s['current_a'],power_kw=s['power_kw'],pilot_a=s['pilot_a']))))

assert len(annotations)==64 and len({r['user_group'] for r in annotations})==64
assert all(r['split'] in ['training','validation'] for r in annotations)
save=lambda name,value:(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
save('first_pass_annotations.json',annotations)
save('second_review_unlabelled_tasks.json',tasks)
save('task_registry.json',[{k:r[k] for k in ['case','event_id','source_path','source_sha256','split','user_group']} for r in annotations])
(OUT/'label_studio_config.xml').write_text('''<View>
  <Header value="$case_id"/>
  <Text name="instruction" value="Review original observations. A reported limit change is not response truth. Mark observed onset/recovery brackets or unresolved regions; do not erase short points."/>
  <TimeSeriesLabels name="intervals" toName="ts">
    <Label value="Observed onset bracket" background="#2a9d8f"/>
    <Label value="Observed recovery completion bracket" background="#457b9d"/>
    <Label value="Other observed change" background="#e9c46a"/>
    <Label value="Unresolved region" background="#e76f51"/>
  </TimeSeriesLabels>
  <TimeSeries name="ts" valueType="json" value="$ts" timeColumn="time">
    <Channel column="current_a"/>
    <Channel column="power_kw"/>
    <Channel column="pilot_a"/>
  </TimeSeries>
  <Choices name="window_observation" toName="ts" choice="single" required="true">
    <Choice value="observed_change"/><Choice value="no_observable_change"/><Choice value="unresolved"/>
  </Choices>
  <Choices name="anchor_following" toName="ts" choice="single" required="true">
    <Choice value="observed_change"/><Choice value="no_observable_change"/><Choice value="unresolved"/><Choice value="not_applicable_no_limit_edge"/>
  </Choices>
  <TextArea name="review_notes" toName="ts" placeholder="Describe missing coverage, other changes and what cannot be established."/>
</View>
''',encoding='utf-8')
summary=dict(windows=len(annotations),users=len({r['user_group'] for r in annotations}),split_counts=dict(collections.Counter(r['split'] for r in annotations)),stratum_counts=dict(collections.Counter(r['stratum'] for r in annotations)),window_observation_counts=dict(collections.Counter(r['window_observation_label'] for r in annotations)),anchor_following_counts=dict(collections.Counter(r['anchor_following_label'] for r in annotations)),onset_brackets=sum(r['onset_bracket'] is not None for r in annotations),recovery_completion_brackets=sum(r['recovery_completion_bracket'] is not None for r in annotations),quality_flagged=sum(bool(r['quality_flags']) for r in annotations),independent_gold_labels=0,production_training_approved=0,models_fit=0,algorithm_comparison_performed=False,test_response_values_read=False,source_points_changed=False)
save('batch_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
