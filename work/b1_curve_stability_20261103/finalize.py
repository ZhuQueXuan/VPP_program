"""One-time decision using the predeclared confirmation and unchanged baselines."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from scipy.stats import t
HERE=Path(__file__).resolve().parent
from prepare import save,formal_hashes

def name(k,v):return k+'_'+format(float(v),'.8g')

def main():
    p=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    s=json.loads((HERE/'confirmation/summary.json').read_text(encoding='utf-8'))
    sel=json.loads((HERE/'selection_freeze.json').read_text(encoding='utf-8'))['selected']
    rows=s['rows'];agg=s['aggregate'];cand=name('adaptive',sel['gamma']);ctrl=name('constant',sel['beta'])
    expected={(seed,k) for seed in p['confirmation']['seeds'] for k in p['confirmation']['mechanisms']}
    actual=[(r['seed'],r['mechanism']) for r in rows]
    assert len(actual)==len(expected)==96 and len(set(actual))==len(actual) and set(actual)==expected
    compared=['retained_S',ctrl,cand,'original_LL','strong_LL2']
    complete=all(agg[n]['outputs']==96 for n in compared)
    deltas={}
    for ref in ('retained_S',ctrl):
        seed_delta=[]
        for seed in p['confirmation']['seeds']:
            rr=[r for r in rows if r['seed']==seed]
            values=[r['policies'][cand]['curve_rmse_seconds']-r['policies'][ref]['curve_rmse_seconds'] for r in rr
                if all(r['policies'].get(n,{}).get('status')=='ok' for n in (cand,ref))]
            seed_delta.append(dict(seed=seed,complete=len(values)==8,delta=float(np.mean(values)) if len(values)==8 else None))
        ds=np.array([r['delta'] for r in seed_delta if r['complete']])
        zero=[r for r in rows if r['mechanism']=='zero_effect']
        target_complete=all(r['policies'].get(n,{}).get('target') is not None for r in zero for n in (ref,cand))
        fps={n:sum(r['policies'][n]['target']['reached'] for r in zero) for n in (ref,cand)} if target_complete else None
        half=float(t.ppf(.975,len(ds)-1)*ds.std(ddof=1)/np.sqrt(len(ds))) if len(ds)>1 else None
        deltas[ref]=dict(relative_gain=1-agg[cand]['mean_curve_rmse']/agg[ref]['mean_curve_rmse'] if complete else None,
            paired_seed_differences=seed_delta,seed_wins=int(np.sum(ds<0)),
            paired_seed_mean_delta=float(ds.mean()) if len(ds) else None,
            paired_seed_descriptive_t95=[float(ds.mean()-half),float(ds.mean()+half)] if half is not None else None,
            zero_targets_complete=target_complete,zero_false_targets=fps)
    gates=dict(all_96_outputs=complete,
        gain_vs_retained_at_least_5pct=complete and deltas['retained_S']['relative_gain']>=.05,
        gain_vs_tuned_constant_at_least_5pct=complete and deltas[ctrl]['relative_gain']>=.05,
        seed_wins_vs_retained_at_least9=deltas['retained_S']['seed_wins']>=9,
        seed_wins_vs_tuned_constant_at_least8=deltas[ctrl]['seed_wins']>=8,
        zero_false_targets_no_increase=all(v['zero_targets_complete'] and v['zero_false_targets'][cand]<=v['zero_false_targets'][ref] for ref,v in deltas.items()))
    by_kind={}
    for kind in p['confirmation']['mechanisms']:
        rr=[r for r in rows if r['mechanism']==kind]
        by_kind[kind]={n:dict(outputs=sum(r['policies'].get(n,{}).get('status')=='ok' for r in rr),
            mean_curve_rmse=float(np.mean([r['policies'][n]['curve_rmse_seconds'] for r in rr if r['policies'].get(n,{}).get('status')=='ok']))) for n in compared}
    old=HERE.parent/'b1_curve_spline_pilot_20261103'
    before=json.loads((HERE/'retained_before.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((old/n).read_bytes()).hexdigest()==h for n,h in before.items())
    assert formal_hashes()==json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
    decision=dict(status='confirmed_new_stability_candidate' if all(gates.values()) else 'new_candidate_not_adopted_keep_retained_spline',
        selected=sel,gates=gates,comparisons=deltas,aggregate={n:agg[n] for n in compared},per_mechanism=by_kind,
        cohorts=96,independent_seed_blocks=12,simulated_user_conditions=2880,base_event_conditions=5760,fact_variants=46080,
        cv_fallback_cohorts=sum(r.get('cv_status')=='fallback_retained_spline' for r in rows),
        raw_alpha_counts=dict(at_spline=sum(r.get('raw_alpha_spline')==1 for r in rows),at_LL2=sum(r.get('raw_alpha_spline')==0 for r in rows)),
        old_retained_artifacts_unchanged=len(before),formal_sources_models_unchanged=len(formal_hashes()),
        earlier_retained_version='unchanged lambda_mean1e-4 candidate from prior comparison',
        default_changed=False,other_parts_changed=False,
        interpretation='Related simulator-family results, no field validation. CV loss is observed-dose level-risk; confirmation primary is uniform-grid contrast-risk.',
        no_post_confirmation_tuning=True)
    save(HERE/'decision.json',decision)
    print(json.dumps(decision,indent=2,ensure_ascii=False))
    plot(decision,cand)

def plot(d,cand):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,(ax,bx)=plt.subplots(1,2,figsize=(12.8,4.8),gridspec_kw={'width_ratios':[1.6,1]})
    kinds=list(d['per_mechanism']);x=np.arange(len(kinds));w=.25
    for off,n,label,color in [(-w,'retained_S','Retained spline','#2274a5'),(0,'strong_LL2','Stronger LL control','#bd9a50'),(w,cand,'Nested-CV blend','#c44e52')]:
        ax.bar(x+off,[d['per_mechanism'][k][n]['mean_curve_rmse'] for k in kinds],w,label=label,color=color)
    ax.set_xticks(x);ax.set_xticklabels([k.replace('_','\n') for k in kinds],fontsize=8)
    ax.set_ylabel('Mean contrast RMSE (seconds)');ax.set_title('All 96 predeclared confirmation curves')
    ax.grid(axis='y',alpha=.15);ax.legend(frameon=False,fontsize=8)
    delta=d['comparisons']['retained_S']['paired_seed_differences']
    xx=np.arange(1,len(delta)+1);yy=[r['delta'] for r in delta]
    bx.axhline(0,color='black',lw=1);bx.bar(xx,yy,color=['#2274a5' if y<0 else '#c44e52' for y in yy])
    bx.set_xlabel('Independent simulation seed block');bx.set_ylabel('Candidate minus retained RMSE (seconds)')
    bx.set_title('Negative = improvement');bx.set_xticks(xx);bx.grid(axis='y',alpha=.15)
    fig.tight_layout();fig.savefig(HERE/'stability_comparison.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
