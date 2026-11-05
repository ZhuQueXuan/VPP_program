"""Plot persisted results only; no fitting or selection."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
    'axes.unicode_minus':False,'font.size':10,'figure.dpi':150})

def main():
    pred=np.load(BASE/'predictions.npz')['curve'];truth=np.load(BASE/'evaluation_truth.npz')['curve']
    e=json.loads((BASE/'evaluation.json').read_text())
    dose=np.array([0,.4,.8,1.2,1.6,2.,2.4])
    names=['零作用','线性作用','平滑非线性','分段变化']
    labels=['每档均值','直线回归','固定节点分段回归'];colors=['#707B87','#2671B8','#D35E43']
    fig,axes=plt.subplots(2,2,figsize=(10,7),sharex=True)
    for si,ax in enumerate(axes.flat):
        ax.plot(dose,100*truth[si,1,0],color='#101820',lw=2,marker='o',label='总体真值（仅评价）')
        for mi in range(3):
            ax.plot(dose,100*pred[:,si,1,0,mi].mean(axis=0),lw=1.7,ls=[':', '--','-'][mi],color=colors[mi],label=labels[mi])
        ax.set_title(names[si]);ax.set_xticks(dose);ax.set_ylim(0,65)
        ax.set_ylabel('平均净交付比例（%）');ax.grid(axis='y',alpha=.2)
    for ax in axes[1]:ax.set_xlabel('模拟激励水平（元/kWh）')
    handles,leg=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,leg,loc='lower center',ncol=4,frameon=False)
    fig.suptitle('B1多档激励：不同机制需要不同曲线表达',fontsize=14)
    fig.text(.5,.925,'全体组；各方法曲线为20次独立重复的均值，不是单次结果或置信带',ha='center',fontsize=9,color='#586675')
    fig.tight_layout(rect=[0,.055,1,.91]);fig.savefig(BASE/'dose_response.png',bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4))
    for mi,method in enumerate(['M0_dose_means','M1_linear','M2_linear_spline']):
        vals=[100*next(r['pooled_curve_rmse'] for r in e['summary'] if r['scenario']==s and r['outcome']=='delivery' and r['group']=='all' and r['method']==method) for s in ['zero','linear','smooth','hinge']]
        bars=ax.bar(np.arange(4)+(mi-1)*.24,vals,.23,color=colors[mi],label=labels[mi])
        ax.bar_label(bars,fmt='%.2f',padding=3,fontsize=9)
    ax.set_xticks(np.arange(4),names);ax.set_ylim(0,3.25);ax.set_ylabel('总体交付曲线RMSE（百分点）')
    ax.set_title('简单模型有适用范围；增加灵活性并非总能改进')
    ax.legend(frameon=False,ncol=3);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.tight_layout();fig.savefig(BASE/'curve_error.png',bbox_inches='tight');plt.close(fig)
    print('saved dose_response.png and curve_error.png')

if __name__=='__main__':main()
