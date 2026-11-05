"""Independent read-only recomputation from saved curves and observations.

Does not import the study engine, formal feature extractor, simulator or fitters.
Only writes new audit artifacts; never changes scientific results.
"""
from pathlib import Path
import argparse, hashlib, json, math
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.stats import t

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
DATA = PROJECT / 'data/B1_unknown_reference_v1_20261030'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed_times(curve, starts, ends):
    # A one-minute grid has dwell ceil(0.5/1)=1 whole bin.
    request = [i for i in range(len(starts)) if starts[i] >= 0 and ends[i] <= 30]
    qualifying = [i for i in request if float(curve[i]) >= .15]
    onset = float(starts[qualifying[0]] * 60) if qualifying else None
    recovery = None
    if onset is not None:
        qualifying_post = [i for i in range(len(starts))
                           if starts[i] >= 30 and abs(float(curve[i])) <= .15]
        if qualifying_post:
            recovery = float(starts[qualifying_post[0]] * 60)
    return onset, recovery


def interval(values):
    v = np.asarray(values, dtype=float)
    n = len(v)
    mean = float(sum(v) / n)
    half = float(t.ppf(.975, n - 1) * np.std(v, ddof=1) / math.sqrt(n))
    return dict(blocks=n, mean_difference=mean, mc95_low=mean-half,
                mc95_high=mean+half, wins=int(sum(x < 0 for x in v)))


