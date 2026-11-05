from common import *

def main():
    write('protected_before.json',snapshot())
    cases=json.loads((OLD/'real_cases.json').read_text(encoding='utf-8'));counts=[];gaps=[];command_bad=[];hashes={};singleton_runs=0;longest_runs=[]
    for c in cases:
        p=ROOT/c['raw_trace_npz'];hashes[c['raw_trace_npz']]=sha(p)
        with np.load(p,allow_pickle=False) as a:
            times=a['relative_time_us'];u=a['command_A'];cur=a['phase_current_A']
            assert len(times)==len(u)==len(cur) and np.all(np.diff(times)>0)
            gaps.extend(np.diff(times).tolist());counts.append(len(times))
            good=np.where(times<0,c['previous_command_A'],c['new_command_A'])
            if not np.array_equal(u,good):command_bad.append(c['event_id'])
        y=np.asarray(c['progress']);mask=(np.asarray(c['starts_s'])>=0)&(y>=.1)
        d=np.diff(np.r_[False,mask,False].astype(int));runs=np.flatnonzero(d==-1)-np.flatnonzero(d==1)
        singleton_runs+=int(np.sum(runs==1));longest_runs.append(int(max(runs,default=0)))
    write('fine_data_audit.json',dict(events=len(cases),recordings=len({c['recording'] for c in cases}),
        bin_seconds=.1,bins_each=200,native_sample_count_range=[min(counts),max(counts)],
        native_gap_us_median=float(np.median(gaps)),native_gap_us_max=int(max(gaps)),
        raw_command_not_equal_simple_step_events=command_bad,
        observed10percent_longest_run_samples_min_median_max=[min(longest_runs),float(np.median(longest_runs)),max(longest_runs)],
        observed_single_bin_runs=singleton_runs,latent_clean_truth=False,fault_labels=False,
        reference='Existing real command/current, not known untreated reference',source_sha256=hashes))
    p=dict(schema='b1.fine-evidence-cpop.v3',methods=['cpop','fine_cpop','labs'],
        candidate='Two observed samples each side confirm local level stability; replace only a >kappa*sigma isolated fine residual by two-sided level, protect command changes +/-1finebin. Then unchanged native CPOP. Not a new CPOP solver or certified anomaly label.',
        active_kappas=[3.,4.,5.],no_coarse_point_screening=True,
        simulation=dict(dt_seconds=10.,window_seconds=[-900,2700],task_seconds=1800.,q_kw=1.5,sigma_kw=.05,
            threshold_kw=.15,dwell_seconds=30.,kinds=['smooth_strong','smooth_weak','brief_weak','interrupted','early_exit','oscillatory','delayed_rebound','null','one_minute_response','one_minute_gap','one_finebin_response','one_finebin_gap'],
            conditions=['gaussian','single_sample_spikes','persistent_bursts'],
            development=dict(seeds=[7651000],per_kind=1),validation=dict(seeds=[7651100,7651101],per_kind=2),test=dict(seeds=[7651200,7651201,7651202,7651203,7651204,7651205],per_kind=2),
            sparse='Exactly2 fine bins within task, independent sign*Uniform(.4,.9)kW',
            persistent='Two disjoint40s intervals, independent sign*Uniform(.4,.9)kW',
            no_upsampling='Generate independent1s ODE and meter10s means directly; never split prior minute measurements.',
            reference='Known simulated baseline. No reference predictor used. Truth and contamination labels evaluator-only.'),
        selection='Validation minimum all-kind all-condition mean of cumulative/longest absolute errors; ties choose larger kappa. No real-data or test tuning.',
        adoption=dict(overall_primary_relative_improvement=.10,gaussian_noninferiority_seconds=5.,
            no_extra_misses_true_one_minute=True,no_extra_misses_true_one_finebin=True,
            one_minute_gap_noninferiority_seconds=10.,one_finebin_gap_noninferiority_seconds=10.,
            null_no_more_false_positive_than_original=True,all_methods_available=True),
        real_auxiliary=dict(selection='Reuse all fixed144 existing events. No error-driven selection or unseen-real claim.',
            conditions=['original','gaussian','single_sample_spikes'],gaussian_sigma=.03,spike_amplitude=.30,seed=7651300,
            truth='No latent truth. Only same-method Gaussian-to-spike feature perturbation stability.',
            features='Observed command-progress target>=.9, task0..15s, dwell.1s; all methods same100ms inputs.'),
        baselines='Original native CPOP1.0.10 beta2log(n), same sigma and full fine grid; unchanged author LABS M5R2 sSIC fixed commit. Both receive same fine observations and commands remain available to all; using them is part of candidate feature block.',
        scope='First feature block only. No uncertainty intervals counted as benefit. No reports/second block/default replacement.',
        reuse=dict(cpop='Existing GPL native package unchanged',labs='Existing MIT author core unchanged',
            scipy='Reviewed scipy GitHub median_filter BSD implementation; do not blindly median smooth or install. Independently implement narrow evidence rule instead.',
            urls=['https://github.com/scipy/scipy/blob/main/scipy/ndimage/_filters.py','https://www.jstatsoft.org/article/view/v109i07','https://doi.org/10.1080/01621459.2017.1385466']))
    write('protocol.json',p)
    print(json.dumps({'audit':read('fine_data_audit.json')|{'source_sha256':'retained'},'new_protocol_frozen_before_development':True}))
if __name__=='__main__':main()
