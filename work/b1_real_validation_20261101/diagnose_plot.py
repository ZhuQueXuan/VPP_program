from common import *

def main():
    records={r['task']['task_id']:r for r in read('records.json')};new={r['task']['task_id']:r for r in read('new_events.json')};rows=read('results.json');extra=[]
    for r in rows:
        if r['methods']['retained']['positive'] or not r['methods']['current']['positive']:continue
        c=records[r['case_id']];p=np.array(c['power_kw']);b=np.array(c['reference']['reference_kw']);conditional=np.array(new[r['case_id']]['process']['conditional_reference_interval_kw']);task=slice(15,45)
        extra.append(dict(case_id=r['case_id'],recording=r['recording'],actual_power_min_mean_max_kw=[float(p[task].min()),float(p[task].mean()),float(p[task].max())],
            original_raw_threshold_bins=int(np.sum((b-p)[task]>=.15)),corrected_raw_threshold_bins=int(np.sum((conditional-p)[task]>=.15)),
            corrected_CPOP_positive=r['methods']['same_corrected_cpop']['positive'],new_duration_positive=r['methods']['current']['positive'],
            corrected_CPOP_duration_seconds=r['methods']['same_corrected_cpop']['cumulative_seconds'],new_duration_seconds=r['methods']['current']['cumulative_seconds'],
            original_mean_residual_kw=float(np.mean((b-p)[task])),corrected_mean_residual_kw=float(np.mean((conditional-p)[task])),
            attribution='All three added background-positive decisions already occur in CPOP receiving the corrected reference; the duration-fusion model does not create these added task-positive flags. Reference-error tracking is the first changed source.'))
    write('diagnosis.json',dict(extra_background_positives=extra,model_changed=False,fitting_or_threshold_tuning_on_real_data=False,
        conclusion='Simulation benefit did not establish real-data transfer. Frozen process correction can produce false positive threshold crossings during ordinary AC charging. Need real-data adaptation and fresh held-out validation before field use.'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
    for column,key in enumerate([extra[0]['case_id'],extra[1]['case_id']]):
        c=records[key];p=np.array(c['power_kw']);b=np.array(c['reference']['reference_kw']);adjusted=np.array(new[key]['process']['conditional_reference_interval_kw']);x=np.arange(-15.,45.)+.5
        name=next(r['recording'].split('/')[0] for r in rows if r['case_id']==key)
        axes[0,column].plot(x,p,color='#222222',label='真实量测',linewidth=2)
        axes[0,column].plot(x,b,color='#2878B5',label='原参考预测',linestyle='--')
        axes[0,column].plot(x,adjusted,color='#DF7F2A',label='校正后的参考')
        axes[0,column].set_title(name+'：指令保持不变',fontproperties=font)
        axes[1,column].plot(x,b-p,color='#2878B5',label='原预测减实测')
        axes[1,column].plot(x,adjusted-p,color='#DF7F2A',label='校正后减实测')
        axes[1,column].axhline(.15,color='#C33B3B',linestyle=':',label='算法响应阈值0.15kW')
        for axis in axes[:,column]:
            axis.axvspan(0,30,color='#777777',alpha=.07);axis.grid(alpha=.2);axis.legend(prop=font,fontsize=9)
        axes[1,column].set_xlabel('相对伪任务起点／分钟',fontproperties=font)
    axes[0,0].set_ylabel('功率／kW',fontproperties=font);axes[1,0].set_ylabel('参考减实测／kW',fontproperties=font)
    fig.suptitle('真实普通充电背景：新校正产生了额外的“响应”识别',fontproperties=font,fontsize=15)
    fig.tight_layout();fig.savefig(HERE/'real_background_examples.png',dpi=160);plt.close(fig)
    print('diagnosis and real plots saved')
if __name__=='__main__':main()
