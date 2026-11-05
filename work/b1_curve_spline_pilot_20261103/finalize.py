"""Apply frozen criteria to all saved cohorts; create a compact scientific figure."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from prepare import save,hashes

def key(v,prefix):return prefix+'_'+format(float(v),'.8g')

def main():
    p=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    selection=json.loads((HERE/'selection_freeze.json').read_text(encoding='utf-8'))['selected']
    s=json.loads((HERE/'confirmation/summary.json').read_text(encoding='utf-8'))
    rows=s['rows'];names=['fixed_LL',key(selection['ll_multiplier'],'LL'),key(selection['lambda_mean'],'spline')]
    a=s['aggregate'];baseline,control,candidate=names
    complete=all(a.get(n,{}).get('outputs')==len(rows) for n in names)
    comparisons={}
    for ref in names[:2]:
        seed_differences=[]
        for seed in p['confirmation']['seeds']:
            subset=[r for r in rows if r['seed']==seed]
            if all(r['policies'].get(n,{}).get('status')=='ok' for r in subset for n in (ref,candidate)):
                delta=float(np.mean([r['policies'][candidate]['curve_rmse_seconds']-r['policies'][ref]['curve_rmse_seconds'] for r in subset]))
                seed_differences.append(dict(seed=seed,candidate_minus_reference_rmse=delta))
        gain=1-a[candidate]['mean_curve_rmse']/a[ref]['mean_curve_rmse'] if complete else None
        zero=[r for r in rows if r['mechanism']=='zero_effect']
        zero_outputs=all(r['policies'].get(n,{}).get('target') is not None for r in zero for n in (ref,candidate))
        fp={n:sum(bool(r['policies'].get(n,{}).get('target',{}).get('reached')) for r in zero) for n in (ref,candidate)} if zero_outputs else None
        comparisons[ref]=dict(relative_gain=gain,seed_differences=seed_differences,
            seed_wins=sum(v['candidate_minus_reference_rmse']<0 for v in seed_differences),
            zero_effect_target_outputs_complete=zero_outputs,zero_effect_false_reached=fp)
    gates=dict(all_designed_curves_output=complete,
        gain_at_least_5pct_vs_both=complete and all(v['relative_gain']>=.05 for v in comparisons.values()),
        at_least_6_of_8_seed_wins_vs_both=all(v['seed_wins']>=6 for v in comparisons.values()),
        zero_effect_false_target_not_increased=all(v['zero_effect_target_outputs_complete'] and
            v['zero_effect_false_reached'][candidate]<=v['zero_effect_false_reached'][ref] for ref,v in comparisons.items()))
    retained=hashes()==json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
    assert retained
    mechanisms={}
    for kind in p['confirmation']['mechanisms']:
        subset=[r for r in rows if r['mechanism']==kind]
        mechanisms[kind]={n:dict(outputs=sum(r['policies'].get(n,{}).get('status')=='ok' for r in subset),
            rmse=float(np.mean([r['policies'][n]['curve_rmse_seconds'] for r in subset if r['policies'].get(n,{}).get('status')=='ok']))) for n in names}
    decision=dict(status='confirmed_single_smoother_candidate' if all(gates.values()) else 'candidate_not_adopted',
        selected=selection,all_gates=gates,comparisons=comparisons,aggregate={n:a[n] for n in names},
        per_mechanism=mechanisms,designed_cohorts=len(rows),independent_seed_blocks=8,
        simulated_user_conditions=8*p['confirmation']['users'],
        simulated_base_event_conditions=8*p['confirmation']['users']*2,
        fact_variants=len(rows)*p['confirmation']['users']*2,
        formal_files_unchanged=retained,formal_file_count=len(hashes()),
        actual_pipeline_scope='Only part3 candidate; no structure/group/direct derivative/band model fit. Derivatives and crossings are diagnostics of each fitted curve.',
        mathematical_truth_scope='Population rather than realized finite cohort mean; no field or independent physical validation.',
        default_changed=False,source='All predeclared confirmation cohorts; no post-confirmation tuning or selection')
    save(HERE/'decision.json',decision)
    print(json.dumps(decision,ensure_ascii=False,indent=2))
    figure(p,rows,names)

def figure(p,rows,names):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.right':False,'axes.spines.top':False})
    fig,axes=plt.subplots(2,3,figsize=(12.6,7.2),sharex=True)
    labels=['Retained DR','Tuned DR control','DR + global spline']
    colors=['#778899','#e09b22','#156cba']
    for ax,kind in zip(axes.ravel(),p['confirmation']['mechanisms']):
        row=next(r for r in rows if r['seed']==p['confirmation']['seeds'][0] and r['mechanism']==kind)
        folder=HERE/'confirmation'/f"{row['seed']}-{kind}"
        truth=json.loads((folder/'truth.json').read_text(encoding='utf-8'))
        ax.plot(p['grid'],truth['contrasts'],'k-',lw=2.1,label='Population truth')
        for n,label,color in zip(names,labels,colors):
            if row['policies'].get(n,{}).get('status')=='ok':
                ax.plot(p['grid'],row['policies'][n]['contrasts'],color=color,lw=1.5,label=label)
        ax.axhline(p['target_seconds'],color='#bbbbbb',ls=':',lw=1)
        ax.set_title(kind.replace('_',' '));ax.grid(alpha=.18)
        ax.set_xlabel('Offered compensation (yuan/kWh)');ax.set_ylabel('Response contrast (seconds)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4,frameon=False)
    fig.suptitle('One predeclared confirmation seed: all six mechanisms (simulation)',fontsize=12)
    fig.tight_layout(rect=(0,.055,1,.95))
    fig.savefig(HERE/'curve_comparison.png',dpi=160)
    plt.close(fig)

if __name__=='__main__':main()