def audit(phase):
    folder = HERE / phase
    receipt_path = folder / 'audit_receipt.json'
    if receipt_path.exists():
        raise RuntimeError('Audit receipt already exists; preserve it instead of overwriting')
    receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['complete']
    freeze = json.loads((folder / 'freeze.json').read_text(encoding='utf-8'))
    for relative, expected in freeze['hashes'].items():
        assert digest(PROJECT / relative) == expected, relative
    protocol = json.loads((HERE / 'protocol.json').read_text(encoding='utf-8'))
    seeds = protocol[phase + '_seeds']
    frame = pd.read_csv(folder / 'metrics.csv')
    arrays = np.load(folder / 'inputs_and_truth.npz')
    curves = np.load(folder / 'method_curves.npz')
    contexts = {}; context_arrays = {}; context_count = 0
    shifts_checked = 0; chronological_records = 0; selection_checks = 0
    for seed in seeds:
        ledger = json.loads((folder / f'ledger_{seed}.json').read_text(encoding='utf-8'))
        roles = ledger['roles']
        for role_a, values in roles.items():
            for role_b, other in roles.items():
                if role_a != role_b:
                    assert not set(values) & set(other)
        for item in ledger['training']:
            assert item['latest_prior_end_min'] < item['notice_min']
            assert item['end_of_data_min'] <= 120000.
            j = int(item['task_id'].rsplit('-', 1)[1])
            assert j >= 2 and len(item['sources']) == j
            assert item['latest_prior_end_min'] == 100000 + 1440*(j-1) + 90
            expected_sources = [item['task_id'].rsplit('-',1)[0] + '-' + str(k) for k in range(j)]
            assert item['sources'] == expected_sources
            assert int(item['user_id'].split('-u')[-1]) in roles['train']
            chronological_records += 1
        metadata = pd.read_csv(DATA / phase / f'metadata_{seed}.csv')
        eligible = metadata[metadata.user.isin(roles['test']) & np.isclose(metadata.lead, 15.)]
        selected = eligible.sort_values('event_id').drop_duplicates('user').index.to_list()[:2]
        assert selected == [c['source_event'] for c in ledger['selected']]
        assert ledger['selected_contexts'] == len(selected)
        selection_checks += 1
        blob = np.load(DATA / phase / f'contexts_{seed}.npz')
        context_arrays[seed] = blob
        starts_full = np.arange(-120., 90.)
        prefix_mask = (starts_full >= -30) & (starts_full+1 <= -15)
        process_mask = (starts_full >= -15) & (starts_full+1 <= 45)
        for c in ledger['selected']:
            order = c['context']; key = (seed, order)
            contexts[key] = c; context_count += 1
            assert c['fit_cutoff_min'] < c['query_notice_min']
            assert int(c['user_id'].split('-u')[-1]) in roles['test']
            prefix = blob[f'{order}_prefix']
            prediction_prefix = blob[f'{order}_prefix_prediction']
            assert len(prefix) == 15
            np.testing.assert_array_equal(prefix, blob[f'{order}_full_meter'][prefix_mask])
            np.testing.assert_array_equal(prediction_prefix, blob[f'{order}_full_prediction'][prefix_mask])
            independent_shift = float(sum(float(a)-float(b) for a,b in zip(prefix,prediction_prefix))/15)
            assert abs(independent_shift-c['shift_kw']) < 1e-12
            fixed = blob[f'{order}_ref_fixed_gbdt']
            np.testing.assert_array_equal(fixed, blob[f'{order}_full_prediction'][process_mask])
            np.testing.assert_allclose(blob[f'{order}_ref_gbdt_pre15_shift'],
                np.maximum(0., fixed + independent_shift), rtol=0, atol=1e-12)
            assert int(np.sum(fixed+independent_shift < 0)) == c['adjustment_floor_bins']
            np.testing.assert_array_equal(blob[f'{order}_ref_oracle_diagnostic'],blob[f'{order}_baseline'])
            shifts_checked += 1
    checks = 0; maximum_difference = 0.; recomputed = []; complete_entries = defaultdict(list)
    for row in frame.itertuples(index=False):
        c = contexts[(row.seed, row.context)]
        blob = context_arrays[row.seed]
        starts = blob['starts']; ends = blob['ends']
        np.testing.assert_array_equal(starts,np.arange(-15.,45.))
        assert np.all(ends-starts==1)
        mask = (starts >= 0) & (ends <= 30)
        truth = arrays[row.identity+'_truth']; power = arrays[row.identity+'_power']
        curve = curves[f'{row.index}_{row.method}']
        reference = blob[f'{row.context}_ref_{row.reference}']
        baseline = blob[f'{row.context}_baseline']
        assert np.all(baseline-truth>=-1e-12)
        if row.mechanism == 'none':
            assert np.all(truth==0)
        values = dict(curve_rmse_kw=math.sqrt(sum(float(curve[i]-truth[i])**2 for i in np.flatnonzero(mask))/30),
            eta_raw=sum(float(reference[i]-power[i]) for i in np.flatnonzero(mask))/45,
            eta_true=sum(float(truth[i]) for i in np.flatnonzero(mask))/45,
            reference_bias_kw=sum(float(reference[i]-baseline[i]) for i in np.flatnonzero(mask))/30)
        values['eta_error'] = values['eta_raw'] - values['eta_true']
        onset, recovery = observed_times(curve,starts,ends)
        true_onset, true_recovery = observed_times(truth,starts,ends)
        statuses=dict(onset_detected=onset is not None, truth_onset_detected=true_onset is not None,
                      recovery_detected=recovery is not None, truth_recovery_detected=true_recovery is not None)
        for name,value in statuses.items():
            assert bool(getattr(row,name)) == value, (row.index,row.method,name)
            checks += 1
        values['onset_abs_error_s'] = None if onset is None or true_onset is None else abs(onset-true_onset)
        values['recovery_abs_error_s'] = None if recovery is None or true_recovery is None else abs(recovery-true_recovery)
        for name,value in values.items():
            given = getattr(row,name)
            if value is None:
                assert pd.isna(given),(row.index,row.method,name,given)
            else:
                difference=abs(float(given)-value)
                maximum_difference=max(maximum_difference,difference)
                assert difference<=1e-10,(row.index,row.method,name,given,value)
            checks += 1
        complete_entries[row.index].append(values['eta_raw'])
        recomputed.append(dict(seed=row.seed,context=row.context,mechanism=row.mechanism,
            reference=row.reference,method=row.method,**statuses,**values))
    assert all(len(v)==3 and max(v)==min(v) for v in complete_entries.values())
    assert len(frame)==receipt['method_rows'] and len(complete_entries)==receipt['reference_variants']
    assert len(contexts)==receipt['contexts']
    re = pd.DataFrame(recomputed)
    timing=[]
    for (reference,method),a in re.groupby(['reference','method']):
        for population,subset in [('all',a),('active_shapes',a[a.mechanism!='none'])]:
            result=dict(reference=reference,method=method,population=population,denominator=len(subset))
            for feature in ('onset','recovery'):
                detected=subset[feature+'_detected']; true=subset['truth_'+feature+'_detected']
                result[feature+'_truth_available']=int(true.sum())
                result[feature+'_matched']=int((detected & true).sum())
                result[feature+'_missed']=int((~detected & true).sum())
                result[feature+'_extra']=int((detected & ~true).sum())
                errors=subset[feature+'_abs_error_s'].dropna()
                result[feature+'_conditional_mae_s']=None if len(errors)==0 else float(errors.mean())
            timing.append(result)
    pd.DataFrame(timing).to_csv(folder/'audit_timing.csv',index=False)
    paired=[]
    for reference in re.reference.unique():
        method_rows=re[re.reference==reference]
        values={(r.seed,r.context,r.mechanism,r.method):r.curve_rmse_kw for r in method_rows.itertuples()}
        keys=sorted(set((r.seed,r.context,r.mechanism) for r in method_rows.itertuples()))
        for comparator in ('native_CPOP_default','original_RIDE_template_3starts'):
            blocks=defaultdict(list)
            for seed,context,mechanism in keys:
                blocks[seed].append(values[(seed,context,mechanism,'frozen_guarded')]-values[(seed,context,mechanism,comparator)])
            paired.append(dict(reference=reference,comparator=comparator,**interval([np.mean(v) for _,v in sorted(blocks.items())])))
    supplied_paired=pd.read_csv(folder/'method_paired.csv')
    for r in paired:
        given=supplied_paired[(supplied_paired.reference==r['reference'])&(supplied_paired.comparator==r['comparator'])].iloc[0]
        for name in ('blocks','mean_difference','mc95_low','mc95_high','wins'):
            assert abs(float(given[name])-r[name])<1e-10,(r,name)
    correction=[]
    for method in re.method.unique():
        a=re[re.method==method]
        lookup={(r.seed,r.context,r.mechanism,r.reference):r for r in a.itertuples()}
        keys=sorted(set((r.seed,r.context,r.mechanism) for r in a.itertuples()))
        blocks=defaultdict(list);fpr_blocks=defaultdict(list)
        fixed=[];adjusted=[]
        for seed,context,mechanism in keys:
            before=lookup[(seed,context,mechanism,'fixed_gbdt')]
            after=lookup[(seed,context,mechanism,'gbdt_pre15_shift')]
            fixed.append(before.curve_rmse_kw);adjusted.append(after.curve_rmse_kw)
            blocks[seed].append(after.curve_rmse_kw-before.curve_rmse_kw)
            if mechanism=='none':
                fpr_blocks[seed].append(int(after.onset_detected)-int(before.onset_detected))
        correction.append(dict(method=method,relative_curve_improvement=1-np.mean(adjusted)/np.mean(fixed),
            no_action_fpr_difference=float(np.mean([np.mean(v) for v in fpr_blocks.values()])),
            all_blocks_nonworse=all(np.mean(v)<=1e-12 for v in blocks.values()),
            **interval([np.mean(v) for _,v in sorted(blocks.items())])))
    supplied_correction=pd.read_csv(folder/'correction_paired.csv')
    for r in correction:
        given=supplied_correction[supplied_correction.method==r['method']].iloc[0]
        for name in ('relative_curve_improvement','no_action_fpr_difference','blocks','mean_difference','mc95_low','mc95_high','wins'):
            assert abs(float(given[name])-r[name])<1e-10,(r,name)
        assert bool(given['all_blocks_nonworse'])==r['all_blocks_nonworse']
    required=[r for r in correction if r['method'] in ('native_CPOP_default','frozen_guarded')]
    if phase=='development':
        admitted=all(r['all_blocks_nonworse'] and r['relative_curve_improvement']>=.05 and r['no_action_fpr_difference']<=.05+1e-12 for r in required)
    else:
        development=json.loads((HERE/'development/receipt.json').read_text(encoding='utf-8'))
        admitted=development['candidate_admitted'] and all(r['mc95_high']<0 and r['no_action_fpr_difference']<=.05+1e-12 for r in required)
    assert bool(admitted)==receipt['candidate_admitted']
    summary=pd.read_csv(folder/'summary.csv')
    for (reference,method),a in re.groupby(['reference','method']):
        supplied=summary[(summary.reference==reference)&(summary.method==method)].iloc[0]
        expected_curve=float(a.groupby('seed').curve_rmse_kw.mean().mean())
        expected_false=float(a[a.mechanism=='none'].groupby('seed').onset_detected.mean().mean())
        assert abs(expected_curve-supplied.mean_curve_rmse_kw)<1e-10
        assert abs(expected_false-supplied.none_false_positive_fraction)<1e-10
    result=dict(passed=True,phase=phase,method_rows=len(frame),reference_variants=len(complete_entries),
        independent_blocks=len(seeds),contexts=context_count,numeric_checks=checks,
        maximum_numeric_difference=maximum_difference,chronological_records_checked=chronological_records,
        selections_checked=selection_checks,pre_notice_adjustments_checked=shifts_checked,
        protected_hashes_checked=len(freeze['hashes']),same_raw_eta_across_methods=True,
        method_and_reference_paired_comparisons_verified=True,candidate_admission_recomputed=bool(admitted),
        audit_code_sha256=digest(__file__),inference_scope='finite controlled stress panel, seed-block MC differences; no causal effect or real-device claim')
    receipt_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('development','test'))
    audit(parser.parse_args().phase)
