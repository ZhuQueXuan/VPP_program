"""Scientific evidence plots from unmodified observed current/commands."""
import os,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ['MPLCONFIGDIR']=str(HERE/'mpl_config')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})

examples=json.loads((HERE/'analysis_run2/examples.json').read_text(encoding='utf-8'))
keys=['fast_transition_then_long_support','observed_brief_threshold_excursion_not_fault_label','first_short_command_return']
titles=['起变快，但随后持续：不能当毛刺','短暂越阈与反复波动：没有故障标签','短指令往返：不等于实际电流响应']
fig,axes=plt.subplots(3,2,figsize=(12,8.8),layout='constrained')
for row,(key,title) in enumerate(zip(keys,titles)):
    r=examples[key]
    with np.load(ROOT/r['raw_source'],allow_pickle=False) as raw:
        if r['panel']=='held':t=raw['relative_time_us']/1e6;y=raw['phase_current_A'];u=raw['command_A']
        else:t=raw['relative_us']/1e6;y=raw['i'+str(r['phase'])];u=raw['command']
    ax=axes[row,0];ax.plot(t,y,color='#176b98',lw=.8,label='原始电流');ax.step(t,u,where='post',color='#c75a17',lw=1.,label='原始指令')
    ax.set(xlim=(-1,15),ylabel='电流 / 指令 (A)',title=title);ax.axvline(0,color='grey',lw=.7);ax.grid(alpha=.2)
    if row==0:ax.legend(loc='upper right',ncol=2)
    with np.load(HERE/r['aligned_file'],allow_pickle=False) as d:
        ax=axes[row,1]
        for w,label,color in [(100000,'100毫秒','#176b98'),(1000000,'1秒','#479d55'),(10000000,'10秒完整格','#b85057')]:
            keyw=str(w)+'us';complete=d['complete_'+keyw];lo=d['lo_'+keyw][complete]/1e6;mean=d['mean_'+keyw][complete]
            hi=d['hi_'+keyw][complete]/1e6;progress=np.sign(r['step_A'])*(mean-r['pre_median_A'])/abs(r['step_A'])
            for j,(a,b,v) in enumerate(zip(lo,hi,progress)):ax.plot([a,b],[v,v],color=color,lw=1.1,label=label if j==0 else None)
        ax.axhline(.9,color='grey',lw=.8,ls='--',label='90%描述阈值');ax.axvline(0,color='grey',lw=.7)
        ax.set(xlim=(-1,15),ylabel='指令变化幅度归一化电流',title='同一原始点聚合；没有删点或填补');ax.grid(alpha=.2)
        if row==0:ax.legend(loc='lower right',ncol=2)
for ax in axes[-1]:ax.set_xlabel('相对指令起变时间 (秒)')
fig.suptitle('粗细对齐核验：看到形态差异，不等于已有故障真值',fontsize=14)
fig.savefig(HERE/'aligned_examples.png',dpi=160)
print('saved aligned_examples.png')
