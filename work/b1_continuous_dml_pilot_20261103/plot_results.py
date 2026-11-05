from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font=Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
spec=read(HERE/'protocol.json')['final'];names={'random_hurdle':'随机补偿、较多零响应','confounded_hurdle':'补偿与用户条件有关','ceiling':'响应接近任务时长上限','zero_effect':'补偿实际上没有作用','nonmonotone':'新机制：先升后降','assignment_mixture':'新机制：复杂补偿分配'}
styles={'existing_DR':('#2875b9','现用连续DR'),'continuous_DML':('#de852b','连续DML'),'soft_two_part':('#3c9b65','DML＋两部结果模型')}
fig,axes=plt.subplots(3,2,figsize=(12,10),constrained_layout=True)
for ax,scenario in zip(axes.flat,spec['mechanisms']):
    d=read(HERE/'final/results'/f'{spec["seeds"][0]}_{scenario}.json');truth=np.asarray(d['truth_seconds']);ax.plot(GRID,truth-truth[0],color='black',lw=2,label='真实作用（模拟设定）')
    for key,(color,label) in styles.items():
        r=d['results'][key]
        if r['status']=='ok':ax.plot(r['grid'],r['contrast_seconds'],color=color,lw=1.5,label=label)
    ax.set_title(names[scenario]);ax.set_xlabel('补偿标准（元/千瓦时，模拟）');ax.set_ylabel('相对0.30元的平均响应时长变化（秒）');ax.grid(alpha=.2)
handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=4,fontsize=10)
fig.suptitle('连续补偿—响应曲线：首个终验随机块的全部六种机制\n每个金额直接计算；此图为模拟示例，结论按全部四个终验块统计',fontsize=14)
fig.savefig(HERE/'continuous_curve_comparison.png',dpi=150);plt.close(fig)
result=read(HERE/'final/summary.json');keys=list(styles);values=[result['summary'][k]['primary_seconds'] for k in keys]
fig,ax=plt.subplots(figsize=(8,5),constrained_layout=True);bars=ax.bar(range(3),values,color=[styles[k][0] for k in keys],alpha=.7,width=.55)
for j,key in enumerate(keys):
    values_by_seed=[np.mean([r['metrics'][key]['penalized_rmse_seconds'] for r in result['entries'] if r['seed']==seed]) for seed in spec['seeds']]
    ax.scatter(j+np.linspace(-.15,.15,4),values_by_seed,color='black',s=24,zorder=3)
    ax.text(j,result['summary'][key]['primary_seconds']+2,f'{result["summary"][key]["primary_seconds"]:.2f}秒',ha='center')
ax.set_xticks(range(3),[styles[k][1] for k in keys]);ax.set_ylabel('整条作用曲线的平均估计误差（秒，越低越好）');ax.set_ylim(0,max(values)*1.45);ax.grid(axis='y',alpha=.2);ax.set_title('新数据终验：现用连续DR总体更准（模拟）\n柱为总体均值，黑点为四个随机块；每块六种机制')
fig.savefig(HERE/'overall_curve_error.png',dpi=150);plt.close(fig)
print('Saved continuous_curve_comparison.png and overall_curve_error.png',flush=True)
