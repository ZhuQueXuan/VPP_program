"""Saved-record diagnosis only. No estimator, optimizer, generator or tuning imports."""
from pathlib import Path
import hashlib,json,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
STUDY=ROOT/'work/b1_cpop_improvement_20261031'
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(rel):
    p=STUDY/rel;inputs[p.relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(p.read_text(encoding='utf-8'))
def main():
    facts=read('facts/test.json');truth=read('evaluator/test.json');curves=read('outputs/test_curves.json')
    metrics=read('outputs/test_metrics.json');summary=read('outputs/test_summary.json')
    frozen=read('validation_freeze.json');protocol=read('protocol.json')
    for name in ['candidate.py','weighted_cpop_batch.R']:
        p=STUDY/name;inputs[p.relative_to(ROOT).as_posix()]=sha(p)
    cf={x['task']['task_id']:x for x in facts};tf={x['task_id']:x for x in truth};of={x['task_id']:x for x in curves}
    miss=[r for r in metrics if r['method']=='candidate_k5' and r['condition']=='gaussian' and r['kind']=='one_bin_response' and r['whole_miss']]
    assert len(miss)==3
    examples=[]
    for row in miss:
        ident=row['task_id'];c,t,o=cf[ident],tf[ident],of[ident]['results']
        true=t['true_reduction_kw'];i=max(range(len(true)),key=true.__getitem__)
        old=o['cpop'];new=o['candidate_k5'];diag=new['weight_diagnostics']
        f=next(v for v in diag['flagged_points'] if v['index']==i)
        y=[a-b for a,b in zip(c['reference_kw'],c['power_kw'])];s=diag['sigma_vector']
        beta=2*math.log(len(y));knots_old=old['native_knots'];knots_new=new['knots']
        def score(pred,knots,scale):return sum(((a-b)/v)**2 for a,b,v in zip(pred,y,scale))+beta*knots
        weighted_old=score(old['prediction'],knots_old,s);weighted_new=score(new['prediction'],knots_new,s)
        assert abs(weighted_new-new['native_cost'])<1e-7
        assert weighted_new<weighted_old and knots_new==0
        assert max(old['prediction'][15:45])>=.15 and max(new['prediction'][15:45])<.15
        assert i not in diag['protected_indices'] and f['weight_ratio']<.1
        assert len(t['injected_indices'])==0
        examples.append({'task_id':ident,'native_bin_index':i,'relative_start_min':c['starts'][i],
          'true_reduction_kw':true[i],'observed_reduction_kw':y[i],
          'five_observed_values_kw':y[i-2:i+3],'effective_sigma_kw':f['effective_sigma'],
          'original_sigma_kw':c['sigma'],'retained_squared_error_weight':f['weight_ratio'],
          'command_edge_protected':False,'old_peak_kw':max(old['prediction'][15:45]),
          'new_peak_kw':max(new['prediction'][15:45]),'old_knots':knots_old,'new_knots':knots_new,
          'weighted_objective_old_curve':weighted_old,'weighted_objective_new_curve':weighted_new,
          'unweighted_objective_old_curve':score(old['prediction'],knots_old,[c['sigma']]*len(y)),
          'unweighted_objective_new_curve':score(new['prediction'],knots_new,[c['sigma']]*len(y)),
          'no_measurement_spike_injected':True})
    old_short=[r for r in metrics if r['method']=='cpop' and r['condition']=='gaussian' and r['kind']=='one_bin_response']
    assert len(old_short)==24 and sum(r['whole_miss'] for r in old_short)==0
    original_summary=[r for r in summary if r['method']=='cpop' and r['condition'] in ('gaussian','gaussian_plus_spikes')]
    records={'status':'diagnosed_saved_records_only','sample':'Already-seen240 base tasks/480paired inputs, no new independent evidence',
       'direct_failure':'Data-dependent downweighting weakened genuine isolated one-minute response evidence; lower weighted objective selected zero-knot fit. Original CPOP recognized all24 genuine single-bin responses in Gaussian condition.',
       'three_misses':examples,'original_cpop_group_metrics':original_summary,
       'distinctions':['The3extra misses were introduced by candidate weighting, not an original CPOP failure or reference prediction',
          'Command-edge protection does not cover all actual response times inside a task',
          'Square-error signal fit is not the same loss as threshold-based cumulative or longest duration',
          'Single-bin genuine action and sensor spike can be observationally indistinguishable without extra information',
          'Jump-vs-ramp model mismatch is a plausible future direction, not proven dominant by current diagnosis'],
       'proposal':'Preserve original point weights; investigate segment-level, sampling-aware CPOP extension admitting both slope changes and level jumps, evaluated by whole-process feature error. Use existing finer observations and states when available; ambiguous single-bin cases remain ambiguous. No fixed minimum duration deleting real short actions.',
       'unchanged_comparators':['original_CPOP','LABS'],
       'new_estimator_runs':0,'new_predictor_fits':0,'new_parameter_selection':False,'algorithm_changes':False,
       'input_sha256':inputs}
    for p,h in inputs.items():assert sha(ROOT/p)==h
    with (HERE/'diagnosis.json').open('x',encoding='utf-8') as f:json.dump(records,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'misses_checked':3,'original_short_response_misses':'0/24',
       'weight_ratios':[r['retained_squared_error_weight'] for r in examples],
       'new_peak_kw':[r['new_peak_kw'] for r in examples],'unchanged_inputs':len(inputs),'new_fits':0},ensure_ascii=False))
if __name__=='__main__':main()
