"""All held-out dates/rooms, forecasts aligned to TARGET time, no model changes."""
from common import *
import argparse,os,sys,math,datetime
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
os.environ['MPLCONFIGDIR']=str(ROOT/'work/python_caches/mpl_air_20261016')
sys.path.insert(0,str(ROOT/'work/python_packages/hvac_plots_20261016'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
font=Path('C:/Windows/Fonts/msyh.ttc');assert font.exists()
font_manager.fontManager.addfont(str(font));plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),'axes.unicode_minus':False,'svg.fonttype':'none','svg.hashsalt':'D063-air-curves-v1','font.size':10})
p=load(BASE/'air_characteristic_protocol_v1.json');predpath=BASE/'runs/BL_DUAL_ZONE_01/predictions.csv';assert sha(predpath)==p['old_predictions_sha256']
pred=read(predpath);lookup={(r['file'],int(r['zone']),r['target_timestamp']):float(r['M_HEAT5']) for r in pred};files=sorted({r['file'] for r in pred},key=lambda n:int(n.split('Day')[1].split('(')[0]));assert len(files)==4
fig,axes=plt.subplots(4,2,figsize=(16,13),sharex=False,sharey=True);bound=[];alltemp=[];allpower=[];panels=[]
for i,name in enumerate(files):
    source=p['sources'][name];fp=ROOT/source['path'];assert sha(fp)==source['sha256'];rows=read(fp);time=[datetime.datetime.strptime(r['Timestamp'],'%Y-%m-%d %H:%M') for r in rows]
    for j,room in enumerate([1,2]):
        t=[float(r[f"Room{room}'s Indoor air temperature (°C)"]) for r in rows];power=[float(r[f"Room{room}'s power consumption (W)"]) for r in rows]
        forecast=[(ts,lookup[(name,room,ts.isoformat())]) for ts in time if (name,room,ts.isoformat()) in lookup]
        assert len(forecast)==286
        ax=axes[i,j];right=ax.twinx();right.fill_between(time,power,color='#b8bec5',alpha=.3,linewidth=0,zorder=1)
        right.set_zorder(0);ax.set_zorder(1);ax.patch.set_visible(False)
        ax.plot(time,t,color='#193b62',lw=1.1,zorder=3)
        ax.plot([x[0] for x in forecast],[x[1] for x in forecast],color='#171717',ls='--',lw=.9,zorder=4)
        ax.set_title(f'{time[0]:%Y-%m-%d}  ·  房间 {room}',loc='left',fontsize=11)
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,6,12,18]));ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.set_xlim(time[0],time[-1]);ax.grid(axis='y',color='#dfe3e7',lw=.5);ax.spines[['top']].set_visible(False);right.spines['top'].set_visible(False)
        ax.set_ylabel('温度（℃）' if j==0 else '')
        right.set_ylabel('发布功率（W）' if j==1 else '');right.tick_params(axis='y',labelsize=8,colors='#626972')
        if i==3:ax.set_xlabel('原始记录时间（未编码时区）')
        alltemp.extend(t+[x[1] for x in forecast]);allpower.extend(power);panels.append((ax,right))
        for ts,tc,pw in zip(time,t,power):bound.append({'file':name,'room':room,'source_timestamp':ts.isoformat(),'measured_T_C':tc,'reported_P_W':pw,'forecast_at_this_target_time_C':lookup.get((name,room,ts.isoformat()))})
for ax,right in panels:
    ax.set_ylim(math.floor(min(alltemp)-.5),math.ceil(max(alltemp)+.5));right.set_ylim(0,math.ceil(max(allpower)*1.1/100)*100)
fig.suptitle('空调室温预测：全部四个评价日、两个原试验房间',x=.06,ha='left',fontsize=17,y=.99)
fig.text(.06,.955,'实测室温与固定模型预测对齐到目标采样时刻；灰色为同一房间发布功率。无平滑、无筛选最好片段。',fontsize=11)
fig.legend(handles=[Line2D([],[],color='#193b62',lw=1.5,label='实测室温'),Line2D([],[],color='#171717',ls='--',lw=1.2,label='固定模型预测（下一标签）'),Patch(facecolor='#b8bec5',alpha=.4,label='原发布功率，非控制指令')],loc='upper left',bbox_to_anchor=(.055,.945),ncol=3,frameon=False)
fig.text(.06,.025,'来源：Choi等，Mendeley Data v1，10.17632/7tzkdhgpfs.1，CC-BY-4.0；图为派生绘制。\n只验证“当前行可得”条件下的离线标签预测；功率平均区间/上传延迟未明，不表示实际在线提前量或可调容量。',fontsize=10,color='#454b52')
fig.subplots_adjust(left=.06,right=.94,top=.895,bottom=.09,hspace=.4,wspace=.23)
fig.savefig(out/'test_temperature_curves.png',dpi=150,metadata={'Software':'matplotlib '+matplotlib.__version__})
fig.savefig(out/'test_temperature_curves.svg',metadata={'Date':'2026-10-16','Creator':'VPP D063 scientific plot; matplotlib '+matplotlib.__version__})
plt.close(fig)
with (out/'plotted_values.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(bound[0]));w.writeheader();w.writerows(bound)
dump(out/'receipt.json',{'status':'created_pending_visual_review','protocol_sha256':sha(BASE/'air_characteristic_protocol_v1.json'),'old_predictions_sha256':sha(predpath),'panel_count':8,'source_room_labels_plotted':len(bound),'predictions_plotted':len(lookup),'forecast_time_is_target_time':True,'matplotlib':matplotlib.__version__,'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
print(json.dumps({'panels':8,'source_room_labels':len(bound),'predictions':len(lookup),'PNG':str(out/'test_temperature_curves.png'),'SVG':str(out/'test_temperature_curves.svg')},ensure_ascii=False))
