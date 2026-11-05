"""Run a raw study or query a saved research-point-one model."""
from pathlib import Path
import argparse,json,sys,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
dependencies=ROOT/'work/b1_research_point1_20261103/runtime/site-packages'
if dependencies.is_dir():sys.path.insert(0,str(dependencies))
from b1_api import (EVFactorStudy,run_research_point_one,load_research_point_one,
                    save_research_point_one,query_research_point_one)


def plot(query,path):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    c=query['mean_curve']['curve']
    if c:
        x=c['incentive_values'];axes[0].plot(x,c['contrasts'],label='Retained continuous DR')
        band=query['mean_curve'].get('inference')
        if band:axes[0].fill_between(x,band['lower'],band['upper'],alpha=.2,label='Conditional sampling band')
        axes[0].axhline(query['target_contrast_seconds'],color='grey',ls='--',label='Response target')
        axes[0].set_ylabel('Mean duration change (s)');axes[0].legend(fontsize=7)
    for key,label in [('retained_smoothed_derivative','Smoothed derivative'),('direct_marginal_effect','Direct DR derivative')]:
        r=query.get(key) or {};v=r.get('values',r.get('estimates'))
        if v is not None:axes[1].plot(r['incentive_values'],v,label=label)
    axes[1].axhline(0,color='grey',lw=.7);axes[1].set_ylabel('Marginal change (s / amount unit)');axes[1].legend(fontsize=7)
    for name,entry in query['group_effects'].items():
        c=(entry.get('mean_curve') or {}).get('curve')
        if c:axes[2].plot(c['incentive_values'],c['contrasts'],label=name)
    axes[2].set_ylabel('Subgroup mean duration change (s)')
    if axes[2].lines:axes[2].legend(fontsize=7)
    else:axes[2].text(.5,.5,'Group curve lacks full-grid support',ha='center',transform=axes[2].transAxes,fontsize=9)
    for ax,title in zip(axes,['Compensation effect','Sensitivity comparison','Pretreatment heterogeneity']):
        ax.set_title(title);ax.set_xlabel('Compensation amount');ax.grid(alpha=.2)
    fig.savefig(path,dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--input');mode.add_argument('--model')
    parser.add_argument('--amounts',nargs='+',type=float,default=[round(.4+.1*i,10) for i in range(17)])
    parser.add_argument('--target',type=float,default=120.);parser.add_argument('--output')
    parser.add_argument('--refit-draws',type=int,default=0)
    args=parser.parse_args()
    output=Path(args.output) if args.output else ROOT/'work/research_point1_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True,exist_ok=False)
    if args.input:
        specpath=Path(args.input).resolve();spec=json.loads(specpath.read_text(encoding='utf-8'))
        def data(name):return json.loads((specpath.parent/spec[name]).read_text(encoding='utf-8'))
        study=EVFactorStudy(**spec['study']);options=spec['fit_options']
        result=run_research_point_one(data('records_file'),data('factors_file'),study,**options)
        model=result['model'];save_research_point_one(model,output/'model.json')
        (output/'events.json').write_text(json.dumps(result['events'],ensure_ascii=False),encoding='utf-8')
    else:
        modelpath=Path(args.model) if args.model else ROOT/'work/b1_research_point1_20261103/physical/model.json'
        model=load_research_point_one(modelpath)
    query=query_research_point_one(model,args.amounts,target_contrast=args.target,refit_draws=args.refit_draws)
    (output/'result.json').write_text(json.dumps(query,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    plot(query,output/'curves.png')
    summary=dict(status=query['status'],events=model['events'],users=model['users'],
        target_change_seconds=args.target,first_target_amount=query['target_threshold'].get('first_point_crossing'),
        default_sensitivity=query['marginal_effect_method'],results=str(output/'result.json'),figure=str(output/'curves.png'))
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
