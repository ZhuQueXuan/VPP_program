"""Export a continuous incentive curve from its actual numeric results."""
from pathlib import Path
import numpy as np


def _ylabel(result,point):
    if point['outcome_unit']!='ratio':return '平均结果增量（'+point['outcome_unit']+'）'
    if result.get('metered_pipeline') is not None:return '相对参考激励的归一化用电减少增量（百分点）'
    if result.get('task',{}).get('outcome_name')=='eta_raw':return '相对参考激励的平均净交付增量（百分点）'
    return '相对参考激励的平均结果增量（百分点）'


def export_incentive_curve(result,path,*,title=None,show_comparators=True):
    """Save PNG/SVG/PDF; unsupported estimates cannot be plotted as valid curves."""
    if result.get('schema_version')!='b1.continuous-effects.v1' or result.get('status') not in ('causal','association'):
        raise ValueError('a supported continuous incentive estimate is required')
    point=result.get('causal_curve') or result.get('standardized_association')
    grid=np.asarray(point['incentive_values']);values=np.asarray(point['contrasts'])
    if len(grid)<2:raise ValueError('at least two query amounts required for a curve plot')
    path=Path(path)
    if path.suffix.lower() not in ('.png','.svg','.pdf'):raise ValueError('PNG, SVG or PDF output required')
    if path.exists():raise ValueError('output exists; choose a new explicit path')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    fontpath=Path('C:/Windows/Fonts/simhei.ttf')
    if fontpath.is_file():font_manager.fontManager.addfont(str(fontpath))
    with plt.rc_context({'font.family':['SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':11}):
        fig,ax=plt.subplots(figsize=(8.4,5.1),layout='constrained')
        multiplier=100. if point['outcome_unit']=='ratio' else 1.
        ax.plot(grid,values*multiplier,color='#1668ac',lw=2.5,label='连续激励作用估计')
        band=result.get('inference')
        if band:
            ax.fill_between(grid,np.asarray(band['lower'])*multiplier,np.asarray(band['upper'])*multiplier,
                            color='#1668ac',alpha=.14,label='条件抽样波动带')
        if show_comparators:
            for name,label,color,style in [('plugin_shared_outcome','通用结果回归对照','#c77c27','--'),
                                         ('straight_line_same_pseudo_outcome','直线对照','#78828d',':')]:
                curve=result.get('comparators',{}).get(name)
                if curve:ax.plot(grid,np.asarray(curve['contrasts'])*multiplier,label=label,color=color,ls=style,lw=1.5)
        ax.axhline(0,color='#a6adb5',lw=.8)
        ylabel=_ylabel(result,point)
        ax.set(xlabel='事先告知的激励补偿（'+point['incentive_unit']+'）',ylabel=ylabel,
            title=title or '同一任务条件下的连续激励作用')
        ax.text(.02,.98,f"任务 {point['task_duration_min']:g} 分钟；请求 {point['request_kw']:g} kW；参考激励 {point['reference_incentive']:g}",
                transform=ax.transAxes,va='top',fontsize=10)
        note='阴影未包含平滑偏差及参考、模型估计的全部不确定性。' if band else '因果假设未确认：图示为调整后的关联。'
        fig.text(.01,-.025,note,fontsize=9,color='#61666b')
        ax.grid(alpha=.15);ax.legend(loc='best',fontsize=9)
        path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig)
    return str(path.resolve())
